#!/usr/bin/env python3
"""自动生成当日「加密货币」交易信号 -> signals_crypto.json(供 live_trader.py 使用)。

这是 generate_signals.py 的 24/7 加密版孪生。规则和纪律与股票版一致(顺势、过滤坏
数据、不追高、大盘风控),但有三点针对加密市场的差异:

  - 全天候:没有「下一个交易日」的概念,valid_for 就是当天(每天重算一次)。
  - 大盘基准 = BTC(而不是 SPY)。BTC 既是交易标的,也是风控基准:BTC 当天大跌就
    不再开新多单。
  - 只做多:Alpaca 的加密账户不支持做空,所以这里永远不生成空单(bearish)。

⚠️ 这是算法生成的启发式信号,不是人工分析,更不保证盈利。上线收费前请先在模拟盘验证。
加密市场波动远大于股票,风险自负。
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.abspath(__file__))
QUOTES = os.path.join(ROOT, "quotes_crypto.json")
OUT = os.path.join(ROOT, "signals_crypto.json")
NY = ZoneInfo("America/New_York")

REGIME_SYMBOL = "BTC"   # 加密大盘基准
TREND_MIN = 1.0         # 3 日趋势至少 ±1% 才有方向
BADDATA_ABS = 40.0      # 加密单日波动天然更大;超过这个才视为坏数据
CHASE_ABS = 12.0        # 当日已在方向上跑过这个 % 就不追(加密比股票放宽)
MAX_NAMES = 5           # 候选池上限
STOP_PCT, T1_PCT, T2_PCT = 0.03, 0.04, 0.08   # 加密波动大,止损/目标略放宽
REGIME_MAX_DROP = 5.0   # BTC 当天跌超过这个 % 就是 risk-off,不开新多

DISCLAIMER = ("算法根据公开行情自动生成,仅供学习/研究参考,不构成投资建议或收益承诺。"
              "加密市场波动极大,盈亏自负。")


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def build_signal(ticker, q, regime_today):
    px = q.get("last")
    today = q.get("change_pct")
    trend = q.get("chg_3d_pct", today)
    if px is None or today is None or trend is None:
        return None
    if abs(today) > BADDATA_ABS:      # 坏数据
        return None

    # 只做多:趋势向上且当日没在大跌。
    if not (trend >= TREND_MIN and today >= -1.0):
        return None
    direction = "bullish"

    # 不追高
    if today > CHASE_ABS:
        return None

    # 大盘风控:BTC 当天大跌就不开新多。
    if regime_today is not None and regime_today <= -REGIME_MAX_DROP:
        return None

    conf = 0.6 + min(abs(trend) * 0.01, 0.12)
    conf = round(min(conf, 0.75), 2)

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
                   f"aligned up. Momentum + trend filter, long-only crypto; "
                   f"algorithmic, not analyst-reviewed."),
            "zh": (f"自动:{ticker} 三日趋势 {trend:+.1f}%(当日 {today:+.1f}%),方向上涨一致。"
                   f"动量+趋势过滤生成(只做多),非人工分析。"),
        },
    }


def main():
    today = datetime.now(NY).date()
    target_str = today.isoformat()   # 加密全天候:适用日就是当天

    existing = load(OUT, {})
    # 每天只生成一次;目标适用日没变就不重写(避免盘中乱跳)。
    if existing.get("valid_for") == target_str and not os.environ.get("FORCE_SIGNALS"):
        print(f"signals_crypto.json already for {target_str}; skip regeneration")
        return

    quotes = load(QUOTES, {}).get("quotes", {})
    regime_today = (quotes.get(REGIME_SYMBOL) or {}).get("change_pct")

    cands = []
    for tkr, q in quotes.items():
        sig = build_signal(tkr, q, regime_today)
        if sig:
            cands.append(sig)
    cands.sort(key=lambda s: s["confidence"], reverse=True)
    signals = cands[:MAX_NAMES]

    out = {
        "updated_at": target_str,
        "valid_for": target_str,
        "generator": "generate_signals_crypto.py (algorithmic, long-only)",
        "note": DISCLAIMER,
        "regime_symbol": REGIME_SYMBOL,
        "regime_max_drop_pct": REGIME_MAX_DROP,
        "signals": signals,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    names = ", ".join(f"{s['sector_or_ticker']}({s['confidence']})" for s in signals)
    print(f"wrote {OUT}: valid_for={target_str}, {len(signals)} signal(s): {names or 'none'}")


if __name__ == "__main__":
    main()
