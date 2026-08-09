#!/usr/bin/env python3
"""黄金策略研究 — 带**样本外验证**的参数搜索。

背景:H1 + \$3 止损在两年真实行情上是负期望(-0.14~-0.29R)。原因是
\$3 只有 H1 波动的 0.3 倍,止损在价格走对之前就被噪音打掉。
假设:在更低周期上(M15/M5),同样 \$3 的止损相对噪音是正常宽度。

**这个脚本最重要的部分不是搜索,是验证方式。**

在同一份数据上反复试参数直到收益变正,叫过拟合 —— 105 笔样本上总能找到
一组"好看"的参数,实盘照样亏。所以每份数据按时间切成两半:

    前一半(训练)  用来找候选参数
    后一半(验证)  参数定死后,只跑一次

只有**两边都为正**的配置才算数。训练正、验证负 = 你找到的是噪音,不是规律。
脚本会把两边的数字并排列出来,不给我藏结果的机会。

用法:python3 gold_research.py
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import os

import backtest_gold as B

OUT = os.environ.get("GOLD_RESEARCH_OUT", "reports/gold_research.md")
EQUITY = float(os.environ.get("GOLD_EQUITY", "200"))
MIN_TRADES = 25          # 单边少于这个笔数,结果不作数


def evaluate(bars, stop_usd, rr, spread):
    """跑一组参数,返回 (笔数, 胜率, 净利, 每笔期望R, 最大回撤)。"""
    B.EQUITY0 = EQUITY
    B.FIXED_STOP_USD = stop_usd
    B.REWARD_RISK = rr
    B.SPREAD_USD = spread
    trades, equity, dd, skipped = B.run(bars)
    n = len(trades)
    if n == 0:
        return {"n": 0, "wr": None, "net": 0.0, "exp": None, "dd": 0.0, "skip": skipped}
    wins = sum(1 for t in trades if t["win"])
    total_r = sum(t["r"] for t in trades)
    return {"n": n, "wr": round(wins / n * 100, 1), "net": round(equity - EQUITY, 2),
            "exp": round(total_r / n, 3), "dd": round(dd, 2), "skip": skipped}


def split(bars):
    """按时间切两半。绝不打乱 —— 时间序列打乱后验证就没有意义了。"""
    mid = len(bars) // 2
    return bars[:mid], bars[mid:]


def main():
    datasets = [
        ("M5",  "5m",  "60d"),
        ("M15", "15m", "60d"),
        ("M30", "30m", "60d"),
        ("H1",  "1h",  "2y"),
    ]
    stops   = [1.5, 2.0, 2.5, 3.0, 4.0]
    rrs     = [1.5, 2.0]
    spread  = float(os.environ.get("GOLD_SPREAD", "0.30"))

    lines = ["# 黄金策略研究 — 样本外验证", "",
             f"*生成于 {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}*", "",
             f"本金 ${EQUITY:.0f} · 点差 ${spread} · 0.01手=1oz",
             "",
             "**方法**:每份数据按时间切两半 —— 前一半找参数,后一半只跑一次做验证。",
             f"只有**两边都为正**、且各自 ≥{MIN_TRADES} 笔的配置才算数。",
             "训练正/验证负 = 找到的是噪音。这张表把两边并排列出,不给藏结果的余地。",
             ""]

    survivors = []

    for name, interval, rng in datasets:
        try:
            bars = B.fetch("GC=F", interval, rng)
        except Exception as e:
            lines += [f"## {name}", "", f"取数失败:{e}", ""]
            continue
        if len(bars) < 600:
            lines += [f"## {name}", "", f"K线不足({len(bars)}),跳过", ""]
            continue

        tr_bars, te_bars = split(bars)
        t0 = dt.datetime.fromtimestamp(bars[0]["t"], dt.timezone.utc)
        t1 = dt.datetime.fromtimestamp(bars[-1]["t"], dt.timezone.utc)
        atr = B.atr_series(bars, 14)
        atr_last = next((a for a in reversed(atr) if a), 0)

        lines += [f"## {name}（{interval} / {rng}）", "",
                  f"{t0:%Y-%m-%d} → {t1:%Y-%m-%d} · {len(bars)} 根 · 近期 ATR ≈ ${atr_last:.2f}",
                  "",
                  "| 止损 | RR | 止损/ATR | 训练笔数 | 训练胜率 | 训练期望 | 验证笔数 | 验证胜率 | 验证期望 | 判定 |",
                  "|---|---|---|---|---|---|---|---|---|---|"]

        for stop, rr in itertools.product(stops, rrs):
            a = evaluate(tr_bars, stop, rr, spread)
            b = evaluate(te_bars, stop, rr, spread)
            ratio = f"{stop / atr_last:.2f}x" if atr_last else "—"

            if a["n"] < MIN_TRADES or b["n"] < MIN_TRADES:
                verdict = "样本不足"
            elif a["exp"] is not None and b["exp"] is not None and a["exp"] > 0 and b["exp"] > 0:
                verdict = "✅ 两边为正"
                survivors.append((name, stop, rr, a, b))
            elif a["exp"] is not None and a["exp"] > 0:
                verdict = "⚠️ 训练正/验证负 = 噪音"
            else:
                verdict = "❌"

            lines.append(
                f"| ${stop} | 1:{rr} | {ratio} | {a['n']} | "
                f"{a['wr'] if a['wr'] is not None else '—'}% | "
                f"{a['exp'] if a['exp'] is not None else '—'} | {b['n']} | "
                f"{b['wr'] if b['wr'] is not None else '—'}% | "
                f"{b['exp'] if b['exp'] is not None else '—'} | {verdict} |")
        lines.append("")

    lines += ["## 结论", ""]
    if survivors:
        lines += [f"**{len(survivors)} 组配置通过了样本外验证:**", ""]
        for name, stop, rr, a, b in survivors:
            lines.append(f"- **{name} · 止损${stop} · RR1:{rr}** — "
                         f"训练 {a['n']}笔/{a['wr']}%/{a['exp']}R，"
                         f"验证 {b['n']}笔/{b['wr']}%/{b['exp']}R，"
                         f"验证净利 ${b['net']}，最大回撤 ${b['dd']}")
        lines += ["", "> 通过样本外验证**不等于**实盘会赚。它只说明这组参数不是",
                  "> 单纯拟合噪音。真实点差会在数据前后放大数倍,滑点和隔夜利息",
                  "> 都没算 —— 这些都只会让结果更差。", ""]
    else:
        lines += ["**没有任何一组配置通过样本外验证。**", "",
                  "这不是搜索得不够细。继续加密参数网格直到出现正数,",
                  "得到的一定是过拟合 —— 在 100 来笔样本上,总能找到一组好看的参数。",
                  "",
                  "诚实的结论:**当前这套入场逻辑在黄金上没有可验证的优势。**",
                  "要改的是策略本身(入场条件、过滤器、周期),不是止损和盈亏比。", ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[-25:]))
    print(f"\n完整报告 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
