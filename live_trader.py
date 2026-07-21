#!/usr/bin/env python3
"""
Broker-agnostic signal trader — the real-execution twin of signal_sim.py.

Runs against a real broker account (Alpaca, paper by default): auth, order
placement, fills, position/account queries. When the paper account is
consistently profitable, flipping to real money is one env var.

MULTI-POSITION, CONVICTION-BASED COUNT: how many names we hold is driven by how
many signals the premarket routine keeps (its judgement), not a fixed number.
    - up to BASE_SLICES (3) names: each gets a fixed 1/BASE_SLICES slice, so
      picking 1 deploys ~1/3 of the book, 3 deploys the full 2x.
    - more than BASE_SLICES (e.g. 10): the book splits evenly across ALL chosen
      names, so total notional still stays within BOOK*LEVERAGE_CAP (~2x).
    - a stop-out on one name risks RISK_PCT of ITS slice; total risk ~5%.
So the count can be 1..MAX_POSITIONS by conviction, and buying more names never
raises total leverage — it just makes each slice smaller.
A total-exposure guard refuses new entries once total notional hits the 2x cap
(also protects against a legacy oversized position after a schema change).
A name that exits is benched for the rest of the day (no falling-knife re-entry).

Each position is managed independently: signal-invalidation exit, trailing
profit-lock, hard stop, T1 (half + stop->BE), T2.

State: live_trader_state.json (committed so GitHub Actions runs persist across
runs). Reports: reports/live_trader/YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parent
SIGNALS_FILE = ROOT / "signals.json"
QUOTES_FILE = ROOT / "quotes.json"
STATE_FILE = ROOT / "live_trader_state.json"
REPORTS_DIR = ROOT / "reports" / "live_trader"

# --- Book & risk config (env-overridable). Mirrors signal_sim.py's discipline. ---
BROKER_NAME = os.environ.get("BROKER", "alpaca").lower()
BOOK_EQUITY = float(os.environ.get("BOOK_EQUITY", "200"))
RISK_PER_TRADE_PCT = float(os.environ.get("RISK_PCT", "0.05"))
LEVERAGE_CAP = float(os.environ.get("LEVERAGE_CAP", "2.0"))   # real US margin ~2x
# The NUMBER of names is driven by conviction (how many signals the premarket
# routine keeps), NOT a fixed number. BASE_SLICES is the floor divisor: up to
# BASE_SLICES names each get a fixed 1/BASE_SLICES slice (so picking 1 deploys
# ~1/3, not the whole book). Beyond that, the book splits across ALL chosen names
# so total notional stays within BOOK*LEVERAGE_CAP no matter the count (even 10+).
BASE_SLICES = max(1, int(os.environ.get("BASE_SLICES", "3")))
MAX_POSITIONS = max(1, int(os.environ.get("MAX_POSITIONS", "20")))   # hard safety ceiling
MIN_CONFIDENCE = 0.6
MAX_CHASE_3D_PCT = 6.0
TRAIL_ARM_PCT = 0.004
TRAIL_GIVEBACK_PCT = 0.0025
ENABLE_SHORT = os.environ.get("ENABLE_SHORT", "false").lower() in ("yes", "true")

# REGIME guard (the Korea/DeepSeek lesson): if the broad market is gapping down
# more than this on the day, a sudden-crash / risk-off open is underway — do NOT
# open new longs into it (symmetric for shorts on a rip). signals.json may
# override with a top-level "regime_max_drop_pct".
REGIME_MAX_DROP_PCT = float(os.environ.get("REGIME_MAX_DROP_PCT", "2.0"))

# Fractional shares: default on for Alpaca (supports ~$1 slices), off otherwise.
_frac = os.environ.get("ALLOW_FRACTIONAL")
ALLOW_FRACTIONAL = (_frac.lower() in ("yes", "true")) if _frac is not None else (BROKER_NAME == "alpaca")


# ----------------------------- broker factory ------------------------------
def get_broker():
    """Return (broker_or_None, available, describe_fn, BrokerError)."""
    from broker_alpaca import AlpacaBroker, BrokerError, describe_config, ALPACA_AVAILABLE
    return (AlpacaBroker() if ALPACA_AVAILABLE else None, ALPACA_AVAILABLE, describe_config, BrokerError)


# ----------------------------- state ---------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        st = json.loads(STATE_FILE.read_text())
        # Migrate the old single-"position" schema -> multi "positions" dict.
        if "positions" not in st:
            positions = {}
            p = st.get("position")
            if p and p.get("ticker"):
                positions[p["ticker"]] = p
            st["positions"] = positions
        st.pop("position", None)
        st.setdefault("trade_log", [])
        st.setdefault("runs", [])
        # Names exited today are benched (no falling-knife / churn re-entry).
        # Keep only today's benches; prior days are eligible again.
        today = ny_today_str()
        st["benched"] = {k: v for k, v in st.get("benched", {}).items() if v == today}
        return st
    return {"positions": {}, "trade_log": [], "runs": [], "benched": {}, "last_key": None}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_weekday_ny() -> bool:
    if ZoneInfo:
        now_ny = dt.datetime.now(ZoneInfo("America/New_York"))
    else:
        now_ny = dt.datetime.utcnow() - dt.timedelta(hours=4)
    return now_ny.weekday() < 5


# ------------------------- signals + quotes --------------------------------
def load_signals_doc() -> dict:
    try:
        return json.loads(SIGNALS_FILE.read_text())
    except Exception as e:
        print(f"signals.json unreadable: {e}", file=sys.stderr)
        return {}


def load_signals() -> list:
    return load_signals_doc().get("signals", [])


def ny_today_str() -> str:
    if ZoneInfo:
        return dt.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    return (dt.datetime.utcnow() - dt.timedelta(hours=4)).strftime("%Y-%m-%d")


def signal_expired(doc: dict, today: str) -> bool:
    """A signal file with valid_for in the past must be refreshed pre-open before
    we act on it — a stale signal never fires (pre-open freshness discipline)."""
    vf = doc.get("valid_for")
    return bool(vf) and str(vf) < today


def broad_market_chg(qmap: dict):
    """Same-day % change of the broad market (SPY, else QQQ) for the regime guard."""
    for sym in ("SPY", "QQQ"):
        q = qmap.get(sym)
        if q and q.get("change_pct") is not None:
            return sym, float(q["change_pct"])
    return None, None


def actionable(s: dict) -> bool:
    return (
        s.get("direction") in ("bullish", "bearish")
        and float(s.get("confidence", 0)) >= MIN_CONFIDENCE
        and s.get("already_priced_in") is not True
    )


def actionable_signals(signals: list) -> list:
    """All tradable signals, best confidence first."""
    picks = [s for s in signals if actionable(s)]
    picks.sort(key=lambda s: float(s.get("confidence", 0)), reverse=True)
    return picks


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
    """Prefer the broker's live price; fall back to quotes.json last price."""
    if broker is not None:
        try:
            p = broker.price(symbol)
            if p:
                return p, "broker"
        except Exception:
            pass
    q = qmap.get(symbol)
    if q and q.get("last") is not None:
        return float(q["last"]), "quotes.json"
    return None, None


# ------------------------------- sizing ------------------------------------
def slice_book(n_names: int) -> float:
    """Book allocated to each position. Up to BASE_SLICES names each get a fixed
    1/BASE_SLICES slice; beyond that, split the book across all chosen names so
    total exposure stays within BOOK*LEVERAGE_CAP regardless of count."""
    return BOOK_EQUITY / max(int(n_names), BASE_SLICES)


def size_shares(entry: float, stop_pct: float, per_position_book: float) -> float:
    """Shares so a stop-out risks RISK_PCT of ONE book slice, capped by that
    slice's share of margin. N slices => total stays within BOOK * LEVERAGE_CAP."""
    risk_amount = per_position_book * RISK_PER_TRADE_PCT
    if stop_pct <= 0 or entry <= 0:
        return 0.0
    shares = risk_amount / (entry * stop_pct)
    max_notional = per_position_book * LEVERAGE_CAP
    if shares * entry > max_notional:
        shares = max_notional / entry
    if not ALLOW_FRACTIONAL:
        shares = float(math.floor(shares))
    return round(shares, 6)


def total_notional(state: dict) -> float:
    return sum(float(p.get("notional_usd", 0) or 0) for p in state.get("positions", {}).values())


# ------------------------------ order helper -------------------------------
def _send(broker, dry: bool, lines: list, desc: str, fn):
    """Place an order (unless dry). Return True on success. State must only be
    mutated by the caller AFTER this returns True, so a failed order never
    leaves us thinking we traded when we didn't."""
    if dry or broker is None:
        lines.append(f"[DRY] {desc}")
        return True
    try:
        fn()
        lines.append(desc)
        return True
    except Exception as e:
        lines.append(f"ORDER FAILED ({desc}): {e}")
        return False


def _log_trade(state, p, action, exit_price, qty, when):
    state["trade_log"].append({
        "ticker": p["ticker"], "side": p["side"], "action": action,
        "entry": p["entry"], "exit": round(exit_price, 4), "qty": round(qty, 6),
        "closed_at": when,
    })


# ------------------------------ exits (one position) -----------------------
def manage_position(broker, state, ticker: str, signals, qmap, dry: bool) -> list:
    """Apply invalidation / trailing / stop / T1 / T2 to ONE tracked position."""
    lines = []
    p = state["positions"][ticker]
    sym = ticker
    side = 1 if p["side"] == "long" else -1
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

    last, src = get_price(broker, sym, qmap)
    if last is None:
        return [f"{sym}: no price available (broker + quotes.json empty), holding"]

    p.setdefault("peak_price", p["entry"])
    p.setdefault("armed", False)

    def close_all(action, ref_price):
        ok = _send(broker, dry, lines, f"CLOSE {sym} {p['side']} ({action}) @ ~${ref_price:.2f} [{src}]",
                   lambda: broker.close(sym))
        if ok:
            _log_trade(state, p, action, ref_price, p["qty"], now)
            state["positions"].pop(sym, None)
            # Bench this name for the rest of the day: no same-day re-entry
            # (the falling-knife lesson). Eligible again tomorrow.
            state.setdefault("benched", {})[sym] = ny_today_str()
        return ok

    # 1. Signal invalidation -> exit at market.
    if not signal_still_valid(sym, p["side"], signals):
        close_all("SIGNAL_INVALIDATED_EXIT", last)
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
            return lines

    # 3. Hard stop.
    stop_hit = (last <= p["stop"]) if side == 1 else (last >= p["stop"])
    if stop_hit:
        close_all("STOP_EXIT" if not p["half_taken"] else "BE_STOP_EXIT", p["stop"])
        return lines

    # 4. T1 — sell half, move stop to breakeven.
    t1_hit = (last >= p["t1"]) if side == 1 else (last <= p["t1"])
    if not p["half_taken"] and t1_hit:
        half = p["qty"] / 2
        if not ALLOW_FRACTIONAL:
            half = float(math.floor(half))
        if half >= 1 or (ALLOW_FRACTIONAL and half > 1e-6):
            reduce_side = "sell" if p["side"] == "long" else "buy"
            fn = (lambda: broker.sell(sym, half, p["t1"])) if p["side"] == "long" \
                else (lambda: broker.buy(sym, half, p["t1"]))
            if _send(broker, dry, lines, f"T1 {reduce_side} half {sym} @ ${p['t1']:.2f}, stop->BE", fn):
                p["qty"] = round(p["qty"] - half, 6)
                p["notional_usd"] = round(p["qty"] * p["entry"], 2)
                p["half_taken"] = True
                p["stop"] = p["entry"]
                p["armed"] = True
                _log_trade(state, p, "T1_HALF", p["t1"], half, now)
        else:
            lines.append(f"{sym}: T1 reached but half-lot < 1 share; holding full until T2/stop")

    # 5. T2 — close remainder.
    t2_hit = (last >= p["t2"]) if side == 1 else (last <= p["t2"])
    if sym in state["positions"] and p["qty"] > 1e-9 and t2_hit:
        close_all("T2_EXIT", p["t2"])

    return lines


# ------------------------------ entry (one signal) -------------------------
def open_from_signal(broker, state, sig, qmap, dry: bool, regime_max=None, per_position_book=None) -> list:
    lines = []
    sym = sig["sector_or_ticker"]
    side = "long" if sig["direction"] == "bullish" else "short"
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    if regime_max is None:
        regime_max = REGIME_MAX_DROP_PCT
    if per_position_book is None:
        per_position_book = slice_book(BASE_SLICES)

    if side == "short" and not ENABLE_SHORT:
        return [f"signal {sym} is SHORT but shorting disabled (set ENABLE_SHORT=yes); skip"]

    # REGIME guard (Korea/DeepSeek lesson): don't open into a risk-off crash open.
    gsym, gchg = broad_market_chg(qmap)
    if gchg is not None:
        if side == "long" and gchg < -regime_max:
            return [f"REGIME: {gsym} {gchg:.1f}% today (< -{regime_max:.1f}%) — risk-off open, standing aside on {sym} long"]
        if side == "short" and gchg > regime_max:
            return [f"REGIME: {gsym} +{gchg:.1f}% today (> {regime_max:.1f}%) — risk-on open, not shorting {sym}"]

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

    shares = size_shares(last, stop_pct, per_position_book)
    if shares <= 0:
        return [
            f"{sym}: risk-based size < 1 share at ${last:.2f} "
            f"(slice ${per_position_book:.0f}, cap {LEVERAGE_CAP}x, fractional={ALLOW_FRACTIONAL}). "
            f"Raise BOOK_EQUITY / keep fewer names, or set ALLOW_FRACTIONAL=yes."
        ]

    entry = last
    stop = round(entry * (1 - stop_pct * s), 2)
    t1 = round(entry * (1 + t1_pct * s), 2)
    t2 = round(entry * (1 + t2_pct * s), 2)
    notional = shares * entry
    slice_risk = per_position_book * RISK_PER_TRADE_PCT

    fn = (lambda: broker.buy(sym, shares, entry)) if side == "long" \
        else (lambda: broker.sell(sym, shares, entry))
    desc = (f"ENTRY {side.upper()} {sym} conf {sig.get('confidence')} {shares:g} sh @ ${entry:.2f} "
            f"[{src}] notional ${notional:.0f} risk ${slice_risk:.2f} | stop ${stop} T1 ${t1} T2 ${t2}")
    if not _send(broker, dry, lines, desc, fn):
        return lines

    state["positions"][sym] = {
        "ticker": sym, "side": side, "qty": shares, "entry": entry,
        "stop": stop, "t1": t1, "t2": t2, "half_taken": False,
        "peak_price": entry, "armed": False,
        "confidence": sig.get("confidence"), "entry_chg_3d_pct": chg_3d,
        "notional_usd": round(notional, 2),
        "book_risk_usd": round(slice_risk, 2),
        "opened_at": now, "price_src": src,
    }
    return lines


# ------------------------- reconciliation ----------------------------------
def reconcile(broker, state, BrokerError) -> list:
    """Drop any tracked name the broker no longer holds (filled/closed elsewhere)."""
    if not state.get("positions") or broker is None:
        return []
    try:
        held = {pos["symbol"]: pos["qty"] for pos in broker.positions()}
    except Exception as e:
        return [f"positions() failed, trusting local state: {e}"]
    lines = []
    for tkr in list(state["positions"].keys()):
        if abs(held.get(tkr, 0.0)) < 1e-6:
            state["positions"].pop(tkr, None)
            lines.append(f"reconcile: broker shows no {tkr} — clearing stale local plan")
    return lines


# ------------------------------ report -------------------------------------
def write_report(state, actions, acct, describe) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    positions = state.get("positions", {})
    closed = len(state["trade_log"])
    lines = [
        f"# Live Trader ({BROKER_NAME}) — {today}",
        "",
        f"- Config: {describe()}",
        f"- Book: ${BOOK_EQUITY:.0f} logical | conviction-based count "
        f"(1-{BASE_SLICES} names each get 1/{BASE_SLICES}, more split evenly; ceiling {MAX_POSITIONS}) | "
        f"risk {int(RISK_PER_TRADE_PCT*100)}%/slice | cap {LEVERAGE_CAP}x | fractional {ALLOW_FRACTIONAL}",
    ]
    if acct:
        lines.append(
            f"- Broker account: cash ${acct.get('cash')}, equity ${acct.get('equity')}, "
            f"mkt_val ${acct.get('market_val')}, status {acct.get('status')}"
        )
    lines.append(f"- Open positions ({len(positions)}), total notional ${total_notional(state):.0f} / cap ${BOOK_EQUITY*LEVERAGE_CAP:.0f}:")
    if positions:
        for tkr, p in positions.items():
            lines.append(
                f"  - {tkr} {p['side']} {round(p['qty'],4)} sh @ ${p['entry']} "
                f"| stop ${p['stop']} T1 ${p['t1']} T2 ${p['t2']} "
                f"{'(half taken)' if p.get('half_taken') else ''}"
            )
    else:
        lines.append("  - FLAT")
    lines += [f"- Closed trades logged: {closed}", "", "## Actions this run", ""]
    lines += [f"- {a}" for a in actions] if actions else ["- (no actionable signal / waiting)"]
    (REPORTS_DIR / f"{today}.md").write_text("\n".join(lines) + "\n")


# ------------------------------- modes -------------------------------------
def run_check(broker, describe) -> int:
    print(f"Config: {describe()}")
    broker.connect()
    try:
        print(f"Account: {json.dumps(broker.account(), indent=2)}")
        print(f"Positions: {json.dumps(broker.positions(), indent=2)}")
        print(f"Market open: {broker.is_market_open()}")
    finally:
        broker.disconnect()
    print("Connection OK.")
    return 0


def run_test_order(broker, symbol: str, qty: float) -> int:
    if BROKER_NAME == "alpaca" and os.environ.get("ALPACA_PAPER", "true").lower() == "false":
        print("Refusing --test-order with ALPACA_PAPER=false. Use paper to prove the path.")
        return 2
    broker.connect()
    try:
        px = 0.0
        try:
            px = broker.price(symbol) or 0.0
        except Exception:
            pass
        print(f"Placing PAPER market BUY {qty} {symbol} (ref ${px:.2f}) ...")
        broker.buy(symbol, qty, px)
        print(f"Positions now: {json.dumps(broker.positions(), indent=2)}")
    finally:
        broker.disconnect()
    return 0


def run_cycle(broker, available, describe, BrokerError, dry: bool) -> int:
    if not is_weekday_ny():
        print("Weekend — skipping.")
        return 0

    state = load_state()
    doc = load_signals_doc()
    signals = doc.get("signals", [])
    qmap = quotes_map()
    regime_max = float(doc.get("regime_max_drop_pct", REGIME_MAX_DROP_PCT))
    expired = signal_expired(doc, ny_today_str())
    actions = []
    acct = None

    connected = False
    if broker is not None and not dry:
        # A real run REQUIRES a working broker. If connect/account fails we report
        # and do NOTHING — never fall through with no broker and fake positions.
        try:
            broker.connect()
            connected = True
            acct = broker.account()
        except Exception as e:
            actions.append(f"broker unavailable — no orders this run: {e}")
            try:
                broker.disconnect()
            except Exception:
                pass
            _finish(state, actions, acct, describe, dry, persist=True)
            return 0
        if broker.is_market_open() is False:
            actions.append("market closed — no orders this run")
            broker.disconnect()
            _finish(state, actions, acct, describe, dry, persist=True)
            return 0

    try:
        if connected:
            actions += reconcile(broker, state, BrokerError)

        # 1) Manage every open position independently (a name may exit here).
        for tkr in list(state["positions"].keys()):
            actions += manage_position(broker, state, tkr, signals, qmap, dry)

        # 2) Open new names up to the cap (skip if signals expired).
        if expired:
            actions.append(
                f"signals expired (valid_for {doc.get('valid_for')} < {ny_today_str()} NY) — "
                "managing existing only, no new entries"
            )
        else:
            picks = actionable_signals(signals)
            if not picks:
                actions.append("no actionable signal (direction, confidence>=0.6, not priced-in)")
            else:
                # Book splits across however many names were kept (conviction-based
                # count). Up to BASE_SLICES => fixed 1/BASE_SLICES each; more => the
                # book divides among all of them so total stays within the 2x cap.
                pbook = slice_book(len(picks))
                exposure_cap = BOOK_EQUITY * LEVERAGE_CAP
                for sig in picks:
                    tkr = sig["sector_or_ticker"]
                    if len(state["positions"]) >= MAX_POSITIONS:
                        break
                    if total_notional(state) >= exposure_cap - 1:
                        actions.append(f"total exposure ~${total_notional(state):.0f} at {LEVERAGE_CAP}x cap — no new entries")
                        break
                    if tkr in state["positions"]:
                        continue  # already holding this name
                    if state.get("benched", {}).get(tkr) == ny_today_str():
                        actions.append(f"{tkr}: benched today (already exited once) — no re-entry until tomorrow")
                        continue
                    actions += open_from_signal(broker, state, sig, qmap, dry, regime_max, pbook)
    finally:
        if connected:
            broker.disconnect()

    # Only a real (non-dry) run mutates the committed state file.
    _finish(state, actions, acct, describe, dry, persist=not dry)
    return 0


def _finish(state, actions, acct, describe, dry, persist):
    state["runs"].append({
        "ran_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "broker": BROKER_NAME,
        "dry_run": dry,
        "actions": actions,
    })
    state["runs"] = state["runs"][-200:]
    if persist:
        save_state(state)
    write_report(state, actions, acct, describe)
    banner = "DRY-RUN" if dry else BROKER_NAME.upper()
    print(f"[{banner}] live_trader done. Open: {list(state.get('positions', {}).keys()) or 'FLAT'}")
    for a in actions:
        print(f"  * {a}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Broker-agnostic signal trader (multi-position)")
    ap.add_argument("--check", action="store_true", help="connect, show account+positions, trade nothing")
    ap.add_argument("--test-order", metavar="SYMBOL", help="place a small paper order to prove the order path")
    ap.add_argument("--qty", type=float, default=1.0, help="qty for --test-order (default 1)")
    ap.add_argument("--dry-run", action="store_true", help="run full logic but send no orders")
    args = ap.parse_args()

    broker, available, describe, BrokerError = get_broker()

    if not available and (args.check or args.test_order):
        print(f"{BROKER_NAME} SDK/keys not ready on this host. Config: {describe()}")
        print("Install:  pip install -r requirements-alpaca.txt   and set the API credentials.")
        return 1

    if args.check:
        return run_check(broker, describe)
    if args.test_order:
        return run_test_order(broker, args.test_order.upper(), args.qty)
    return run_cycle(broker, available, describe, BrokerError, dry=args.dry_run or broker is None)


if __name__ == "__main__":
    sys.exit(main())
