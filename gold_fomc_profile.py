#!/usr/bin/env python3
"""FOMC 当天黄金的实际表现 —— 用真实数据检验"加息=金价跌"这类说法。

教科书说法是"利率上升 -> 持有黄金的机会成本上升 -> 金价跌"。
但那讲的是**实际利率**和**预期之外的部分**;当市场已经把 80% 的加息概率定进价格,
真正推动行情的是"意外",不是"加息"本身。方向猜不了,但有两件事可以量出来:

  1. FOMC 当天的波幅比平常大多少?  -> 决定要不要降仓 / 提前清仓
  2. 决议时点前后几小时的走势分布?  -> 决定黑名单窗口该开多宽
  3. 涨跌各占多少?                 -> 检验"加息必跌"到底成不成立

产出 reports/gold_fomc.md。

用法:
    python3 gold_fomc_profile.py --interval 1h --range 2y
"""
import argparse
import json
import os
from datetime import datetime, timezone
from urllib import request as urlrequest

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

# FOMC 决议日(第二天出结果的那一天)。决议 14:00 ET,发布会 14:30 ET。
FOMC_DAYS = [
    "2024-01-31", "2024-03-20", "2024-05-01", "2024-06-12",
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16",
]


def fetch(symbol="GC=F", interval="1h", rng="2y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={rng}&interval={interval}")
    req = urlrequest.Request(url, headers={"User-Agent": BROWSER_UA,
                                           "Accept": "application/json"})
    with urlrequest.urlopen(req, timeout=40) as r:
        payload = json.loads(r.read().decode())
    res = payload["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    o, h, l, c = (q.get("open") or [], q.get("high") or [],
                  q.get("low") or [], q.get("close") or [])
    bars = []
    for i, t in enumerate(ts):
        try:
            oo, hh, ll, cc = o[i], h[i], l[i], c[i]
        except IndexError:
            continue
        if None in (oo, hh, ll, cc):
            continue
        bars.append({"t": datetime.fromtimestamp(int(t), tz=timezone.utc),
                     "o": float(oo), "h": float(hh), "l": float(ll), "c": float(cc)})
    bars.sort(key=lambda b: b["t"])
    return bars


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="GC=F")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--range", dest="rng", default="2y")
    ap.add_argument("--server-offset", type=int, default=3)
    a = ap.parse_args()

    bars = fetch(a.symbol, a.interval, a.rng)
    if not bars:
        raise SystemExit("没有取到数据")

    fomc = set(FOMC_DAYS)
    by_day = {}
    for b in bars:
        by_day.setdefault(b["t"].date().isoformat(), []).append(b)

    # 只保留数据完整的交易日
    days = {d: v for d, v in by_day.items() if len(v) >= 12}
    fomc_days = {d: v for d, v in days.items() if d in fomc}
    norm_days = {d: v for d, v in days.items() if d not in fomc}

    def day_range(v):
        return max(x["h"] for x in v) - min(x["l"] for x in v)

    def day_move(v):
        return v[-1]["c"] - v[0]["o"]

    fr = [day_range(v) for v in fomc_days.values()]
    nr = [day_range(v) for v in norm_days.values()]
    fm = [day_move(v) for v in fomc_days.values()]
    nm = [day_move(v) for v in norm_days.values()]

    out = []
    out.append("# FOMC 当天黄金实测\n")
    out.append(f"*生成于 {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}*\n")
    out.append(f"数据：**{a.symbol} · {a.interval} · {a.rng}** — "
               f"命中 FOMC 决议日 **{len(fomc_days)}** 天，普通交易日 {len(norm_days)} 天\n")
    out.append("> 决议 14:00 ET / 发布会 14:30 ET = UTC 18:00 / 18:30 "
               f"= 服务器(+{a.server_offset}) **{(18+a.server_offset)%24:02d}:00 / "
               f"{(18+a.server_offset)%24:02d}:30**\n")

    if not fr:
        out.append("\n⚠️ 数据区间内没有命中 FOMC 日，无法比较。\n")
    else:
        avg_f, avg_n = sum(fr)/len(fr), sum(nr)/len(nr)
        out.append("\n## 一、波幅：FOMC 日 vs 平常\n")
        out.append("| | 天数 | 平均日波幅 | 中位数 | 最大 |")
        out.append("|---|---|---|---|---|")
        for name, arr in (("FOMC 日", fr), ("普通日", nr)):
            srt = sorted(arr)
            out.append(f"| {name} | {len(arr)} | ${sum(arr)/len(arr):.2f} | "
                       f"${srt[len(srt)//2]:.2f} | ${max(arr):.2f} |")
        out.append(f"\n**FOMC 日波幅是平常的 {avg_f/avg_n:.2f} 倍。**")

        # 涨跌分布 —— 检验"加息必跌"
        up = sum(1 for m in fm if m > 0)
        out.append("\n## 二、方向：涨跌各占多少\n")
        out.append(f"- FOMC 日收涨 **{up}/{len(fm)}**（{100*up/len(fm):.0f}%），"
                   f"收跌 {len(fm)-up}/{len(fm)}")
        upn = sum(1 for m in nm if m > 0)
        out.append(f"- 对照：普通日收涨 {upn}/{len(nm)}（{100*upn/len(nm):.0f}%）")
        pct_up = 100.0 * up / len(fm)
        verdict = "没有明显方向性偏差" if 35 < pct_up < 65 else "存在方向性偏差，但样本极小"
        out.append(f"\n> 若「加息=金价跌」成立，FOMC 日应显著偏向下跌。"
                   f"实测 {pct_up:.0f}% 收涨 —— {verdict}。")

        # 决议时点前后逐小时
        out.append("\n## 三、决议前后逐小时波幅（UTC）\n")
        out.append("| UTC | 服务器 | FOMC 日均波幅 | 普通日均波幅 | 倍数 |")
        out.append("|---|---|---|---|---|")
        for h in range(14, 24):
            fh = [b["h"]-b["l"] for v in fomc_days.values() for b in v if b["t"].hour == h]
            nh = [b["h"]-b["l"] for v in norm_days.values() for b in v if b["t"].hour == h]
            if not fh or not nh:
                continue
            af, an = sum(fh)/len(fh), sum(nh)/len(nh)
            mark = " ←决议" if h == 18 else (" ←发布会" if h == 19 else "")
            out.append(f"| {h:02d}:00 | {(h+a.server_offset)%24:02d}:00 | ${af:.2f} | "
                       f"${an:.2f} | **{af/an:.2f}×**{mark} |")

    os.makedirs("reports", exist_ok=True)
    path = "reports/gold_fomc.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\n-> 已写入 {path}")


if __name__ == "__main__":
    main()
