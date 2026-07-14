#!/usr/bin/env python3
"""
Real-time watchlist quote fetcher.

Runs on the GitHub Actions runner (can reach Yahoo Finance). Writes:
  - quotes.json : machine-readable {symbol: {...}} with a UTC timestamp
  - quotes.md   : human-readable table

Purpose: give an accurate, timestamped price source. The Claude sandbox's
egress proxy blocks Yahoo/Stooq, so prices must be fetched here and committed.
"""

import datetime as dt
import json
import sys
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parent
QUOTES_JSON = ROOT / "quotes.json"
QUOTES_MD = ROOT / "quotes.md"

WATCHLIST = [
    "SPY", "QQQ",              # broad market
    "NVDA", "AMD", "TSLA",     # tech / chips
    "XOM", "OXY", "CVX",       # energy majors (oil catalyst)
    "VLO", "MPC", "PSX",       # refiners (crack spread + oil)
    "XLE",                     # energy sector ETF (signal target)
    "JPM",                     # financials
    "USO",                     # oil ETF proxy
]

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)


def fetch_quote(symbol: str) -> dict:
    """Return latest quote for one symbol from Yahoo chart JSON."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           "?range=1d&interval=1m")
    req = urlrequest.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "application/json",
    })
    with urlrequest.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    meta = result.get("meta", {})
    last = meta.get("regularMarketPrice")
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")
    day_high = meta.get("regularMarketDayHigh")
    day_low = meta.get("regularMarketDayLow")
    vol = meta.get("regularMarketVolume")
    chg_pct = None
    if last is not None and prev:
        chg_pct = round((last - prev) / prev * 100, 2)
    return {
        "symbol": symbol,
        "last": last,
        "prev_close": prev,
        "day_high": day_high,
        "day_low": day_low,
        "change_pct": chg_pct,
        "volume": vol,
        "market_time": meta.get("regularMarketTime"),
    }


def main() -> int:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    quotes = {}
    errors = {}
    for sym in WATCHLIST:
        try:
            quotes[sym] = fetch_quote(sym)
        except Exception as e:
            errors[sym] = f"{type(e).__name__}: {e}"
            print(f"{sym}: FAILED {e}", file=sys.stderr)

    out = {"fetched_at": now, "quotes": quotes, "errors": errors}
    QUOTES_JSON.write_text(json.dumps(out, indent=2))

    lines = [
        f"# Live Quotes — {now}",
        "",
        "| Symbol | Last | Chg% | Day Low | Day High | Prev Close | Volume |",
        "|--------|------|------|---------|----------|------------|--------|",
    ]
    for sym in WATCHLIST:
        q = quotes.get(sym)
        if not q or q.get("last") is None:
            lines.append(f"| {sym} | n/a | | | | | |")
            continue
        lines.append(
            f"| {sym} | {q['last']:.2f} | {q['change_pct']:+.2f}% | "
            f"{(q['day_low'] or 0):.2f} | {(q['day_high'] or 0):.2f} | "
            f"{(q['prev_close'] or 0):.2f} | {(q['volume'] or 0):,} |"
        )
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- {s}: {e}" for s, e in errors.items()]
    QUOTES_MD.write_text("\n".join(lines) + "\n")

    print(f"Wrote {len(quotes)} quotes at {now}")
    for sym in WATCHLIST:
        q = quotes.get(sym, {})
        if q.get("last") is not None:
            print(f"  {sym}: ${q['last']:.2f} ({q['change_pct']:+.2f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
