#!/usr/bin/env python3
"""
ai4trade autonomous NASDAQ sim-trading bot.

Runs on a schedule (GitHub Actions). Each run:
  1. Skip if US market closed (server enforces this too).
  2. Read our ledger (state.json) + append price samples (price_history.json).
  3. Manage open positions: 5% hard stop-loss, take-profit, trend-break exit.
  4. Open new positions from an aggressive NASDAQ watchlist on positive momentum.
  5. Write/refresh today's report and, near close, a "lessons learned" entry
     that nudges strategy parameters (params.json) = the daily learning loop.

State lives in the repo (committed back by the workflow) so it survives
across runs even though the runner is stateless and your PC is off.

Budget is capped (default $100) regardless of the platform's $100k sim cash.
"""

import json
import os
import sys
import time
import datetime as dt
from pathlib import Path
from urllib import request as urlrequest
from urllib import parse as urlparse
from urllib.error import HTTPError, URLError

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------
BASE = "https://ai4trade.ai"
TOKEN = os.environ.get("AI4TRADE_TOKEN", "").strip()
MARKET = "us-stock"

BUDGET_USD = float(os.environ.get("BUDGET_USD", "100"))   # total capital to deploy
MAX_POSITIONS = 5                                          # hold at most 5 names
SLOT_USD = BUDGET_USD / MAX_POSITIONS                      # ~$20 per name

# Curated for the week of 2026-07-06.  Rationale in reports/PICKS.md.
# 1. AMD  - ai4trade buy signal 3.5, Meta 6GW MI300 deal, +10%/5d
# 2. PLTR - Army NGC2 win + NVDA sovereign-AI deal (Jul 1), +7.77% Jul 1
# 3. MSTR - new capital plan, Citi $260 target, leveraged BTC proxy
# 4. AVGO - constructive trend, hold signal 1.0, steady AI-infra ballast
# 5. COIN - crypto beta without MSTR single-name concentration
WATCHLIST = ["AMD", "PLTR", "MSTR", "AVGO", "COIN"]

ROOT = Path(__file__).resolve().parent
STATE_FILE = ROOT / "state.json"
HIST_FILE = ROOT / "price_history.json"
PARAMS_FILE = ROOT / "params.json"
REPORTS_DIR = ROOT / "reports"
LEARN_FILE = ROOT / "learnings.md"

# Default tunable strategy parameters (the daily loop adjusts these).
DEFAULT_PARAMS = {
    "entry_momentum": 0.003,   # need >= +0.3% short-term momentum to buy
    "exit_momentum": -0.004,   # trend-break exit at <= -0.4% momentum
    "stop_loss": -0.05,        # HARD -5% stop (user rule, never loosened)
    "take_profit": 0.06,       # lock gains at +6%
    "momentum_lookback": 2,    # samples back for momentum calc
    "cooldown_runs": 3,        # runs to wait before re-buying a stopped name
}

# ----------------------------------------------------------------------------
# HTTP helpers
# ----------------------------------------------------------------------------
def _headers():
    return {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _get(path, params=None):
    url = f"{BASE}{path}"
    if params:
        url += "?" + urlparse.urlencode(params)
    req = urlrequest.Request(url, headers=_headers(), method="GET")
    with urlrequest.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def _post(path, body):
    data = json.dumps(body).encode()
    req = urlrequest.Request(f"{BASE}{path}", data=data, headers=_headers(), method="POST")
    try:
        with urlrequest.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"detail": str(e)}


def get_price(symbol):
    try:
        d = _get("/api/price", {"symbol": symbol, "market": MARKET})
        p = d.get("price")
        return float(p) if p is not None else None
    except (HTTPError, URLError, ValueError):
        return None


def place_trade(action, symbol, price, quantity, content):
    """action in buy/sell. Returns (ok, detail)."""
    body = {
        "action": action,
        "symbol": symbol,
        "market": MARKET,
        "price": round(price, 4),
        "quantity": round(quantity, 6),
        "content": content,
        "executed_at": utcnow_iso(),
    }
    status, resp = _post("/api/signals/realtime", body)
    if status == 200 and resp.get("success"):
        return True, resp
    return False, resp

# ----------------------------------------------------------------------------
# Time helpers
# ----------------------------------------------------------------------------
def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def utcnow_iso():
    return utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def ny_now():
    """US Eastern wall-clock, DST-aware (US rules)."""
    u = utcnow()
    year = u.year
    # 2nd Sunday of March -> 1st Sunday of Nov is EDT (UTC-4); else EST (UTC-5).
    def nth_sunday(y, month, n):
        d = dt.datetime(y, month, 1, tzinfo=dt.timezone.utc)
        offset = (6 - d.weekday()) % 7  # weekday: Mon=0..Sun=6
        return d + dt.timedelta(days=offset + 7 * (n - 1))
    dst_start = nth_sunday(year, 3, 2).replace(hour=7)   # 2am ET = 7am UTC
    dst_end = nth_sunday(year, 11, 1).replace(hour=6)    # 2am ET = 6am UTC
    edt = dst_start <= u < dst_end
    return u + dt.timedelta(hours=-4 if edt else -5)


def market_open_now():
    n = ny_now()
    if n.weekday() >= 5:  # Sat/Sun
        return False
    mins = n.hour * 60 + n.minute
    return 570 <= mins <= 960  # 9:30 (570) .. 16:00 (960)

# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return json.loads(json.dumps(default))


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2))


def load_state():
    return load_json(STATE_FILE, {
        "positions": {},        # symbol -> {qty, entry, entry_at}
        "cooldown": {},         # symbol -> runs remaining
        "realized_pnl": 0.0,    # cumulative realized $
        "run_count": 0,
        "last_reflection_date": "",
        "trade_log": [],        # recent closed trades for reflection
        "position_schema_seen": None,
    })

# ----------------------------------------------------------------------------
# Strategy
# ----------------------------------------------------------------------------
def append_history(hist, prices):
    stamp = utcnow_iso()
    for sym, px in prices.items():
        if px is None:
            continue
        hist.setdefault(sym, []).append({"t": stamp, "p": px})
        hist[sym] = hist[sym][-60:]  # keep last 60 samples per symbol
    return hist


def momentum(hist, sym, lookback):
    series = hist.get(sym, [])
    if len(series) < lookback + 1:
        return None
    now = series[-1]["p"]
    then = series[-1 - lookback]["p"]
    if then <= 0:
        return None
    return (now - then) / then


def deployed_cost(state):
    return sum(p["qty"] * p["entry"] for p in state["positions"].values())

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main():
    if not TOKEN:
        print("ERROR: AI4TRADE_TOKEN not set")
        sys.exit(1)

    REPORTS_DIR.mkdir(exist_ok=True)
    state = load_state()
    params = load_json(PARAMS_FILE, DEFAULT_PARAMS)
    for k, v in DEFAULT_PARAMS.items():
        params.setdefault(k, v)
    hist = load_json(HIST_FILE, {})

    n = ny_now()
    print(f"NY time: {n:%Y-%m-%d %H:%M} ET | open={market_open_now()}")

    if not market_open_now():
        print("Market closed. Recording prices only, no trades.")
        prices = {}
        for s in WATCHLIST:
            prices[s] = get_price(s)
            time.sleep(1.1)  # respect 1 req/sec price limit
        hist = append_history(hist, prices)
        save_json(HIST_FILE, hist)
        return

    state["run_count"] += 1
    actions = []

    # --- fetch prices (watchlist + held) ---
    symbols = list(dict.fromkeys(WATCHLIST + list(state["positions"].keys())))
    prices = {}
    for s in symbols:
        prices[s] = get_price(s)
        time.sleep(1.1)
    hist = append_history(hist, prices)

    # --- log platform position schema once (for debugging/reconciliation) ---
    try:
        pos_api = _get("/api/positions")
        if state.get("position_schema_seen") is None and pos_api.get("positions"):
            state["position_schema_seen"] = list(pos_api["positions"][0].keys())
    except Exception:
        pass

    # --- decrement cooldowns ---
    for s in list(state["cooldown"].keys()):
        state["cooldown"][s] -= 1
        if state["cooldown"][s] <= 0:
            del state["cooldown"][s]

    # --- manage open positions (exits) ---
    for sym in list(state["positions"].keys()):
        pos = state["positions"][sym]
        px = prices.get(sym)
        if px is None:
            continue
        pnl_pct = (px - pos["entry"]) / pos["entry"]
        mom = momentum(hist, sym, params["momentum_lookback"])
        reason = None
        if pnl_pct <= params["stop_loss"]:
            reason = f"STOP {pnl_pct:+.2%}"
        elif pnl_pct >= params["take_profit"]:
            reason = f"TAKE-PROFIT {pnl_pct:+.2%}"
        elif mom is not None and mom <= params["exit_momentum"]:
            reason = f"TREND-BREAK mom {mom:+.2%} (pnl {pnl_pct:+.2%})"
        if reason:
            ok, resp = place_trade("sell", sym, px, pos["qty"], f"exit: {reason}")
            if ok:
                realized = (px - pos["entry"]) * pos["qty"]
                state["realized_pnl"] += realized
                state["trade_log"].append({
                    "sym": sym, "pnl_pct": pnl_pct, "pnl_usd": realized,
                    "reason": reason.split()[0], "closed_at": utcnow_iso(),
                })
                state["trade_log"] = state["trade_log"][-50:]
                # stop-outs get a cooldown before re-entry
                if reason.startswith("STOP"):
                    state["cooldown"][sym] = params["cooldown_runs"]
                del state["positions"][sym]
                actions.append(f"SELL {sym} {pos['qty']:.4f}@{px:.2f} ({reason}) => {realized:+.2f}$")
            else:
                actions.append(f"SELL {sym} FAILED: {resp.get('detail')}")

    # --- open new positions ---
    # First market-open run of the mandate: seed equal-weight across the whole
    # watchlist so the week starts with real exposure instead of waiting several
    # runs to accumulate enough history for a momentum signal.
    seeding = (state["run_count"] == 1 and not state["positions"])
    for sym in WATCHLIST:
        if len(state["positions"]) >= MAX_POSITIONS:
            break
        if sym in state["positions"] or sym in state["cooldown"]:
            continue
        px = prices.get(sym)
        if px is None:
            continue
        if seeding:
            reason_note = "seed"
        else:
            mom = momentum(hist, sym, params["momentum_lookback"])
            if mom is None or mom < params["entry_momentum"]:
                continue
            reason_note = f"mom {mom:+.2%}"
        if deployed_cost(state) + SLOT_USD > BUDGET_USD + 1e-6:
            continue
        qty = SLOT_USD / px
        ok, resp = place_trade("buy", sym, px, qty, f"entry: {reason_note}")
        if ok:
            state["positions"][sym] = {"qty": qty, "entry": px, "entry_at": utcnow_iso()}
            actions.append(f"BUY {sym} {qty:.4f}@{px:.2f} ({reason_note})")
        else:
            actions.append(f"BUY {sym} FAILED: {resp.get('detail')}")

    # --- persist + report ---
    save_json(HIST_FILE, hist)
    write_report(state, params, prices, actions, n)

    # daily reflection near close (once per day)
    today = n.strftime("%Y-%m-%d")
    if n.hour >= 15 and state["last_reflection_date"] != today:
        reflect_and_learn(state, params, today)
        state["last_reflection_date"] = today
        save_json(PARAMS_FILE, params)

    save_json(STATE_FILE, state)
    print("Actions:", actions or "none")


def unrealized(state, prices):
    tot = 0.0
    for sym, pos in state["positions"].items():
        px = prices.get(sym)
        if px:
            tot += (px - pos["entry"]) * pos["qty"]
    return tot


def write_report(state, params, prices, actions, n):
    today = n.strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"{today}.md"
    unreal = unrealized(state, prices)
    lines = [
        f"# Report {today}",
        f"_Last update: {n:%H:%M} ET (run #{state['run_count']})_",
        "",
        f"- Budget: ${BUDGET_USD:.0f} | Deployed: ${deployed_cost(state):.2f}",
        f"- Realized P&L (cumulative): ${state['realized_pnl']:+.2f}",
        f"- Unrealized P&L (open): ${unreal:+.2f}",
        f"- Total P&L: ${state['realized_pnl'] + unreal:+.2f}",
        "",
        "## Open positions",
    ]
    if state["positions"]:
        lines.append("| Symbol | Qty | Entry | Now | P&L% |")
        lines.append("|--------|-----|-------|-----|------|")
        for sym, pos in state["positions"].items():
            px = prices.get(sym) or pos["entry"]
            pnl = (px - pos["entry"]) / pos["entry"]
            lines.append(f"| {sym} | {pos['qty']:.4f} | {pos['entry']:.2f} | {px:.2f} | {pnl:+.2%} |")
    else:
        lines.append("_none_")
    lines += ["", "## Actions this run"]
    lines += [f"- {a}" for a in actions] or ["- none"]
    path.write_text("\n".join(lines) + "\n")


def reflect_and_learn(state, params, today):
    """Daily learning: inspect recent closed trades, nudge parameters."""
    recent = [t for t in state["trade_log"] if t["closed_at"][:10] == today]
    wins = [t for t in recent if t["pnl_usd"] > 0]
    losses = [t for t in recent if t["pnl_usd"] <= 0]
    stops = [t for t in recent if t["reason"] == "STOP"]
    net = sum(t["pnl_usd"] for t in recent)

    notes = []
    # Rule 1: too many stop-outs => entries too loose, be more selective.
    if len(stops) >= 2 and net < 0:
        params["entry_momentum"] = round(min(params["entry_momentum"] + 0.001, 0.02), 4)
        params["cooldown_runs"] = min(params["cooldown_runs"] + 1, 8)
        notes.append(f"{len(stops)} stop-outs, net {net:+.2f}$ -> raise entry_momentum "
                     f"to {params['entry_momentum']:.3f}, cooldown to {params['cooldown_runs']}")
    # Rule 2: profitable day with wins => allow slightly earlier entries.
    elif net > 0 and len(wins) >= max(1, len(losses)):
        params["entry_momentum"] = round(max(params["entry_momentum"] - 0.0005, 0.001), 4)
        notes.append(f"green day net {net:+.2f}$ -> ease entry_momentum to {params['entry_momentum']:.3f}")
    else:
        notes.append(f"net {net:+.2f}$, {len(wins)}W/{len(losses)}L -> params held")

    # stop_loss is a user hard rule: never touch it.
    entry = [
        f"## {today}",
        f"- Trades: {len(recent)} ({len(wins)}W / {len(losses)}L), stop-outs: {len(stops)}",
        f"- Realized today: ${net:+.2f} | cumulative: ${state['realized_pnl']:+.2f}",
        f"- Lesson: {notes[0]}",
        "",
    ]
    prev = LEARN_FILE.read_text() if LEARN_FILE.exists() else "# Learning journal\n\n"
    LEARN_FILE.write_text(prev + "\n".join(entry) + "\n")


if __name__ == "__main__":
    main()
