#!/usr/bin/env python3
"""
Structured-signal paper trader (long + short).

Reads:
  - signals.json : trade signals in the requested schema + execution fields
  - quotes.json  : live prices (written by quotes.py earlier in the workflow)

Executes the single highest-confidence ACTIONABLE signal as a $200 paper
trade with 10x leverage and a $40 drawdown circuit breaker (drops to 5x).
Supports SHORT (bearish) as well as LONG (bullish).

A signal is actionable when:
  direction in ("bullish", "bearish")
  AND confidence >= MIN_CONFIDENCE
  AND already_priced_in == false
  AND no position is currently open

Exits use each run's day_high / day_low from quotes.json (conservative:
stop is checked before targets). T1 sells half and moves stop to breakeven;
T2 closes the rest.

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


def pick_signal(state: dict):
    """Return the best actionable signal dict, or None."""
    try:
        data = json.loads(SIGNALS_FILE.read_text())
    except Exception as e:
        print(f"signals.json unreadable: {e}", file=sys.stderr)
        return None
    actionable = []
    for s in data.get("signals", []):
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


def manage_exit(state: dict, quote: dict) -> list:
    lines = []
    p = state["position"]
    side = 1 if p["side"] == "long" else -1
    lev = p.get("leverage", BASE_LEVERAGE)
    high = quote.get("day_high") or quote["last"]
    low = quote.get("day_low") or quote["last"]

    # Stop check first (conservative). Long stops below; short stops above.
    stop_hit = (low <= p["stop"]) if side == 1 else (high >= p["stop"])
    if stop_hit:
        fill = p["stop"]
        proceeds = leveraged_proceeds(p["shares"], p["entry"], fill, lev, side)
        pnl = proceeds - p["shares"] * p["entry"]
        state["cash"] += proceeds
        state["trade_log"].append({
            "ticker": p["ticker"], "side": p["side"],
            "action": "STOP_EXIT" if not p["half_taken"] else "BE_STOP_EXIT",
            "entry": p["entry"], "exit": fill, "leverage": lev,
            "pnl_usd": round(pnl, 4),
            "closed_at": quote.get("market_time"),
        })
        state["position"] = None
        lines.append(f"EXIT: {p['ticker']} {p['side']} stopped @ ${fill:.2f} ({lev}x) -> P&L ${pnl:+.2f}")
        return lines

    t1_hit = (high >= p["t1"]) if side == 1 else (low <= p["t1"])
    if not p["half_taken"] and t1_hit:
        half = p["shares"] / 2
        fill = p["t1"]
        proceeds = leveraged_proceeds(half, p["entry"], fill, lev, side)
        pnl = proceeds - half * p["entry"]
        state["cash"] += proceeds
        p["shares"] -= half
        p["half_taken"] = True
        p["stop"] = p["entry"]  # move to breakeven
        state["trade_log"].append({
            "ticker": p["ticker"], "side": p["side"], "action": "T1_HALF",
            "entry": p["entry"], "exit": fill, "leverage": lev,
            "pnl_usd": round(pnl, 4),
        })
        lines.append(f"T1: sold half {p['ticker']} {p['side']} @ ${fill:.2f} ({lev}x), stop->BE, booked ${pnl:+.2f}")

    t2_hit = (high >= p["t2"]) if side == 1 else (low <= p["t2"])
    if state["position"] and p["shares"] > 1e-9 and t2_hit:
        fill = p["t2"]
        proceeds = leveraged_proceeds(p["shares"], p["entry"], fill, lev, side)
        pnl = proceeds - p["shares"] * p["entry"]
        state["cash"] += proceeds
        state["trade_log"].append({
            "ticker": p["ticker"], "side": p["side"], "action": "T2_EXIT",
            "entry": p["entry"], "exit": fill, "leverage": lev,
            "pnl_usd": round(pnl, 4),
        })
        state["position"] = None
        lines.append(f"T2: closed {p['ticker']} {p['side']} @ ${fill:.2f} ({lev}x), booked ${pnl:+.2f}")
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
    stop_pct = float(sig.get("stop_pct", 0.02))
    t1_pct = float(sig.get("t1_pct", 0.03))
    t2_pct = float(sig.get("t2_pct", 0.06))
    lev = next_leverage(state)

    stop = entry * (1 - stop_pct * s)
    t1 = entry * (1 + t1_pct * s)
    t2 = entry * (1 + t2_pct * s)
    shares = state["cash"] / entry
    state["cash"] -= shares * entry
    state["position"] = {
        "ticker": ticker, "side": side, "shares": shares, "entry": entry,
        "stop": round(stop, 2), "t1": round(t1, 2), "t2": round(t2, 2),
        "half_taken": False, "leverage": lev,
        "confidence": sig.get("confidence"),
        "opened_at": quote.get("market_time"),
    }
    lines.append(
        f"ENTRY ({side.upper()} {ticker}, conf {sig.get('confidence')}, {lev}x): "
        f"{shares:.6f} @ ${entry:.2f} - stop ${stop:.2f}, T1 ${t1:.2f}, T2 ${t2:.2f}"
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
    lines = [
        f"# Signal Sim ($200, 10x, long+short) - {today}",
        "",
        f"- Cash: ${state['cash']:.2f}",
        f"- Position: {json.dumps(pos) if pos else 'FLAT'}",
        f"- Mark ({mark_sym}): ${mark:.2f}" if mark else "- Mark: n/a",
        f"- Mark-to-market equity: ${eq:.2f} ({pnl_pct:+.2f}% vs $200)",
        f"- Realized P&L to date: ${realized:+.2f}",
        f"- Closed trades: {len(state['trade_log'])}",
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
    actions = []
    mark_sym, mark = None, None

    if state.get("position"):
        # Manage the open position against its ticker's live quote.
        p = state["position"]
        mark_sym = p["ticker"]
        quote = get_quote(mark_sym)
        if quote:
            mark = quote["last"]
            actions += manage_exit(state, quote)
    if not state.get("position"):
        sig = pick_signal(state)
        if sig:
            mark_sym = sig["sector_or_ticker"]
            q = get_quote(mark_sym)
            mark = q["last"] if q else None
            actions += open_from_signal(state, sig)
        else:
            actions.append("no actionable signal (need direction, confidence>=0.6, not priced-in)")

    # refresh mark from any (new) open position
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
