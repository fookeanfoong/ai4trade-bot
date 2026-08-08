#!/usr/bin/env python3
"""成交记录归因分析 -> 打印 + reports/analysis.md。

回答那些「不记录就永远答不了」的问题:
  - 哪种 setup 真的在赚钱?(超卖反弹 vs 顺势做多)
  - 哪种离场方式在亏钱?(信号失效 / 止损 / 目标 / 追踪)
  - 期望值扣完手续费之后是正是负?

关键点:**所有数字都是扣完两边手续费之后的**。研究和实盘都反复证明,
扣费前的胜率和盈亏比会骗人——这个策略的手续费能占到毛利的 50-67%。

用法:
    python3 analyze_trades.py [state_file ...]
默认分析 live_trader_crypto_state.json。
"""

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT = ["live_trader_crypto_state.json"]
REPORT = ROOT / "reports" / "analysis.md"

# 老记录没有 fee_rate 字段(归因是后来才加的),用这个兜底。
FALLBACK_FEE = 0.0025
# 少于这个笔数的分组不下结论——研究说要 100 笔才能排除运气,
# 我们连 30 都没有,所以宁可标「样本不足」也不要编一个结论出来。
MIN_SAMPLE = 20


def net_of(t: dict) -> float:
    """这一笔扣完两边手续费之后的真实盈亏。"""
    fee = float(t.get("fee_rate", FALLBACK_FEE) or 0)
    qty = float(t.get("qty") or 0)
    cost = float(t.get("entry") or 0) * qty
    proceeds = float(t.get("exit") or 0) * qty
    gross = (proceeds - cost) if t.get("side") != "short" else (cost - proceeds)
    return gross - (cost + proceeds) * fee


def summarize(rows: list) -> dict:
    nets = [net_of(t) for t in rows]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n <= 0]
    n = len(nets)
    return {
        "n": n,
        "net": sum(nets),
        "win_rate": (len(wins) / n * 100) if n else 0.0,
        "avg_win": (sum(wins) / len(wins)) if wins else 0.0,
        "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
        # 期望值 = 平均每笔赚多少。这是唯一真正重要的数字:
        # 正的才有资格谈优化,负的说明整套逻辑还在倒贴。
        "expectancy": (sum(nets) / n) if n else 0.0,
    }


def table(title: str, groups: dict, key_name: str) -> list:
    out = [f"### {title}", "",
           f"| {key_name} | 笔数 | 净盈亏 | 胜率 | 均盈 | 均亏 | 期望值/笔 |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for k, rows in sorted(groups.items(), key=lambda kv: summarize(kv[1])["net"]):
        s = summarize(rows)
        flag = "" if s["n"] >= MIN_SAMPLE else "  ⚠️样本不足"
        out.append(f"| {k}{flag} | {s['n']} | ${s['net']:+.2f} | {s['win_rate']:.0f}% | "
                   f"${s['avg_win']:+.2f} | ${s['avg_loss']:+.2f} | ${s['expectancy']:+.3f} |")
    out.append("")
    return out


def main() -> int:
    files = sys.argv[1:] or DEFAULT
    trades = []
    for f in files:
        p = ROOT / f
        if not p.exists():
            print(f"skip {f} (not found)")
            continue
        doc = json.loads(p.read_text())
        for t in doc.get("trade_log", []):
            t["_book"] = f
            trades.append(t)

    if not trades:
        print("no trades to analyse")
        return 0

    lines = ["# 成交归因分析", "",
             f"共 {len(trades)} 笔已平仓交易。**所有金额均为扣除两边手续费后的净额。**", ""]

    overall = summarize(trades)
    lines += ["## 总体", "",
              f"- 净盈亏 **${overall['net']:+.2f}**",
              f"- 胜率 **{overall['win_rate']:.0f}%**（{overall['n']} 笔）",
              f"- 平均每笔 **${overall['expectancy']:+.3f}** ← 期望值，正数才谈得上有效",
              f"- 均盈 ${overall['avg_win']:+.2f} / 均亏 ${overall['avg_loss']:+.2f}", ""]
    if overall["n"] < 100:
        lines += [f"> ⚠️ 只有 {overall['n']} 笔。业界经验是**至少 100 笔**才能把运气从结论里剔除，"
                  "下面的分组数字只能当线索，不能当定论。", ""]

    by_setup = defaultdict(list)
    by_action = defaultdict(list)
    by_ticker = defaultdict(list)
    for t in trades:
        by_setup[t.get("setup") or "(未记录)"].append(t)
        by_action[t.get("action") or "?"].append(t)
        by_ticker[t.get("ticker") or "?"].append(t)

    if len({t["_book"] for t in trades}) > 1:
        by_book = defaultdict(list)
        for t in trades:
            by_book[t["_book"].replace("live_trader_", "").replace("_state.json", "")].append(t)
        lines += table("按账本（不同账本仓位规模差很多，别混着看）", by_book, "账本")

    lines += table("按 setup（哪种打法赚钱）", by_setup, "setup")
    lines += table("按离场原因（哪种退出在亏）", by_action, "离场原因")
    lines += table("按币种", by_ticker, "币")

    held = [float(t["held_min"]) for t in trades if t.get("held_min") is not None]
    if held:
        lines += ["### 持仓时长", "",
                  f"- 中位数 **{statistics.median(held):.0f} 分钟**",
                  f"- 最短 {min(held):.0f} / 最长 {max(held):.0f} 分钟",
                  "", "> 中位数很短说明还在 churn：每次进出都要付一次手续费。", ""]

    fees = sum((float(t.get("entry") or 0) + float(t.get("exit") or 0))
               * float(t.get("qty") or 0) * float(t.get("fee_rate", FALLBACK_FEE) or 0)
               for t in trades)
    gross = overall["net"] + fees
    lines += ["### 手续费吃掉了多少", "",
              f"- 毛利 ${gross:+.2f} → 手续费 ${fees:.2f} → **净 ${overall['net']:+.2f}**", ""]
    if gross > 0:
        lines.append(f"> 手续费占毛利 **{fees / gross * 100:.0f}%**。"
                     "这个比例越高，越说明该减少交易次数、放大每次的目标。")
    else:
        lines.append("> 毛利本身就是负的——问题不在手续费，在信号本身没有方向性优势。")
    lines.append("")

    text = "\n".join(lines)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
