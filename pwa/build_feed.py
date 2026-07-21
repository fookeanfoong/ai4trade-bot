#!/usr/bin/env python3
"""把机器人产出的 signals.json 转成 PWA 消费的干净信号源。

用法:
    python3 pwa/build_feed.py            # 只用真实信号(机器人每天的产出)
    python3 pwa/build_feed.py --demo     # 追加几条示例信号,方便演示界面

机器人每个交易日开盘前重写根目录 signals.json,把这行加进它的收尾流程即可
让 PWA 每天自动更新:
    python3 pwa/build_feed.py && git add pwa/data/signals.json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "signals.json")
QUOTES = os.path.join(ROOT, "quotes.json")
OUT = os.path.join(ROOT, "pwa", "data", "signals.json")


def load_quotes():
    """symbol -> latest price, from quotes.json (机器人盘前/盘中刷新的实时报价)。"""
    try:
        with open(QUOTES, "r", encoding="utf-8") as f:
            q = json.load(f).get("quotes", {})
        return {k: v.get("last") for k, v in q.items() if v.get("last")}
    except Exception:
        return {}

DISCLAIMER = (
    "以下内容由模拟交易机器人根据公开新闻与行情自动生成,仅供学习/研究参考,"
    "不构成任何投资建议或收益承诺。市场有风险,任何操作都可能造成本金亏损,"
    "盈亏目标不代表实际结果。请自行判断并为自己的决定负责。"
)

# 演示用示例信号(--demo 时追加,界面里会打「示例」标)。真实运行请勿依赖。
DEMO = [
    {
        "ticker": "NVDA", "direction": "bullish", "confidence": 0.64,
        "timeframe": "1-2 days", "stop_pct": 0.03, "t1_pct": 0.04, "t2_pct": 0.07,
        "ref_price": 172.0,
        "reasoning": {
            "en": "Sample: AI-chip leader; leads the rally if the market steadies and semis bounce.",
            "zh": "示例:AI 芯片龙头,若大盘企稳、半导体反弹则领涨。",
        },
        "tradable": True, "demo": True,
    },
    {
        "ticker": "COIN", "direction": "bullish", "confidence": 0.61,
        "timeframe": "1-3 days", "stop_pct": 0.04, "t1_pct": 0.05, "t2_pct": 0.09,
        "ref_price": 305.0,
        "reasoning": {
            "en": "Sample: high-beta crypto proxy for when sentiment warms up — volatile, keep the stop tight.",
            "zh": "示例:加密情绪回暖时的高 beta 代理标的,波动大、止损要严。",
        },
        "tradable": True, "demo": True,
    },
]


def convert(sig: dict, ref_price) -> dict:
    tradable = (
        sig.get("direction") in ("bullish", "bearish")
        and float(sig.get("confidence", 0)) >= 0.6
        and not sig.get("already_priced_in", False)
    )
    ticker = sig.get("sector_or_ticker")
    out = {
        "ticker": ticker,
        "direction": sig.get("direction"),
        "confidence": sig.get("confidence"),
        "timeframe": sig.get("timeframe"),
        "entry_mode": sig.get("entry_mode", "market"),
        "stop_pct": sig.get("stop_pct"),
        "t1_pct": sig.get("t1_pct"),
        "t2_pct": sig.get("t2_pct"),
        "reasoning": sig.get("reasoning"),
        "tradable": tradable,
    }
    # 附上参考价 -> App 能算出「买入价/止损价/目标价」。价格按「当天冻结」处理
    # (见 main:同一 valid_for 内复用第一次的价),避免盘中每几分钟就变导致重部署。
    if ref_price:
        out["ref_price"] = round(ref_price, 2)
    if sig.get("requires_preopen_recheck"):
        out["preopen_recheck"] = True
    return out


def load_existing() -> dict:
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main() -> None:
    with open(SRC, "r", encoding="utf-8") as f:
        src = json.load(f)

    quotes = load_quotes()
    existing = load_existing()

    # 当天(同一 valid_for)冻结参考价:复用上一次已写入的 ref_price,只有换了
    # 交易日 / 换了标的才用最新报价。这样盘中每 5 分钟跑,输出不变 -> 不产生
    # pwa/ 变更 -> Vercel 不会每几分钟重部署一次。
    frozen = {}
    if existing.get("valid_for") == src.get("valid_for"):
        for s in existing.get("signals", []):
            if s.get("ticker") and s.get("ref_price") is not None:
                frozen[s["ticker"]] = s["ref_price"]

    signals = []
    for s in src.get("signals", []):
        tkr = s.get("sector_or_ticker")
        ref = frozen.get(tkr, quotes.get(tkr))   # frozen for the day, else live
        signals.append(convert(s, ref))
    if "--demo" in sys.argv:
        signals += DEMO

    feed = {
        "updated_at": src.get("updated_at"),
        "valid_for": src.get("valid_for"),
        "disclaimer": DISCLAIMER,
        "signals": signals,
    }

    new = json.dumps(feed, ensure_ascii=False, indent=2)
    try:
        with open(OUT, "r", encoding="utf-8") as f:
            old = f.read()
    except Exception:
        old = None
    # Idempotent: don't rewrite (and thus don't create a commit / Vercel deploy)
    # when nothing meaningful changed.
    if old is not None and old.strip() == new.strip():
        print(f"{OUT} unchanged; skip write (valid_for={feed['valid_for']})")
        return

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"wrote {OUT}: {len(signals)} signal(s), valid_for={feed['valid_for']}")


if __name__ == "__main__":
    main()
