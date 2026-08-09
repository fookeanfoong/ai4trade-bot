#!/usr/bin/env python3
"""外汇每日战报。

**这里报的不是「收益」。** 机器人不下单、没有账户、没有钱在动 —— 它没有收益。

报的是两个必须分开看的数:

  1. 【信号战绩】机器人发出的信号,按后续行情回放判定的结果(R 倍数)。
     这衡量的是**规则好不好**。

  2. 【如果你照做】把 R 换算成 MT5 上 0.01 手的美元数。
     这是**假设值** —— 假设你每一笔都按信号进出、没有滑点、没有手续费。
     它不是你的账户余额,你的真实盈亏只有你自己的 MT5 能告诉你。

把这两个混为一谈是最危险的自我欺骗:你会拿一个假设的数字去证明系统有效,
然后加大真实仓位。

用法:python3 forex_daily_report.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os

JOURNAL_FILE = os.environ.get("FOREX_JOURNAL_FILE", "signals_forex_journal.json")
REPORT_DIR = os.environ.get("FOREX_REPORT_DIR", "reports/forex")
EQUITY = float(os.environ.get("FOREX_EQUITY_USD", "200"))

# MT5 最小手数 0.01 在 XXX_USD 品种上 = $0.10/点。
# 这是你实际会点的手数,所以美元换算按它来,而不是按理论上的精确仓位。
USD_PER_PIP_MIN_LOT = 0.10


def _d(ts):
    if not ts:
        return None
    try:
        return str(ts)[:10]
    except Exception:
        return None


def mt5_usd(e):
    """把 R 倍数换算成 0.01 手下的美元。假设值,不是真实盈亏。"""
    r = e.get("r_multiple")
    pips = e.get("stop_pips")
    if r is None or not pips:
        return None
    return round(r * pips * USD_PER_PIP_MIN_LOT, 2)


def build(journal, day):
    entries = journal.get("entries", [])
    emitted = [e for e in entries if _d(e.get("signal_time")) == day]
    resolved = [e for e in entries
                if _d(e.get("exit_time")) == day
                and e.get("state") in ("won", "lost", "ambiguous")]

    day_r = sum(e.get("r_multiple") or 0 for e in resolved)
    day_usd = sum(mt5_usd(e) or 0 for e in resolved)

    closed_all = [e for e in entries if e.get("state") in ("won", "lost", "ambiguous")]
    total_r = sum(e.get("r_multiple") or 0 for e in closed_all)
    total_usd = sum(mt5_usd(e) or 0 for e in closed_all)
    wins = sum(1 for e in closed_all if e["state"] == "won")

    L = [f"# 外汇战报 · {day}", ""]

    if not emitted and not resolved:
        L += ["**今天没有信号,也没有结算。**", "",
              "这是正常的,不是故障 —— 引擎只在「触发 + ≥2 确认」同时成立时才出信号。",
              "$200 本金一周有 1~3 个合格信号就不错了。频繁交易才是小账户的死因。", ""]
    else:
        L += ["## 今天", "",
              f"- 新信号:**{len(emitted)}** 个",
              f"- 结算:**{len(resolved)}** 笔"]
        if resolved:
            w = sum(1 for e in resolved if e["state"] == "won")
            L.append(f"- 今日战绩:**{w} 胜 {len(resolved) - w} 负** · **{day_r:+.2f} R**")
        L.append("")

    if resolved:
        L += ["| 方案 | 方向 | 入场 | 结局 | R | 如果你照做(0.01手) |",
              "|---|---|---|---|---|---|"]
        for e in resolved:
            u = mt5_usd(e)
            L.append(f"| {e['plan'][:6]} | {'多' if e['direction']=='long' else '空'} | "
                     f"{e['entry']} | {e['state']} | {e.get('r_multiple'):+.1f} | "
                     f"{('$%+.2f' % u) if u is not None else '—'} |")
        L.append("")

    if emitted:
        L += ["## 今天发出的信号", "",
              "| 时间 | 方案 | 方向 | 入场 | 止损 | TP1 | 状态 |", "|---|---|---|---|---|---|---|"]
        for e in emitted:
            L.append(f"| {e['signal_time'][11:16]} | {e['plan'][:6]} | "
                     f"{'多' if e['direction']=='long' else '空'} | {e['entry']} | "
                     f"{e['stop']} | {e['tp1']} | {e['state']} |")
        L.append("")

    L += ["## 累计(信号战绩)", "",
          "| 指标 | 值 |", "|---|---|",
          f"| 已结算 | {len(closed_all)} 笔 |",
          f"| 胜率 | {round(wins/len(closed_all)*100,1) if closed_all else '—'}% |",
          f"| 累计 R | **{total_r:+.2f} R** |",
          f"| 如果每笔都照做(0.01手) | **${total_usd:+.2f}** |", ""]

    if len(closed_all) < 20:
        L += [f"> ⚠️ **只有 {len(closed_all)} 笔,任何结论都不成立。** 20 笔以下的胜率是噪音,",
              "> 抛硬币都能连赢 5 次。别根据这张表加仓,也别根据它改规则。", ""]

    L += ["---", "",
          "## 这不是你的收益",
          "",
          "上面的美元数是**假设值**:假设你每一笔都按信号进出、无滑点、无手续费。",
          "机器人不下单、没有账户 —— 它没有收益。**你的真实盈亏只有你的 MT5 知道。**",
          "",
          "把这两个数混为一谈是最危险的自我欺骗:你会拿假设的成绩去证明系统有效,",
          "然后加大真实仓位。",
          "",
          "*研究/学习用途,不构成投资建议。*"]
    return "\n".join(L), {
        "day": day, "emitted": len(emitted), "resolved": len(resolved),
        "day_r": round(day_r, 2), "day_usd": round(day_usd, 2),
        "total_closed": len(closed_all), "total_r": round(total_r, 2),
        "total_usd": round(total_usd, 2),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="YYYY-MM-DD,默认今天(UTC)")
    args = ap.parse_args()
    day = args.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")

    try:
        with open(JOURNAL_FILE) as f:
            journal = json.load(f)
    except Exception:
        journal = {"entries": []}

    md, summary = build(journal, day)
    os.makedirs(REPORT_DIR, exist_ok=True)
    path = f"{REPORT_DIR}/{day}.md"
    with open(path, "w") as f:
        f.write(md)
    print(f"[daily] {path} · 新信号 {summary['emitted']} · 结算 {summary['resolved']} "
          f"· 今日 {summary['day_r']:+.2f}R · 累计 {summary['total_r']:+.2f}R "
          f"({summary['total_closed']} 笔)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
