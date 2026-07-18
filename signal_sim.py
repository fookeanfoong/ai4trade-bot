#!/usr/bin/env python3
"""
Structured-signal paper trader (long + short) with pro-grade risk control.

Reads:
  - signals.json : trade signals in the requested schema + execution fields
  - quotes.json  : live prices + 3d/5d extension (written by quotes.py)

Position sizing (Paul Tudor Jones / Market Wizards rule):
  Each trade is sized so that a stop-out loses at most RISK_PER_TRADE_PCT of
  current equity — NOT the whole account. Leverage still amplifies the move,
  but one bad trade can't wreck the account. The rest stays in cash.

Entry discipline:
  - NO-CHASE guard: skip if the name already ran > MAX_CHASE_3D_PCT over 3
    sessions in the signal's direction (wait for a pullback).

Exit priority (get out in time so winners don't round-trip to losers):
  1. Signal invalidation -> market exit.
  2. Trailing profit-lock (arm at TRAIL_ARM_PCT, exit on TRAIL_GIVEBACK_PCT
     retrace, floored at breakeven).
  3. Hard stop.
  4. T1 (sell half, stop -> breakeven), then T2 (close rest).

State: signal_sim_state.json   Reports: reports/signal_sim/YYYY-MM-DD.md
"""

import datetime as dt
import json
import sys
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parent
SIGNALS_FILE = ROOT / "signals.json"
QUOTES_FILE = ROOT / "quotes.json"
STATE_FILE = ROOT / "signal_sim_state.json"
REPORTS_DIR = ROOT / "reports" / "signal_sim"

STARTING_CASH = 200.0
BASE_LEVERAGE = 10.0
REDUCED_LEVERAGE = 5.0
DRAWDOWN_CAP_USD = 40.0
MIN_CONFIDENCE = 0.6

# Risk-based sizing: a stop-out costs at most this fraction of equity.
# Market Wizards risk 1-2% per trade; 5% is our aggressive-but-survivable cap
# (still 4x safer than the old all-in ~20%-per-trade).
RISK_PER_TRADE_PCT = 0.05

# No-chase guard: refuse to enter if the name already ran this much (%) over
# 3 sessions in our direction. Wait for a pullback instead of chasing.
MAX_CHASE_3D_PCT = 6.0

# Trailing profit-lock (underlying-price percentages; leverage amplifies).
TRAIL_ARM_PCT = 0.004       # arm once +0.4% in our favour
TRAIL_GIVEBACK_PCT = 0.0025  # exit if it gives back 0.25% from the best price


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "cash": STARTING_CASH,
        "position": None,
        "trade_log": [],
        "runs": [],
        "peak_equity": STARTING_CASH,
        "last_key": None,
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_weekday_ny() -> bool:
    if ZoneInfo:
        now_ny = dt.datetime.now(ZoneInfo("America/New_York"))
    else:
        now_ny = dt.datetime.utcnow() - dt.timedelta(hours=4)
    return now_ny.weekday() < 5


def next_leverage(state: dict) -> float:
    peak = state.get("peak_equity", STARTING_CASH)
    p = state.get("position")
    realized = state["cash"] + (p["shares"] * p["entry"] if p else 0.0)
    return REDUCED_LEVERAGE if (peak - realized) >= DRAWDOWN_CAP_USD else BASE_LEVERAGE


def leveraged_proceeds(shares, entry, exit_price, leverage, side):
    """Cash back on close. side=+1 long, -1 short. Cost basis always returns."""
    cost = shares * entry
    raw_pnl = shares * (exit_price - entry) * side
    return cost + raw_pnl * leverage


def load_signals() -> list:
    try:
        return json.loads(SIGNALS_FILE.read_text()).get("signals", [])
    except Exception as e:
        print(f"signals.json unreadable: {e}", file=sys.stderr)
        return []


def signal_still_valid(ticker: str, side: str, signals: list) -> bool:
    """True if an actionable signal matching this open position still exists."""
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
    return False  # signal removed entirely -> invalidated


def pick_signal(state: dict):
    actionable = []
    for s in load_signals():
        if s.get("direction") not in ("bullish", "bearish"):
            continue
        if float(s.get("confidence", 0)) < MIN_CONFIDENCE:
            continue
        if s.get("already_priced_in") is True:
            continue
        actionable.append(s)
    if not actionable:
        return None
    actionable.sort(key=lambda s: float(s.get("confidence", 0)), reverse=True)
    return actionable[0]


def get_quote(symbol: str):
    try:
        q = json.loads(QUOTES_FILE.read_text())["quotes"].get(symbol)
    except Exception:
        return None
    if not q or q.get("last") is None:
        return None
    return q


def _close(state, p, fill, side, lev, action, when):
    proceeds = leveraged_proceeds(p["shares"], p["entry"], fill, lev, side)
    pnl = proceeds - p["shares"] * p["entry"]
    state["cash"] += proceeds
    state["trade_log"].append({
        "ticker": p["ticker"], "side": p["side"], "action": action,
        "entry": p["entry"], "exit": round(fill, 4), "leverage": lev,
        "pnl_usd": round(pnl, 4), "closed_at": when,
    })
    state["position"] = None
    return pnl


def manage_exit(state: dict, quote: dict, signals: list) -> list:
    lines = []
    p = state["position"]
    side = 1 if p["side"] == "long" else -1
    lev = p.get("leverage", BASE_LEVERAGE)
    last = quote["last"]
    high = quote.get("day_high") or last
    low = quote.get("day_low") or last

    # backfill trailing fields for positions opened before this feature
    p.setdefault("peak_price", p["entry"])
    p.setdefault("armed", False)

    # --- 1. Signal invalidation -> exit at market (judge in time, pull out) ---
    if not signal_still_valid(p["ticker"], p["side"], signals):
        pnl = _close(state, p, last, side, lev, "SIGNAL_INVALIDATED_EXIT", quote.get("market_time"))
        lines.append(f"EXIT (signal invalidated): {p['ticker']} {p['side']} @ market ${last:.2f} ({lev}x) -> P&L ${pnl:+.2f}")
        return lines

    # --- update peak + arm trailing ---
    if side == 1:
        p["peak_price"] = max(p["peak_price"], high)
        if not p["armed"] and p["peak_price"] >= p["entry"] * (1 + TRAIL_ARM_PCT):
            p["armed"] = True
    else:
        p["peak_price"] = min(p["peak_price"], low)
        if not p["armed"] and p["peak_price"] <= p["entry"] * (1 - TRAIL_ARM_PCT):
            p["armed"] = True

    # --- 2. Trailing profit-lock (only once armed; floored at breakeven) ---
    if p["armed"]:
        if side == 1:
            trail = max(p["peak_price"] * (1 - TRAIL_GIVEBACK_PCT), p["entry"])
            trail_hit = low <= trail
        else:
            trail = min(p["peak_price"] * (1 + TRAIL_GIVEBACK_PCT), p["entry"])
            trail_hit = high >= trail
        if trail_hit:
            pnl = _close(state, p, trail, side, lev, "TRAIL_LOCK_EXIT", quote.get("market_time"))
            lines.append(f"TRAIL-LOCK: {p['ticker']} {p['side']} exited @ ${trail:.2f} ({lev}x), kept profit ${pnl:+.2f}")
            return lines

    # --- 3. Hard stop ---
    stop_hit = (low <= p["stop"]) if side == 1 else (high >= p["stop"])
    if stop_hit:
        action = "STOP_EXIT" if not p["half_taken"] else "BE_STOP_EXIT"
        pnl = _close(state, p, p["stop"], side, lev, action, quote.get("market_time"))
        lines.append(f"EXIT: {p['ticker']} {p['side']} stopped @ ${p['stop']:.2f} ({lev}x) -> P&L ${pnl:+.2f}")
        return lines

    # --- 4. T1 (sell half, stop -> breakeven) ---
    t1_hit = (high >= p["t1"]) if side == 1 else (low <= p["t1"])
    if not p["half_taken"] and t1_hit:
        half = p["shares"] / 2
        fill = p["t1"]
        proceeds = leveraged_proceeds(half, p["entry"], fill, lev, side)
        pnl = proceeds - half * p["entry"]
        state["cash"] += proceeds
        p["shares"] -= half
        p["half_taken"] = True
        p["stop"] = p["entry"]
        p["armed"] = True  # protect the remainder with the trail from here
        state["trade_log"].append({
            "ticker": p["ticker"], "side": p["side"], "action": "T1_HALF",
            "entry": p["entry"], "exit": fill, "leverage": lev,
            "pnl_usd": round(pnl, 4),
        })
        lines.append(f"T1: sold half {p['ticker']} {p['side']} @ ${fill:.2f} ({lev}x), stop->BE, booked ${pnl:+.2f}")

    # --- 5. T2 (close remainder) ---
    t2_hit = (high >= p["t2"]) if side == 1 else (low <= p["t2"])
    if state["position"] and p["shares"] > 1e-9 and t2_hit:
        pnl = _close(state, p, p["t2"], side, lev, "T2_EXIT", quote.get("market_time"))
        lines.append(f"T2: closed {p['ticker']} {p['side']} @ ${p['t2']:.2f} ({lev}x), booked ${pnl:+.2f}")
    return lines


def open_from_signal(state: dict, sig: dict) -> list:
    lines = []
    ticker = sig["sector_or_ticker"]
    quote = get_quote(ticker)
    if not quote:
        lines.append(f"signal {ticker}: no live quote, skip")
        return lines
    entry = quote["last"]
    side = "long" if sig["direction"] == "bullish" else "short"
    s = 1 if side == "long" else -1

    # --- NO-CHASE guard: don't buy a move that already ran (the XLE lesson) ---
    chg_3d = quote.get("chg_3d_pct")
    max_chase = float(sig.get("max_chase_3d_pct", MAX_CHASE_3D_PCT))
    if chg_3d is not None:
        if side == "long" and chg_3d > max_chase:
            lines.append(f"NO-CHASE: {ticker} already +{chg_3d:.1f}% over 3d (> {max_chase:.1f}%) - wait for pullback, not chasing")
            return lines
        if side == "short" and chg_3d < -max_chase:
            lines.append(f"NO-CHASE: {ticker} already {chg_3d:.1f}% over 3d (< -{max_chase:.1f}%) - wait for bounce, not chasing")
            return lines

    stop_pct = float(sig.get("stop_pct", 0.02))
    t1_pct = float(sig.get("t1_pct", 0.03))
    t2_pct = float(sig.get("t2_pct", 0.06))
    lev = next_leverage(state)

    stop = entry * (1 - stop_pct * s)
    t1 = entry * (1 + t1_pct * s)
    t2 = entry * (1 + t2_pct * s)

    # --- Risk-based sizing (Paul Tudor Jones): a stop-out loses at most
    #     RISK_PER_TRADE_PCT of equity, not the whole account. ---
    equity_now = state["cash"]  # flat before entry, so cash == equity
    risk_amount = equity_now * RISK_PER_TRADE_PCT
    if stop_pct > 0 and lev > 0:
        cost = risk_amount / (stop_pct * lev)   # cash to deploy
    else:
        cost = state["cash"]
    cost = min(cost, state["cash"])             # never deploy more than we have
    shares = cost / entry
    state["cash"] -= cost

    state["position"] = {
        "ticker": ticker, "side": side, "shares": shares, "entry": entry,
        "stop": round(stop, 2), "t1": round(t1, 2), "t2": round(t2, 2),
        "half_taken": False, "leverage": lev,
        "peak_price": entry, "armed": False,
        "confidence": sig.get("confidence"),
        "entry_chg_3d_pct": chg_3d,
        "risk_usd": round(risk_amount, 2),
        "cost_deployed": round(cost, 2),
        "opened_at": quote.get("market_time"),
    }
    lines.append(
        f"ENTRY ({side.upper()} {ticker}, conf {sig.get('confidence')}, {lev}x, "
        f"risk ${risk_amount:.2f}, deployed ${cost:.2f}): {shares:.6f} @ ${entry:.2f} "
        f"- stop ${stop:.2f}, T1 ${t1:.2f}, T2 ${t2:.2f}"
    )
    return lines


def equity(state: dict, mark: float) -> float:
    p = state.get("position")
    if not p:
        return state["cash"]
    side = 1 if p["side"] == "long" else -1
    return state["cash"] + leveraged_proceeds(
        p["shares"], p["entry"], mark, p.get("leverage", BASE_LEVERAGE), side
    )


def write_report(state: dict, actions: list, mark_sym: str, mark: float) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    eq = equity(state, mark) if mark else state["cash"]
    pnl_pct = (eq - STARTING_CASH) / STARTING_CASH * 100
    pos = state.get("position")
    realized = sum(t["pnl_usd"] for t in state["trade_log"])
    wins = sum(1 for t in state["trade_log"] if t["pnl_usd"] > 0)
    closed = len(state["trade_log"])
    lines = [
        f"# Signal Sim ($200, risk-{int(RISK_PER_TRADE_PCT*100)}%/trade, {int(BASE_LEVERAGE)}x, trailing+no-chase) - {today}",
        "",
        f"- Cash: ${state['cash']:.2f}",
        f"- Position: {json.dumps(pos) if pos else 'FLAT'}",
        f"- Mark ({mark_sym}): ${mark:.2f}" if mark else "- Mark: n/a",
        f"- Mark-to-market equity: ${eq:.2f} ({pnl_pct:+.2f}% vs $200)",
        f"- Realized P&L to date: ${realized:+.2f}",
        f"- Closed trades: {closed}  |  Wins: {wins}  |  Win rate: {(100*wins/closed) if closed else 0:.0f}%",
        "",
        "## Actions this run",
        "",
    ]
    lines += [f"- {a}" for a in actions] if actions else ["- (no actionable signal / waiting)"]
    (REPORTS_DIR / f"{today}.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    if not is_weekday_ny():
        print("Weekend - skipping.")
        return 0

    state = load_state()
    signals = load_signals()
    actions = []
    mark_sym, mark = None, None

    if state.get("position"):
        p = state["position"]
        mark_sym = p["ticker"]
        quote = get_quote(mark_sym)
        if quote:
            mark = quote["last"]
            actions += manage_exit(state, quote, signals)
    if not state.get("position"):
        sig = pick_signal(state)
        if sig:
            mark_sym = sig["sector_or_ticker"]
            q = get_quote(mark_sym)
            mark = q["last"] if q else None
            actions += open_from_signal(state, sig)
        else:
            actions.append("no actionable signal (need direction, confidence>=0.6, not priced-in)")

    if state.get("position"):
        q = get_quote(state["position"]["ticker"])
        if q:
            mark_sym, mark = state["position"]["ticker"], q["last"]

    eq = equity(state, mark) if mark else state["cash"]
    state["peak_equity"] = max(state.get("peak_equity", STARTING_CASH), eq)
    state["runs"].append({
        "ran_at": dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "equity": round(eq, 4),
        "actions": actions,
    })
    state["runs"] = state["runs"][-200:]

    save_state(state)
    write_report(state, actions, mark_sym or "-", mark or 0.0)

    print(f"Done. Signal-sim equity ${eq:.2f} ({(eq - STARTING_CASH) / STARTING_CASH * 100:+.2f}%)")
    for a in actions:
        print(f"  * {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
