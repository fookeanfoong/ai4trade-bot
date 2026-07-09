#!/usr/bin/env python3
"""
SPY $200 TA-based paper trading simulation.

Runs on GitHub Actions at Nasdaq open. Uses free Stooq daily bars, no API key.

Strategy (from the July 2026 SPY TA report card):
  Setup A (breakout): daily close > $760.40 on volume > 60M.
    Entry $761.00, stop $752.50, T1 $782 (sell half, stop -> BE), T2 $805.
  Setup B (pullback): day's low tags the $739-$741 zone and close holds >= $739.
    Entry $740.50, stop $732, T1 $752 (sell half, stop -> BE), T2 $760.
  Invalidation: daily close < $722 -> stay flat, log bearish flip.

Paper account: $200 in fractional SPY. Deterministic; separate from bot.py.
State: spy_sim_state.json.  Reports: reports/spy_sim/YYYY-MM-DD.md.
"""

import csv
import datetime as dt
import io
import json
import sys
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "spy_sim_state.json"
REPORTS_DIR = ROOT / "reports" / "spy_sim"

STARTING_CASH = 200.0

BREAKOUT_TRIGGER = 760.40
BREAKOUT_VOL_MIN = 60_000_000
BREAKOUT_ENTRY   = 761.00
BREAKOUT_STOP    = 752.50
BREAKOUT_T1      = 782.00
BREAKOUT_T2      = 805.00

PULLBACK_LOW     = 739.00
PULLBACK_HIGH    = 741.00
PULLBACK_ENTRY   = 740.50
PULLBACK_STOP    = 732.00
PULLBACK_T1      = 752.00
PULLBACK_T2      = 760.00

BEAR_FLIP_CLOSE  = 722.00


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "cash": STARTING_CASH,
        "position": None,
        "trade_log": [],
        "runs": [],
        "peak_equity": STARTING_CASH,
        "last_bar_date": None,
    }


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def fetch_stooq_daily() -> list:
    """Return SPY daily bars (oldest -> newest) from Stooq, no API key."""
    url = "https://stooq.com/q/d/l/?s=spy.us&i=d"
    req = urlrequest.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlrequest.urlopen(req, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    bars = []
    for row in reader:
        try:
            bars.append({
                "date":   row["Date"],
                "open":   float(row["Open"]),
                "high":   float(row["High"]),
                "low":    float(row["Low"]),
                "close":  float(row["Close"]),
                "volume": int(row["Volume"]),
            })
        except (KeyError, ValueError):
            continue
    return bars


def is_weekday_ny() -> bool:
    if ZoneInfo:
        now_ny = dt.datetime.now(ZoneInfo("America/New_York"))
    else:
        now_ny = dt.datetime.utcnow() - dt.timedelta(hours=4)
    return now_ny.weekday() < 5


def check_exits(state: dict, bar: dict) -> list:
    """Apply intraday stop/target fills to open position based on today's OHLC."""
    lines = []
    p = state.get("position")
    if not p:
        return lines
    kind = p["kind"]

    # Conservative: if both stop and target hit intraday, stop fills first.
    if bar["low"] <= p["stop"]:
        fill = p["stop"]
        proceeds = p["shares"] * fill
        pnl = proceeds - (p["shares"] * p["entry"])
        state["cash"] += proceeds
        state["trade_log"].append({
            "kind": kind,
            "action": "STOP_EXIT" if not p["half_taken"] else "BE_STOP_EXIT",
            "entry": p["entry"], "exit": fill,
            "shares": round(p["shares"], 8),
            "pnl_usd": round(pnl, 4),
            "pnl_pct": round(pnl / (p["shares"] * p["entry"]) * 100, 3),
            "closed_on": bar["date"],
        })
        state["position"] = None
        lines.append(f"EXIT: {kind} stopped at ${fill:.2f} — realized P&L ${pnl:+.2f}")
        return lines

    if not p["half_taken"] and bar["high"] >= p["t1"]:
        half = p["shares"] / 2
        fill = p["t1"]
        proceeds = half * fill
        pnl = proceeds - (half * p["entry"])
        state["cash"] += proceeds
        p["shares"] -= half
        p["half_taken"] = True
        p["stop"] = p["entry"]
        state["trade_log"].append({
            "kind": kind, "action": "T1_HALF",
            "entry": p["entry"], "exit": fill,
            "shares": round(half, 8),
            "pnl_usd": round(pnl, 4),
            "pnl_pct": round(pnl / (half * p["entry"]) * 100, 3),
            "closed_on": bar["date"],
        })
        lines.append(f"T1 HIT: sold half of {kind} at ${fill:.2f}, stop -> BE ${p['stop']:.2f}, booked ${pnl:+.2f}")

    if p["shares"] > 1e-9 and bar["high"] >= p["t2"]:
        fill = p["t2"]
        proceeds = p["shares"] * fill
        pnl = proceeds - (p["shares"] * p["entry"])
        state["cash"] += proceeds
        state["trade_log"].append({
            "kind": kind, "action": "T2_EXIT",
            "entry": p["entry"], "exit": fill,
            "shares": round(p["shares"], 8),
            "pnl_usd": round(pnl, 4),
            "pnl_pct": round(pnl / (p["shares"] * p["entry"]) * 100, 3),
            "closed_on": bar["date"],
        })
        state["position"] = None
        lines.append(f"T2 HIT: closed remaining {kind} at ${fill:.2f}, booked ${pnl:+.2f}")
    return lines


def check_entries(state: dict, bar: dict) -> list:
    lines = []
    if state.get("position") or state["cash"] < 5:
        return lines

    close = bar["close"]
    low   = bar["low"]
    vol   = bar["volume"]

    if close < BEAR_FLIP_CLOSE:
        lines.append(f"BEAR FLIP: close ${close:.2f} < ${BEAR_FLIP_CLOSE:.2f} — staying flat.")
        return lines

    if close > BREAKOUT_TRIGGER and vol > BREAKOUT_VOL_MIN:
        shares = state["cash"] / BREAKOUT_ENTRY
        state["cash"] -= shares * BREAKOUT_ENTRY
        state["position"] = {
            "kind": "BREAKOUT_LONG_A",
            "shares": shares,
            "entry": BREAKOUT_ENTRY,
            "stop":  BREAKOUT_STOP,
            "t1":    BREAKOUT_T1,
            "t2":    BREAKOUT_T2,
            "half_taken": False,
            "opened_on": bar["date"],
        }
        lines.append(
            f"ENTRY (Setup A breakout): {shares:.6f} SPY @ ${BREAKOUT_ENTRY:.2f} "
            f"— stop ${BREAKOUT_STOP}, T1 ${BREAKOUT_T1}, T2 ${BREAKOUT_T2}"
        )
        return lines

    tagged_zone = PULLBACK_LOW <= low <= PULLBACK_HIGH
    held_close  = close >= PULLBACK_LOW
    if tagged_zone and held_close:
        shares = state["cash"] / PULLBACK_ENTRY
        state["cash"] -= shares * PULLBACK_ENTRY
        state["position"] = {
            "kind": "PULLBACK_LONG_B",
            "shares": shares,
            "entry": PULLBACK_ENTRY,
            "stop":  PULLBACK_STOP,
            "t1":    PULLBACK_T1,
            "t2":    PULLBACK_T2,
            "half_taken": False,
            "opened_on": bar["date"],
        }
        lines.append(
            f"ENTRY (Setup B pullback): {shares:.6f} SPY @ ${PULLBACK_ENTRY:.2f} "
            f"— stop ${PULLBACK_STOP}, T1 ${PULLBACK_T1}, T2 ${PULLBACK_T2}"
        )
    return lines


def equity(state: dict, mark: float) -> float:
    p = state.get("position")
    return state["cash"] + (p["shares"] * mark if p else 0.0)


def write_report(state: dict, bar: dict, actions: list) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"{today}.md"
    eq = equity(state, bar["close"])
    pnl_pct = (eq - STARTING_CASH) / STARTING_CASH * 100
    pos = state.get("position")

    lines = [
        f"# SPY $200 Sim — {today}",
        "",
        f"Bar processed: {bar['date']}  "
        f"O:{bar['open']}  H:{bar['high']}  L:{bar['low']}  C:{bar['close']}  V:{bar['volume']:,}",
        "",
        f"- Cash: ${state['cash']:.2f}",
        f"- Position: {json.dumps(pos) if pos else 'FLAT'}",
        f"- Mark-to-market equity: ${eq:.2f} ({pnl_pct:+.2f}% vs $200 start)",
        f"- Realized trades to date: {len(state['trade_log'])}",
        "",
        "## Actions this run",
        "",
    ]
    lines += [f"- {a}" for a in actions] if actions else ["- (no trigger — waiting)"]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    if not is_weekday_ny():
        print("Weekend — skipping.")
        return 0
    try:
        bars = fetch_stooq_daily()
    except (HTTPError, URLError) as e:
        print(f"stooq fetch failed: {e}", file=sys.stderr)
        return 1
    if not bars:
        print("no bars returned", file=sys.stderr)
        return 1
    latest = bars[-1]

    state = load_state()
    if state.get("last_bar_date") == latest["date"]:
        print(f"Already processed bar {latest['date']}; nothing to do.")
        return 0

    actions = []
    actions += check_exits(state, latest)
    actions += check_entries(state, latest)

    state["last_bar_date"] = latest["date"]
    eq = equity(state, latest["close"])
    state["peak_equity"] = max(state.get("peak_equity", STARTING_CASH), eq)
    state["runs"].append({
        "ran_at":  dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "bar_date": latest["date"],
        "close":   latest["close"],
        "equity":  round(eq, 4),
        "actions": actions,
    })
    state["runs"] = state["runs"][-200:]

    save_state(state)
    write_report(state, latest, actions)

    print(f"Done. Equity ${eq:.2f} ({(eq - STARTING_CASH) / STARTING_CASH * 100:+.2f}%)")
    for a in actions:
        print(f"  * {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
