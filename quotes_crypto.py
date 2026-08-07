#!/usr/bin/env python3
"""
Intraday CRYPTO data + technical analysis — the "scalper" data layer.

This is the Xynth-style data step done programmatically: instead of uploading a
TradingView screenshot, we PULL the raw 5-minute BTCUSD (and alt) series for the
last few hours and compute the same indicators a scalper reads off the chart:

  * RSI(14)                — momentum / overbought-oversold
  * Bollinger Bands(20, 2) — volatility envelope + %B (where price sits in it)
  * EMA(9) vs EMA(21)      — short-term trend direction
  * Volume ratio           — current bar vs its 20-bar average (confirmation)
  * Support / Resistance   — recent swing low / high over the analysis window

Runs on the GitHub Actions runner (can reach Yahoo Finance). Writes:
  - quotes_crypto.json : {symbol: {price + indicators}} with a UTC timestamp
  - quotes_crypto.md   : human-readable technical snapshot

Symbols are stored BARE ("BTC") to match the rest of the pipeline. Yahoo is
queried with its "BTC-USD" convention. All indicators are pure-Python (no numpy),
so nothing extra needs installing on the runner.
"""

import datetime as dt
import json
import sys
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parent
QUOTES_JSON = ROOT / "quotes_crypto.json"
QUOTES_MD = ROOT / "quotes_crypto.md"

# Liquid majors — scalping needs tight spreads / real volume.
WATCHLIST = ["ETH"]   # focused: ETH only (no diversification)

INTERVAL = "5m"
RANGE = "1d"          # a full day of 5m bars; we analyse the most recent window
ANALYSIS_BARS = 48    # ~4h of 5m bars for support/resistance + trend
RSI_PERIOD = 14
BB_PERIOD = 20
BB_K = 2.0

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


# ------------------------------- indicators --------------------------------
def rsi(closes, period=RSI_PERIOD):
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    seed = deltas[:period]
    up = sum(d for d in seed if d > 0) / period
    down = -sum(d for d in seed if d < 0) / period
    for d in deltas[period:]:
        up = (up * (period - 1) + (d if d > 0 else 0.0)) / period
        down = (down * (period - 1) + (-d if d < 0 else 0.0)) / period
    if down == 0:
        return 100.0
    rs = up / down
    return round(100 - 100 / (1 + rs), 1)


def bollinger(closes, period=BB_PERIOD, k=BB_K):
    if len(closes) < period:
        return None
    window = closes[-period:]
    mid = sum(window) / period
    var = sum((c - mid) ** 2 for c in window) / period
    sd = var ** 0.5
    return mid, mid + k * sd, mid - k * sd, sd


def ema(vals, period):
    if not vals:
        return None
    k = 2 / (period + 1)
    e = vals[0]
    for v in vals[1:]:
        e = v * k + e * (1 - k)
    return e


def pct_b(price, upper, lower):
    if upper is None or lower is None or upper == lower:
        return None
    return round((price - lower) / (upper - lower), 3)


def analyze(bare: str) -> dict:
    """Fetch 5m bars for one symbol and return price + technical indicators."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol(bare)}"
           f"?range={RANGE}&interval={INTERVAL}")
    req = urlrequest.Request(url, headers={
        "User-Agent": BROWSER_UA,
        "Accept": "application/json",
    })
    with urlrequest.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    result = payload["chart"]["result"][0]
    meta = result.get("meta", {})
    q = result["indicators"]["quote"][0]

    # Aligned OHLCV, dropping bars with a null close (gaps).
    bars = []
    for o, h, l, c, v in zip(q.get("open", []), q.get("high", []),
                             q.get("low", []), q.get("close", []),
                             q.get("volume", [])):
        if c is None:
            continue
        bars.append((o, h, l, c, v or 0))

    closes = [b[3] for b in bars]
    highs = [b[1] for b in bars if b[1] is not None]
    lows = [b[2] for b in bars if b[2] is not None]
    vols = [b[4] for b in bars]

    last = meta.get("regularMarketPrice")
    if last is None and closes:
        last = closes[-1]
    prev = meta.get("chartPreviousClose") or meta.get("previousClose")

    out = {
        "symbol": bare,
        "last": last,
        "prev_close": prev,
        "change_pct": _pct(last, prev),        # day change — used by the regime guard
        "chg_1h_pct": _pct(last, closes[-13]) if len(closes) >= 13 else None,
        "bars_5m": len(closes),
        # daily-momentum fields intentionally null: this is an intraday book, so
        # the engine's multi-day no-chase guard is skipped (chase is enforced by
        # RSI/%B in the signal generator instead).
        "chg_3d_pct": None,
        "chg_5d_pct": None,
    }
    if not closes:
        return out

    win_h = highs[-ANALYSIS_BARS:] or highs
    win_l = lows[-ANALYSIS_BARS:] or lows
    support = round(min(win_l), 4) if win_l else None
    resistance = round(max(win_h), 4) if win_h else None

    bb = bollinger(closes)
    e9 = ema(closes[-40:], 9)
    e21 = ema(closes[-60:], 21)
    trend = None
    if e9 is not None and e21 is not None:
        if e9 > e21 * 1.0005:
            trend = "up"
        elif e9 < e21 * 0.9995:
            trend = "down"
        else:
            trend = "flat"

    vol_last = vols[-1] if vols else None
    vol_avg = (sum(vols[-20:]) / len(vols[-20:])) if len(vols) >= 1 else None
    vol_ratio = round(vol_last / vol_avg, 2) if (vol_last and vol_avg) else None

    out.update({
        "rsi": rsi(closes),
        "support": support,
        "resistance": resistance,
        "ema9": round(e9, 4) if e9 is not None else None,
        "ema21": round(e21, 4) if e21 is not None else None,
        "trend": trend,
        "vol_last": vol_last,
        "vol_avg": round(vol_avg, 2) if vol_avg else None,
        "vol_ratio": vol_ratio,
    })
    if bb:
        mid, upper, lower, sd = bb
        out.update({
            "sma20": round(mid, 4),
            "bb_upper": round(upper, 4),
            "bb_lower": round(lower, 4),
            "pct_b": pct_b(last, upper, lower),
        })
    return out


def main() -> int:
    now = dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    quotes = {}
    errors = {}
    for sym in WATCHLIST:
        try:
            quotes[sym] = analyze(sym)
        except Exception as e:
            errors[sym] = f"{type(e).__name__}: {e}"
            print(f"{sym}: FAILED {e}", file=sys.stderr)

    out = {"fetched_at": now, "interval": INTERVAL, "quotes": quotes, "errors": errors}
    QUOTES_JSON.write_text(json.dumps(out, indent=2))

    lines = [
        f"# Crypto Technicals ({INTERVAL}) — {now}",
        "",
        "| Symbol | Last | Day% | RSI | %B | Trend | Vol× | Support | Resist |",
        "|--------|------|------|-----|----|-------|------|---------|--------|",
    ]
    for sym in WATCHLIST:
        q = quotes.get(sym)
        if not q or q.get("last") is None:
            lines.append(f"| {sym} | n/a | | | | | | | |")
            continue

        def g(v, fmt="{:+.2f}%"):
            return fmt.format(v) if v is not None else "n/a"

        lines.append(
            f"| {sym} | {q['last']:,.2f} | {g(q.get('change_pct'))} | "
            f"{g(q.get('rsi'), '{:.0f}')} | {g(q.get('pct_b'), '{:.2f}')} | "
            f"{q.get('trend') or 'n/a'} | {g(q.get('vol_ratio'), '{:.2f}')} | "
            f"{g(q.get('support'), '{:,.2f}')} | {g(q.get('resistance'), '{:,.2f}')} |"
        )
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- {s}: {e}" for s, e in errors.items()]
    QUOTES_MD.write_text("\n".join(lines) + "\n")

    print(f"Wrote {len(quotes)} crypto technicals at {now}")
    for sym in WATCHLIST:
        q = quotes.get(sym, {})
        if q.get("last") is not None:
            print(f"  {sym}: ${q['last']:,.2f} RSI {q.get('rsi')} %B {q.get('pct_b')} "
                  f"trend {q.get('trend')} vol× {q.get('vol_ratio')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
