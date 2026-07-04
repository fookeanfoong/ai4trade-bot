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
# News feed (free Yahoo Finance RSS, no key)
# ----------------------------------------------------------------------------
NEG_KEYWORDS = [
    "downgrade", "cut price target", "sec probe", "sec investigation",
    "recall", "lawsuit", "guidance cut", "misses", "shortfall", "warns",
    "layoffs", "resigns", "resignation", "halts", "halted", "fraud",
    "delisting", "restated", "restatement", "bankruptcy", "default",
    "subpoena", "settlement", "fired", "class action",
]
POS_KEYWORDS = [
    "beats", "beat estimates", "raises guidance", "upgrade", "raises target",
    "record revenue", "partnership", "deal", "wins contract", "approval",
    "buyback", "dividend hike", "surge", "acquires", "acquisition",
    "outperform", "expands", "milestone",
]


def _rss_items(sym):
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"
    req = urlrequest.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlrequest.urlopen(req, timeout=15) as r:
            xml = r.read().decode("utf-8", errors="ignore")
    except Exception:
        return []
    items = []
    for chunk in xml.split("<item>")[1:]:
        chunk = chunk.split("</item>")[0]
        def _tag(name):
            start = chunk.find(f"<{name}>")
            if start < 0:
                return ""
            start += len(name) + 2
            end = chunk.find(f"</{name}>", start)
            return chunk[start:end] if end > 0 else ""
        items.append({
            "title": _tag("title").replace("<![CDATA[", "").replace("]]>", "").strip(),
            "pubDate": _tag("pubDate").strip(),
            "link": _tag("link").strip(),
        })
    return items[:8]


def score_headlines(items):
    """Return (score, top_negative_headline_or_None). Score: negative bad."""
    score = 0
    worst = None
    for it in items:
        t = it["title"].lower()
        neg = sum(1 for k in NEG_KEYWORDS if k in t)
        pos = sum(1 for k in POS_KEYWORDS if k in t)
        s = pos - neg
        score += s
        if neg > 0 and (worst is None or s < 0):
            worst = it["title"]
    return score, worst


def refresh_news(state, symbols):
    """Poll RSS for each symbol; store latest snapshot in state['news'][sym]."""
    state.setdefault("news", {})
    fresh = {}
    for sym in symbols:
        items = _rss_items(sym)
        if not items:
            continue
        score, worst = score_headlines(items)
        prev_titles = {i["title"] for i in state["news"].get(sym, {}).get("items", [])}
        new_items = [i for i in items if i["title"] not in prev_titles]
        state["news"][sym] = {
            "at": utcnow_iso(),
            "score": score,
            "worst": worst,
            "items": items,
        }
        fresh[sym] = {"score": score, "worst": worst, "new_count": len(new_items)}
        time.sleep(0.3)  # be gentle to Yahoo
    return fresh

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
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return json.loads(json.dumps(default))


def save_json(path, obj):
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


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
def write_premarket(state, params, prices, n):
    """Pre-open research digest: ai4trade macro + per-stock signals + news."""
    today = n.strftime("%Y-%m-%d")
    path = REPORTS_DIR / f"{today}-premarket.md"

    overview = _safe_get("/api/market-intel/overview")
    macro = _safe_get("/api/market-intel/macro-signals")
    per_stock = {}
    for sym in WATCHLIST:
        per_stock[sym] = _safe_get(f"/api/market-intel/stocks/{sym}/latest")
        time.sleep(1.1)

    lines = [
        f"# Pre-market digest {today}",
        f"_Generated {n:%H:%M} ET_",
        "",
        "## Macro",
    ]
    if overview:
        lines += [
            f"- Verdict: **{overview.get('macro_verdict')}** "
            f"({overview.get('macro_bullish_count')}/{overview.get('macro_total_count')} risk-on)",
            f"- {overview.get('macro_summary', '')}",
            f"- BTC ETF flow: {overview.get('etf_direction')} — {overview.get('etf_summary', '')}",
            f"- Headlines tracked: {overview.get('headline_count')} "
            f"({overview.get('news_status')}), latest: _{overview.get('latest_headline')}_",
        ]
    else:
        lines.append("_intel unavailable_")

    lines += ["", "## Per-name snapshot"]
    for sym in WATCHLIST:
        d = per_stock.get(sym) or {}
        px = prices.get(sym)
        px_txt = f"${px:.2f}" if px else "n/a"
        sig = d.get("signal", "?")
        score = d.get("signal_score", "?")
        trend = d.get("trend_status", "?")
        summary = d.get("summary", "").strip()
        lines.append(f"- **{sym}** {px_txt} | {sig} ({score}) | {trend}")
        if summary:
            lines.append(f"  - {summary}")
        for f in (d.get("bullish_factors") or [])[:2]:
            lines.append(f"  - + {f}")
        for f in (d.get("risk_factors") or [])[:2]:
            lines.append(f"  - − {f}")

    lines += ["", "## Plan for the session",
              f"- Budget $ {BUDGET_USD:.0f}, up to {MAX_POSITIONS} names, ~${SLOT_USD:.2f} each.",
              f"- Hard stop {params['stop_loss']:.0%}, take profit {params['take_profit']:.0%}.",
              f"- Entry threshold: momentum >= {params['entry_momentum']:.3f}."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"pre-market digest -> {path.name}")


def _safe_get(path):
    try:
        return _get(path)
    except Exception:
        return None


def write_weekly_summary(state, prices, n):
    """Saturday summary of the last 7 days for the human reader."""
    today = n.strftime("%Y-%m-%d")
    week_start = (n - dt.timedelta(days=6)).strftime("%Y-%m-%d")
    trades = [t for t in state["trade_log"]
              if t["closed_at"][:10] >= week_start]
    wins = [t for t in trades if t["pnl_usd"] > 0]
    losses = [t for t in trades if t["pnl_usd"] <= 0]
    realized = sum(t["pnl_usd"] for t in trades)
    unreal = unrealized(state, prices)

    lines = [
        f"# Weekly summary {week_start} — {today}",
        "",
        f"- Trades closed: **{len(trades)}** ({len(wins)}W / {len(losses)}L)",
        f"- Realized P&L this week: **${realized:+.2f}**",
        f"- Open unrealized P&L: **${unreal:+.2f}**",
        f"- Net week: **${realized + unreal:+.2f}** on ${BUDGET_USD:.0f} budget "
        f"(**{(realized + unreal) / BUDGET_USD * 100:+.2f}%**)",
        f"- Cumulative realized since start: ${state['realized_pnl']:+.2f}",
        "",
        "## Open positions right now",
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

    lines += ["", "## Wins this week"]
    lines += [f"- {t['sym']}: {t['pnl_pct']:+.2%} (${t['pnl_usd']:+.2f}) via {t['reason']}"
              for t in sorted(wins, key=lambda t: -t["pnl_usd"])] or ["_none_"]
    lines += ["", "## Losses this week"]
    lines += [f"- {t['sym']}: {t['pnl_pct']:+.2%} (${t['pnl_usd']:+.2f}) via {t['reason']}"
              for t in sorted(losses, key=lambda t: t["pnl_usd"])] or ["_none_"]
    lines += ["", "## What the bot learned",
              "See `learnings.md` for the day-by-day reflections and parameter changes.",
              "Current parameters (`params.json`):"]
    lines.append("```json")
    lines.append(json.dumps(load_json(PARAMS_FILE, DEFAULT_PARAMS), indent=2))
    lines.append("```")

    path = REPORTS_DIR / f"WEEKLY-{today}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"weekly summary -> {path.name}")


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

    mode = os.environ.get("MODE", "auto").lower()  # auto | premarket | weekly

    n = ny_now()
    print(f"NY time: {n:%Y-%m-%d %H:%M} ET | open={market_open_now()} | mode={mode}")

    # --- always sample prices (cheap, respects 1 req/sec) ---
    prices = {}
    for s in WATCHLIST:
        prices[s] = get_price(s)
        time.sleep(1.1)
    hist = append_history(hist, prices)
    save_json(HIST_FILE, hist)

    # --- weekly summary mode ---
    if mode == "weekly" or (n.weekday() == 5 and mode == "auto"):
        write_weekly_summary(state, prices, n)
        save_json(STATE_FILE, state)
        if mode == "weekly":
            return

    # --- pre-market research pass ---
    if mode == "premarket" or (n.weekday() < 5 and not market_open_now() and n.hour < 9):
        write_premarket(state, params, prices, n)
        save_json(STATE_FILE, state)
        return

    if not market_open_now():
        print("Market closed. Prices recorded, no trades.")
        return

    state["run_count"] += 1
    actions = []

    # --- also fetch prices for any held names not in the current watchlist ---
    held_extras = [s for s in state["positions"] if s not in prices]
    for s in held_extras:
        prices[s] = get_price(s)
        time.sleep(1.1)
    if held_extras:
        hist = append_history(hist, {k: prices[k] for k in held_extras})
        save_json(HIST_FILE, hist)

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

    # --- refresh news for held names + watchlist ---
    news_fresh = refresh_news(state,
        list(dict.fromkeys(list(state["positions"].keys()) + WATCHLIST)))
    for sym, info in news_fresh.items():
        if info["worst"] and info["score"] < 0:
            actions.append(f"NEWS {sym} score={info['score']} :: {info['worst'][:80]}")

    # --- manage open positions (exits) ---
    for sym in list(state["positions"].keys()):
        pos = state["positions"][sym]
        px = prices.get(sym)
        if px is None:
            continue
        pnl_pct = (px - pos["entry"]) / pos["entry"]
        mom = momentum(hist, sym, params["momentum_lookback"])
        news = news_fresh.get(sym, {})
        reason = None
        if pnl_pct <= params["stop_loss"]:
            reason = f"STOP {pnl_pct:+.2%}"
        elif pnl_pct >= params["take_profit"]:
            reason = f"TAKE-PROFIT {pnl_pct:+.2%}"
        elif news.get("score", 0) <= -2 and news.get("new_count", 0) > 0:
            reason = f"NEWS-RISK {news['score']} :: {(news.get('worst') or '')[:60]}"
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
        news = news_fresh.get(sym, {})
        if news.get("score", 0) <= -2:
            actions.append(f"SKIP {sym}: news score {news.get('score')}")
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
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    prev = LEARN_FILE.read_text(encoding="utf-8") if LEARN_FILE.exists() else "# Learning journal\n\n"
    LEARN_FILE.write_text(prev + "\n".join(entry) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
