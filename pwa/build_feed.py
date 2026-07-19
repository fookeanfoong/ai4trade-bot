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
OUT = os.path.join(ROOT, "pwa", "data", "signals.json")

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
        "reasoning": "示例:AI 芯片龙头,若大盘企稳、半导体反弹则领涨。",
        "tradable": True, "demo": True,
    },
    {
        "ticker": "COIN", "direction": "bullish", "confidence": 0.61,
        "timeframe": "1-3 days", "stop_pct": 0.04, "t1_pct": 0.05, "t2_pct": 0.09,
        "ref_price": 305.0,
        "reasoning": "示例:加密情绪回暖时的高 beta 代理标的,波动大、止损要严。",
        "tradable": True, "demo": True,
    },
]


def convert(sig: dict) -> dict:
    tradable = (
        sig.get("direction") in ("bullish", "bearish")
        and float(sig.get("confidence", 0)) >= 0.6
        and not sig.get("already_priced_in", False)
    )
    out = {
        "ticker": sig.get("sector_or_ticker"),
        "direction": sig.get("direction"),
        "confidence": sig.get("confidence"),
        "timeframe": sig.get("timeframe"),
        "stop_pct": sig.get("stop_pct"),
        "t1_pct": sig.get("t1_pct"),
        "t2_pct": sig.get("t2_pct"),
        "reasoning": sig.get("reasoning"),
        "tradable": tradable,
    }
    if sig.get("requires_preopen_recheck"):
        out["preopen_recheck"] = True
    return out


def main() -> None:
    with open(SRC, "r", encoding="utf-8") as f:
        src = json.load(f)

    signals = [convert(s) for s in src.get("signals", [])]
    if "--demo" in sys.argv:
        signals += DEMO

    feed = {
        "updated_at": src.get("updated_at"),
        "valid_for": src.get("valid_for"),
        "disclaimer": DISCLAIMER,
        "signals": signals,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)
    print(f"wrote {OUT}: {len(signals)} signal(s), valid_for={feed['valid_for']}")


if __name__ == "__main__":
    main()
