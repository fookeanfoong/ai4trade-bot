#!/usr/bin/env python3
"""黄金按小时的波动画像 —— 用真实数据验证"最佳交易时段"的说法。

网上关于"黄金什么时候最好做"的文章绝大多数是券商营销页,结论互相抄。
与其信它们,不如把真实K线拉下来自己算一遍。

产出 reports/gold_sessions.md,回答三个问题:
  1. 每个 UTC 小时的平均真实波幅有多大?
  2. 当日最高/最低点最常在哪个小时形成?(这决定突破策略该在什么时候盯盘)
  3. 连续窗口里哪一段的波动占比最高?

用法:
    python3 gold_session_profile.py                  # 默认 GC=F 1h 2y
    python3 gold_session_profile.py --interval 15m --range 60d
"""
import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from urllib import request as urlrequest

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


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
            continue          # 带 None 的整根丢掉,不做前值填充
        bars.append({"t": int(t), "o": float(oo), "h": float(hh),
                     "l": float(ll), "c": float(cc)})
    bars.sort(key=lambda b: b["t"])
    return bars


def profile(bars):
    """按 UTC 小时聚合波幅;并统计当日高低点落在哪个小时。"""
    per_hour = defaultdict(lambda: {"range": 0.0, "body": 0.0, "n": 0})
    days = defaultdict(list)

    for b in bars:
        dt = datetime.fromtimestamp(b["t"], tz=timezone.utc)
        # 周末不算:黄金周六日基本不动,混进来会把均值稀释
        if dt.weekday() >= 5:
            continue
        h = dt.hour
        per_hour[h]["range"] += b["h"] - b["l"]
        per_hour[h]["body"] += abs(b["c"] - b["o"])
        per_hour[h]["n"] += 1
        days[dt.date()].append((h, b["h"], b["l"]))

    # 当日高/低在哪个小时形成
    hi_hour = defaultdict(int)
    lo_hour = defaultdict(int)
    full_days = 0
    for _, rows in days.items():
        if len(rows) < 12:        # 数据不全的日子不计入
            continue
        full_days += 1
        hi_hour[max(rows, key=lambda r: r[1])[0]] += 1
        lo_hour[min(rows, key=lambda r: r[2])[0]] += 1

    return per_hour, hi_hour, lo_hour, full_days


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="GC=F")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--range", dest="rng", default="2y")
    ap.add_argument("--server-offset", type=int, default=3,
                    help="经纪商服务器时区相对 UTC 的偏移(OANDA 夏令时为 +3)")
    a = ap.parse_args()

    bars = fetch(a.symbol, a.interval, a.rng)
    if not bars:
        raise SystemExit("没有取到数据")
    per_hour, hi_hour, lo_hour, full_days = profile(bars)

    total_range = sum(v["range"] for v in per_hour.values())
    t0 = datetime.fromtimestamp(bars[0]["t"], tz=timezone.utc)
    t1 = datetime.fromtimestamp(bars[-1]["t"], tz=timezone.utc)

    out = []
    out.append("# 黄金按小时波动画像（真实数据）\n")
    out.append(f"*生成于 {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}*\n")
    out.append(f"数据：**{a.symbol} · {a.interval} · {a.rng}** — "
               f"{t0:%Y-%m-%d} → {t1:%Y-%m-%d}，{len(bars)} 根（已剔除周末），"
               f"完整交易日 {full_days} 天\n")
    out.append("> 这张表不是从任何文章抄来的，是把真实K线按 UTC 小时聚合算出来的。\n")

    # 用 f-string 而不是 % 格式化：表头里本来就有字面量 "%"，
    # 和 %d 混在一起会被当成格式符（TypeError: not enough arguments）
    out.append(f"\n| UTC | 服务器(+{a.server_offset}) | 平均波幅$ | 占全天% | "
               f"当日最高在此 | 当日最低在此 | 主导时段 |")
    out.append("|---|---|---|---|---|---|---|")
    for h in range(24):
        v = per_hour.get(h)
        if not v or v["n"] == 0:
            continue
        avg = v["range"] / v["n"]
        share = 100.0 * v["range"] / total_range if total_range else 0
        hp = 100.0 * hi_hour.get(h, 0) / full_days if full_days else 0
        lp = 100.0 * lo_hour.get(h, 0) / full_days if full_days else 0
        if 0 <= h < 7:
            sess = "亚洲"
        elif 7 <= h < 12:
            sess = "伦敦"
        elif 12 <= h < 16:
            sess = "**伦敦+纽约重叠**"
        elif 16 <= h < 21:
            sess = "纽约"
        else:
            sess = "盘后"
        srv = (h + a.server_offset) % 24
        out.append(f"| {h:02d}:00 | {srv:02d}:00 | {avg:.2f} | {share:.1f}% | "
                   f"{hp:.0f}% | {lp:.0f}% | {sess} |")

    # 最优连续窗口
    out.append("\n## 连续窗口的波动占比\n")
    out.append("| 窗口(UTC) | 窗口(服务器) | 小时数 | 占全天波动 | 每小时平均 |")
    out.append("|---|---|---|---|---|")
    best = []
    for width in (4, 6, 8, 10, 13):
        top = None
        for start in range(24):
            hrs = [(start + i) % 24 for i in range(width)]
            s = sum(per_hour[h]["range"] for h in hrs if h in per_hour)
            if top is None or s > top[1]:
                top = (start, s)
        start, s = top
        end = (start + width) % 24
        share = 100.0 * s / total_range if total_range else 0
        out.append(f"| {start:02d}:00–{end:02d}:00 | "
                   f"{(start + a.server_offset) % 24:02d}:00–{(end + a.server_offset) % 24:02d}:00 | "
                   f"{width} | **{share:.1f}%** | {share / width:.1f}% |")
        best.append((width, start, end, share))

    out.append("\n## 结论\n")
    w, s, e, sh = best[1]          # 6 小时窗口
    out.append(f"- 波动最集中的 6 小时是 **UTC {s:02d}:00–{e:02d}:00**"
               f"（服务器 {(s + a.server_offset) % 24:02d}:00–{(e + a.server_offset) % 24:02d}:00），"
               f"占全天波动的 **{sh:.1f}%** —— 若均匀分布应为 25%。")
    quiet = sorted((h for h in per_hour if per_hour[h]["n"] > 0),
                   key=lambda h: per_hour[h]["range"] / per_hour[h]["n"])[:4]
    out.append(f"- 最安静的 4 个小时：UTC " +
               "、".join(f"{h:02d}:00" for h in sorted(quiet)) +
               " —— 这几个小时点差通常最宽而波幅最小，是成本最不划算的时段。")

    os.makedirs("reports", exist_ok=True)
    path = "reports/gold_sessions.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\n-> 已写入 {path}")


if __name__ == "__main__":
    main()
