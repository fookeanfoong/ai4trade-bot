#!/usr/bin/env python3
"""黄金"停滞"到底多常见 —— 用真实分钟K线量 InpStallMinutes 该设多少。

EA 的停滞离场规则是：有利润 + 最近 N 分钟的高低差 < ATR × k -> 立刻平仓。
N 设得太短的话，这条规则会退化成"到点就走"：因为黄金"一分钟没怎么动"
本来就是常态，不是信号。

这个脚本回答一个很具体的问题：
    对每个窗口长度 N，随便挑一个时刻，"最近 N 分钟高低差 < ATR × k" 的概率是多少？

命中率接近 100% = 这个 N 没有区分度，等于无条件平仓。
命中率个位数   = 这个 N 太严，规则几乎不会触发。
要找的是中间那一段。

ATR 口径和 EA 一致：5 分钟K线、14 周期。

产出 reports/gold_stall.md。

用法：
    python3 gold_stall_profile.py --symbol GC=F --k 0.25
"""
import argparse
import json
import os
from datetime import datetime, timezone
from urllib import request as urlrequest

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

WINDOWS = [1, 2, 3, 5, 10, 15, 20, 30, 45, 60]


def fetch(symbol, interval, rng):
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


def atr_series(bars, period=14):
    """经典 Wilder ATR，返回与 bars 等长的列表（前 period 个为 None）。"""
    trs = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b["h"] - b["l"])
            continue
        pc = bars[i - 1]["c"]
        trs.append(max(b["h"] - b["l"], abs(b["h"] - pc), abs(b["l"] - pc)))
    out = [None] * len(bars)
    if len(trs) < period:
        return out
    cur = sum(trs[:period]) / period
    out[period - 1] = cur
    for i in range(period, len(trs)):
        cur = (cur * (period - 1) + trs[i]) / period
        out[i] = cur
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="GC=F")
    ap.add_argument("--k", type=float, default=0.25,
                    help="停滞阈值：窗口高低差 < ATR × k")
    a = ap.parse_args()

    # Yahoo 的 1m 只给最近几天；5m 给得多一些，用来算 ATR
    m1 = fetch(a.symbol, "1m", "7d")
    m5 = fetch(a.symbol, "5m", "1mo")
    if len(m1) < 200 or len(m5) < 50:
        raise SystemExit(f"数据不足：1m={len(m1)} 根，5m={len(m5)} 根")

    atr5 = atr_series(m5, 14)
    # 把 5m 的 ATR 按时间对齐到 1m：取该时刻之前最近一个已收盘的 5m ATR
    stamps = [(m5[i]["t"], atr5[i]) for i in range(len(m5)) if atr5[i] is not None]
    if not stamps:
        raise SystemExit("ATR 算不出来")

    def atr_at(t):
        lo, hi, best = 0, len(stamps) - 1, None
        while lo <= hi:
            mid = (lo + hi) // 2
            if stamps[mid][0] <= t:
                best = stamps[mid][1]
                lo = mid + 1
            else:
                hi = mid - 1
        return best

    rows = []
    for n in WINDOWS:
        hit = tot = 0
        rng_sum = 0.0
        for i in range(n, len(m1)):
            win = m1[i - n:i]
            # 跨越缺口（收盘/周末）的窗口不算
            span = (win[-1]["t"] - win[0]["t"]).total_seconds()
            if span > (n + 2) * 60:
                continue
            atr = atr_at(win[-1]["t"])
            if not atr or atr <= 0:
                continue
            rng = max(w["h"] for w in win) - min(w["l"] for w in win)
            tot += 1
            rng_sum += rng
            if rng < a.k * atr:
                hit += 1
        if tot:
            rows.append((n, tot, 100.0 * hit / tot, rng_sum / tot))

    out = []
    out.append("# 黄金「停滞」实测 —— InpStallMinutes 该设多少\n")
    out.append(f"*生成于 {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}*\n")
    out.append(f"数据：**{a.symbol}** · 1m {len(m1)} 根（约 7 天）· "
               f"ATR 用 5m/14 周期，与 EA 口径一致\n")
    out.append(f"停滞定义：窗口内高低差 < ATR × **{a.k}**\n")
    out.append("\n## 各窗口长度的命中率\n")
    out.append("| 窗口(分钟) | 样本数 | 判为停滞 | 平均窗口波幅 |")
    out.append("|---|---|---|---|")
    for n, tot, pct, avg in rows:
        mark = ""
        if pct >= 80:
            mark = " ← 几乎无条件触发"
        elif pct <= 5:
            mark = " ← 几乎不会触发"
        out.append(f"| {n} | {tot} | **{pct:.1f}%** | ${avg:.2f} |{mark}")

    # 第二张表：反过来问 —— 每个窗口要多大的 k 才落到 ~25% 命中率
    out.append("\n## 每个窗口对应的 k（让命中率落在 ~25%）\n")
    out.append("这张表比上一张更实用：**k 不能跨窗口通用**。窗口越长，"
               "价格自然走得越远，同一个 k 就会越难命中。想换窗口长度，"
               "k 必须跟着换 —— 直接从这里查。\n")
    out.append("| 窗口(分钟) | 建议 k | 对应命中率 |")
    out.append("|---|---|---|")
    for n in WINDOWS:
        wins = []
        for i in range(n, len(m1)):
            win = m1[i - n:i]
            span = (win[-1]["t"] - win[0]["t"]).total_seconds()
            if span > (n + 2) * 60:
                continue
            atr = atr_at(win[-1]["t"])
            if not atr or atr <= 0:
                continue
            rng = max(w["h"] for w in win) - min(w["l"] for w in win)
            wins.append(rng / atr)
        if len(wins) < 30:
            continue
        wins.sort()
        q = wins[int(0.25 * len(wins))]          # 25 分位数就是那个 k
        out.append(f"| {n} | **{q:.2f}** | 25% |")

    out.append("\n## 怎么读这张表\n")
    out.append("命中率就是「这条规则平均多久生效一次」的直接度量：\n")
    out.append("- **接近 100%** —— 这个窗口没有区分度。规则退化成「有利润就平」，"
               "等于把每个赢单都砍在门槛上，盈亏比被拿走。")
    out.append("- **个位数** —— 窗口太严，规则基本是死代码，加了等于没加。")
    out.append("- 要找的是**中间那一段**：既真的能筛掉磨盘的单子，"
               "又不会把还在走的趋势单一起砍了。\n")
    if rows:
        good = [r for r in rows if 10.0 <= r[2] <= 45.0]
        if good:
            out.append(f"> 本次数据下，落在 10%~45% 这个区间的窗口是："
                       f"**{'、'.join(str(r[0]) + ' 分钟' for r in good)}**。")
        else:
            out.append("> ⚠️ 本次数据下没有窗口落在 10%~45%。"
                       f"说明 k={a.k} 这个阈值本身要调，而不是调窗口长度。")
    out.append("\n> ⚠️ 只有约 7 天的分钟数据（Yahoo 的 1m 上限），"
               "覆盖不到不同的波动环境。这是**量级参考**，不是定论。")

    os.makedirs("reports", exist_ok=True)
    path = "reports/gold_stall.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("\n".join(out))
    print(f"\n-> 已写入 {path}")


if __name__ == "__main__":
    main()
