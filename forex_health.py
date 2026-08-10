#!/usr/bin/env python3
"""策略健康监测 —— 决定「继续 / 停手 / 换策略」,**不调参数**。

你要我「从错误中学习并改变」。这个脚本是那句话的具体实现,但它做的
可能和你预期的不一样,所以先说清楚为什么。

**它不会自动调参数。** 在几十笔样本上根据近期表现改止损、改盈亏比,
不是学习,是追噪音 —— 每笔 R 的标准差是 1.236,而验证出来的期望只有
0.018。信号被噪音淹没了 68 倍。任何基于近期几笔的"改进"都是在拟合随机。

**它做的是三件能被数据支持的事:**

  1. 算实盘期望的**置信区间**,而不是只看点估计
  2. 和验证基线对比,发现**灾难性偏离**就叫停(不是微调)
  3. 样本够了之后判断:这个 edge 是否**大到值得交易**

第 3 条是关键,因为有个数必须面对:

    每笔期望   95%置信度确认所需笔数   按2.5笔/天
      +0.018R          18,105            19.8 年
      +0.300R              65             26 天

**当前验证出来的 +0.018R,需要跑 20 年才能证明它不是零。**
换句话说:它在统计上和「没有优势」无法区分。这不是耐心问题 ——
再等 30 笔、300 笔都不够。要么 edge 变大,要么承认没有 edge。

所以这个监测器的输出只有四种:继续观察 / 叫停 / 换策略 / 通过。
没有「调一下参数再试试」这个选项 —— 那是最容易骗自己的那条路。
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os

JOURNAL = os.environ.get("FOREX_JOURNAL_FILE", "signals_forex_journal.json")
OUT = os.environ.get("FOREX_HEALTH_OUT", "reports/forex_health.md")

# 验证基线(reports/forex_research.md: EUR/USD 25点 1:1.5 的验证半段)
BASE_EXP      = 0.018
BASE_WR       = 42.3
BASE_DD_USD   = 31.70
BASE_N        = 52

USEFUL_EDGE   = 0.30      # 值得交易的最低期望(和 learnings 的毕业门槛一致)
HALT_EXP      = -0.30     # 跌破这个 = 明显坏掉
MIN_N_JUDGE   = 20        # 少于这个不下任何判断
RR            = 1.5


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"entries": []}


def stats(entries):
    closed = [e for e in entries if e.get("state") in ("won", "lost", "ambiguous")]
    n = len(closed)
    if n == 0:
        return None
    rs = [e.get("r_multiple") or 0 for e in closed]
    wins = sum(1 for e in closed if e["state"] == "won")
    mu = sum(rs) / n
    var = sum((r - mu) ** 2 for r in rs) / n if n > 1 else 0.0
    sd = math.sqrt(var)
    se = sd / math.sqrt(n) if n else 0.0
    # 权益曲线回撤(按 R,再折算成美元需要知道每笔风险,这里用 R 更通用)
    peak = cum = dd = 0.0
    streak = worst = 0
    for e in sorted(closed, key=lambda x: x.get("exit_time") or ""):
        cum += e.get("r_multiple") or 0
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
        if e["state"] == "won":
            streak = 0
        else:
            streak += 1
            worst = max(worst, streak)
    return {"n": n, "wins": wins, "wr": round(wins / n * 100, 1),
            "exp": round(mu, 4), "sd": round(sd, 3), "se": round(se, 4),
            "ci_lo": round(mu - 1.96 * se, 4), "ci_hi": round(mu + 1.96 * se, 4),
            "dd_r": round(dd, 2), "worst_streak": worst,
            "total_r": round(sum(rs), 2)}


def needed_n(edge, sd=1.236):
    """95% 置信度下确认某个期望所需的笔数。"""
    if edge <= 0:
        return None
    return int((1.96 * sd / edge) ** 2)


def verdict(s):
    """四种结论,没有『调参再试』这一项。"""
    if s is None or s["n"] < MIN_N_JUDGE:
        got = 0 if s is None else s["n"]
        return ("ACCUMULATE", f"样本 {got} 笔,不足 {MIN_N_JUDGE} 笔 —— 继续观察,不下判断",
                "20 笔以下的胜率是噪音,抛硬币都能连赢 5 次。")

    if s["exp"] <= HALT_EXP:
        return ("HALT", f"每笔期望 {s['exp']}R,已跌破停手线 {HALT_EXP}R",
                "这不是运气差,是规则在当前市场明显失效。**停止交易**,"
                "回到研究阶段重新验证 —— 不要调参数继续跑。")

    if s["dd_r"] > 0 and s["dd_r"] * 1.0 > (BASE_DD_USD / 2.0) * 1.5:
        # 验证段回撤 $31.7,单笔风险约 $2 -> 约 15.9R。1.5 倍 = 23.8R
        pass

    if s["dd_r"] > 23.8:
        return ("HALT", f"回撤 {s['dd_r']}R 超过验证基线({BASE_DD_USD/2.0:.1f}R)的 1.5 倍",
                "实盘回撤显著超出回测,说明当前市场状态和验证期不同。**停手**。")

    if s["n"] >= needed_n(USEFUL_EDGE) and s["ci_hi"] < USEFUL_EDGE:
        return ("RETHINK", f"{s['n']} 笔后,期望的 95% 置信上界只有 {s['ci_hi']}R",
                f"样本已经足够排除「edge ≥ {USEFUL_EDGE}R」。就算它是正的,也小到"
                "无法在合理时间内被证明,更不值得拿真钱冒险。"
                "**要改的是入场逻辑,不是止损和盈亏比。**")

    if s["ci_lo"] > 0:
        return ("OK", f"期望 {s['exp']}R,置信下界 {s['ci_lo']}R > 0",
                "统计上已能确认存在正 edge。继续积累,对照毕业门槛。")

    return ("WATCH", f"期望 {s['exp']}R,置信区间 [{s['ci_lo']}, {s['ci_hi']}] 仍跨越 0",
            "还分不清是 edge 还是运气。继续跑,不要动参数。")


def main():
    now = dt.datetime.now(dt.timezone.utc)
    s = stats(load(JOURNAL).get("entries", []))
    state, headline, advice = verdict(s)

    L = ["# 策略健康监测", "",
         f"*更新于 {now.isoformat(timespec='seconds')}*", "",
         f"## 结论:`{state}`", "", f"**{headline}**", "", advice, ""]

    L += ["## 必须面对的一个数", "",
          "| 每笔期望 | 95%置信度确认所需笔数 | 按 2.5 笔/天 |",
          "|---|---|---|"]
    for m in (0.018, 0.10, 0.30, 0.50):
        n = needed_n(m)
        d = n / 2.5
        t = f"{d/365:.1f} 年" if d > 365 else f"{d:.0f} 天"
        tag = " ← 回测验证值" if m == 0.018 else (" ← 毕业门槛" if m == 0.30 else "")
        L.append(f"| +{m}R | {n:,} | {t}{tag} |")
    L += ["",
          "> 每笔 R 的标准差约 **1.236**,而验证出的期望只有 **0.018** —— ",
          "> 信号被噪音淹没 68 倍。**+0.018R 要跑 20 年才能证明不是零。**",
          "> 这不是耐心问题:再等 30 笔、300 笔都不够。",
          "> 所以真正的判断不是「赢了没」,而是「edge 有没有大到值得做」。", ""]

    if s:
        L += ["## 实盘信号战绩", "",
              "| 指标 | 实盘 | 验证基线 |", "|---|---|---|",
              f"| 笔数 | {s['n']} | {BASE_N} |",
              f"| 胜率 | {s['wr']}% | {BASE_WR}% |",
              f"| 每笔期望 | **{s['exp']}R** | {BASE_EXP}R |",
              f"| 95%置信区间 | [{s['ci_lo']}, {s['ci_hi']}] | — |",
              f"| 累计 R | {s['total_r']} | — |",
              f"| 最大回撤 | {s['dd_r']}R | ~15.9R |",
              f"| 最长连亏 | {s['worst_streak']} 笔 | — |", ""]
    else:
        L += ["## 实盘信号战绩", "", "_还没有已结算的信号_", ""]

    L += ["---", "",
          "## 为什么这里不会「自动调参数」", "",
          "你要我从错误中学习并改变。**在几十笔样本上改参数不是学习,是追噪音。**",
          "",
          "每笔 R 的标准差 1.236,意味着连续 5 笔亏损在正期望系统里也完全正常。",
          "如果那时候去调止损、调盈亏比,你改的是随机性,不是规律 —— 而且改完",
          "会因为「最近好像好了」而更加相信它,直到下一段随机把你打回原形。",
          "",
          "能被数据支持的「改变」只有三种,这个脚本做的就是这三种:",
          "1. **叫停** —— 明显坏掉时停手,而不是调参续命",
          "2. **换策略** —— 样本足够排除有用 edge 时,改入场逻辑,不改止损",
          "3. **通过** —— 置信下界站上 0 之后,才谈得上稳定",
          "",
          "*研究/学习用途,不构成投资建议。*"]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print(f"[health] {state} · {headline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
