#!/usr/bin/env python3
"""ScalperGuard 成交分析 —— 把 EA 日志的标签和真实盈亏对起来算分组期望值。

回答的是这些问题（都不是"赚了多少"，那个看账户就行）：
  - 净利是不是**一两笔扛起来的**？（小样本最常见的假象）
  - 四条入场路径里哪条真的赚钱？路径 D（宽松）是不是在拖后腿？
  - 带"冲突"的单是不是真的更差？（决定 InpConflictAsVeto 该不该改回 true）
  - 市场质量闸门若开着，会不会反而砍掉赚钱的单？
  - 哪个时段/分级在贡献，哪个在消耗？

用法：
    python3 analyze_scalperguard.py --log XAUUSD_ScalperGuard_log.csv \
                                    --history ReportHistory.csv

  --log      来自 MQL5\\Files\\ 的 EA 决策日志（提供标签：路径/冲突/质量/分级）
  --history  MT5「历史」标签右键 -> 报告 导出的成交历史（提供权威盈亏）

只给 --log 也能跑，但那样只有信号侧统计，没有盈亏 —— 日志里的 CLOSE 行
在旧版本中不含金额（新版已补上）。
"""
import argparse
import csv
import io
import re
import sys
from collections import defaultdict
from datetime import datetime


# ------------------------------------------------------------------ 解析
def parse_log(path):
    """EA 日志是 3 列 CSV：时间, 标签, 正文。正文里可能含逗号，所以只切前两个。"""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\r\n")
            if not line:
                continue
            parts = line.split(",", 2)
            if len(parts) < 3:
                continue
            ts, tag, msg = parts[0].strip(), parts[1].strip(), parts[2].strip()
            try:
                t = datetime.strptime(ts, "%Y.%m.%d %H:%M:%S")
            except ValueError:
                continue
            rows.append({"t": t, "tag": tag, "msg": msg})
    return rows


def trigger_path(note):
    """从成交备注里判断是哪条入场路径。四条路径的措辞在 EA 里是固定的。"""
    if "扫损反手" in note:
        return "C 扫损反手"
    if "宽松顺势" in note:
        return "D 宽松顺势"
    if "突破" in note and "回踩" in note:
        return "A 突破回踩"
    if "回调" in note or "反弹" in note:
        return "B 趋势回调"
    return "未标注"


def extract_opens(rows):
    """[OPEN] 行 -> 每笔的标签。新版带 #单号，旧版没有，两种都吃。"""
    opens = {}
    order = []
    last = None
    for r in rows:
        if r["tag"] == "OPEN":
            m = re.match(r"#(\d+)\s+(BUY|SELL)", r["msg"])
            tk = m.group(1) if m else None
            side = m.group(2) if m else ("BUY" if "BUY" in r["msg"] else "SELL")
            grade = re.search(r"(A\+|A|B)级\s+(\d+)/10", r["msg"])
            rr = re.search(r"RR\s+([\d.]+)", r["msg"])
            risk = re.search(r"风险 \$([\d.]+)", r["msg"])
            lot = re.search(r"([\d.]+)\s*手", r["msg"])
            rec = {
                "t": r["t"], "ticket": tk, "side": side,
                "path": trigger_path(r["msg"]),
                "conflict": "有冲突" if "冲突:" in r["msg"] else
                            ("无冲突" if "无冲突" in r["msg"] else "未标注"),
                "grade": grade.group(1) if grade else "?",
                "score": int(grade.group(2)) if grade else None,
                "rr": float(rr.group(1)) if rr else None,
                "risk": float(risk.group(1)) if risk else None,
                "lot": float(lot.group(1)) if lot else None,
                "quality": "未标注",
                "hour": r["t"].hour,
            }
            key = tk or f"t{len(order)}"
            opens[key] = rec
            order.append(key)
            last = key
        elif r["tag"] == "QUALITY" and last:
            m = re.match(r"#(\d+)\s", r["msg"])
            key = m.group(1) if m and m.group(1) in opens else last
            body = re.sub(r"^#\d+\s*", "", r["msg"])
            opens[key]["quality"] = "质量BAD" if "BAD|" in body else \
                                    ("质量OK" if "OK|" in body else "未标注")
    return opens, order


def parse_history(path):
    """MT5 成交历史。支持导出的 CSV/HTML —— 只挑出 (单号, 盈亏) 两列。"""
    raw = open(path, encoding="utf-8", errors="replace").read()
    deals = defaultdict(float)

    if "<" in raw[:2000] and "table" in raw.lower()[:5000]:      # HTML 报告
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", raw, re.S | re.I)
        cells = [re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip() for c in cells]
        # 在单元格流里找「长数字(单号) ... 金额」的模式过于脆弱，
        # 所以 HTML 只做兜底：把所有形如 位置单号 的行按顺序配对。
        nums = [c for c in cells if re.fullmatch(r"\d{6,}", c)]
        amts = [c for c in cells if re.fullmatch(r"-?[\d\s,]+\.\d{2}", c)]
        if len(nums) == len(amts):
            for n, a in zip(nums, amts):
                deals[n] += float(a.replace(" ", "").replace(",", ""))
        else:
            print("⚠️ HTML 报告结构无法可靠解析，请改导出 XLSX/CSV 或直接发我原文件",
                  file=sys.stderr)
    else:                                                        # CSV
        rdr = csv.reader(io.StringIO(raw))
        for row in rdr:
            if len(row) < 3:
                continue
            tk = None
            for c in row:
                if re.fullmatch(r"\d{6,}", c.strip()):
                    tk = c.strip()
                    break
            if not tk:
                continue
            for c in reversed(row):
                c2 = c.strip().replace(" ", "").replace(",", "")
                if re.fullmatch(r"-?\d+\.\d{2}", c2):
                    deals[tk] += float(c2)
                    break
    return dict(deals)


# ------------------------------------------------------------------ 统计
def stats(pnls):
    n = len(pnls)
    if n == 0:
        return None
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gp, gl = sum(wins), -sum(losses)
    eq = peak = dd = 0.0
    streak = maxstreak = 0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
        streak = 0 if p > 0 else streak + 1
        maxstreak = max(maxstreak, streak)
    return {
        "n": n, "wins": len(wins), "losses": len(losses),
        "wr": 100.0 * len(wins) / n, "net": sum(pnls),
        "gp": gp, "gl": gl,
        "pf": (gp / gl) if gl > 0 else float("inf"),
        "avg": sum(pnls) / n,
        "avgw": (gp / len(wins)) if wins else 0.0,
        "avgl": (gl / len(losses)) if losses else 0.0,
        "dd": dd, "maxstreak": maxstreak,
        "best": max(pnls), "worst": min(pnls),
    }


def table(title, groups):
    print(f"\n## {title}\n")
    print("| 分组 | 笔数 | 胜率 | 净利 | 均值/笔 | 盈亏比 |")
    print("|---|---|---|---|---|---|")
    for k, pnls in sorted(groups.items(), key=lambda kv: -sum(kv[1])):
        s = stats(pnls)
        if not s:
            continue
        pf = "∞" if s["pf"] == float("inf") else f"{s['pf']:.2f}"
        print(f"| {k} | {s['n']} | {s['wr']:.0f}% | ${s['net']:+.2f} | "
              f"${s['avg']:+.2f} | {pf} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--history")
    a = ap.parse_args()

    rows = parse_log(a.log)
    opens, order = extract_opens(rows)
    print(f"# ScalperGuard 成交分析\n")
    print(f"日志 {len(rows)} 行，识别到 {len(opens)} 笔开仓记录。")

    if not a.history:
        print("\n⚠️ 未提供 --history，只能给信号侧分布，没有盈亏。")
        for name, key in [("入场路径", "path"), ("冲突", "conflict"),
                          ("行情质量", "quality"), ("分级", "grade")]:
            c = defaultdict(int)
            for r in opens.values():
                c[r[key]] += 1
            print(f"\n## {name}分布")
            for k, v in sorted(c.items(), key=lambda kv: -kv[1]):
                print(f"  {k:12} {v} 笔")
        return

    deals = parse_history(a.history)
    print(f"成交历史 {len(deals)} 笔。")

    matched = []
    for key, rec in opens.items():
        pnl = deals.get(rec["ticket"]) if rec["ticket"] else None
        if pnl is not None:
            matched.append((rec, pnl))
    if not matched:
        print("\n⚠️ 日志与历史对不上（旧版 [OPEN] 行没有单号）。")
        print("   本次只能按顺序粗配：把两边按时间排序后一一对应。")
        pnls = list(deals.values())
        recs = [opens[k] for k in order]
        matched = list(zip(recs, pnls))[:min(len(recs), len(pnls))]

    all_pnl = [p for _, p in matched]
    s = stats(all_pnl)
    print(f"\n## 总览\n")
    print(f"- 笔数 **{s['n']}** ｜ 胜 {s['wins']} 负 {s['losses']} ｜ 胜率 **{s['wr']:.1f}%**")
    pf_txt = "∞" if s["pf"] == float("inf") else f"{s['pf']:.2f}"
    print(f"- 净利 **${s['net']:+.2f}** ｜ 毛盈 ${s['gp']:.2f} 毛亏 ${s['gl']:.2f} ｜ "
          f"盈亏比 **{pf_txt}**")
    print(f"- 均盈 ${s['avgw']:.2f} ｜ 均亏 ${s['avgl']:.2f} ｜ 均值/笔 ${s['avg']:+.2f}")
    print(f"- 最大回撤 ${s['dd']:.2f} ｜ 最长连亏 {s['maxstreak']} 笔")
    print(f"- 最大单笔盈利 ${s['best']:+.2f} ｜ 最大单笔亏损 ${s['worst']:+.2f}")

    # 小样本最重要的一条检查
    if s["net"] > 0 and s["best"] > 0:
        share = 100.0 * s["best"] / s["net"]
        top3 = sum(sorted(all_pnl, reverse=True)[:3])
        share3 = 100.0 * top3 / s["net"]
        print(f"\n### ⚠️ 集中度检查（小样本最容易被这一条骗）\n")
        print(f"- 最赚的 **1** 笔占净利 **{share:.0f}%**")
        print(f"- 最赚的 **3** 笔占净利 **{share3:.0f}%**")
        if share3 > 80:
            print(f"\n  > 前 3 笔贡献了 {share3:.0f}% —— **这不是一个策略的业绩，"
                  f"是几笔行情的业绩**。去掉它们后剩下的才是常态表现。")
        rest = sorted(all_pnl, reverse=True)[3:]
        if rest:
            rs = stats(rest)
            print(f"- 去掉最赚的 3 笔后：{rs['n']} 笔，净利 ${rs['net']:+.2f}，"
                  f"胜率 {rs['wr']:.0f}%")

    for name, key in [("入场路径", "path"), ("有无冲突", "conflict"),
                      ("行情质量", "quality"), ("Setup 分级", "grade")]:
        g = defaultdict(list)
        for rec, pnl in matched:
            g[rec[key]].append(pnl)
        table(f"按{name}", g)

    g = defaultdict(list)
    for rec, pnl in matched:
        g[f"{rec['hour']:02d}:00"].append(pnl)
    table("按服务器小时", g)

    print(f"\n---\n")
    print(f"**样本量提醒**：{s['n']} 笔的胜率误差约 ±{50/max(s['n'],1)**0.5:.0f} 个百分点。")
    print("分组之后每组只剩几笔，那些分组数字**只能用来发现明显异常**"
          "（比如某条路径全亏），不足以支撑\"关掉哪条路径\"这种决定。")
    print("要做参数决策，每组至少 30 笔。")


if __name__ == "__main__":
    main()
