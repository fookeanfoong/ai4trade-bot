#!/usr/bin/env python3
"""用历史 5 分钟行情回测加密策略 -> reports/backtest.md。

**存在的理由**:到目前为止,每一个参数(RSI 门槛、盈亏比 1.5、20 分钟最短持有、
$0.50 保底)都是推理出来的,没有一个用数据验证过。26 笔实盘不足以判断
——业界经验是至少 100 笔。这个脚本用几个月的历史数据把笔数补上,
在动真钱之前先回答:**这套逻辑扣完手续费到底有没有正期望**。

复用真实代码,不重写一份:
  - 信号:直接调用 generate_signals_crypto.build_setup(),所以回测和实盘
    用的是同一套判定。改了策略,回测自动跟着变。
  - 离场:复刻引擎的规则(保底/追踪/止损/最短持有),在下面 simulate() 里。

刻意保守的地方:
  - 入场按**下一根 K 线的开盘价**成交,不是当根收盘价。用信号出现那根自己的
    价格成交等于偷看未来,回测会好看得离谱。
  - 止损/目标按**当根 K 线的最低/最高价**判定是否触及,同根同时触及时算止损
    (悲观假设),不假设自己总能拿到好的那一边。
  - 手续费两边都扣,费率可配。

用法:
    python3 backtest_crypto.py                 # 默认 60 天
    python3 backtest_crypto.py --days 30 --fee 0.0025
"""

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import generate_signals_crypto as G          # noqa: E402  信号逻辑,与实盘同源
import quotes_crypto as Q                    # noqa: E402  指标计算,与实盘同源

REPORT = ROOT / "reports" / "backtest.md"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36")


def fetch_bars(bare: str, days: int) -> list:
    """Yahoo 5m K 线。5 分钟粒度最多只能取约 60 天,所以 days 超过会被截断。"""
    rng = f"{min(days, 60)}d"
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{Q.yahoo_symbol(bare)}"
           f"?range={rng}&interval=5m")
    req = urlrequest.Request(url, headers={"User-Agent": BROWSER_UA, "Accept": "application/json"})
    with urlrequest.urlopen(req, timeout=60) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    res = payload["chart"]["result"][0]
    q = res["indicators"]["quote"][0]
    ts = res.get("timestamp") or []
    bars = []
    for t, o, h, l, c, v in zip(ts, q.get("open", []), q.get("high", []),
                                q.get("low", []), q.get("close", []), q.get("volume", [])):
        if None in (o, h, l, c):
            continue
        bars.append({"t": t, "o": o, "h": h, "l": l, "c": c, "v": v or 0})
    return bars


def quote_at(bare: str, bars: list, i: int) -> dict:
    """重建「第 i 根 K 线收盘时 quotes_crypto.py 会算出什么」。

    只用 bars[:i+1],绝不碰未来的数据——回测最容易出错的地方就是这里。"""
    win = bars[:i + 1]
    if len(win) < 25:
        return {}
    closes = [b["c"] for b in win]
    highs = [b["h"] for b in win]
    lows = [b["l"] for b in win]
    vols = [b["v"] for b in win]
    last = closes[-1]

    a = win[-Q.ANALYSIS_BARS:] if len(win) >= Q.ANALYSIS_BARS else win
    support = round(min(b["l"] for b in a), 6)
    resistance = round(max(b["h"] for b in a), 6)

    bb = Q.bollinger(closes)
    e9, e21 = Q.ema(closes[-40:], 9), Q.ema(closes[-60:], 21)
    trend = None
    if e9 is not None and e21 is not None:
        trend = "up" if e9 > e21 * 1.0005 else ("down" if e9 < e21 * 0.9995 else "flat")
    vol_avg = sum(vols[-20:]) / len(vols[-20:]) if vols else None
    vol_ratio = round(vols[-1] / vol_avg, 2) if (vols and vol_avg) else None

    win_high = max(highs[-Q.ANALYSIS_BARS:]) if highs else None
    out = {
        "symbol": bare, "last": last,
        "change_pct": None, "chg_1h_pct": None, "chg_15m_pct": None,
        "drop_from_high_pct": (round((last - win_high) / win_high * 100, 2)
                               if win_high else None),
        "rsi": Q.rsi(closes), "support": support, "resistance": resistance,
        "trend": trend, "vol_ratio": vol_ratio, "chg_3d_pct": None,
    }
    if bb:
        mid, up, lo, _ = bb
        out.update({"sma20": round(mid, 6), "bb_upper": round(up, 6),
                    "bb_lower": round(lo, 6), "pct_b": Q.pct_b(last, up, lo)})
    return out


def gross_for_net(net_usd: float, notional: float, fee: float) -> float:
    return (net_usd + 2.0 * fee * notional) / (notional * (1.0 - fee))


def simulate(sym: str, bars: list, args) -> list:
    """在一个币上按顺序走完所有 K 线。同时最多持有一个仓位。"""
    trades = []
    pos = None
    benched_day = None

    for i in range(30, len(bars) - 1):
        bar = bars[i]
        nxt = bars[i + 1]
        day = dt.datetime.utcfromtimestamp(bar["t"]).strftime("%Y-%m-%d")

        # ---- 管理已有仓位:先看止损,再看追踪止盈(同根 K 线同时触及算止损)----
        if pos:
            held_min = (bar["t"] - pos["opened_t"]) / 60.0
            if bar["l"] <= pos["stop"]:
                trades.append(close(pos, pos["stop"], "STOP", bar["t"], args.fee))
                pos, benched_day = None, day
                continue
            if not pos["armed"] and bar["h"] >= pos["floor"]:
                pos["armed"] = True
            if pos["armed"]:
                pos["peak"] = max(pos["peak"], bar["h"])
                trail = max(pos["peak"] * (1 - args.giveback), pos["floor"])
                if bar["l"] <= trail:
                    trades.append(close(pos, trail, "TRAIL", bar["t"], args.fee))
                    pos, benched_day = None, day
                    continue
            # 信号失效离场,受最短持有时间保护(和实盘同一条规则)
            if held_min >= args.min_hold:
                q = quote_at(sym, bars, i)
                if q and G.build_setup(sym, q, False) is None:
                    trades.append(close(pos, nxt["o"], "SIGNAL_GONE", bar["t"], args.fee))
                    pos, benched_day = None, day
            continue

        # ---- 找新入场 ----
        if benched_day == day:      # 当天已经交易过这个币,不再进(和实盘的 bench 一致)
            continue
        q = quote_at(sym, bars, i)
        if not q:
            continue
        setup = G.build_setup(sym, q, False)
        if not setup:
            continue

        entry = nxt["o"]            # 下一根开盘成交,不偷看未来
        notional = args.book / args.names
        g = gross_for_net(args.floor_usd, notional, args.fee)
        if g > args.max_move:
            continue
        stop_pct = min(float(setup["stop_pct"]), g / args.min_rr)
        pos = {"sym": sym, "setup": setup["setup"], "conf": setup["confidence"],
               "entry": entry, "qty": notional / entry, "opened_t": nxt["t"],
               "stop": entry * (1 - stop_pct), "floor": entry * (1 + g),
               "peak": entry, "armed": False}

    return trades


def close(pos, price, why, t, fee):
    cost = pos["entry"] * pos["qty"]
    proceeds = price * pos["qty"]
    return {"sym": pos["sym"], "setup": pos["setup"], "conf": pos["conf"],
            "why": why, "entry": pos["entry"], "exit": price,
            "held_min": round((t - pos["opened_t"]) / 60.0, 1),
            "net": (proceeds - cost) - (cost + proceeds) * fee,
            "gross": proceeds - cost, "fees": (cost + proceeds) * fee}


def group_table(title, key, trades):
    from collections import defaultdict
    g = defaultdict(list)
    for t in trades:
        g[t[key]].append(t)
    out = [f"### {title}", "", "| 分组 | 笔数 | 净盈亏 | 胜率 | 期望值/笔 |", "|---|---:|---:|---:|---:|"]
    for k, rows in sorted(g.items(), key=lambda kv: sum(x["net"] for x in kv[1])):
        net = sum(x["net"] for x in rows)
        wr = sum(1 for x in rows if x["net"] > 0) / len(rows) * 100
        out.append(f"| {k} | {len(rows)} | ${net:+.2f} | {wr:.0f}% | ${net/len(rows):+.3f} |")
    out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--fee", type=float, default=0.0020)
    ap.add_argument("--book", type=float, default=200.0)
    ap.add_argument("--names", type=int, default=2)
    ap.add_argument("--floor-usd", type=float, default=0.50)
    ap.add_argument("--giveback", type=float, default=0.006)
    ap.add_argument("--min-hold", type=float, default=20.0)
    ap.add_argument("--min-rr", type=float, default=1.0)
    ap.add_argument("--max-move", type=float, default=0.035)
    args = ap.parse_args()

    all_trades, errors, spans = [], {}, {}
    for sym in Q.WATCHLIST:
        try:
            bars = fetch_bars(sym, args.days)
        except Exception as e:
            errors[sym] = str(e)[:120]
            continue
        if len(bars) < 60:
            errors[sym] = f"only {len(bars)} bars"
            continue
        spans[sym] = (dt.datetime.utcfromtimestamp(bars[0]["t"]).strftime("%Y-%m-%d"),
                      dt.datetime.utcfromtimestamp(bars[-1]["t"]).strftime("%Y-%m-%d"),
                      len(bars))
        all_trades += simulate(sym, bars, args)

    lines = ["# 回测报告", "",
             f"生成于 {dt.datetime.utcnow().isoformat(timespec='seconds')}Z", ""]
    if spans:
        s = next(iter(spans.values()))
        lines += [f"数据区间 {s[0]} ~ {s[1]}，每个币约 {s[2]} 根 5 分钟 K 线。",
                  f"参数：手续费 {args.fee*100:.2f}%/边 · 本金 ${args.book:.0f} · "
                  f"{args.names} 个仓 · 保底 ${args.floor_usd:.2f} · "
                  f"回撤 {args.giveback*100:.1f}% · 最短持有 {args.min_hold:.0f}m", ""]
    if errors:
        lines += ["> ⚠️ 取数失败：" + "；".join(f"{k}（{v}）" for k, v in errors.items()), ""]

    if not all_trades:
        lines += ["## 结果", "", "**这段区间内一笔都没开。**", "",
                  "入场条件太严，或者行情不符合。这本身是结论：策略在这段行情里"
                  "无事可做，而不是它赚钱或亏钱。", ""]
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return 0

    n = len(all_trades)
    net = sum(t["net"] for t in all_trades)
    gross = sum(t["gross"] for t in all_trades)
    fees = sum(t["fees"] for t in all_trades)
    wins = [t["net"] for t in all_trades if t["net"] > 0]
    losses = [t["net"] for t in all_trades if t["net"] <= 0]

    lines += ["## 总体（全部为扣费后净额）", "",
              f"- 交易 **{n} 笔**",
              f"- 净盈亏 **${net:+.2f}**（占本金 {net/args.book*100:+.1f}%）",
              f"- 胜率 **{len(wins)/n*100:.0f}%**",
              f"- **期望值 ${net/n:+.4f}/笔** ← 决定性的数字",
              f"- 均盈 ${(sum(wins)/len(wins) if wins else 0):+.2f} / "
              f"均亏 ${(sum(losses)/len(losses) if losses else 0):+.2f}",
              f"- 毛利 ${gross:+.2f} − 手续费 ${fees:.2f} = 净 ${net:+.2f}", ""]

    verdict = ("**正期望** — 这套逻辑在这段历史行情里扣完手续费还剩钱。"
               if net > 0 else
               "**负期望** — 这套逻辑在这段历史行情里扣完手续费是亏的。"
               "调参数之前,先接受这个结论:它现在没有优势。")
    lines += ["## 结论", "", verdict, ""]
    if n < 100:
        lines += [f"> ⚠️ 只有 {n} 笔,低于 100 笔的经验门槛,这个结论仍可能是运气。", ""]
    if gross <= 0:
        lines += ["> 毛利本身就是负的 —— 问题不在手续费,在信号没有方向性优势。"
                  "降手续费救不了它。", ""]
    elif net <= 0:
        lines += [f"> 毛利是正的(${gross:+.2f}),但手续费(${fees:.2f})把它吃光了。"
                  "方向判断有微弱优势,输在交易太频繁 —— 应该减少次数、放大目标。", ""]

    lines += group_table("按 setup", "setup", all_trades)
    lines += group_table("按离场原因", "why", all_trades)
    lines += group_table("按币种", "sym", all_trades)

    held = sorted(t["held_min"] for t in all_trades)
    lines += ["### 持仓时长", "",
              f"- 中位数 {held[len(held)//2]:.0f} 分钟 · 最长 {held[-1]:.0f} 分钟", ""]

    text = "\n".join(lines)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
