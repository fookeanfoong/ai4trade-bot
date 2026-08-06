#!/usr/bin/env python3
"""生成加密货币「剥头皮(scalp)」交易信号 -> signals_crypto.json。

这是 Xynth/ChatGPT 那套 BTC scalping 流程的自动化版第 3 步「生成交易设置」:读取
quotes_crypto.py 算好的 5 分钟技术指标(RSI / 布林带 %B / EMA 趋势 / 量比 / 支撑阻力),
把它变成清晰的多头 scalp setup(入场、止损、T1/T2、盈亏比)。没有好机会就说「没有」。

两类简单、顺基本面的 setup(只做多,Alpaca 加密不能做空):
  A. 超卖反弹(mean-revert):RSI 超卖 + 价格贴近下轨/支撑 + 有量 → 打反弹,
     目标中轨/上轨。
  B. 趋势回踩续涨(continuation):EMA9>EMA21 上升趋势 + 回踩到中轨附近 + 不超买 →
     顺势做多,目标上轨/阻力。

纪律:
  - 不追高:RSI≥68 或 %B≥0.85 一律不开新多(scalper 最忌追顶)。
  - 大盘风控:BTC 当天跌超过 REGIME_MAX_DROP% = risk-off,不开新多。
  - 盈亏比过滤:到 T2 的 R:R < 1.2 的设置直接丢掉。
  - 信号「粘性」:只要还处于多头有利状态就持续给出该信号,避免持仓每 5 分钟被
    signal_still_valid 误平;真正转空/超买时信号消失 -> 引擎按「信号失效」离场。

⚠️ 算法启发式,非人工分析,不构成投资建议。加密波动极大,已按风险(非全仓)定量,盈亏自负。
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
QUOTES = os.path.join(ROOT, "quotes_crypto.json")
OUT = os.path.join(ROOT, "signals_crypto.json")
NY = ZoneInfo("America/New_York")

REGIME_SYMBOL = "BTC"
REGIME_MAX_DROP = 5.0      # BTC 当天跌超过这个 % 就不开新多

# AGGRESSIVE crypto profile (intentionally looser than the stock book): trades
# in flat tape too, chases a bit harder, takes lower R:R. Every trade still
# carries a hard stop below support — aggressive, not suicidal.
# Overbought / no-chase gates (relaxed).
RSI_OVERBOUGHT = 75.0
PCTB_OVERBOUGHT = 0.92
# Oversold-bounce (setup A) triggers (relaxed).
RSI_OVERSOLD = 48.0
PCTB_LOW = 0.32
# Momentum-long (setup B): any up-OR-flat, non-overbought tape with RSI >= this.
RSI_MOMO_MIN = 40.0

STOP_BUFFER = 0.0015       # place stop a touch below support/swing
STOP_MIN, STOP_MAX = 0.004, 0.05   # clamp scalp stop distance (0.4%–5%)
MIN_RR = 1.0               # reward(to T2):risk floor (aggressive)
MAX_NAMES = 5

DISCLAIMER = ("算法根据 5 分钟行情自动生成的剥头皮信号,仅供学习/研究参考,不构成投资建议。"
              "已按风险定量(非全仓),加密波动极大,盈亏自负。")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def build_setup(tkr, q, regime_today):
    """Return a long scalp setup dict, or None if there's no good trade."""
    last = q.get("last")
    rsi = q.get("rsi")
    pctb = q.get("pct_b")
    trend = q.get("trend")
    support = q.get("support")
    resistance = q.get("resistance")
    sma20 = q.get("sma20")
    bb_upper = q.get("bb_upper")
    vol_ratio = q.get("vol_ratio")
    if last is None or rsi is None or pctb is None or support is None:
        return None

    # No-chase / overbought: never open a new long at the top.
    if rsi >= RSI_OVERBOUGHT or pctb >= PCTB_OVERBOUGHT:
        return None
    # Regime: don't buy into a BTC risk-off flush.
    if regime_today is not None and regime_today <= -REGIME_MAX_DROP:
        return None
    # Need room above support to justify a long.
    if last <= support:
        return None

    setup = None
    conf = 0.60
    # --- Setup A: oversold bounce (mean-revert) ----------------------------
    if rsi <= RSI_OVERSOLD and pctb <= PCTB_LOW:
        setup = "oversold_bounce"
        conf = 0.64
        if vol_ratio and vol_ratio >= 1.2:
            conf += 0.05
        if (last - support) / last <= 0.008:   # hugging support
            conf += 0.05
        target2 = max(sma20 or 0, bb_upper or 0, resistance or 0)
        target1 = sma20 or (last * 1.008)
    # --- Setup B: momentum long (aggressive) -------------------------------
    #     Any up-OR-flat, non-overbought tape is tradable long — this is what
    #     keeps the crypto book active in chop instead of sitting flat.
    elif trend in ("up", "flat") and rsi >= RSI_MOMO_MIN:
        setup = "momentum_long"
        conf = 0.62
        if trend == "up":
            conf += 0.04
        if vol_ratio and vol_ratio >= 1.0:
            conf += 0.03
        target2 = max(bb_upper or 0, resistance or 0, last * 1.02)
        target1 = bb_upper or (last * 1.008)
    else:
        return None   # only skip clear downtrends / overbought

    # Stop just below support; clamp the distance to a scalp-sized band.
    stop_price = support * (1 - STOP_BUFFER)
    stop_pct = _clamp((last - stop_price) / last, STOP_MIN, STOP_MAX)

    # Targets as fractions above entry (engine consumes stop_pct/t1_pct/t2_pct).
    if not target1 or target1 <= last:
        target1 = last * 1.006
    if not target2 or target2 <= target1:
        target2 = last * 1.012
    t1_pct = (target1 - last) / last
    t2_pct = (target2 - last) / last

    rr = t2_pct / stop_pct if stop_pct > 0 else 0
    if rr < MIN_RR:
        return None   # not worth the risk

    conf = round(min(conf, 0.78), 2)
    rr = round(rr, 2)
    return {
        "sector_or_ticker": tkr,
        "direction": "bullish",
        "confidence": conf,
        "timeframe": "5m scalp",
        "entry_mode": "market",
        "setup": setup,
        "stop_pct": round(stop_pct, 4),
        "t1_pct": round(t1_pct, 4),
        "t2_pct": round(t2_pct, 4),
        "rr": rr,
        "already_priced_in": False,
        "auto_generated": True,
        "ta": {"rsi": rsi, "pct_b": pctb, "trend": trend,
               "support": support, "resistance": resistance, "vol_ratio": vol_ratio},
        "reasoning": {
            "en": (f"{setup.replace('_', ' ')} long on {tkr} (5m): RSI {rsi}, %B {pctb}, "
                   f"trend {trend}, vol× {vol_ratio}. Stop below support ${support:g}; "
                   f"targets +{t1_pct*100:.1f}%/+{t2_pct*100:.1f}%, R:R {rr}. "
                   f"Algorithmic scalp, risk-sized (not all-in), not analyst-reviewed."),
            "zh": (f"{tkr} 5分钟{('超卖反弹' if setup=='oversold_bounce' else '顺势做多')}:"
                   f"RSI {rsi},%B {pctb},趋势{trend},量比{vol_ratio}。止损设在支撑 ${support:g} 下方,"
                   f"目标 +{t1_pct*100:.1f}%/+{t2_pct*100:.1f}%,盈亏比 {rr}。算法剥头皮、按风险定量(非全仓)。"),
        },
    }


def main():
    now = datetime.now(NY)
    target_str = now.date().isoformat()   # 加密全天候:适用日=当天;每次运行都重算(盘中)

    quotes = load(QUOTES, {}).get("quotes", {})
    regime_today = (quotes.get(REGIME_SYMBOL) or {}).get("change_pct")

    cands = []
    for tkr, q in quotes.items():
        s = build_setup(tkr, q, regime_today)
        if s:
            cands.append(s)
    cands.sort(key=lambda s: (s["confidence"], s["rr"]), reverse=True)
    signals = cands[:MAX_NAMES]

    out = {
        "updated_at": now.isoformat(timespec="seconds"),
        "valid_for": target_str,
        "generator": "generate_signals_crypto.py (5m scalp, long-only)",
        "note": DISCLAIMER,
        "regime_symbol": REGIME_SYMBOL,
        "regime_max_drop_pct": REGIME_MAX_DROP,
        "signals": signals,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    if signals:
        names = ", ".join(f"{s['sector_or_ticker']}({s['setup']} {s['confidence']} rr{s['rr']})"
                          for s in signals)
        print(f"wrote {OUT}: {len(signals)} scalp setup(s): {names}")
    else:
        print(f"wrote {OUT}: no good scalp setup right now — standing aside (SAY SO)")


if __name__ == "__main__":
    main()
