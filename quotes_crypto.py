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
import os
import sys
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parent
QUOTES_JSON = ROOT / "quotes_crypto.json"
QUOTES_MD = ROOT / "quotes_crypto.md"

# Liquid majors — scalping needs tight spreads / real volume.
WATCHLIST = ["BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK"]

# Timeframe is env-driven. The 60-day backtest was clear that 5m is mostly
# noise: on 1h bars the same logic lost 44% less and win rate went 10% -> 45%.
# Yahoo serves 1h directly, so this asks for the bars it wants rather than
# aggregating 5m — fewer requests and a longer usable history.
INTERVAL = os.environ.get("CRYPTO_INTERVAL", "5m")
RANGE = os.environ.get("CRYPTO_RANGE", "1d")
ANALYSIS_BARS = 48    # bars used for support/resistance + trend


def _interval_minutes(iv: str) -> int:
    """Minutes per bar, parsed from the Yahoo interval string ("5m", "1h", "1d")."""
    iv = (iv or "5m").strip().lower()
    try:
        if iv.endswith("m"):
            return max(1, int(iv[:-1]))
        if iv.endswith("h"):
            return max(1, int(iv[:-1])) * 60
        if iv.endswith("d"):
            return max(1, int(iv[:-1])) * 60 * 24
    except ValueError:
        pass
    return 5


BAR_MIN = _interval_minutes(INTERVAL)
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


def _back(minutes: int) -> int:
    """How many bars back `minutes` is, at the configured interval (min 1)."""
    return max(1, round(minutes / BAR_MIN))


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
        # Look-backs are expressed in MINUTES and converted to bars, not
        # hard-coded bar counts. The old closes[-13] meant "65 minutes ago" only
        # while bars were 5m; on 1h bars it silently became 13 HOURS ago, and the
        # crash guard keys off chg_1h_pct to detect a fast drop — it would have
        # been comparing against the wrong point entirely.
        "chg_1h_pct": _pct(last, closes[-_back(60)]) if len(closes) > _back(60) else None,
        "chg_15m_pct": (_pct(last, closes[-_back(15)])
                        if len(closes) > _back(15) else None),
        "bars": len(closes),
        "bar_minutes": BAR_MIN,
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

    # Volume ratio must come from the last COMPLETED bar, not the one still
    # forming. The in-progress bar has accumulated only part of its volume — on
    # 5m that was a small distortion, but on 1h bars it reads 0 for most of the
    # hour, which made vol_ratio None and permanently blocked every momentum
    # entry (the setup requires vol_ratio >= 1.0). Comparing a partial bar to an
    # average of full bars is not a like-for-like ratio in any case.
    done = vols[:-1] if len(vols) > 1 else vols
    vol_last = done[-1] if done else None
    ref = done[-20:] if done else []
    vol_avg = (sum(ref) / len(ref)) if ref else None
    vol_ratio = round(vol_last / vol_avg, 2) if (vol_last and vol_avg) else None

    # Crash telemetry: how far price has fallen from the highest high in the
    # analysis window. A flash-crash shows up here long before the day-change
    # figure catches up, so the risk-off guard keys off this.
    win_high = max(win_h) if win_h else None
    drop_from_high = None
    if win_high and last:
        drop_from_high = round((last - win_high) / win_high * 100, 2)

    out.update({
        "rsi": rsi(closes),
        "window_high": round(win_high, 4) if win_high else None,
        "drop_from_high_pct": drop_from_high,
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
