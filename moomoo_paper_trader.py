#!/usr/bin/env python3
"""
Signal-driven Moomoo paper trader — the real-execution twin of signal_sim.py.

signal_sim.py proves the STRATEGY on a synthetic internal book. This file
proves the PLUMBING: it takes the same signals.json + quotes.json the GitHub
Actions pipeline already produces and routes real orders through a Moomoo
account (paper by default) via broker_moomoo.py. When the paper account is
consistently profitable, flipping to real money is one env var.

Key difference from signal_sim.py — REAL leverage, not synthetic:
  signal_sim models a 10x P&L multiplier. A real US brokerage account gives at
  most ~2x (Reg-T margin), so here we size in ACTUAL shares under a real
  leverage cap and let the broker settle the true P&L. Sizing still follows the
  Market Wizards rule: a stop-out risks at most RISK_PER_TRADE_PCT of the book.

    risk_amount = BOOK_EQUITY * RISK_PER_TRADE_PCT
    shares      = risk_amount / (entry * stop_pct)      # stop-out loses risk_amount
    notional    = min(shares * entry, BOOK_EQUITY * LEVERAGE_CAP)   # margin cap

We DO NOT size off the paper account's (often huge) virtual balance — we size
off BOOK_EQUITY so the paper run mirrors the real $200 plan we intend to trade.

Modes:
  python moomoo_paper_trader.py --check           connect, print account+positions, trade nothing
  python moomoo_paper_trader.py --test-order SPY  place 1-share market buy to prove the order path
  python moomoo_paper_trader.py --dry-run         run full logic, print intended orders, send none
  python moomoo_paper_trader.py                    run one signal-driven cycle (paper by default)

State: moomoo_trader_state.json (our exit plan; cash/equity come from the broker)
Reports: reports/moomoo_paper/YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

from broker_moomoo import MoomooBroker, BrokerError, describe_config, MOOMOO_AVAILABLE

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parent
SIGNALS_FILE = ROOT / "signals.json"
QUOTES_FILE = ROOT / "quotes.json"
STATE_FILE = ROOT / "moomoo_trader_state.json"
REPORTS_DIR = ROOT / "reports" / "moomoo_paper"

# --- Book & risk config (env-overridable). Mirrors signal_sim.py's discipline. ---
BOOK_EQUITY = float(os.environ.get("MOOMOO_BOOK_EQUITY", "200"))
RISK_PER_TRADE_PCT = float(os.environ.get("MOOMOO_RISK_PCT", "0.05"))
LEVERAGE_CAP = float(os.environ.get("MOOMOO_LEVERAGE_CAP", "2.0"))  # Reg-T ~2x on US stocks
MIN_CONFIDENCE = 0.6
MAX_CHASE_3D_PCT = 6.0
TRAIL_ARM_PCT = 0.004
TRAIL_GIVEBACK_PCT = 0.0025
ALLOW_FRACTIONAL = os.environ.get("MOOMOO_ALLOW_FRACTIONAL", "false").lower() == "yes" \
    or os.environ.get("MOOMOO_ALLOW_FRACTIONAL", "false").lower() == "true"
ENABLE_SHORT = os.environ.get("MOOMOO_ENABLE_SHORT", "false").lower() in ("yes", "true")


# ----------------------------- state ---------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"position": None, "trade_log": [], "runs": [], "last_key": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_weekday_ny() -> bool:
    if ZoneInfo:
        now_ny = dt.datetime.now(ZoneInfo("America/New_York"))
    else:
        now_ny = dt.datetime.utcnow() - dt.timedelta(hours=4)
    return now_ny.weekday() < 5


# ------------------------- signals + quotes --------------------------------
# (Mirror of signal_sim.py's semantics so paper and sim agree on what to trade.)
def load_signals() -> list:
    try:
        return json.loads(SIGNALS_FILE.read_text()).get("signals", [])
    except Exception as e:
        print(f"signals.json unreadable: {e}", file=sys.stderr)
        return []


def actionable(s: dict) -> bool:
    return (
        s.get("direction") in ("bullish", "bearish")
        and float(s.get("confidence", 0)) >= MIN_CONFIDENCE
        and s.get("already_priced_in") is not True
    )


def pick_signal(signals: list):
    picks = [s for s in signals if actionable(s)]
    if not picks:
        return None
    picks.sort(key=lambda s: float(s.get("confidence", 0)), reverse=True)
    return picks[0]


def signal_still_valid(ticker: str, side: str, signals: list) -> bool:
    want = "bullish" if side == "long" else "bearish"
    for s in signals:
        if s.get("sector_or_ticker") != ticker:
            continue
        if s.get("direction") != want:
            return False
        if s.get("already_priced_in") is True:
            return False
        if float(s.get("confidence", 0)) < MIN_CONFIDENCE:
            return False
        return True
    return False


def quotes_map() -> dict:
    try:
        return json.loads(QUOTES_FILE.read_text()).get("quotes", {})
    except Exception:
        return {}


def get_price(broker, symbol: str, qmap: dict):
    """Prefer the broker's live snapshot; fall back to quotes.json last price."""
    if broker is not None:
        try:
            p = broker.price(symbol)
            if p:
                return p, "broker"
        except BrokerError:
            pass
    q = qmap.get(symbol)
    if q and q.get("last") is not None:
        return float(q["last"]), "quotes.json"
    return None, None


# ------------------------------- sizing ------------------------------------
def size_shares(entry: float, stop_pct: float) -> float:
    """Shares so a stop-out risks RISK_PER_TRADE_PCT of the book, capped by margin."""
    risk_amount = BOOK_EQUITY * RISK_PER_TRADE_PCT
    if stop_pct <= 0 or entry <= 0:
        return 0.0
    shares = risk_amount / (entry * stop_pct)
    max_notional = BOOK_EQUITY * LEVERAGE_CAP
    if shares * entry > max_notional:
        shares = max_notional / entry
    if not ALLOW_FRACTIONAL:
        shares = float(math.floor(shares))
    return shares


# ------------------------------ exits --------------------------------------
def _log_trade(state, p, action, exit_price, qty, when):
    state["trade_log"].append({
        "ticker": p["ticker"], "side": p["side"], "action": action,
        "entry": p["entry"], "exit": round(exit_price, 4), "qty": round(qty, 6),
        "closed_at": when,
    })


def manage_open(broker, state, signals, qmap, dry: bool) -> list:
    """Apply invalidation / trailing / stop / T1 / T2 to the tracked position."""
    lines = []
    p = state["position"]
    sym = p["ticker"]
    side = 1 if p["side"] == "long" else -1
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    last, src = get_price(broker, sym, qmap)
    if last is None:
        return [f"{sym}: no price available (broker + quotes.json both empty), holding"]

    p.setdefault("peak_price", p["entry"])
    p.setdefault("armed", False)

    def close_all(action, ref_price):
        qty = p["qty"]
        if not dry and broker is not None:
            if p["side"] == "long":
                broker.sell(sym, qty, ref_price)
            else:
                broker.buy(sym, qty, ref_price)   # buy-to-cover
        _log_trade(state, p, action, ref_price, qty, now)
        state["position"] = None

    # 1. Signal invalidation -> exit at market.
    if not signal_still_valid(sym, p["side"], signals):
        close_all("SIGNAL_INVALIDATED_EXIT", last)
        lines.append(f"EXIT (signal invalidated): {sym} {p['side']} @ ~${last:.2f} [{src}]{' [DRY]' if dry else ''}")
        return lines

    # update peak + arm trailing
    if side == 1:
        p["peak_price"] = max(p["peak_price"], last)
        if not p["armed"] and p["peak_price"] >= p["entry"] * (1 + TRAIL_ARM_PCT):
            p["armed"] = True
    else:
        p["peak_price"] = min(p["peak_price"], last)
        if not p["armed"] and p["peak_price"] <= p["entry"] * (1 - TRAIL_ARM_PCT):
            p["armed"] = True

    # 2. Trailing profit-lock (floored at breakeven).
    if p["armed"]:
        if side == 1:
            trail = max(p["peak_price"] * (1 - TRAIL_GIVEBACK_PCT), p["entry"])
            hit = last <= trail
        else:
            trail = min(p["peak_price"] * (1 + TRAIL_GIVEBACK_PCT), p["entry"])
            hit = last >= trail
        if hit:
            close_all("TRAIL_LOCK_EXIT", last)
            lines.append(f"TRAIL-LOCK: {sym} {p['side']} exited @ ~${last:.2f} [{src}]{' [DRY]' if dry else ''}")
            return lines

    # 3. Hard stop.
    stop_hit = (last <= p["stop"]) if side == 1 else (last >= p["stop"])
    if stop_hit:
        action = "STOP_EXIT" if not p["half_taken"] else "BE_STOP_EXIT"
        close_all(action, p["stop"])
        lines.append(f"EXIT: {sym} {p['side']} stopped @ ~${p['stop']:.2f}{' [DRY]' if dry else ''}")
        return lines

    # 4. T1 — sell half, move stop to breakeven.
    t1_hit = (last >= p["t1"]) if side == 1 else (last <= p["t1"])
    if not p["half_taken"] and t1_hit:
        half = p["qty"] / 2
        if not ALLOW_FRACTIONAL:
            half = float(math.floor(half))
        if half >= 1 or (ALLOW_FRACTIONAL and half > 1e-6):
            if not dry and broker is not None:
                if p["side"] == "long":
                    broker.sell(sym, half, p["t1"])
                else:
                    broker.buy(sym, half, p["t1"])
            p["qty"] -= half
            p["half_taken"] = True
            p["stop"] = p["entry"]
            p["armed"] = True
            _log_trade(state, p, "T1_HALF", p["t1"], half, now)
            lines.append(f"T1: sold half {sym} {p['side']} @ ${p['t1']:.2f}, stop->BE{' [DRY]' if dry else ''}")
        else:
            lines.append(f"T1 reached but half-lot < 1 share; holding full until T2/stop")

    # 5. T2 — close remainder.
    t2_hit = (last >= p["t2"]) if side == 1 else (last <= p["t2"])
    if state["position"] and p["qty"] > 1e-9 and t2_hit:
        close_all("T2_EXIT", p["t2"])
        lines.append(f"T2: closed {sym} {p['side']} @ ${p['t2']:.2f}{' [DRY]' if dry else ''}")

    return lines


def open_from_signal(broker, state, sig, qmap, dry: bool) -> list:
    lines = []
    sym = sig["sector_or_ticker"]
    side = "long" if sig["direction"] == "bullish" else "short"
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    if side == "short" and not ENABLE_SHORT:
        return [f"signal {sym} is SHORT but shorting disabled (set MOOMOO_ENABLE_SHORT=yes); skip"]

    last, src = get_price(broker, sym, qmap)
    if last is None:
        return [f"signal {sym}: no price available, skip"]

    # NO-CHASE guard (the XLE lesson): don't buy a move that already ran.
    q = qmap.get(sym, {})
    chg_3d = q.get("chg_3d_pct")
    max_chase = float(sig.get("max_chase_3d_pct", MAX_CHASE_3D_PCT))
    if chg_3d is not None:
        if side == "long" and chg_3d > max_chase:
            return [f"NO-CHASE: {sym} +{chg_3d:.1f}%/3d > {max_chase:.1f}% — wait for pullback"]
        if side == "short" and chg_3d < -max_chase:
            return [f"NO-CHASE: {sym} {chg_3d:.1f}%/3d < -{max_chase:.1f}% — wait for bounce"]

    stop_pct = float(sig.get("stop_pct", 0.02))
    t1_pct = float(sig.get("t1_pct", 0.03))
    t2_pct = float(sig.get("t2_pct", 0.06))
    s = 1 if side == "long" else -1

    shares = size_shares(last, stop_pct)
    if shares <= 0:
        return [
            f"{sym}: risk-based size < 1 share at ${last:.2f} "
            f"(book ${BOOK_EQUITY:.0f}, cap {LEVERAGE_CAP}x). "
            f"Raise MOOMOO_BOOK_EQUITY, set MOOMOO_ALLOW_FRACTIONAL=yes, or pick a cheaper ticker."
        ]

    entry = last
    stop = round(entry * (1 - stop_pct * s), 2)
    t1 = round(entry * (1 + t1_pct * s), 2)
    t2 = round(entry * (1 + t2_pct * s), 2)
    notional = shares * entry

    if not dry and broker is not None:
        if side == "long":
            broker.buy(sym, shares, entry)
        else:
            broker.sell(sym, shares, entry)   # sell-to-open (short)

    state["position"] = {
        "ticker": sym, "side": side, "qty": shares, "entry": entry,
        "stop": stop, "t1": t1, "t2": t2, "half_taken": False,
        "peak_price": entry, "armed": False,
        "confidence": sig.get("confidence"), "entry_chg_3d_pct": chg_3d,
        "notional_usd": round(notional, 2),
        "book_risk_usd": round(BOOK_EQUITY * RISK_PER_TRADE_PCT, 2),
        "opened_at": now, "price_src": src,
    }
    lines.append(
        f"ENTRY ({side.upper()} {sym}, conf {sig.get('confidence')}, {shares:g} sh @ ${entry:.2f} "
        f"[{src}], notional ${notional:.0f}, risk ${BOOK_EQUITY*RISK_PER_TRADE_PCT:.2f}) "
        f"- stop ${stop}, T1 ${t1}, T2 ${t2}{' [DRY]' if dry else ''}"
    )
    return lines


# ------------------------- reconciliation ----------------------------------
def reconcile(broker, state) -> list:
    """If the broker no longer holds our tracked symbol, the position closed
    outside our control (fill, manual close) — drop our stale plan."""
    p = state.get("position")
    if not p or broker is None:
        return []
    try:
        held = {pos["symbol"]: pos["qty"] for pos in broker.positions()}
    except BrokerError as e:
        return [f"positions() failed, trusting local state: {e}"]
    if abs(held.get(p["ticker"], 0.0)) < 1e-6:
        state["position"] = None
        return [f"reconcile: broker shows no {p['ticker']} position — clearing stale local plan"]
    return []


# ------------------------------ report -------------------------------------
def write_report(state, actions, acct, mark_sym, mark) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    pos = state.get("position")
    closed = len(state["trade_log"])
    lines = [
        f"# Moomoo Paper Trader — {today}",
        "",
        f"- Config: {describe_config()}",
        f"- Book: ${BOOK_EQUITY:.0f} logical | risk {int(RISK_PER_TRADE_PCT*100)}%/trade | cap {LEVERAGE_CAP}x",
    ]
    if acct:
        lines.append(
            f"- Broker account: cash ${acct.get('cash')}, total ${acct.get('total_assets')}, "
            f"mkt_val ${acct.get('market_val')}"
        )
    lines += [
        f"- Position: {json.dumps(pos) if pos else 'FLAT'}",
        f"- Mark ({mark_sym}): ${mark:.2f}" if mark else "- Mark: n/a",
        f"- Closed trades logged: {closed}",
        "",
        "## Actions this run",
        "",
    ]
    lines += [f"- {a}" for a in actions] if actions else ["- (no actionable signal / waiting)"]
    (REPORTS_DIR / f"{today}.md").write_text("\n".join(lines) + "\n")


# ------------------------------- modes -------------------------------------
def run_check(broker) -> int:
    print(f"Config: {describe_config()}")
    broker.connect()
    try:
        acct = broker.account()
        print(f"Account: {json.dumps(acct, indent=2)}")
        pos = broker.positions()
        print(f"Positions ({len(pos)}): {json.dumps(pos, indent=2)}")
    finally:
        broker.disconnect()
    print("Connection OK.")
    return 0


def run_test_order(broker, symbol: str, qty: float) -> int:
    env_name = os.environ.get("MOOMOO_TRD_ENV", "SIMULATE").upper()
    if env_name == "REAL":
        print("Refusing --test-order in REAL env. Use SIMULATE to prove the order path.")
        return 2
    print(f"Config: {describe_config()}")
    broker.connect()
    try:
        px = broker.price(symbol) or 0.0
        print(f"Placing PAPER market BUY {qty} {symbol} (ref ${px:.2f}) ...")
        data = broker.buy(symbol, qty, px)
        print(f"Order accepted:\n{data}")
        print(f"Positions now: {json.dumps(broker.positions(), indent=2)}")
    finally:
        broker.disconnect()
    return 0


def run_cycle(broker, dry: bool) -> int:
    if not is_weekday_ny():
        print("Weekend — skipping.")
        return 0

    state = load_state()
    signals = load_signals()
    qmap = quotes_map()
    actions = []
    acct = None
    mark_sym, mark = None, None

    connected = False
    if broker is not None:
        try:
            broker.connect()
            connected = True
            acct = broker.account()
        except BrokerError as e:
            actions.append(f"broker connect failed, running logic offline: {e}")
            broker = None

    try:
        if broker is not None:
            actions += reconcile(broker, state)

        if state.get("position"):
            mark_sym = state["position"]["ticker"]
            actions += manage_open(broker, state, signals, qmap, dry)

        if not state.get("position"):
            sig = pick_signal(signals)
            if sig:
                mark_sym = sig["sector_or_ticker"]
                actions += open_from_signal(broker, state, sig, qmap, dry)
            else:
                actions.append("no actionable signal (direction, confidence>=0.6, not priced-in)")

        if mark_sym:
            mark, _ = get_price(broker, mark_sym, qmap)
    finally:
        if connected:
            broker.disconnect()

    state["runs"].append({
        "ran_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "env": os.environ.get("MOOMOO_TRD_ENV", "SIMULATE").upper(),
        "dry_run": dry,
        "actions": actions,
    })
    state["runs"] = state["runs"][-200:]
    save_state(state)
    write_report(state, actions, acct, mark_sym or "-", mark or 0.0)

    banner = "DRY-RUN" if dry else os.environ.get("MOOMOO_TRD_ENV", "SIMULATE").upper()
    print(f"[{banner}] Moomoo paper trader done.")
    for a in actions:
        print(f"  * {a}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Signal-driven Moomoo paper trader")
    ap.add_argument("--check", action="store_true", help="connect, show account+positions, trade nothing")
    ap.add_argument("--test-order", metavar="SYMBOL", help="place a small paper market buy to prove the order path")
    ap.add_argument("--qty", type=float, default=1.0, help="qty for --test-order (default 1)")
    ap.add_argument("--dry-run", action="store_true", help="run full logic but send no orders")
    args = ap.parse_args()

    if not MOOMOO_AVAILABLE and (args.check or args.test_order):
        print("moomoo SDK not installed on this host. Install it where OpenD runs:")
        print("  pip install -r requirements-moomoo.txt")
        print(f"Config would be: {describe_config()}")
        return 1

    broker = MoomooBroker() if MOOMOO_AVAILABLE else None

    if args.check:
        return run_check(broker)
    if args.test_order:
        return run_test_order(broker, args.test_order.upper(), args.qty)
    return run_cycle(broker, dry=args.dry_run or broker is None)


if __name__ == "__main__":
    sys.exit(main())
