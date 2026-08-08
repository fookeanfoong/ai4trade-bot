#!/usr/bin/env python3
"""Swing-trade research pipeline — 4 steps, encoded as code instead of a chat prompt.

  Step 1  Mandate      account size, risk per trade, hold horizon, long-only.
  Step 2  Screen       medium volatility (ATR% band), real liquidity, EARLY trend
                       strength -> top 5 candidates.
  Step 3  Compare      full technical scorecard on those 5 -> pick the strongest
                       chart for a multi-day / multi-week swing.
  Step 4  Setups       3 DISTINCT setups on the winner (breakout / MA-pullback /
                       Fibonacci retracement), each with entry, stop, target,
                       expected duration, share count, $ profit, $ loss and R:R.

Reads swing_history.json (written by swing_history.py on the Actions runner —
the sandbox cannot reach Yahoo). Writes swing_setups.json + a markdown report in
reports/swing/YYYY-MM-DD.md.

Long-only by design: the screen looks for *early trend strength*, and shorting a
$1000 cash account is not the trade this book is for.

⚠️ Algorithmic output on public price data. Research/education only — not advice,
not a profit promise. Paper-trade it before risking a dollar.

Usage:
    python swing_analysis.py                 # full run off swing_history.json
    python swing_analysis.py --selftest      # indicator maths on synthetic bars
"""

import json
import math
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "swing_history.json"
OUT_JSON = ROOT / "swing_setups.json"
REPORT_DIR = ROOT / "reports" / "swing"


def _env_f(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def _env_i(name, default):
    try:
        return int(float(os.environ.get(name, default)))
    except (TypeError, ValueError):
        return int(default)


# ---- Step 1: the mandate -----------------------------------------------------
ACCOUNT_USD = _env_f("SWING_ACCOUNT_USD", 1000.0)
RISK_PCT = _env_f("SWING_RISK_PCT", 2.0)        # % of account risked per trade
MAX_POSITION_PCT = _env_f("SWING_MAX_POS_PCT", 100.0)   # no margin by default
FRACTIONAL = os.environ.get("SWING_FRACTIONAL", "").lower() in ("1", "yes", "true")

# ---- Step 2: screen thresholds ----------------------------------------------
ATR_PCT_MIN = _env_f("SWING_ATR_MIN", 4.0)      # "medium volatility" band
ATR_PCT_MAX = _env_f("SWING_ATR_MAX", 5.0)
ATR_RELAX = _env_f("SWING_ATR_RELAX", 1.0)      # widening used only to fill empty slots
MIN_DOLLAR_VOL = _env_f("SWING_MIN_DOLLAR_VOL", 50e6)   # 20d average $ traded
MIN_PRICE = _env_f("SWING_MIN_PRICE", 5.0)
MIN_ADX = _env_f("SWING_MIN_ADX", 20.0)         # trend exists at all
RSI_MIN, RSI_MAX = _env_f("SWING_RSI_MIN", 50.0), _env_f("SWING_RSI_MAX", 72.0)
MAX_ATR_ABOVE_SMA20 = _env_f("SWING_MAX_EXT_ATR", 2.5)  # no-chase: extension cap
TOP_N = _env_i("SWING_TOP_N", 5)

EXCLUDE_AS_CANDIDATE = {"SPY", "QQQ", "IWM"}    # benchmarks, not trade candidates

DISCLAIMER = ("算法根据公开日线数据自动生成的波段研究,仅供学习/研究参考,"
              "不构成投资建议或收益承诺。市场有风险,盈亏自负。")


# =============================================================================
# Indicator primitives — pure Python, no numpy (the Actions runner installs
# nothing extra for this step). All return lists aligned to the input, with
# None for the warm-up bars so index -1 is always "today".
# =============================================================================

def sma(vals, n):
    out, run = [], 0.0
    for i, v in enumerate(vals):
        run += v
        if i >= n:
            run -= vals[i - n]
        out.append(run / n if i >= n - 1 else None)
    return out


def ema(vals, n):
    k = 2.0 / (n + 1)
    out, prev = [], None
    for i, v in enumerate(vals):
        if i < n - 1:
            out.append(None)
        elif i == n - 1:
            prev = sum(vals[:n]) / n
            out.append(prev)
        else:
            prev = v * k + prev * (1 - k)
            out.append(prev)
    return out


def _wilder(vals, n, seed_from):
    """Wilder smoothing: seed with a simple average, then prev*(n-1)/n + cur/n."""
    out = [None] * len(vals)
    if len(vals) < seed_from + n:
        return out
    prev = sum(vals[seed_from:seed_from + n]) / n
    out[seed_from + n - 1] = prev
    for i in range(seed_from + n, len(vals)):
        prev = (prev * (n - 1) + vals[i]) / n
        out[i] = prev
    return out


def rsi(closes, n=14):
    gains = [0.0] * len(closes)
    losses = [0.0] * len(closes)
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains[i] = max(d, 0.0)
        losses[i] = max(-d, 0.0)
    ag = _wilder(gains, n, 1)
    al = _wilder(losses, n, 1)
    out = []
    for g, l in zip(ag, al):
        if g is None or l is None:
            out.append(None)
        elif l == 0:
            # Both zero = a flat tape, not a maximal uptrend; RSI is undefined
            # there, so call it neutral rather than screaming overbought.
            out.append(100.0 if g > 0 else 50.0)
        else:
            out.append(100.0 - 100.0 / (1.0 + g / l))
    return out


def true_range(h, l, c):
    tr = [h[0] - l[0]] if h else []
    for i in range(1, len(h)):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return tr


def atr(h, l, c, n=14):
    return _wilder(true_range(h, l, c), n, 1)


def macd(closes, fast=12, slow=26, sig=9):
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [(a - b) if (a is not None and b is not None) else None for a, b in zip(ef, es)]
    seed = next((i for i, v in enumerate(line) if v is not None), len(line))
    dense = line[seed:]
    sline = ema(dense, sig) if len(dense) >= sig else [None] * len(dense)
    signal = [None] * seed + sline
    hist = [(a - b) if (a is not None and b is not None) else None
            for a, b in zip(line, signal)]
    return line, signal, hist


def adx(h, l, c, n=14):
    """Wilder's ADX. Returns (adx, +DI, -DI)."""
    plus_dm, minus_dm = [0.0], [0.0]
    for i in range(1, len(h)):
        up, down = h[i] - h[i - 1], l[i - 1] - l[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
    tr = true_range(h, l, c)
    str_ = _wilder(tr, n, 1)
    spdm, smdm = _wilder(plus_dm, n, 1), _wilder(minus_dm, n, 1)

    pdi = [None] * len(h)
    mdi = [None] * len(h)
    dx = [0.0] * len(h)
    first_dx = None
    for i in range(len(h)):
        if str_[i] in (None, 0) or spdm[i] is None or smdm[i] is None:
            continue
        pdi[i] = 100.0 * spdm[i] / str_[i]
        mdi[i] = 100.0 * smdm[i] / str_[i]
        denom = pdi[i] + mdi[i]
        dx[i] = 100.0 * abs(pdi[i] - mdi[i]) / denom if denom else 0.0
        if first_dx is None:
            first_dx = i
    adx_line = [None] * len(h)
    if first_dx is not None and len(h) >= first_dx + n:
        smoothed = _wilder(dx, n, first_dx)
        adx_line = smoothed
    return adx_line, pdi, mdi


def pct(a, b):
    """Percent change from b to a."""
    if a is None or not b:
        return None
    return (a - b) / b * 100.0


# =============================================================================
# Step 2/3: features + screen + score
# =============================================================================

def features(sym, bars, bench_closes):
    c, h, l, v = bars["c"], bars["h"], bars["l"], bars["v"]
    if len(c) < 70:   # 60d lookbacks read c[-61]; leave slack for the warm-up
        return None

    a = atr(h, l, c, 14)
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    r = rsi(c, 14)
    _, _, hist = macd(c)
    adx_line, pdi, mdi = adx(h, l, c, 14)

    px = c[-1]
    atr_abs = a[-1]
    if atr_abs is None or not px:
        return None

    v20 = sum(v[-20:]) / 20.0
    v5 = sum(v[-5:]) / 5.0
    # accumulation: volume traded on up-closes vs down-closes over 20 sessions
    up_v = sum(v[i] for i in range(-20, 0) if c[i] >= c[i - 1])
    dn_v = sum(v[i] for i in range(-20, 0) if c[i] < c[i - 1]) or 1.0

    hi20, lo20 = max(h[-20:]), min(l[-20:])
    hi60, lo60 = max(h[-60:]), min(l[-60:])
    lo10 = min(l[-10:])

    f = {
        "symbol": sym,
        "price": round(px, 4),
        "date": bars["dates"][-1],
        "atr": round(atr_abs, 4),
        "atr_pct": round(atr_abs / px * 100.0, 2),
        "sma20": round(s20[-1], 4) if s20[-1] else None,
        "sma50": round(s50[-1], 4) if s50[-1] else None,
        "sma200": round(s200[-1], 4) if s200[-1] else None,
        "sma20_slope_pct": round(pct(s20[-1], s20[-6]), 2) if s20[-1] and s20[-6] else None,
        "rsi": round(r[-1], 1) if r[-1] else None,
        "adx": round(adx_line[-1], 1) if adx_line[-1] else None,
        "adx_5d_ago": round(adx_line[-6], 1) if len(adx_line) > 6 and adx_line[-6] else None,
        "di_plus": round(pdi[-1], 1) if pdi[-1] else None,
        "di_minus": round(mdi[-1], 1) if mdi[-1] else None,
        "macd_hist": round(hist[-1], 4) if hist[-1] is not None else None,
        "macd_hist_prev": round(hist[-4], 4) if len(hist) > 4 and hist[-4] is not None else None,
        "avg_dollar_vol_20d": round(v20 * px),
        "vol_ratio_5_20": round(v5 / v20, 2) if v20 else None,
        "accum_ratio": round(up_v / dn_v, 2),
        "chg_5d_pct": round(pct(px, c[-6]), 2),
        "chg_20d_pct": round(pct(px, c[-21]), 2),
        "hi20": round(hi20, 4), "lo20": round(lo20, 4), "lo10": round(lo10, 4),
        "hi60": round(hi60, 4), "lo60": round(lo60, 4),
        "pct_from_hi60": round((px - hi60) / hi60 * 100.0, 2),
        "range10_in_atr": round((max(h[-10:]) - min(l[-10:])) / atr_abs, 2),
    }
    f["ext_atr_from_sma20"] = (round((px - f["sma20"]) / atr_abs, 2)
                               if f["sma20"] else None)

    # relative strength vs the benchmark, 20d and 60d
    if bench_closes and len(bench_closes) > 61:
        f["rs_20d"] = round(pct(px, c[-21]) - pct(bench_closes[-1], bench_closes[-21]), 2)
        f["rs_60d"] = round(pct(px, c[-61]) - pct(bench_closes[-1], bench_closes[-61]), 2)
    else:
        f["rs_20d"] = f["rs_60d"] = None

    # higher highs / higher lows over the last two 20-bar windows
    f["higher_highs"] = max(h[-20:]) > max(h[-40:-20])
    f["higher_lows"] = min(l[-20:]) > min(l[-40:-20])
    return f


def screen(f, atr_min, atr_max):
    """Return (passed, [reasons it failed])."""
    fails = []
    if f["price"] < MIN_PRICE:
        fails.append(f"price ${f['price']:.2f} < ${MIN_PRICE:.0f}")
    if not (atr_min < f["atr_pct"] < atr_max):
        fails.append(f"ATR {f['atr_pct']:.2f}% outside {atr_min:g}-{atr_max:g}%")
    if f["avg_dollar_vol_20d"] < MIN_DOLLAR_VOL:
        fails.append(f"20d $vol ${f['avg_dollar_vol_20d']/1e6:.0f}M < "
                     f"${MIN_DOLLAR_VOL/1e6:.0f}M")
    if not (f["sma20"] and f["sma50"] and f["price"] > f["sma20"] > f["sma50"]):
        fails.append("not in price > SMA20 > SMA50 stack")
    if not (f["sma20_slope_pct"] and f["sma20_slope_pct"] > 0):
        fails.append("SMA20 not rising")
    if not (f["adx"] and f["adx"] >= MIN_ADX):
        fails.append(f"ADX {f['adx']} < {MIN_ADX:g} (no trend yet)")
    if f["adx_5d_ago"] is not None and f["adx"] is not None and f["adx"] < f["adx_5d_ago"]:
        fails.append("ADX falling (trend maturing, not early)")
    if f["rsi"] is None or not (RSI_MIN <= f["rsi"] <= RSI_MAX):
        fails.append(f"RSI {f['rsi']} outside {RSI_MIN:g}-{RSI_MAX:g}")
    if f["ext_atr_from_sma20"] is not None and f["ext_atr_from_sma20"] > MAX_ATR_ABOVE_SMA20:
        fails.append(f"extended {f['ext_atr_from_sma20']:.1f} ATR above SMA20 (no-chase)")
    if f["rs_20d"] is not None and f["rs_20d"] <= 0:
        fails.append(f"20d relative strength {f['rs_20d']:+.1f}% vs benchmark")
    return (not fails), fails


def score(f):
    """0-100 composite + per-bucket breakdown (this is Step 3's scorecard)."""
    b = {}

    # Trend structure — 25
    t = 0.0
    if f["sma20"] and f["price"] > f["sma20"]:
        t += 8
    if f["sma20"] and f["sma50"] and f["sma20"] > f["sma50"]:
        t += 8
    if f["sma50"] and f["sma200"] and f["sma50"] > f["sma200"]:
        t += 9
    elif f["sma200"] and f["price"] > f["sma200"]:
        t += 4
    b["trend_structure"] = round(t, 1)

    # Momentum — 25
    m = 0.0
    if f["adx"]:
        m += min(max((f["adx"] - 15.0) / 20.0, 0.0), 1.0) * 10   # 15->35 maps 0->10
    if f["adx"] and f["adx_5d_ago"] and f["adx"] > f["adx_5d_ago"]:
        m += 4
    if f["macd_hist"] is not None and f["macd_hist"] > 0:
        m += 4
        if f["macd_hist_prev"] is not None and f["macd_hist"] > f["macd_hist_prev"]:
            m += 3
    if f["rsi"]:
        m += 4 if 55 <= f["rsi"] <= 68 else (2 if 50 <= f["rsi"] <= 72 else 0)
    b["momentum"] = round(m, 1)

    # Volume — 20
    vv = 0.0
    if f["vol_ratio_5_20"]:
        vv += min(max((f["vol_ratio_5_20"] - 0.8) / 0.7, 0.0), 1.0) * 10
    vv += min(max((f["accum_ratio"] - 0.9) / 0.8, 0.0), 1.0) * 10
    b["volume"] = round(vv, 1)

    # Relative strength — 20
    rsc = 0.0
    if f["rs_20d"] is not None:
        rsc += min(max(f["rs_20d"] / 12.0, 0.0), 1.0) * 12
    if f["rs_60d"] is not None:
        rsc += min(max(f["rs_60d"] / 25.0, 0.0), 1.0) * 8
    b["relative_strength"] = round(rsc, 1)

    # Entry quality — 10. Closest to the 20-SMA wins: room to run, tight stop.
    e = 0.0
    if f["ext_atr_from_sma20"] is not None:
        e = min(max((MAX_ATR_ABOVE_SMA20 - f["ext_atr_from_sma20"]) /
                    MAX_ATR_ABOVE_SMA20, 0.0), 1.0) * 10
    b["entry_quality"] = round(e, 1)

    b["total"] = round(sum(b.values()), 1)
    return b


def regime(bench_bars):
    """Broad-market state. The journal's most expensive stock lesson was buying
    good-looking charts into a risk-off tape, so the read goes on the report."""
    if not bench_bars:
        return {"state": "unknown", "note": "no benchmark bars"}
    c, h, l = bench_bars["c"], bench_bars["h"], bench_bars["l"]
    if len(c) < 70:
        return {"state": "unknown", "note": "benchmark history too short"}
    s50, s200 = sma(c, 50), sma(c, 200)
    px = c[-1]
    chg5 = pct(px, c[-6])
    above50 = bool(s50[-1] and px > s50[-1])
    above200 = bool(s200[-1] and px > s200[-1])

    if above50 and above200 and chg5 > -3.0:
        state, note = "risk-on", "benchmark above its 50 and 200-day — full size allowed"
    elif above200 and chg5 > -3.0:
        state, note = ("mixed", "benchmark under its 50-day but above the 200 — "
                                "half size, best setup only")
    else:
        state, note = ("risk-off", "benchmark broken or dropping fast — stand aside "
                                   "or paper-trade the setups until it repairs")
    return {
        "state": state, "note": note,
        "benchmark_price": round(px, 2),
        "benchmark_5d_pct": round(chg5, 2),
        "above_sma50": above50, "above_sma200": above200,
    }


def patterns(f):
    """Plain-language chart read used in the Step 3 write-up."""
    out = []
    if f["higher_highs"] and f["higher_lows"]:
        out.append("higher highs + higher lows (intact uptrend structure)")
    elif f["higher_highs"]:
        out.append("higher highs, but lows not yet rising (uneven)")
    if f["range10_in_atr"] is not None and f["range10_in_atr"] < 3.0:
        out.append(f"10-day range only {f['range10_in_atr']:.1f}×ATR — coiling/flag")
    if f["pct_from_hi60"] > -2.0:
        out.append("within 2% of the 60-day high — breakout zone")
    elif f["pct_from_hi60"] < -12.0:
        out.append(f"{abs(f['pct_from_hi60']):.0f}% below the 60-day high — repair job")
    if f["sma20"] and f["sma50"] and f["sma50"] < f["price"] < f["sma20"]:
        out.append("pulled back under the 20-SMA but holding the 50 — dip zone")
    if f["accum_ratio"] >= 1.3:
        out.append(f"up-volume {f['accum_ratio']:.1f}× down-volume — accumulation")
    elif f["accum_ratio"] <= 0.8:
        out.append(f"down-volume dominates ({f['accum_ratio']:.1f}×) — distribution")
    if f["vol_ratio_5_20"] and f["vol_ratio_5_20"] >= 1.3:
        out.append(f"5d volume {f['vol_ratio_5_20']:.1f}× its 20d average — participation rising")
    if f["macd_hist"] is not None and f["macd_hist"] > 0 and \
            f["macd_hist_prev"] is not None and f["macd_hist"] > f["macd_hist_prev"]:
        out.append("MACD histogram positive and expanding")
    return out or ["no distinctive pattern — trend is the only edge here"]


# =============================================================================
# Step 4: the three setups
# =============================================================================

def _size(entry, stop):
    """Shares from fixed-fractional risk, capped by cash (no margin)."""
    per_share = entry - stop
    if per_share <= 0:
        return 0, 0.0, per_share
    risk_budget = ACCOUNT_USD * RISK_PCT / 100.0
    raw = risk_budget / per_share
    cap = (ACCOUNT_USD * MAX_POSITION_PCT / 100.0) / entry
    shares = min(raw, cap)
    shares = round(shares, 4) if FRACTIONAL else math.floor(shares)
    return shares, risk_budget, per_share


def _duration_days(entry, target, atr_abs, trigger_wait=0):
    """A swing lasts as long as the move needs: ~0.55 ATR of net progress a day."""
    if atr_abs <= 0:
        return "unknown"
    days = math.ceil(abs(target - entry) / (0.55 * atr_abs)) + trigger_wait
    days = max(3, min(days, 25))
    return f"{max(3, days - 2)}-{days + 3} trading days"


def _pack(name, basis, entry, stop, target, f, trigger_wait=0, notes=None):
    if entry <= stop or target <= entry:
        return None
    shares, risk_budget, per_share = _size(entry, stop)
    rr = (target - entry) / per_share
    capped = shares > 0 and shares * entry > ACCOUNT_USD * MAX_POSITION_PCT / 100.0 - 0.01
    out = {
        "name": name,
        "technical_basis": basis,
        "direction": "long",
        "entry": round(entry, 2),
        "stop": round(stop, 2),
        "target": round(target, 2),
        "risk_per_share": round(per_share, 2),
        "reward_per_share": round(target - entry, 2),
        "risk_reward": round(rr, 2),
        "shares": shares,
        "position_value": round(shares * entry, 2),
        "profit_at_target": round((target - entry) * shares, 2),
        "loss_at_stop": round(-per_share * shares, 2),
        "risk_pct_of_account": round(per_share * shares / ACCOUNT_USD * 100.0, 2),
        "stop_pct": round((entry - stop) / entry * 100.0, 2),
        "target_pct": round((target - entry) / entry * 100.0, 2),
        "expected_duration": _duration_days(entry, target, f["atr"], trigger_wait),
        "notes": list(notes or []),
    }
    if shares == 0:
        out["notes"].append(
            f"0 shares: one share risks ${per_share:.2f} > the ${risk_budget:.2f} "
            f"budget. Needs fractional shares (SWING_FRACTIONAL=1) or a bigger account.")
    elif capped:
        out["notes"].append(
            "Size capped by cash, not by risk — actual risk is below the "
            f"{RISK_PCT:g}% budget.")
    if rr < 1.5:
        out["notes"].append(f"R:R {rr:.2f} is below 1.5 — thin edge, skippable.")
    return out


def build_setups(f):
    px, a = f["price"], f["atr"]
    s20, s50 = f["sma20"], f["sma50"]
    setups = []

    # A. Breakout continuation — buy-stop over the 20-day high, measured move.
    entry = max(f["hi20"] * 1.002, px)
    base_low = max(f["lo10"], entry - 2.0 * a)
    stop = min(base_low - 0.1 * a, entry - 0.8 * a)
    measured = f["hi20"] - f["lo20"]
    target = max(entry + measured, entry + 2.0 * (entry - stop))
    setups.append(_pack(
        "A. Breakout continuation",
        f"Buy-stop 0.2% above the 20-day high ${f['hi20']:.2f}; the trade only "
        f"exists if the range actually breaks. Stop under the 10-day base low "
        f"${f['lo10']:.2f}; target is the measured move (range height "
        f"${measured:.2f}) projected off the breakout.",
        entry, stop, target, f, trigger_wait=2,
        notes=["Entry is a STOP order — no break, no trade. Cancel it if price "
               "closes back under the 20-SMA first."]))

    # B. Pullback to the rising 20-SMA — the trend-following buy-the-dip.
    if s20:
        entry_b = s20 if px > s20 else px
        # Below the normal-pullback zone, and below the 50-SMA when that sits
        # just underneath — but never wider than 2.5 ATR, or size collapses.
        stop_b = min(entry_b - 1.5 * a,
                     (s50 - 0.2 * a) if s50 and s50 < entry_b else entry_b - 1.5 * a)
        stop_b = max(stop_b, entry_b - 2.5 * a)
        target_b = max(f["hi20"], entry_b + 2.0 * (entry_b - stop_b))
        setups.append(_pack(
            "B. 20-SMA pullback",
            f"Limit buy at the rising 20-SMA ${s20:.2f} — in a live uptrend that "
            f"average is dynamic support, and buying it beats chasing strength. "
            f"Stop 1.5×ATR below (${1.5*a:.2f}), i.e. below where a normal pullback "
            f"should hold; target the prior swing high ${f['hi20']:.2f}.",
            entry_b, stop_b, target_b, f, trigger_wait=3,
            notes=["Entry is a LIMIT order — if it never pulls back, you never pay. "
                   "Invalid if the 20-SMA rolls over before you get filled."]))

    # C. Fibonacci retracement of the last impulse leg — the deep-value entry.
    leg_lo, leg_hi = f["lo60"], f["hi60"]
    leg = leg_hi - leg_lo
    if leg > 0:
        fib382 = leg_hi - 0.382 * leg
        fib618 = leg_hi - 0.618 * leg
        entry_c = min(fib382, px)          # never pay above the zone
        # Below the 61.8% line = the leg is broken, not retracing. If price has
        # already sunk into/through that line, fall back to an ATR stop so the
        # setup stays coherent instead of inverting.
        stop_c = min(fib618 - 0.5 * a, entry_c - 1.0 * a)
        target_c = leg_hi                  # retest of the impulse high
        setups.append(_pack(
            "C. Fib 38.2% retracement",
            f"Limit buy at the 38.2% retracement (${fib382:.2f}) of the "
            f"${leg_lo:.2f}→${leg_hi:.2f} impulse leg. Stop 0.5×ATR under the "
            f"61.8% line (${fib618:.2f}) — past that the leg is broken, not "
            f"retracing. Target a retest of the leg high ${leg_hi:.2f}.",
            entry_c, stop_c, target_c, f, trigger_wait=4,
            notes=["The widest stop of the three, so the smallest size — this is "
                   "the patient setup, not the active one."]))

    return [s for s in setups if s]


# =============================================================================
# Report
# =============================================================================

def _fmt(v, suffix="", nd=2):
    return "n/a" if v is None else f"{v:.{nd}f}{suffix}"


def render(picked, ranked, winner, setups, meta):
    d = meta["as_of"]
    L = [
        f"# Swing Trade Research — {d}",
        "",
        f"_Data as of {d} (daily bars fetched {meta['fetched_at']}). "
        f"Universe {meta['universe_n']} symbols, benchmark {meta['benchmark']}._",
        "",
        "## Step 1 — Mandate",
        "",
        f"- Account **${ACCOUNT_USD:,.0f}**, risk **{RISK_PCT:g}%** "
        f"(**${ACCOUNT_USD*RISK_PCT/100:,.2f}**) per trade, no margin "
        f"(max position {MAX_POSITION_PCT:g}% of account).",
        "- Hold horizon: several days to a few weeks. Long-only, shares only — "
        "no options, no complex structures.",
        f"- Screen: {ATR_PCT_MIN:g}% < ATR(14) < {ATR_PCT_MAX:g}% of price, "
        f"20d turnover ≥ ${MIN_DOLLAR_VOL/1e6:.0f}M, early trend strength.",
        f"- **Market regime: {meta['regime']['state'].upper()}** — "
        f"{meta['regime']['note']} ({meta['benchmark']} ${meta['regime'].get('benchmark_price', 0):.2f}, "
        f"5d {meta['regime'].get('benchmark_5d_pct', 0):+.1f}%).",
        "",
        "## Step 2 — Screen",
        "",
        f"{meta['n_pass']} of {meta['n_scored']} scored symbols cleared every gate. "
        f"Top {len(picked)} by composite score:",
        "",
        "| # | Symbol | Price | ATR% | RSI | ADX | SMA20/50/200 | RS 20d | $Vol 20d | Score |",
        "|---|--------|-------|------|-----|-----|--------------|--------|----------|-------|",
    ]
    for i, (f, sc, relaxed) in enumerate(picked, 1):
        stack = "".join([
            "↑" if f["sma20"] and f["price"] > f["sma20"] else "↓",
            "↑" if f["sma20"] and f["sma50"] and f["sma20"] > f["sma50"] else "↓",
            "↑" if f["sma50"] and f["sma200"] and f["sma50"] > f["sma200"] else "↓",
        ])
        tag = f"{f['symbol']}*" if relaxed else f["symbol"]
        L.append(
            f"| {i} | **{tag}** | {f['price']:.2f} | {f['atr_pct']:.2f} | "
            f"{_fmt(f['rsi'], nd=1)} | {_fmt(f['adx'], nd=1)} | {stack} | "
            f"{_fmt(f['rs_20d'], '%', 1)} | ${f['avg_dollar_vol_20d']/1e6:,.0f}M | "
            f"{sc['total']:.1f} |")
    if any(r for _, _, r in picked):
        L += ["", "\\* filled from the relaxed ATR band "
              f"({ATR_PCT_MIN-ATR_RELAX:g}-{ATR_PCT_MAX+ATR_RELAX:g}%) because fewer "
              "than 5 names cleared the strict band. Treat those as second-tier."]
    L += ["", "## Step 3 — Comparative technical read", ""]
    for f, sc, _ in picked:
        L += [
            f"### {f['symbol']} — score {sc['total']:.1f}/100",
            "",
            f"- Buckets: trend {sc['trend_structure']}/25 · momentum {sc['momentum']}/25 "
            f"· volume {sc['volume']}/20 · rel-strength {sc['relative_strength']}/20 "
            f"· entry quality {sc['entry_quality']}/10",
            f"- Price ${f['price']:.2f}, ATR ${f['atr']:.2f} ({f['atr_pct']:.2f}%), "
            f"{_fmt(f['ext_atr_from_sma20'], nd=1)}×ATR from the 20-SMA, "
            f"{f['pct_from_hi60']:+.1f}% vs the 60-day high",
            f"- 20d {f['chg_20d_pct']:+.1f}% vs benchmark ({_fmt(f['rs_20d'], '%', 1)} RS), "
            f"5d volume {_fmt(f['vol_ratio_5_20'], '×')} of 20d avg",
            "- Chart: " + "; ".join(patterns(f)),
            "",
        ]
    L += [
        f"**Strongest chart: {winner['symbol']}** — highest composite "
        f"({ranked[0][1]['total']:.1f}), and the setups below are built on it.",
        "",
        "## Step 4 — Three setups on " + winner["symbol"],
        "",
        f"Sizing: ${ACCOUNT_USD:,.0f} account, {RISK_PCT:g}% risk = "
        f"${ACCOUNT_USD*RISK_PCT/100:,.2f} per trade, whole shares"
        + (" (fractional enabled)" if FRACTIONAL else "") + ".",
        "",
    ]
    if meta["regime"]["state"] != "risk-on":
        L += [f"> **Regime caveat ({meta['regime']['state']}):** {meta['regime']['note']}. "
              f"The sizing below assumes a normal tape — cut it accordingly.", ""]
    L += [
        "| Setup | Entry | Stop | Target | Shares | Risk $ | Profit $ | R:R | Duration |",
        "|-------|-------|------|--------|--------|--------|----------|-----|----------|",
    ]
    for s in setups:
        L.append(
            f"| {s['name']} | {s['entry']:.2f} | {s['stop']:.2f} | {s['target']:.2f} | "
            f"{s['shares']} | {s['loss_at_stop']:.2f} | +{s['profit_at_target']:.2f} | "
            f"{s['risk_reward']:.2f} | {s['expected_duration']} |")
    L.append("")
    for s in setups:
        L += [
            f"### {s['name']}",
            "",
            f"- **Basis:** {s['technical_basis']}",
            f"- **Entry** ${s['entry']:.2f} · **stop** ${s['stop']:.2f} "
            f"(−{s['stop_pct']:.2f}%) · **target** ${s['target']:.2f} "
            f"(+{s['target_pct']:.2f}%)",
            f"- **Size** {s['shares']} share{'' if s['shares'] == 1 else 's'} "
            f"= ${s['position_value']:,.2f} "
            f"({s['position_value']/ACCOUNT_USD*100:.0f}% of the account); "
            f"risking ${abs(s['loss_at_stop']):.2f} ({s['risk_pct_of_account']:.2f}% "
            f"of account) to make ${s['profit_at_target']:.2f}",
            f"- **R:R** {s['risk_reward']:.2f}:1 · **expected duration** "
            f"{s['expected_duration']}",
        ]
        for n in s["notes"]:
            L.append(f"- ⚠️ {n}")
        L.append("")
    L += [
        "## Management rules (same for all three)",
        "",
        "- One setup at a time. They are three ways to own the same stock, not "
        "three positions — stacking them triples the risk on one name.",
        "- Take half off at +1R, move the stop to breakeven, trail the rest under "
        "the 20-SMA. Locking beats hoping (the journal's most expensive lesson).",
        "- Exit early if the daily close breaks the 20-SMA on above-average volume, "
        "or if the thesis-driving catalyst reverses.",
        "- Stops are **daily-close** based unless noted; intraday spikes through "
        "the level are noise at this ATR.",
        "",
        "---",
        "",
        f"_{DISCLAIMER}_",
        "",
        "_Generated by `swing_analysis.py` — algorithmic, not analyst-reviewed. "
        "Paper-trade before risking real money._",
    ]
    return "\n".join(L) + "\n"


# =============================================================================
# Main
# =============================================================================

def run():
    if not HISTORY.exists():
        print(f"missing {HISTORY.name} — run swing_history.py on the Actions runner "
              f"first (Yahoo is blocked from the sandbox).", file=sys.stderr)
        return 1
    raw = json.loads(HISTORY.read_text())
    bars_all = raw.get("bars", {})
    bench = raw.get("benchmark", "SPY")
    bench_closes = (bars_all.get(bench) or {}).get("c")

    scored = []
    for sym, bars in bars_all.items():
        if sym in EXCLUDE_AS_CANDIDATE:
            continue
        f = features(sym, bars, bench_closes)
        if not f:
            continue
        ok, fails = screen(f, ATR_PCT_MIN, ATR_PCT_MAX)
        ok_relaxed, _ = screen(f, ATR_PCT_MIN - ATR_RELAX, ATR_PCT_MAX + ATR_RELAX)
        scored.append((f, score(f), ok, ok_relaxed, fails))

    if not scored:
        print("no symbol produced features — history file looks empty", file=sys.stderr)
        return 1

    strict = sorted([s for s in scored if s[2]], key=lambda s: -s[1]["total"])
    relaxed = sorted([s for s in scored if not s[2] and s[3]], key=lambda s: -s[1]["total"])

    picked = [(f, sc, False) for f, sc, _, _, _ in strict[:TOP_N]]
    if len(picked) < TOP_N:
        picked += [(f, sc, True) for f, sc, _, _, _ in relaxed[:TOP_N - len(picked)]]

    if not picked:
        print("nothing cleared the screen even relaxed — no trade today.")
        picked, ranked, winner, setups = [], [], None, []
    else:
        ranked = [(f, sc) for f, sc, _ in picked]
        winner = ranked[0][0]
        setups = build_setups(winner)

    as_of = (bars_all.get(bench) or next(iter(bars_all.values())))["dates"][-1]
    reg = regime(bars_all.get(bench))
    meta = {
        "as_of": as_of,
        "fetched_at": raw.get("fetched_at", "unknown"),
        "benchmark": bench,
        "universe_n": len(bars_all),
        "n_scored": len(scored),
        "n_pass": len(strict),
        "regime": reg,
    }

    out = {
        "generated_on": date.today().isoformat(),
        "as_of": as_of,
        "generator": "swing_analysis.py (algorithmic)",
        "note": DISCLAIMER,
        "regime": reg,
        "mandate": {
            "account_usd": ACCOUNT_USD, "risk_pct": RISK_PCT,
            "max_position_pct": MAX_POSITION_PCT, "fractional": FRACTIONAL,
            "horizon": "several days to a few weeks", "direction": "long-only",
        },
        "screen": {
            "atr_pct_min": ATR_PCT_MIN, "atr_pct_max": ATR_PCT_MAX,
            "min_dollar_vol": MIN_DOLLAR_VOL, "min_adx": MIN_ADX,
            "rsi_band": [RSI_MIN, RSI_MAX], "scored": len(scored),
            "passed_strict": len(strict),
        },
        "candidates": [
            {**f, "score": sc, "relaxed": rel, "patterns": patterns(f)}
            for f, sc, rel in picked
        ],
        "winner": winner["symbol"] if winner else None,
        "setups": setups,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    if winner:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report = REPORT_DIR / f"{as_of}.md"
        report.write_text(render(picked, ranked, winner, setups, meta), encoding="utf-8")
        print(f"wrote {OUT_JSON.name} and {report}")
        print(f"  screened {len(scored)}, {len(strict)} passed strict; "
              f"picked {', '.join(f['symbol'] for f, _, _ in picked)}")
        print(f"  winner {winner['symbol']} with {len(setups)} setup(s)")
    else:
        print(f"wrote {OUT_JSON.name} (no candidates)")
    return 0


# =============================================================================
# Self-test — indicator maths against hand-checkable synthetic series, so the
# pipeline can be verified without market data (the sandbox has none).
# =============================================================================

def selftest():
    ok = True

    def chk(name, got, want, tol=1e-6):
        nonlocal ok
        good = got is not None and abs(got - want) <= tol
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} {name}: got {got}, want {want}")

    chk("sma(1..10, 5)", sma(list(range(1, 11)), 5)[-1], 8.0)
    chk("ema seeds as sma", ema([2.0] * 30, 10)[-1], 2.0)
    chk("rsi of a monotonic ramp", rsi([float(i) for i in range(1, 40)])[-1], 100.0)
    chk("rsi of a flat line is neutral", rsi([5.0] * 40)[-1], 50.0)

    # ATR: bars with a constant $2 range and no gaps => ATR == 2.
    n = 40
    h = [10.0 + 2.0] * n
    l = [10.0] * n
    c = [11.0] * n
    chk("atr of constant-range bars", atr(h, l, c, 14)[-1], 2.0)

    # ADX on a clean one-way ramp should be strongly trending (>40) with +DI > -DI.
    h = [100.0 + i for i in range(60)]
    l = [99.0 + i for i in range(60)]
    c = [99.5 + i for i in range(60)]
    a_line, pdi, mdi = adx(h, l, c, 14)
    print(f"  {'PASS' if a_line[-1] and a_line[-1] > 40 else 'FAIL'} "
          f"adx of a clean ramp > 40: {a_line[-1]}")
    print(f"  {'PASS' if pdi[-1] > mdi[-1] else 'FAIL'} +DI > -DI on an uptrend: "
          f"{pdi[-1]:.1f} vs {mdi[-1]:.1f}")
    ok = ok and bool(a_line[-1] and a_line[-1] > 40) and pdi[-1] > mdi[-1]

    # MACD on a flat series collapses to zero.
    line, sig, hist = macd([50.0] * 60)
    chk("macd hist on a flat series", hist[-1], 0.0, tol=1e-9)

    # Sizing + setup packing on a synthetic uptrend.
    n = 260
    bars = {
        "dates": [f"2026-01-{(i % 28) + 1:02d}" for i in range(n)],
        "o": [100.0 + i * 0.5 for i in range(n)],
        "h": [102.0 + i * 0.5 for i in range(n)],
        "l": [98.0 + i * 0.5 for i in range(n)],
        "c": [100.5 + i * 0.5 for i in range(n)],
        "v": [1_000_000 + (i % 5) * 100_000 for i in range(n)],
    }
    bench = [100.0 + i * 0.1 for i in range(n)]
    f = features("TEST", bars, bench)
    print(f"  features: px {f['price']}, atr% {f['atr_pct']}, rsi {f['rsi']}, "
          f"adx {f['adx']}, rs20 {f['rs_20d']}")
    sc = score(f)
    print(f"  score: {sc}")
    setups = build_setups(f)
    for s in setups:
        risk = round(abs(s["loss_at_stop"]), 2)
        budget = ACCOUNT_USD * RISK_PCT / 100.0
        good = s["shares"] == 0 or risk <= budget + 0.01
        ok = ok and good and s["risk_reward"] > 0
        print(f"  {'PASS' if good else 'FAIL'} {s['name']}: entry {s['entry']} "
              f"stop {s['stop']} target {s['target']} shares {s['shares']} "
              f"risk ${risk} (budget ${budget:.2f}) RR {s['risk_reward']}")
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
