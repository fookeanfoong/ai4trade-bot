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
NEWS = os.path.join(ROOT, "news_crypto.json")
OUT = os.path.join(ROOT, "signals_crypto.json")
NY = ZoneInfo("America/New_York")

REGIME_SYMBOL = "BTC"      # 用 BTC 当大盘:BTC 崩,全场 risk-off
REGIME_MAX_DROP = 4.0      # BTC 当天跌超过这个 % 就不开新多

# --- 崩盘熔断 (crash circuit breaker) ---------------------------------------
# 加密每年都会来几次「毫无预警的跳水」(例如 BTC 从高位直接砸到 3 万区间)。
# 单看「当日涨跌幅」发现得太晚——日内从高点砸下来的那一段,day% 可能还是正的。
# 所以熔断改看三个更快的信号,任一触发就 risk-off(不开新仓):
#   1. BTC 从近 4 小时最高点回落超过 CRASH_FAST_DROP%   → 正在跳水
#   2. BTC 最近 1 小时跌超过 CRASH_1H_DROP%            → 急跌
#   3. BTC 当日跌超过 REGIME_MAX_DROP%                 → 慢性熊
# 另外单币自己从高点砸超过 NAME_CRASH_DROP% 也单独拉黑(别接飞刀)。
CRASH_FAST_DROP = 3.0      # BTC 距近 4h 高点回撤 % 阈值
CRASH_1H_DROP = 2.5        # BTC 近 1 小时跌幅 % 阈值
NAME_CRASH_DROP = 6.0      # 单币距近 4h 高点回撤 % 阈值(只拉黑该币)
# 更狠的一档:BTC 崩到这个程度,引擎会直接清仓离场(见 live_trader.py)。
PANIC_FLATTEN_DROP = 7.0

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
# 集中而非分散:美金目标下,仓位越大门槛越低。$200 押 1 个币,净赚 $1 只要涨
# 1.00%;分 2 个要 1.50%;分 4 个就要 2.51% —— 5 分钟内基本等不到。
# 所以这里只挑最强的 1-2 个,把火力集中在最好的机会上。
MAX_NAMES = 2

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


def assess_regime(quotes, news=None):
    """看 BTC 价格 + 新闻,判断全场风险状态。

    返回 (risk_off: bool, panic: bool, reason: str)。
    risk_off -> 不开新仓;panic -> 引擎清仓走人。

    价格和新闻的分工:
      - 价格是事实,可以单独触发清仓。
      - 新闻是启发式的、会误判,所以**单独出现时只停止开新仓,不清仓**。
      - 两者同时告警 -> 升级为清仓:重大利空叠加真实下跌,基本就是真崩。
    """
    btc = quotes.get(REGIME_SYMBOL) or {}
    day = btc.get("change_pct")
    hour = btc.get("chg_1h_pct")
    from_high = btc.get("drop_from_high_pct")

    news = news or {}
    news_off = bool(news.get("news_risk_off"))
    news_reason = news.get("reason") or ""

    # 新闻 + 价格双确认 -> 清仓。单看新闻永远不清仓(误判代价太大)。
    if news_off and from_high is not None and from_high <= -CRASH_FAST_DROP:
        return True, True, (f"重大利空 + {REGIME_SYMBOL} 已从高点跌 {from_high:.1f}% "
                            f"— 双重确认,清仓离场 | {news_reason}")

    if from_high is not None and from_high <= -PANIC_FLATTEN_DROP:
        return True, True, (f"{REGIME_SYMBOL} 距近期高点已跌 {from_high:.1f}% "
                            f"(≥{PANIC_FLATTEN_DROP}%) — 疑似崩盘,清仓离场")
    if day is not None and day <= -PANIC_FLATTEN_DROP:
        return True, True, (f"{REGIME_SYMBOL} 当日跌 {day:.1f}% "
                            f"(≥{PANIC_FLATTEN_DROP}%) — 疑似崩盘,清仓离场")
    if from_high is not None and from_high <= -CRASH_FAST_DROP:
        return True, False, (f"{REGIME_SYMBOL} 正从高点跳水 {from_high:.1f}% "
                             f"(≥{CRASH_FAST_DROP}%) — 暂停开新仓")
    if hour is not None and hour <= -CRASH_1H_DROP:
        return True, False, (f"{REGIME_SYMBOL} 近1小时急跌 {hour:.1f}% "
                             f"(≥{CRASH_1H_DROP}%) — 暂停开新仓")
    if day is not None and day <= -REGIME_MAX_DROP:
        return True, False, (f"{REGIME_SYMBOL} 当日跌 {day:.1f}% "
                             f"(≥{REGIME_MAX_DROP}%) — 大盘走弱,暂停开新仓")
    # 价格还没出事,但新闻已经在响 -> 只停手观望,不动已有仓位。
    if news_off:
        return True, False, f"新闻风控:{news_reason}"
    return False, False, ""


def build_setup(tkr, q, risk_off):
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
    # Regime: don't buy into a market-wide flush.
    if risk_off:
        return None
    # Per-name falling knife: this coin itself is collapsing off its highs.
    name_drop = q.get("drop_from_high_pct")
    if name_drop is not None and name_drop <= -NAME_CRASH_DROP:
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
    news = load(NEWS, {})
    risk_off, panic, regime_reason = assess_regime(quotes, news)

    cands = []
    for tkr, q in quotes.items():
        s = build_setup(tkr, q, risk_off)
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
        "regime_day_pct": regime_today,
        "news_risk_off": bool(news.get("news_risk_off")),
        "news_hits": news.get("hit_count"),
        "news_degraded": bool(news.get("degraded")),
        "risk_off": risk_off,
        "panic_flatten": panic,
        "regime_reason": regime_reason,
        "signals": signals,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    if risk_off:
        print(f"RISK-OFF: {regime_reason}")
    if signals:
        names = ", ".join(f"{s['sector_or_ticker']}({s['setup']} {s['confidence']} rr{s['rr']})"
                          for s in signals)
        print(f"wrote {OUT}: {len(signals)} scalp setup(s): {names}")
    else:
        print(f"wrote {OUT}: no good scalp setup right now — standing aside (SAY SO)")


if __name__ == "__main__":
    main()
