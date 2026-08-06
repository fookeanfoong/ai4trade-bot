#!/usr/bin/env python3
"""
Real-time CRYPTO quote fetcher — the 24/7 twin of quotes.py.

Runs on the GitHub Actions runner (can reach Yahoo Finance). Writes:
  - quotes_crypto.json : machine-readable {symbol: {...}} with a UTC timestamp
  - quotes_crypto.md   : human-readable table

Symbols are stored BARE ("BTC") to match the rest of the pipeline
(signals_crypto.json, live_trader.py, broker_alpaca_crypto.py). Yahoo is queried
with its "BTC-USD" convention. Crypto trades 7 days a week, so the 3d/5d change
is a literal calendar-day extension — same no-chase purpose as the stock book.
"""

import datetime as dt
import json
import sys
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parent
QUOTES_JSON = ROOT / "quotes_crypto.json"
QUOTES_MD = ROOT / "quotes_crypto.md"

# Bare symbols. BTC is both a target AND the regime benchmark (REGIME_SYMBOLS=BTC).
WATCHLIST = [
    "BTC",   # regime benchmark + primary target
    "ETH",
    "SOL",
    "XRP",
    "DOGE",
    "LTC",
    "LINK",
    "AVAX",
]

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)


def yahoo_symbol(bare: str) -> str:
    return f"{bare}-USD"


def _pct(now_val, then_val):
    if now_val is None or then_val in (None, 0):
        return None
    return round((now_val - then_val) / then_val * 100, 2)


def fetch_quote(bare: str) -> dict:
    """Return latest quote + multi-day change for one crypto symbol from Yahoo."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(bare)}"
           "?range=1mo&interval=1d")
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

    closes = [c for c in result["indicators"]["quote"][0].get("close", []) if c is not None]
    ref = last if last is not None else (closes[-1] if closes else None)
    chg_3d = _pct(ref, closes[-4]) if len(closes) >= 4 else None
    chg_5d = _pct(ref, closes[-6]) if len(closes) >= 6 else None

    return {
        "symbol": bare,
        "last": last,
        "prev_close": prev,
        "day_high": day_high,
        "day_low": day_low,
        "change_pct": _pct(last, prev),
        "chg_3d_pct": chg_3d,
        "chg_5d_pct": chg_5d,
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
        f"# Live Crypto Quotes — {now}",
        "",
        "| Symbol | Last | Chg% | 3d% | 5d% | Day Low | Day High | Volume |",
        "|--------|------|------|-----|-----|---------|----------|--------|",
    ]
    for sym in WATCHLIST:
        q = quotes.get(sym)
        if not q or q.get("last") is None:
            lines.append(f"| {sym} | n/a | | | | | | |")
            continue

        def f(v, suffix="%"):
            return f"{v:+.2f}{suffix}" if v is not None else "n/a"

        lines.append(
            f"| {sym} | {q['last']:,.2f} | {f(q['change_pct'])} | "
            f"{f(q['chg_3d_pct'])} | {f(q['chg_5d_pct'])} | "
            f"{(q['day_low'] or 0):,.2f} | {(q['day_high'] or 0):,.2f} | "
            f"{(q['volume'] or 0):,} |"
        )
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- {s}: {e}" for s, e in errors.items()]
    QUOTES_MD.write_text("\n".join(lines) + "\n")

    print(f"Wrote {len(quotes)} crypto quotes at {now}")
    for sym in WATCHLIST:
        q = quotes.get(sym, {})
        if q.get("last") is not None:
            print(f"  {sym}: ${q['last']:,.2f} ({q['change_pct']:+.2f}%, 3d {q['chg_3d_pct']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
