#!/usr/bin/env python3
"""自动生成当日交易信号 -> signals.json（供 PWA / signal_sim / live_trader 使用）。

原来 signals.json 是「Claude 手写」的,不会自己更新。这个脚本用 quotes.json 的动量 +
简单的趋势/风控规则,每个交易日开盘前自动挑几只票并写出 signals.json,让 App 每天有新内容。

设计原则(都是从之前 0胜9负 的教训里来的):
  - 只顺势:要求 3 日趋势和当日方向一致,不接下跌中的反弹。
  - 过滤坏数据:单日涨跌 > 18% 的大盘股/ETF 视为坏数据,跳过(VLO/MPC/PSX 教训)。
  - 大盘风控:SPY 当日 < -2% 不发新多单;> +2% 不发新空单。
  - 不追高:当日已在信号方向上跑过头就跳过。
  - 每天只在盘前生成一次,盘中不来回改(避免让用户看到信号乱跳)。

⚠️ 这是算法生成的启发式信号,不是人工分析,更不保证盈利。上线收费前请先在模拟盘验证。
"""
import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
QUOTES = os.path.join(ROOT, "quotes.json")
NEWS = os.path.join(ROOT, "news.json")
OUT = os.path.join(ROOT, "signals.json")
NY = ZoneInfo("America/New_York")

# 只做个股 / 板块 ETF;SPY、QQQ 仅用于大盘风控,不作为标的。
EXCLUDE = {"SPY", "QQQ"}
TREND_MIN = 1.0        # 3 日趋势至少 ±1% 才有方向
BADDATA_ABS = 18.0     # 单日涨跌超过这个视为坏数据
CHASE_ABS = 7.0        # 当日已在方向上跑过这个 % 就不追
MAX_NAMES = 3
STOP_PCT, T1_PCT, T2_PCT = 0.025, 0.03, 0.06
REGIME_MAX_DROP = 2.0

DISCLAIMER = ("算法根据公开行情自动生成,仅供学习/研究参考,不构成投资建议或收益承诺。"
              "市场有风险,盈亏自负。")


def next_trading_day(d):
    d = d + timedelta(days=1)
    while d.weekday() >= 5:  # 5=Sat, 6=Sun
        d = d + timedelta(days=1)
    return d


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def news_score_for(news, ticker):
    """从 news.json 粗略取该标的的新闻情绪(有就用,没有就 0)。"""
    try:
        for m in news.get("movers", []):
            if isinstance(m, dict) and m.get("symbol") == ticker:
                return m.get("score", 0)
    except Exception:
        pass
    return 0


def build_signal(ticker, q, news, spy_today):
    px = q.get("last")
    today = q.get("change_pct")
    trend = q.get("chg_3d_pct", today)
    if px is None or today is None or trend is None:
        return None
    if abs(today) > BADDATA_ABS:      # 坏数据
        return None

    direction = None
    if trend >= TREND_MIN and today >= -0.5:
        direction = "bullish"
    elif trend <= -TREND_MIN and today <= 0.5:
        direction = "bearish"
    if direction is None:
        return None
    # 只做多模式(很多散户不方便做空):设 LONG_ONLY=1 时跳过所有空单。
    if direction == "bearish" and os.environ.get("LONG_ONLY"):
        return None

    # 不追高 / 不追低
    if direction == "bullish" and today > CHASE_ABS:
        return None
    if direction == "bearish" and today < -CHASE_ABS:
        return None

    # 大盘风控
    if spy_today is not None:
        if direction == "bullish" and spy_today <= -REGIME_MAX_DROP:
            return None
        if direction == "bearish" and spy_today >= REGIME_MAX_DROP:
            return None

    conf = 0.6 + min(abs(trend) * 0.01, 0.12)
    ns = news_score_for(news, ticker)
    if (direction == "bullish" and ns > 0) or (direction == "bearish" and ns < 0):
        conf += 0.03
    conf = round(min(conf, 0.75), 2)

    updn = "上涨" if direction == "bullish" else "下跌"
    endir = "up" if direction == "bullish" else "down"
    return {
        "sector_or_ticker": ticker,
        "direction": direction,
        "confidence": conf,
        "timeframe": "1-3 days",
        "entry_mode": "market",
        "stop_pct": STOP_PCT,
        "t1_pct": T1_PCT,
        "t2_pct": T2_PCT,
        "already_priced_in": False,
        "auto_generated": True,
        "reasoning": {
            "en": (f"Auto: {ticker} 3-day trend {trend:+.1f}% (today {today:+.1f}%), "
                   f"aligned {endir}. Momentum + trend filter; algorithmic, not analyst-reviewed."),
            "zh": (f"自动:{ticker} 三日趋势 {trend:+.1f}%(当日 {today:+.1f}%),方向{updn}一致。"
                   f"动量+趋势过滤生成,非人工分析。"),
        },
    }


def main():
    now = datetime.now(NY)
    today = now.date()
    minutes = now.hour * 60 + now.minute
    is_weekday = now.weekday() < 5
    before_close = is_weekday and minutes < 960  # 16:00 ET
    target = today if before_close else next_trading_day(today)
    target_str = target.isoformat()

    existing = load(OUT, {})
    # 每天盘前只生成一次:目标适用日没变就不重写(避免盘中乱跳)。
    if existing.get("valid_for") == target_str and not os.environ.get("FORCE_SIGNALS"):
        print(f"signals.json already for {target_str}; skip regeneration")
        return

    quotes = load(QUOTES, {}).get("quotes", {})
    news = load(NEWS, {})
    spy_today = (quotes.get("SPY") or {}).get("change_pct")

    cands = []
    for tkr, q in quotes.items():
        if tkr in EXCLUDE:
            continue
        sig = build_signal(tkr, q, news, spy_today)
        if sig:
            cands.append(sig)
    cands.sort(key=lambda s: s["confidence"], reverse=True)
    signals = cands[:MAX_NAMES]

    out = {
        "updated_at": today.isoformat(),
        "valid_for": target_str,
        "generator": "generate_signals.py (algorithmic)",
        "note": DISCLAIMER,
        "regime_max_drop_pct": REGIME_MAX_DROP,
        "signals": signals,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    names = ", ".join(f"{s['sector_or_ticker']}({s['direction'][:4]} {s['confidence']})" for s in signals)
    print(f"wrote {OUT}: valid_for={target_str}, {len(signals)} signal(s): {names or 'none'}")


if __name__ == "__main__":
    main()
