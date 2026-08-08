#!/usr/bin/env python3
"""Daily OHLCV history fetcher for the swing book -> swing_history.json.

Why a separate fetcher: quotes.py only stores a snapshot (last / 3d / 5d), but a
swing screen needs *bars* — ATR(14), SMA 20/50/200, ADX, MACD, relative strength
vs SPY. Those need ~1 year of daily candles, so this pulls them once per run and
commits them; swing_analysis.py then works purely off the committed file.

Runs on the GitHub Actions runner (which can reach Yahoo). The Claude sandbox's
egress proxy blocks Yahoo, exactly like quotes.py — so never call this from the
sandbox and expect data; run the analysis step against the committed JSON instead.

Universe: liquid, higher-beta US names, i.e. where a 4-5% ATR actually happens.
Mega-caps are kept in as a control group (they usually screen OUT on ATR — that is
the screen doing its job, not a bug).
"""

import datetime as dt
import json
import sys
import time
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parent
OUT_JSON = ROOT / "swing_history.json"

BENCHMARK = "SPY"

UNIVERSE = [
    BENCHMARK, "QQQ", "IWM",
    # semis / AI hardware
    "NVDA", "AMD", "MU", "AVGO", "MRVL", "ARM", "SMCI", "INTC", "ON", "TSM",
    # mega / large tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NFLX", "TSLA",
    # software / high beta
    "PLTR", "SNOW", "NET", "CRWD", "DDOG", "APP", "U", "SHOP", "ROKU", "DKNG",
    # crypto proxies
    "COIN", "MSTR", "MARA", "RIOT", "HOOD",
    # fintech / consumer
    "SOFI", "AFRM", "PYPL", "UBER", "ABNB", "CVNA", "CELH",
    # EV / mobility
    "RIVN", "LCID", "NIO", "XPEV",
    # China ADR
    "BABA", "PDD",
    # energy / power / nuclear
    "XOM", "CVX", "OXY", "XLE", "FSLR", "ENPH", "VST", "OKLO", "SMR",
    # speculative / retail favourites
    "IONQ", "RGTI", "GME", "PLUG",
]

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0 Safari/537.36"
)

MAX_BARS = 280          # enough for SMA200 + a little slack, keeps the file small
REQUEST_PAUSE = 0.35    # be polite to Yahoo; ~60 symbols => ~20s


def fetch_bars(symbol: str) -> dict:
    """Return {'dates': [...], 'o','h','l','c','v': [...]} of daily bars."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           "?range=1y&interval=1d")
    req = urlrequest.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "application/json",
    })
    with urlrequest.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    stamps = result.get("timestamp") or []
    q = result["indicators"]["quote"][0]

    dates, o, h, l, c, v = [], [], [], [], [], []
    for i, ts in enumerate(stamps):
        bar = (q["open"][i], q["high"][i], q["low"][i], q["close"][i], q["volume"][i])
        if any(x is None for x in bar):
            continue  # a half-formed bar poisons every indicator downstream
        dates.append(dt.datetime.utcfromtimestamp(ts).date().isoformat())
        o.append(round(bar[0], 4))
        h.append(round(bar[1], 4))
        l.append(round(bar[2], 4))
        c.append(round(bar[3], 4))
        v.append(int(bar[4]))

    if len(c) < 60:
        raise ValueError(f"only {len(c)} usable bars")

    return {
        "dates": dates[-MAX_BARS:],
        "o": o[-MAX_BARS:], "h": h[-MAX_BARS:], "l": l[-MAX_BARS:],
        "c": c[-MAX_BARS:], "v": v[-MAX_BARS:],
    }


def main() -> int:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    bars, errors = {}, {}
    for sym in UNIVERSE:
        try:
            bars[sym] = fetch_bars(sym)
            print(f"  {sym}: {len(bars[sym]['c'])} bars, last {bars[sym]['c'][-1]}")
        except Exception as e:
            errors[sym] = f"{type(e).__name__}: {e}"
            print(f"{sym}: FAILED {e}", file=sys.stderr)
        time.sleep(REQUEST_PAUSE)

    if not bars:
        print("no bars fetched — leaving swing_history.json untouched", file=sys.stderr)
        return 1

    OUT_JSON.write_text(json.dumps({
        "fetched_at": now,
        "benchmark": BENCHMARK,
        "bars": bars,
        "errors": errors,
    }, separators=(",", ":")))
    print(f"Wrote {OUT_JSON.name}: {len(bars)} symbols, {len(errors)} error(s) at {now}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
