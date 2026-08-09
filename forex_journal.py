#!/usr/bin/env python3
"""外汇信号日志 + 学习回路。

**为什么需要它**:执行是手动的,机器人根本看不到你做了什么 —— 有没有进场、
赚了还是亏了,它一无所知。没有结局数据,「从交易中学习」就是一句空话。

解法:让它**自动追踪自己发出的每一个信号的结局**,用后续的 K 线回放判定。
不需要你汇报任何东西。判定的是「这个信号本身好不好」,而这正是要评估的对象 ——
你执行得好不好是另一回事,那个得你自己记。

判定流程(和真实挂单的行为对齐):
    信号发出 -> 限价单挂在 entry,24h 有效
      -> 24h 内价格没碰到 entry            = expired(没成交,不算胜负)
      -> 碰到 entry 视为成交,之后看先碰哪个:
           先碰 TP1 = won  (+RR1 个 R)
           先碰 SL  = lost (-1 个 R)

⚠️ **同一根 K 线同时包含 SL 和 TP1 时,OHLC 无法判断谁先到。**
   这种情况标记为 ambiguous,并且**按亏损计入统计**。这是回测里最经典的作弊点:
   默认成「先到 TP」能把任何垃圾策略美化成圣杯。宁可低估自己。
"""

from __future__ import annotations

import datetime as dt
import json
import os

JOURNAL_FILE = os.environ.get("FOREX_JOURNAL_FILE", "signals_forex_journal.json")
LEARNINGS_FILE = os.environ.get("FOREX_LEARNINGS_FILE", "learnings_forex.md")
ORDER_EXPIRY_H = float(os.environ.get("FOREX_ORDER_EXPIRY_HOURS", "24"))


def _parse(ts):
    if not ts:
        return None
    try:
        d = dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def load(path=JOURNAL_FILE):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {"entries": []}


def save(doc, path=JOURNAL_FILE):
    with open(path, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def record(journal, pair_result, plan, signal_time):
    """把一个 triggered 信号记进日志。同一根 K 线的同一方案只记一次。"""
    eid = f"{pair_result['instrument']}|{plan['name']}|{signal_time}"
    if any(e["id"] == eid for e in journal["entries"]):
        return False
    journal["entries"].append({
        "id": eid,
        "instrument": pair_result["instrument"],
        "plan": plan["name"],
        "direction": plan["direction"],
        "signal_time": signal_time,
        "entry": plan["entry"], "stop": plan["stop"], "tp1": plan["tp1"],
        "stop_pips": plan["stop_pips"], "rr1": plan["rr1"],
        "mt5_lots": plan.get("mt5_lots"),
        "confirmations": {k: bool(v) for k, v in plan["confirmations"].items()},
        "confirmed": plan["confirmed"],
        "state": "pending",
        "fill_time": None, "exit_time": None, "exit_price": None,
        "r_multiple": None,
        "actual": None,   # 留给你手填:你自己实际做了什么(见 learnings_forex.md)
    })
    return True


def resolve(journal, candles_by_inst, now=None):
    """用后续 K 线把未结的日志条目判出结局。"""
    now = now or dt.datetime.now(dt.timezone.utc)
    changed = 0

    for e in journal["entries"]:
        if e["state"] in ("won", "lost", "expired", "ambiguous"):
            continue

        candles = candles_by_inst.get(e["instrument"]) or []
        t0 = _parse(e["signal_time"])
        if not t0 or not candles:
            continue

        long = e["direction"] == "long"
        entry, sl, tp = e["entry"], e["stop"], e["tp1"]
        expiry = t0 + dt.timedelta(hours=ORDER_EXPIRY_H)
        filled = e["state"] == "filled"
        fill_t = _parse(e.get("fill_time"))

        for c in candles:
            ct = _parse(c.get("time"))
            # 只看信号之后的 K 线。信号那根本身不能用 —— 它是生成信号的依据,
            # 拿它来判成交等于让结果回头去解释原因。
            if not ct or ct <= t0:
                continue

            if not filled:
                if ct > expiry:
                    e["state"] = "expired"
                    e["exit_time"] = c["time"]
                    changed += 1
                    break
                # 限价单:多单要价格跌到 entry,空单要涨到 entry
                touched = (c["l"] <= entry) if long else (c["h"] >= entry)
                if touched:
                    filled = True
                    fill_t = ct
                    e["state"] = "filled"
                    e["fill_time"] = c["time"]
                    changed += 1
                    # 成交那根 K 线本身也可能立刻打到 SL/TP,继续往下判
                else:
                    continue

            if filled and (fill_t is None or ct >= fill_t):
                hit_tp = (c["h"] >= tp) if long else (c["l"] <= tp)
                hit_sl = (c["l"] <= sl) if long else (c["h"] >= sl)
                if hit_tp and hit_sl:
                    # 一根 K 线里两个都碰到了 —— OHLC 判不出先后。
                    # 按亏损算。默认成「先到 TP」是回测造假的头号手法。
                    e["state"] = "ambiguous"
                    e["exit_time"] = c["time"]
                    e["exit_price"] = sl
                    e["r_multiple"] = -1.0
                    changed += 1
                    break
                if hit_tp:
                    e["state"] = "won"
                    e["exit_time"] = c["time"]
                    e["exit_price"] = tp
                    e["r_multiple"] = float(e["rr1"])
                    changed += 1
                    break
                if hit_sl:
                    e["state"] = "lost"
                    e["exit_time"] = c["time"]
                    e["exit_price"] = sl
                    e["r_multiple"] = -1.0
                    changed += 1
                    break

        # 兜底:K 线数据没覆盖到过期时间(数据窗口滚走、品种改了、行情有缺口)时,
        # 上面的循环不会触发 expired,条目会永远卡在 pending 里污染统计。
        # 用真实时间再判一次。
        if e["state"] == "pending" and now > expiry:
            e["state"] = "expired"
            changed += 1
    return changed


# ------------------------------- 统计 ---------------------------------------
def stats(entries):
    closed = [e for e in entries if e["state"] in ("won", "lost", "ambiguous")]
    wins = [e for e in closed if e["state"] == "won"]
    losses = [e for e in closed if e["state"] in ("lost", "ambiguous")]
    total_r = sum(e.get("r_multiple") or 0 for e in closed)
    return {
        "signals": len(entries),
        "pending": sum(1 for e in entries if e["state"] == "pending"),
        "filled_open": sum(1 for e in entries if e["state"] == "filled"),
        "expired": sum(1 for e in entries if e["state"] == "expired"),
        "closed": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "total_r": round(total_r, 2),
        "expectancy_r": round(total_r / len(closed), 3) if closed else None,
    }


def confirmation_edge(entries):
    """哪些确认信号真的和盈利相关 —— 这是这套日志最值钱的输出。

    如果某个确认项在赢单和输单里出现得一样频繁,它就没有信息量,
    只是让你自我感觉良好的装饰。留着它反而会拖低出手频率。
    """
    closed = [e for e in entries if e["state"] in ("won", "lost", "ambiguous")]
    if not closed:
        return {}
    keys = set()
    for e in closed:
        keys.update(e.get("confirmations", {}).keys())
    out = {}
    for k in sorted(keys):
        with_k = [e for e in closed if e.get("confirmations", {}).get(k)]
        without_k = [e for e in closed if not e.get("confirmations", {}).get(k)]
        def wr(g):
            if not g:
                return None
            w = sum(1 for e in g if e["state"] == "won")
            return round(w / len(g) * 100, 1)
        out[k] = {"n_with": len(with_k), "wr_with": wr(with_k),
                  "n_without": len(without_k), "wr_without": wr(without_k)}
    return out


# --------------------------- 毕业条件 ---------------------------------------
# 什么时候这套规则才配得上真钱。
#
# **胜率不是判据。** 在 1:2 的赔率下(赢 +2R,输 -1R),盈亏平衡点只要 33.3%:
#     期望 = 胜率×2 − (1−胜率)×1
#     33.3% -> 0.00R   40% -> +0.20R   50% -> +0.50R   70% -> +1.10R
# 70% 胜率 = 每笔期望 +1.1R,这在零售外汇里基本不存在。把门槛设在那里,等于
# 永远不开户;或者更糟 —— 在前 10 笔里碰巧刷到 70%,然后拿真钱去赌一个噪声。
#
# 而且盯胜率会把人推向错误的方向:想提高胜率,最快的办法是把止盈拉近、止损放远。
# 那样胜率立刻变漂亮,期望却变成负的。**能决定你是否赚钱的是期望,不是胜率。**
GRAD_MIN_SAMPLE = int(os.environ.get("FOREX_GRAD_MIN_SAMPLE", "30"))
GRAD_MIN_EXPECTANCY = float(os.environ.get("FOREX_GRAD_MIN_EXPECTANCY", "0.30"))


def drawdown_r(entries):
    """按结算时间排序走一遍权益曲线,返回 (最大回撤R, 最长连亏笔数)。

    这是「你要能扛住多少」的数字。期望为正的系统照样会连亏 6 笔 ——
    不知道这个数,第一次连亏就会把人吓停,而停在连亏之后正是最贵的时点。
    """
    closed = sorted([e for e in entries if e["state"] in ("won", "lost", "ambiguous")],
                    key=lambda e: e.get("exit_time") or "")
    peak = cum = 0.0
    max_dd = 0.0
    streak = worst_streak = 0
    for e in closed:
        cum += e.get("r_multiple") or 0
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
        if e["state"] == "won":
            streak = 0
        else:
            streak += 1
            worst_streak = max(worst_streak, streak)
    return round(max_dd, 2), worst_streak


def graduation(entries):
    """这套规则够不够格拿真钱。返回逐条判定 + 是否全部通过。"""
    s = stats(entries)
    n, exp = s["closed"], s["expectancy_r"]
    dd, streak = drawdown_r(entries)
    checks = [
        {"name": f"样本 ≥ {GRAD_MIN_SAMPLE} 笔",
         "now": f"{n} 笔", "pass": n >= GRAD_MIN_SAMPLE,
         "why": "少于这个数,胜率和期望都是噪声"},
        {"name": f"每笔期望 ≥ +{GRAD_MIN_EXPECTANCY} R",
         "now": f"{exp if exp is not None else '—'} R",
         "pass": exp is not None and exp >= GRAD_MIN_EXPECTANCY,
         "why": "**这才是唯一决定你赚不赚钱的指标**"},
        {"name": "胜率 ≥ 40%（仅参考）",
         "now": f"{s['win_rate'] if s['win_rate'] is not None else '—'}%",
         "pass": s["win_rate"] is not None and s["win_rate"] >= 40,
         "why": "1:2 赔率下 33.3% 就已盈亏平衡;胜率高低本身说明不了什么"},
    ]
    return {"checks": checks, "passed": all(c["pass"] for c in checks),
            "max_dd_r": dd, "worst_losing_streak": streak}


def render_learnings(journal, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    entries = journal.get("entries", [])
    s = stats(entries)
    L = [f"# 外汇信号 · 学习日志", "",
         f"*更新于 {now.isoformat(timespec='seconds')}*", "",
         "机器人自动追踪它发出的**每一个** `triggered` 信号的结局(用后续 K 线回放判定),",
         "不需要你汇报。判定的是**信号本身**好不好;你执行得好不好,在下面手工记录。", ""]

    L += ["## 战绩", "",
          f"| 指标 | 值 |", "|---|---|",
          f"| 累计信号 | {s['signals']} |",
          f"| 已了结 | {s['closed']} |",
          f"| 胜 / 负 | {s['wins']} / {s['losses']} |",
          f"| 胜率 | {s['win_rate'] if s['win_rate'] is not None else '—'}% |",
          f"| 累计 R | {s['total_r']} |",
          f"| 每笔期望 | {s['expectancy_r'] if s['expectancy_r'] is not None else '—'} R |",
          f"| 挂单未成交 | {s['pending']} |",
          f"| 持仓中 | {s['filled_open']} |",
          f"| 到期未成交 | {s['expired']} |", ""]

    if s["closed"] < 20:
        L += [f"> ⚠️ **样本只有 {s['closed']} 笔,还不能下任何结论。** 20 笔以下的胜率",
              "> 基本是噪音 —— 连抛硬币都能连赢 5 次。别根据这张表改规则。", ""]
    if s["expectancy_r"] is not None and s["closed"] >= 20:
        if s["expectancy_r"] > 0:
            L += [f"> 每笔期望 **+{s['expectancy_r']} R**。1:2 的赔率下,胜率只要超过 33% 就是正期望。", ""]
        else:
            L += [f"> 每笔期望 **{s['expectancy_r']} R** —— 这套规则目前是负期望。",
                  "> 不要加大仓位去摊平,那是加速归零。要么改规则,要么停手。", ""]

    # 毕业条件 —— 什么时候这套规则配得上真钱
    g = graduation(entries)
    L += ["## 能开真钱账户了吗", "",
          f"### {'✅ 三项全部达标' if g['passed'] else '❌ 还不行'}", "",
          "| 条件 | 现状 | 达标 | 为什么 |", "|---|---|---|---|"]
    for c in g["checks"]:
        L.append(f"| {c['name']} | {c['now']} | {'✅' if c['pass'] else '❌'} | {c['why']} |")
    L += ["",
          f"- 历史最大回撤:**{g['max_dd_r']} R** · 最长连亏:**{g['worst_losing_streak']} 笔**",
          "",
          "> **为什么门槛不是「胜率 70%」:** 这套规则是 1:2 赔率(赢 +2R,输 −1R),",
          "> 盈亏平衡点只要 **33.3%**。换算一下:",
          ">",
          "> | 胜率 | 33% | 40% | 50% | 60% | 70% |",
          "> |---|---|---|---|---|---|",
          "> | 每笔期望 | 0.00R | +0.20R | +0.50R | +0.80R | +1.10R |",
          ">",
          "> **70% 胜率 = 每笔期望 +1.1R,零售外汇里基本不存在。** 把门槛设在那儿",
          "> 等于永远不开户;更糟的是,前 10 笔里碰巧刷到 70% 的概率并不低 ——",
          "> 那时候你会拿真钱去赌一个噪声。",
          ">",
          "> 而且**盯胜率会把人推向错误的方向**:想让胜率好看,最快的办法是把止盈拉近、",
          "> 止损放远。胜率立刻变漂亮,期望却变成负的。**决定你赚不赚钱的是期望。**", ""]

    # 分方案
    by_plan = {}
    for e in entries:
        if e["state"] in ("won", "lost", "ambiguous"):
            by_plan.setdefault(e["plan"][:6], []).append(e)
    if by_plan:
        L += ["## 分方案", "", "| 方案 | 笔数 | 胜率 | 累计R |", "|---|---|---|---|"]
        for k, g in sorted(by_plan.items()):
            w = sum(1 for e in g if e["state"] == "won")
            r = round(sum(e.get("r_multiple") or 0 for e in g), 2)
            L.append(f"| {k} | {len(g)} | {round(w/len(g)*100,1)}% | {r} |")
        L.append("")

    edge = confirmation_edge(entries)
    if edge:
        L += ["## 确认信号有没有用", "",
              "有它 vs 没它的胜率差。**差值接近 0 = 这个确认项没有信息量**,",
              "留着它只会拖低出手频率,不会提高胜率。", "",
              "| 确认项 | 有(笔/胜率) | 无(笔/胜率) |", "|---|---|---|"]
        for k, v in edge.items():
            L.append(f"| {k} | {v['n_with']} / "
                     f"{v['wr_with'] if v['wr_with'] is not None else '—'}% | "
                     f"{v['n_without']} / "
                     f"{v['wr_without'] if v['wr_without'] is not None else '—'}% |")
        L.append("")

    recent = [e for e in entries if e["state"] != "pending"][-15:]
    if recent:
        L += ["## 最近 15 笔", "",
              "| 时间 | 方案 | 方向 | 入场 | 结局 | R |", "|---|---|---|---|---|---|"]
        for e in reversed(recent):
            L.append(f"| {e['signal_time'][:16]} | {e['plan'][:6]} | "
                     f"{'多' if e['direction']=='long' else '空'} | {e['entry']} | "
                     f"{e['state']} | {e.get('r_multiple') if e.get('r_multiple') is not None else '—'} |")
        L.append("")

    L += ["## 你的执行记录(手工填)", "",
          "机器人只知道信号该怎么走,不知道你实际做了什么。把差异记在这里 ——",
          "**这个差异才是你真正要改的东西。**", "",
          "在 `signals_forex_journal.json` 里给对应条目填 `actual` 字段,例如:",
          "",
          "```json",
          '"actual": "没进 — 当时在睡觉"',
          '"actual": "提前手动平了,只吃到 0.8R,因为心里发慌"',
          '"actual": "追高进的,没等回踩"',
          "```", "",
          "跑满 20 笔后问自己一个问题:**亏损是因为信号错,还是因为我没按信号做?**",
          "前者要改规则,后者才是自动化能解决的问题。", "",
          "---", "",
          "*研究/学习用途,不构成投资建议。*"]
    return "\n".join(L)


def update(journal, candles_by_inst, now=None):
    """一次跑完:判定结局 + 写 learnings。返回本次判出的条数。"""
    n = resolve(journal, candles_by_inst, now)
    save(journal)
    with open(LEARNINGS_FILE, "w") as f:
        f.write(render_learnings(journal, now))
    return n
