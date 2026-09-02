#!/usr/bin/env python3
"""黄金 EA(GoldScalper)健康监测 —— 决定「继续 / 停手 / 换 preset」,**不追噪音**。

和 forex_health.py 同一套纪律,只是基线换成黄金 EA 的样本外验证值。
它读一个和 signals_forex_journal.json 同结构的成交日志(默认 gold_journal.json,
由 mt5_bridge.py 从 MT5 真实成交生成),给出一个结论:

    ACCUMULATE  样本不足,继续观察,不下判断
    HALT        跌破停手线 / 回撤爆表 —— **关掉 EA**,不是换参数续命
    RETHINK     样本已足够排除「edge 够大」—— 换经过验证的 preset,或改入场逻辑
    OK          置信下界站上 0,存在正 edge
    WATCH       区间仍跨 0,分不清 edge 还是运气,不要动参数

## 为什么黄金这里更要克制

reports/gold_backtest.md 显示:1 小时周期的各种止损/盈亏比配置**前后两半一致为负**。
唯一在样本外验证里勉强为正的是 **M15 + 固定$3止损 + RR1:2**
(训练 41.4%/+0.098R,验证 40.5%/+0.091R)—— 也就是 EA 的默认参数。

但 +0.091R、每笔 R 的标准差约 1.48,意味着要 **上千笔** 才能 95% 确认它不是零。
所以真正能被数据支持的动作只有:**明显坏了就停,证明 edge 太小就换整套逻辑/preset。**
凭最近连亏几笔去调止损、调盈亏比,改的是随机性,不是规律 —— 一定会更差。

*研究/学习用途,不构成投资建议。黄金杠杆交易可能损失全部本金。*
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os

JOURNAL = os.environ.get("GOLD_JOURNAL_FILE", "gold_journal.json")
OUT = os.environ.get("GOLD_HEALTH_OUT", "reports/gold_health.md")

# ── 验证基线(reports/gold_backtest.md + EA 默认参数注释) ──────────────
#   M15 · 固定$3止损 · RR1:2 · 验证段 40.5% / +0.091R
BASE_EXP    = 0.091      # 验证段每笔期望(R)
BASE_WR     = 40.5       # 验证段胜率 %
BASE_N      = 500        # 验证样本量级(约数,仅作展示对照)
BASE_RR     = 2.0        # 盈亏比
# RR2 + WR40.5% 下每笔 R 只能是 -1 或 +2,理论标准差:
#   sqrt(0.595*(-1-0.091)^2 + 0.405*(2-0.091)^2) ≈ 1.48
SD_R        = 1.48

USEFUL_EDGE = 0.30       # 值得交易的最低期望(和 learnings 的毕业门槛一致)
HALT_EXP    = -0.30      # 跌破这个 = 明显坏掉,停手
MIN_N_JUDGE = 20         # 少于这个不下任何判断
# 验证段最大回撤约 $95(见 gold_backtest.md,$200 本金),单笔风险约 $2 → 约 47R。
# 但那是乐观上界;实盘停手线设在样本外回撤的 1.5 倍更稳:约 30R。
HALT_DD_R   = 30.0


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"entries": []}


def stats(entries):
    """从成交日志算实盘统计。和 forex_health.stats 同口径。"""
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


def needed_n(edge, sd=SD_R):
    """95% 置信度下确认某个期望所需的笔数。"""
    if edge <= 0:
        return None
    return int((1.96 * sd / edge) ** 2)


def verdict(s):
    """四类结论,没有「调参再试」这一项。返回 (state, headline, advice, preset_hint)。

    preset_hint 给 mt5_bridge 用:
      None      不需要动 preset
      "HALT"    关 EA
      "SWITCH"  该考虑换经过验证的 preset(见 presets/gold/)
    """
    if s is None or s["n"] < MIN_N_JUDGE:
        got = 0 if s is None else s["n"]
        return ("ACCUMULATE",
                f"样本 {got} 笔,不足 {MIN_N_JUDGE} 笔 —— 继续观察,不下判断",
                "20 笔以下的胜率是噪音,抛硬币都能连赢 5 次。让 EA 继续按当前 preset 跑。",
                None)

    if s["exp"] <= HALT_EXP:
        return ("HALT",
                f"每笔期望 {s['exp']}R,已跌破停手线 {HALT_EXP}R",
                "这不是运气差,是当前 preset 在现在的黄金行情里明显失效。"
                "**关掉 EA / 卸下图表**,回到研究阶段,不要靠调参续命。",
                "HALT")

    if s["dd_r"] > HALT_DD_R:
        return ("HALT",
                f"回撤 {s['dd_r']}R 超过停手线 {HALT_DD_R}R",
                "实盘回撤显著超出验证基线,说明当前市场状态和验证期不同。**关掉 EA**。",
                "HALT")

    if s["n"] >= needed_n(USEFUL_EDGE) and s["ci_hi"] < USEFUL_EDGE:
        return ("RETHINK",
                f"{s['n']} 笔后,期望的 95% 置信上界只有 {s['ci_hi']}R",
                f"样本已足够排除「edge ≥ {USEFUL_EDGE}R」。就算它是正的,也小到无法在合理"
                "时间内证明,更不值得拿真钱冒险。**换一个经过验证的 preset(见 "
                "presets/gold/),或改入场逻辑 —— 不要只改止损和盈亏比。**",
                "SWITCH")

    if s["ci_lo"] > 0:
        return ("OK",
                f"期望 {s['exp']}R,置信下界 {s['ci_lo']}R > 0",
                "统计上已能确认存在正 edge。保持当前 preset,继续积累,对照毕业门槛。",
                None)

    return ("WATCH",
            f"期望 {s['exp']}R,置信区间 [{s['ci_lo']}, {s['ci_hi']}] 仍跨越 0",
            "还分不清是 edge 还是运气。保持当前 preset,继续跑,不要动参数。",
            None)


def evaluate(journal_path=None):
    """给 mt5_bridge 调用:返回 (stats_dict_or_None, state, headline, advice, preset_hint)。"""
    path = journal_path or JOURNAL
    s = stats(load(path).get("entries", []))
    state, headline, advice, hint = verdict(s)
    return s, state, headline, advice, hint


def render(s, state, headline, advice):
    now = dt.datetime.now(dt.timezone.utc)
    L = ["# 黄金 EA 健康监测", "",
         f"*更新于 {now.isoformat(timespec='seconds')}*", "",
         f"## 结论:`{state}`", "", f"**{headline}**", "", advice, ""]

    L += ["## 必须面对的一个数", "",
          "| 每笔期望 | 95%置信度确认所需笔数 | 按 3 笔/天 |",
          "|---|---|---|"]
    for m in (0.091, 0.15, 0.30, 0.50):
        n = needed_n(m)
        d = n / 3.0
        t = f"{d/365:.1f} 年" if d > 365 else f"{d:.0f} 天"
        tag = " ← 回测验证值" if abs(m - 0.091) < 1e-6 else (" ← 毕业门槛" if m == 0.30 else "")
        L.append(f"| +{m}R | {n:,} | {t}{tag} |")
    L += ["",
          f"> 每笔 R 的标准差约 **{SD_R}**(RR{BASE_RR:.0f}、胜率 ~{BASE_WR}%),",
          f"> 验证出的期望只有 **+{BASE_EXP}R** —— **要上千笔才能证明它不是零。**",
          "> 所以真正的判断不是「赢了没」,而是「edge 有没有大到值得做」。", ""]

    if s:
        L += ["## 实盘战绩(来自 MT5 真实成交)", "",
              "| 指标 | 实盘 | 验证基线 |", "|---|---|---|",
              f"| 笔数 | {s['n']} | ~{BASE_N} |",
              f"| 胜率 | {s['wr']}% | {BASE_WR}% |",
              f"| 每笔期望 | **{s['exp']}R** | {BASE_EXP}R |",
              f"| 95%置信区间 | [{s['ci_lo']}, {s['ci_hi']}] | — |",
              f"| 累计 R | {s['total_r']} | — |",
              f"| 最大回撤 | {s['dd_r']}R | ~47R(乐观上界) |",
              f"| 最长连亏 | {s['worst_streak']} 笔 | — |", ""]
    else:
        L += ["## 实盘战绩(来自 MT5 真实成交)", "", "_还没有已结算的成交_", ""]

    L += ["---", "",
          "## 为什么这里不会「一亏就换止损」", "",
          "黄金 EA 的 edge 在 0.0x 量级,每笔 R 波动约 1.5 —— 信号被噪音淹没十几倍。",
          "连亏 5、6 笔在正期望系统里完全正常。那时候去调止损、调盈亏比,改的是随机性,",
          "而且会因为「最近好像好了」更加相信它,直到下一段随机把你打回原形。",
          "",
          "能被数据支持的动作只有三种,这个监测器做的就是这三种:",
          "1. **停手(HALT)** —— 明显坏掉时关 EA,而不是调参续命",
          "2. **换 preset / 改逻辑(RETHINK)** —— 样本足够排除有用 edge 时,换整套经过验证的配置",
          "3. **通过(OK)** —— 置信下界站上 0 之后,才谈得上稳定",
          "",
          "*研究/学习用途,不构成投资建议。*"]
    return "\n".join(L)


def main():
    s, state, headline, advice, _hint = evaluate()
    text = render(s, state, headline, advice)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(text)
    print(f"[gold-health] {state} · {headline}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
