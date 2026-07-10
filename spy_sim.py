#!/usr/bin/env python3
"""
SPY $200 leveraged TA-based paper trading simulation.

Runs on GitHub Actions (folded into ai4trade-bot workflow). Uses free public
market-data endpoints, no API key.

Strategy (aggressive tuning based on July 2026 SPY TA report card):
  Setup A (breakout): daily close > $760.40 on volume > 40M.
    Entry $761.00, stop $752.50, T1 $782 (sell half, stop -> BE), T2 $805.
  Setup B (pullback, WIDENED): day's low tags the $745-$749 zone and close holds >= $745.
    Entry $747.00, stop $743.50, T1 $752 (sell half, stop -> BE), T2 $758.
  Invalidation: daily close < $722 -> stay flat, log bearish flip.

Leverage: dynamic. Default BASE_LEVERAGE (10x). If drawdown from peak equity
reaches DRAWDOWN_CAP_USD ($40 = 20% of a $200 account), the NEXT entry uses
REDUCED_LEVERAGE (5x) — a circuit breaker to slow account destruction on a
losing streak. Each open position stores its own leverage so exits use the
leverage it was opened at.

Paper account: $200. Deterministic; separate from bot.py.
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

BASE_LEVERAGE       = 10.0
REDUCED_LEVERAGE    = 5.0
DRAWDOWN_CAP_USD    = 40.0   # 20% of $200

BREAKOUT_TRIGGER = 760.40
BREAKOUT_VOL_MIN = 40_000_000   # lowered from 60M for aggressive entry
BREAKOUT_ENTRY   = 761.00
BREAKOUT_STOP    = 752.50
BREAKOUT_T1      = 782.00
BREAKOUT_T2      = 805.00

# Widened pullback zone: covers current SPY area to catch more setups.
PULLBACK_LOW     = 745.00
PULLBACK_HIGH    = 749.00
PULLBACK_ENTRY   = 747.00
PULLBACK_STOP    = 743.50
PULLBACK_T1      = 752.00
PULLBACK_T2      = 758.00

BEAR_FLIP_CLOSE  = 722.00

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)


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


def fetch_yahoo_daily() -> list:
    """Fetch SPY daily OHLCV from Yahoo Finance chart JSON (no API key)."""
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/SPY"
           "?range=3mo&interval=1d")
    req = urlrequest.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "application/json",
    })
    with urlrequest.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    ts = result["timestamp"]
    q = result["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i]
        if None in (o, h, l, c, v):
            continue
        bars.append({
            "date":   dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"),
            "open":   float(o),
            "high":   float(h),
            "low":    float(l),
            "close":  float(c),
            "volume": int(v),
        })
    return bars


def fetch_stooq_daily() -> list:
    """Fallback: Stooq daily CSV. Often bot-blocked on cloud IPs."""
    url = "https://stooq.com/q/d/l/?s=spy.us&i=d"
    req = urlrequest.Request(url, headers={"User-Agent": BROWSER_UA})
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


def fetch_daily_bars() -> list:
    """Try Yahoo first, fall back to Stooq. Logs which source served."""
    errors = []
    for name, fn in [("yahoo", fetch_yahoo_daily), ("stooq", fetch_stooq_daily)]:
        try:
            bars = fn()
            if bars:
                print(f"data source: {name} ({len(bars)} bars)")
                return bars
            errors.append(f"{name}: empty response")
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
    raise RuntimeError("all data sources failed: " + "; ".join(errors))


def is_weekday_ny() -> bool:
    if ZoneInfo:
        now_ny = dt.datetime.now(ZoneInfo("America/New_York"))
    else:
        now_ny = dt.datetime.utcnow() - dt.timedelta(hours=4)
    return now_ny.weekday() < 5


def next_leverage(state: dict) -> float:
    """Leverage for the NEXT entry, based on drawdown from peak equity.

    Uses realized equity (cash + cost basis of any open position, no MTM) so
    a transient dip below cap doesn't oscillate the setting on unrelated bars.
    """
    peak = state.get("peak_equity", STARTING_CASH)
    p = state.get("position")
    realized = state["cash"] + (p["shares"] * p["entry"] if p else 0.0)
    dd = peak - realized
    return REDUCED_LEVERAGE if dd >= DRAWDOWN_CAP_USD else BASE_LEVERAGE


def leveraged_proceeds(shares: float, entry: float, exit_price: float, leverage: float) -> float:
    """Cash returned when selling `shares` bought at `entry`, price now `exit_price`.

    Applies the position's own `leverage` to the price move. Cost basis
    (shares*entry) always comes back; the P&L component is amplified.
    """
    cost = shares * entry
    raw_pnl = shares * (exit_price - entry)
    return cost + raw_pnl * leverage


def check_exits(state: dict, bar: dict) -> list:
    """Apply intraday stop/target fills to open position based on today's OHLC."""
    lines = []
    p = state.get("position")
    if not p:
        return lines
    kind = p["kind"]
    lev = p.get("leverage", BASE_LEVERAGE)

    if bar["low"] <= p["stop"]:
        fill = p["stop"]
        proceeds = leveraged_proceeds(p["shares"], p["entry"], fill, lev)
        pnl = proceeds - (p["shares"] * p["entry"])
        state["cash"] += proceeds
        state["trade_log"].append({
            "kind": kind,
            "action": "STOP_EXIT" if not p["half_taken"] else "BE_STOP_EXIT",
            "entry": p["entry"], "exit": fill,
            "shares": round(p["shares"], 8),
            "leverage": lev,
            "pnl_usd": round(pnl, 4),
            "pnl_pct": round(pnl / (p["shares"] * p["entry"]) * 100, 3),
            "closed_on": bar["date"],
        })
        state["position"] = None
        lines.append(f"EXIT: {kind} stopped at ${fill:.2f} ({lev}x-lev) - realized P&L ${pnl:+.2f}")
        return lines

    if not p["half_taken"] and bar["high"] >= p["t1"]:
        half = p["shares"] / 2
        fill = p["t1"]
        proceeds = leveraged_proceeds(half, p["entry"], fill, lev)
        pnl = proceeds - (half * p["entry"])
        state["cash"] += proceeds
        p["shares"] -= half
        p["half_taken"] = True
        p["stop"] = p["entry"]
        state["trade_log"].append({
            "kind": kind, "action": "T1_HALF",
            "entry": p["entry"], "exit": fill,
            "shares": round(half, 8),
            "leverage": lev,
            "pnl_usd": round(pnl, 4),
            "pnl_pct": round(pnl / (half * p["entry"]) * 100, 3),
            "closed_on": bar["date"],
        })
        lines.append(f"T1 HIT: sold half of {kind} at ${fill:.2f} ({lev}x-lev), stop -> BE ${p['stop']:.2f}, booked ${pnl:+.2f}")

    if p["shares"] > 1e-9 and bar["high"] >= p["t2"]:
        fill = p["t2"]
        proceeds = leveraged_proceeds(p["shares"], p["entry"], fill, lev)
        pnl = proceeds - (p["shares"] * p["entry"])
        state["cash"] += proceeds
        state["trade_log"].append({
            "kind": kind, "action": "T2_EXIT",
            "entry": p["entry"], "exit": fill,
            "shares": round(p["shares"], 8),
            "leverage": lev,
            "pnl_usd": round(pnl, 4),
            "pnl_pct": round(pnl / (p["shares"] * p["entry"]) * 100, 3),
            "closed_on": bar["date"],
        })
        state["position"] = None
        lines.append(f"T2 HIT: closed remaining {kind} at ${fill:.2f} ({lev}x-lev), booked ${pnl:+.2f}")
    return lines


def check_entries(state: dict, bar: dict) -> list:
    lines = []
    if state.get("position") or state["cash"] < 5:
        return lines

    close = bar["close"]
    low   = bar["low"]
    vol   = bar["volume"]

    if close < BEAR_FLIP_CLOSE:
        lines.append(f"BEAR FLIP: close ${close:.2f} < ${BEAR_FLIP_CLOSE:.2f} - staying flat.")
        return lines

    lev = next_leverage(state)

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
            "leverage": lev,
            "opened_on": bar["date"],
        }
        lines.append(
            f"ENTRY (Setup A breakout, {lev}x-lev): {shares:.6f} SPY @ ${BREAKOUT_ENTRY:.2f} "
            f"- stop ${BREAKOUT_STOP}, T1 ${BREAKOUT_T1}, T2 ${BREAKOUT_T2}"
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
            "leverage": lev,
            "opened_on": bar["date"],
        }
        lines.append(
            f"ENTRY (Setup B pullback, {lev}x-lev): {shares:.6f} SPY @ ${PULLBACK_ENTRY:.2f} "
            f"- stop ${PULLBACK_STOP}, T1 ${PULLBACK_T1}, T2 ${PULLBACK_T2}"
        )
    return lines


def equity(state: dict, mark: float) -> float:
    """Mark-to-market account value, position valued at its own leverage."""
    p = state.get("position")
    if not p:
        return state["cash"]
    return state["cash"] + leveraged_proceeds(
        p["shares"], p["entry"], mark, p.get("leverage", BASE_LEVERAGE)
    )


def write_report(state: dict, bar: dict, actions: list) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.datetime.utcnow().strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"{today}.md"
    eq = equity(state, bar["close"])
    pnl_pct = (eq - STARTING_CASH) / STARTING_CASH * 100
    pos = state.get("position")
    lev_now = next_leverage(state)
    dd_now = state.get("peak_equity", STARTING_CASH) - (state["cash"] + (pos["shares"] * pos["entry"] if pos else 0.0))

    lines = [
        f"# SPY $200 Sim (10x leverage, aggressive) - {today}",
        "",
        f"Bar processed: {bar['date']}  "
        f"O:{bar['open']}  H:{bar['high']}  L:{bar['low']}  C:{bar['close']}  V:{bar['volume']:,}",
        "",
        f"- Cash: ${state['cash']:.2f}",
        f"- Position: {json.dumps(pos) if pos else 'FLAT'}",
        f"- Mark-to-market equity: ${eq:.2f} ({pnl_pct:+.2f}% vs $200 start)",
        f"- Peak equity: ${state.get('peak_equity', STARTING_CASH):.2f}",
        f"- Drawdown from peak (realized): ${dd_now:.2f}",
        f"- Leverage for NEXT entry: {lev_now}x (base {BASE_LEVERAGE}x, cap trips at ${DRAWDOWN_CAP_USD} dd)",
        f"- Realized trades to date: {len(state['trade_log'])}",
        "",
        "## Actions this run",
        "",
    ]
    lines += [f"- {a}" for a in actions] if actions else ["- (no trigger - waiting)"]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    if not is_weekday_ny():
        print("Weekend - skipping.")
        return 0
    try:
        bars = fetch_daily_bars()
    except Exception as e:
        print(f"data fetch failed: {e}", file=sys.stderr)
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

    print(f"Done. Equity ${eq:.2f} ({(eq - STARTING_CASH) / STARTING_CASH * 100:+.2f}%) [next-lev {next_leverage(state)}x]")
    for a in actions:
        print(f"  * {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
