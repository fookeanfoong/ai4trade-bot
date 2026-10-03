#!/usr/bin/env python3
"""CryptoEmaMacdScalper 策略回测(Python 复刻,跑在 GitHub Actions 上取真实行情)。

**为什么需要它**:EA 的规则从来没在历史上跑过。这个脚本用币安公开的真实 5 分钟
K 线(带真实成交量)把 mql5/CryptoEmaMacdScalper.mq5 的规则逐条复刻跑一遍,
给出**真实**的信号数、胜率、期望 R、回撤。难看也照报。

数据:data.binance.vision 的月度 K 线归档(公开、免 key、GitHub 的美国机房也能访问)。
Claude 的沙箱访问不了外网,所以真实数字只能在 Actions 上产生。

⚠️ **它不等于 MT5 策略测试器**,差异必须说清楚:
   1. K 线级回测,不是 tick 级。同一根 K 线同时触及止损和止盈 —— **一律按止损算**。
   2. 点差按固定百分比扣(默认 0.03%,每边一半);无滑点。实盘 CFD 点差可能更大。
   3. 成交量用的是交易所真实成交量;MT5 券商多半只有 tick 成交量,放量判断会有差异。
   4. 新闻过滤无法复刻(没有历史经济日历),回测里**没有**新闻过滤。
   5. 移动止损按 K 线收盘价近似,EA 是新 K 线第一个 tick 才改。
   6. MACD 信号线按 MT5 iMACD 的口径 = MACD 线的 **SMA(9)**(TradingView 是 EMA),
      和 EA 保持一致。
   结论:这份回测的结果是**乐观上界**。实盘只会更差,不会更好。

用法:
    python3 backtest_crypto_scalper.py                          # BTC/ETH/SOL 最近 6 个完整月
    python3 backtest_crypto_scalper.py --symbols BTCUSDT --months 12
    python3 backtest_crypto_scalper.py --csv my_btc_m5.csv      # 离线:t,o,h,l,c,v(t 为秒或毫秒)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import math
import os
import sys
import zipfile
from urllib import error as urlerror
from urllib import request as urlrequest

UA = "Mozilla/5.0 (ai4trade-bot backtest)"

# --- 与 EA 对齐的参数(改这里 = 改 EA 的 input,见 presets/crypto/default.set) -------
FAST, SLOW               = 20, 50
MACD_FAST, MACD_SLOW, MACD_SIG = 12, 26, 9
EMA_CROSS_LOOKBACK       = 12
MACD_CROSS_LOOKBACK      = 3
TOUCH_TOL_PCT            = 0.10
WICK_RATIO               = 2.0
VOL_AVG_BARS             = 20
VOL_MULT                 = 1.5
SWING_LOOKBACK           = 10
TP1_R, TP2_R             = 1.5, 2.0
TRAIL_EMA20              = True
TREND_BARS               = 5
CHOP_LOOKBACK            = 36
MAX_CROSSES_IN_CHOP      = 1
MAX_STOP_PCT             = 1.5
MIN_STOP_SPREAD_X        = 3.0
SL_BUFFER_PCT            = 0.05
DAILY_LOSS_PCT           = 4.0
WARMUP                   = 300   # EMA/MACD 需要预热,前这么多根不交易


# ------------------------------- 数据 ---------------------------------------
def month_list(n: int):
    """最近 n 个**完整**月(不含本月),旧→新。"""
    y, m = dt.date.today().year, dt.date.today().month
    out = []
    for _ in range(n):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append((y, m))
    return out[::-1]


def fetch_binance(symbol: str, months: int, interval: str = "5m"):
    rows = []
    for y, m in month_list(months):
        url = (f"https://data.binance.vision/data/spot/monthly/klines/{symbol}/{interval}/"
               f"{symbol}-{interval}-{y}-{m:02d}.zip")
        try:
            req = urlrequest.Request(url, headers={"User-Agent": UA})
            with urlrequest.urlopen(req, timeout=90) as r:
                raw = r.read()
        except urlerror.HTTPError as e:
            print(f"[data] {symbol} {y}-{m:02d}: HTTP {e.code},跳过")
            continue
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            with z.open(z.namelist()[0]) as f:
                for row in csv.reader(io.TextIOWrapper(f, encoding="utf-8")):
                    if not row or not row[0].strip().isdigit():
                        continue                      # 表头
                    rows.append(_row(row[0], *row[1:6]))
        print(f"[data] {symbol} {y}-{m:02d}: ok")
    return _finish(rows)


def load_csv(path: str):
    rows = []
    with open(path, newline="") as f:
        for row in csv.reader(f):
            if not row or not row[0].strip().isdigit():
                continue
            rows.append(_row(*row[:6]))
    return _finish(rows)


def _row(t, o, h, l, c, v):
    t = int(t)
    while t > 10**11:          # 微秒/毫秒 → 秒(币安 2025 年起现货归档是微秒)
        t //= 1000
    return (t, float(o), float(h), float(l), float(c), float(v))


def _finish(rows):
    rows.sort()
    out, last = [], None
    for r in rows:
        if r[0] != last:
            out.append(r)
            last = r[0]
    return {k: [r[i] for r in out] for i, k in enumerate("tohlcv")}


# ------------------------------- 指标 ---------------------------------------
def ema(v, p):
    k = 2.0 / (p + 1)
    out = [v[0]] * len(v)
    for i in range(1, len(v)):
        out[i] = v[i] * k + out[i - 1] * (1 - k)
    return out


def sma(v, p):
    out, s = [0.0] * len(v), 0.0
    for i, x in enumerate(v):
        s += x
        if i >= p:
            s -= v[i - p]
        out[i] = s / min(i + 1, p)
    return out


# ------------------------------- 规则(逐条对应 EA) ---------------------------
class Rules:
    def __init__(self, B):
        self.B = B
        c = B["c"]
        self.e20 = ema(c, FAST)
        self.e50 = ema(c, SLOW)
        fast, slow = ema(c, MACD_FAST), ema(c, MACD_SLOW)
        self.mm = [a - b for a, b in zip(fast, slow)]
        self.ms = sma(self.mm, MACD_SIG)

    # EA 的 shift s 对应这里的下标 i-s+1(shift 1 = 信号 K = 下标 i)
    def ema_cross(self, j):
        now, prev = self.e20[j] > self.e50[j], self.e20[j - 1] > self.e50[j - 1]
        return 1 if now and not prev else -1 if prev and not now else 0

    def macd_cross(self, j):
        now, prev = self.mm[j] > self.ms[j], self.mm[j - 1] > self.ms[j - 1]
        return 1 if now and not prev else -1 if prev and not now else 0

    def chop_crosses(self, i):
        return sum(1 for s in range(1, CHOP_LOOKBACK + 1) if self.ema_cross(i - s + 1) != 0)

    def hammer(self, i, up=True):
        B = self.B
        o, h, l, c = B["o"][i], B["h"][i], B["l"][i], B["c"][i]
        rng = h - l
        if rng <= 0:
            return False
        body = abs(c - o)
        lower, upper = min(o, c) - l, h - max(o, c)
        wick, other = (lower, upper) if up else (upper, lower)
        return wick >= WICK_RATIO * max(body, rng * 0.05) and other <= rng * 0.25

    def engulf(self, i, up=True):
        o, c = self.B["o"], self.B["c"]
        if up:
            return c[i-1] < o[i-1] and c[i] > o[i] and o[i] <= c[i-1] and c[i] >= o[i-1]
        return c[i-1] > o[i-1] and c[i] < o[i] and o[i] >= c[i-1] and c[i] <= o[i-1]

    def evaluate(self, i, d):
        """返回 (c1, c2, c3, c4, cross_index)。"""
        B, e20, e50 = self.B, self.e20, self.e50
        # 1 EMA 交叉
        last_s, last_d = 0, 0
        for s in range(1, CHOP_LOOKBACK + 1):
            cd = self.ema_cross(i - s + 1)
            if cd:
                last_s, last_d = s, cd
                break
        side = e20[i] > e50[i] if d > 0 else e20[i] < e50[i]
        c1 = side and last_d == d and 1 <= last_s <= EMA_CROSS_LOOKBACK
        # 2 MACD 交叉 + 柱
        m_ok = any(self.macd_cross(i - s + 1) == d for s in range(1, MACD_CROSS_LOOKBACK + 1))
        hist = self.mm[i] - self.ms[i]
        c2 = m_ok and (hist > 0 if d > 0 else hist < 0)
        # 3 回踩/反弹 EMA + 形态
        up = d > 0
        eng = self.engulf(i, up)
        pin = self.hammer(i, up)
        cl = B["c"][i]
        tol = cl * TOUCH_TOL_PCT / 100.0
        if up:
            ext = min(B["l"][i], B["l"][i-1]) if eng else B["l"][i]
            n20 = ext <= e20[i] + tol and cl >= e20[i] - tol
            n50 = ext <= e50[i] + tol and cl >= e50[i] - tol
            struct = cl > e50[i]
        else:
            ext = max(B["h"][i], B["h"][i-1]) if eng else B["h"][i]
            n20 = ext >= e20[i] - tol and cl <= e20[i] + tol
            n50 = ext >= e50[i] - tol and cl <= e50[i] + tol
            struct = cl < e50[i]
        c3 = (eng or pin) and (n20 or n50) and struct
        # 4 放量(做空要求阴线)
        v = B["v"]
        avg = sum(v[i - k] for k in range(1, VOL_AVG_BARS + 1)) / VOL_AVG_BARS
        c4 = avg > 0 and v[i] >= avg * VOL_MULT and (up or B["c"][i] < B["o"][i])
        return c1, c2, c3, c4, (i - last_s + 1 if c1 else None)


# ------------------------------- 模拟 ---------------------------------------
def simulate(B, spread_pct, fee_pct, equity0, risk_pct):
    R = Rules(B)
    n = len(B["t"])
    o, h, l, c, t = B["o"], B["h"], B["l"], B["c"], B["t"]
    trades = []
    funnel = {"L": [0] * 5, "S": [0] * 5}          # c1..c4, all
    blocked = {"chop": 0, "cross_used": 0, "stop_invalid": 0, "stop_too_tight": 0,
               "stop_too_far": 0, "daily_loss": 0}
    traded_cross = None
    equity = equity0
    day, day_start = None, equity0
    i = WARMUP
    while i < n - 2:
        d_now = dt.datetime.utcfromtimestamp(t[i + 1]).date()
        if d_now != day:
            day, day_start = d_now, equity

        sig = None
        for d, key in ((1, "L"), (-1, "S")):
            ck = R.evaluate(i, d)
            for k in range(4):
                funnel[key][k] += ck[k]
            if all(ck[:4]):
                funnel[key][4] += 1
                sig = (d, ck[4])
        if sig is None:
            i += 1
            continue

        d, cross_i = sig
        if R.chop_crosses(i) > MAX_CROSSES_IN_CHOP:
            blocked["chop"] += 1; i += 1; continue
        if (day_start - equity) / day_start * 100 >= DAILY_LOSS_PCT:
            blocked["daily_loss"] += 1; i += 1; continue
        if cross_i == traded_cross:
            blocked["cross_used"] += 1; i += 1; continue

        # --- 入场:下一根开盘(= EA 在新 K 线第一个 tick 市价进) ---
        j0 = i + 1
        hs = o[j0] * spread_pct / 200.0                # 半个点差
        spread = 2 * hs
        entry = o[j0] + d * hs                          # 多 = ask,空 = bid
        buf = max(spread, entry * SL_BUFFER_PCT / 100.0)
        lows = l[i - SWING_LOOKBACK + 1:i + 1]
        highs = h[i - SWING_LOOKBACK + 1:i + 1]
        sl = (min(lows) - buf) if d > 0 else (max(highs) + buf)
        dist = (entry - sl) * d
        if dist <= 0:
            blocked["stop_invalid"] += 1; i += 1; continue
        if dist < spread * MIN_STOP_SPREAD_X:
            blocked["stop_too_tight"] += 1; i += 1; continue
        if dist / entry * 100 > MAX_STOP_PCT:
            blocked["stop_too_far"] += 1; i += 1; continue

        traded_cross = cross_i
        legs = [{"tp": entry + d * dist * TP1_R, "w": 0.5, "exit": None, "why": None},
                {"tp": entry + d * dist * TP2_R, "w": 0.5, "exit": None, "why": None}]
        trailed = False
        j = j0
        while j < n:
            # 价格以 bid(多)/ask(空)触发:多单看 低-hs / 高-hs,空单看 高+hs / 低+hs
            adv  = (l[j] - hs) if d > 0 else (h[j] + hs)    # 不利极值
            fav  = (h[j] - hs) if d > 0 else (l[j] + hs)    # 有利极值
            opn  = (o[j] - hs) if d > 0 else (o[j] + hs)
            sl_hit = (adv <= sl) if d > 0 else (adv >= sl)
            for leg in legs:
                if leg["exit"] is not None:
                    continue
                tp_hit = (fav >= leg["tp"]) if d > 0 else (fav <= leg["tp"])
                if sl_hit:                                   # 同根同时触及 → 按止损
                    gap = (opn < sl) if d > 0 else (opn > sl)
                    leg["exit"], leg["why"] = (opn if gap else sl), ("trail" if trailed else "sl")
                elif tp_hit:
                    leg["exit"], leg["why"] = leg["tp"], "tp"
            if all(leg["exit"] is not None for leg in legs):
                break
            # 收盘后:强趋势 → 止损跟随 EMA20(只往有利方向)
            if TRAIL_EMA20 and j >= TREND_BARS:
                rng = range(j - TREND_BARS + 1, j + 1)
                strong = all(c[k] > R.e20[k] for k in rng) if d > 0 else all(c[k] < R.e20[k] for k in rng)
                if strong:
                    new = R.e20[j] - d * buf
                    better = (new > sl) if d > 0 else (new < sl)
                    valid = (new < c[j] - hs) if d > 0 else (new > c[j] + hs)
                    if better and valid:
                        sl, trailed = new, True
            j += 1
        if any(leg["exit"] is None for leg in legs):
            break                                            # 数据结束时仍持仓:丢弃这笔

        r_total = 0.0
        for leg in legs:
            fee_r = fee_pct / 100.0 * (entry + leg["exit"]) / dist
            leg["r"] = (leg["exit"] - entry) * d / dist - fee_r
            r_total += leg["w"] * leg["r"]
        equity += equity * risk_pct / 100.0 * r_total
        trades.append({"t_in": t[j0], "t_out": t[j], "dir": d, "entry": entry, "stop_pct":
                       dist / entry * 100, "r": r_total, "legs": [(lg["why"], lg["r"]) for lg in legs],
                       "bars": j - j0 + 1, "equity": equity})
        i = j          # 平仓那根收盘后才能评估下一个信号(EA:同时只持一组仓)
    return trades, funnel, blocked, equity


# ------------------------------- 统计/报告 -----------------------------------
def stats(trades):
    n = len(trades)
    if n == 0:
        return None
    rs = [x["r"] for x in trades]
    mu = sum(rs) / n
    sd = math.sqrt(sum((r - mu) ** 2 for r in rs) / (n - 1)) if n > 1 else 0.0
    se = sd / math.sqrt(n) if n > 1 else 0.0
    gp = sum(r for r in rs if r > 0)
    gl = -sum(r for r in rs if r < 0)
    peak = cum = dd = 0.0
    streak = worst = 0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
        streak = 0 if r > 0 else streak + 1
        worst = max(worst, streak)
    legs = [lg for x in trades for lg in x["legs"]]
    tp1 = sum(1 for x in trades if x["legs"][0][0] == "tp")
    tp2 = sum(1 for x in trades if x["legs"][1][0] == "tp")
    return {"n": n, "wr": sum(1 for r in rs if r > 0) / n * 100, "exp": mu,
            "lo": mu - 1.96 * se, "hi": mu + 1.96 * se, "total": sum(rs),
            "pf": (gp / gl) if gl > 0 else float("inf"), "dd": dd, "streak": worst,
            "tp1": tp1 / n * 100, "tp2": tp2 / n * 100,
            "trail": sum(1 for lg in legs if lg[0] == "trail") / len(legs) * 100,
            "stop_pct": sum(x["stop_pct"] for x in trades) / n,
            "bars": sum(x["bars"] for x in trades) / n}


def verdict(s):
    if s is None or s["n"] < 20:
        return "**样本不足**(< 20 笔):这个结果什么也证明不了。"
    if s["hi"] < 0:
        return "**确认为负**:95% 置信上界都 < 0 —— 这套规则在这段行情里亏钱。不要上实盘。"
    if s["lo"] > 0:
        return "**确认为正**:95% 置信下界 > 0。仍须模拟盘验证(回测是乐观上界)。"
    if s["exp"] <= 0:
        return "**偏负且不显著**:期望 ≤ 0,分不清是运气还是没有 edge。不要上实盘。"
    return "**偏正但不显著**:期望 > 0 但置信区间跨 0 —— 分不清 edge 还是运气。只能模拟盘继续攒样本。"


def fmt_stats_row(label, s):
    if s is None:
        return f"| {label} | 0 | – | – | – | – | – | – | – |"
    pf = "∞" if s["pf"] == float("inf") else f"{s['pf']:.2f}"
    return (f"| {label} | {s['n']} | {s['wr']:.1f}% | {s['exp']:+.3f}R "
            f"| [{s['lo']:+.2f}, {s['hi']:+.2f}] | {s['total']:+.1f}R | "
            f"{pf} | {s['dd']:.1f}R | {s['streak']} |")


def report(results, args, label):
    L = []
    L.append("# CryptoEmaMacdScalper 回测（真实历史行情）\n")
    L.append(f"*生成于 {dt.datetime.utcnow():%Y-%m-%dT%H:%MZ} · {label}*\n")
    L.append("> ⚠️ Python 复刻的 **K 线级** 回测，不等于 MT5 策略测试器。同一根 K 线同时触及止损和止盈一律按**止损**计；")
    L.append(f"> 点差按固定 {args.spread_pct:.3f}% 扣，手续费每边 {args.fee_pct:.3f}%，无滑点；**没有新闻过滤**；")
    L.append("> 成交量是交易所真实成交量（MT5 券商多为 tick 量）。**结果是乐观上界，实盘只会更差。**\n")
    L.append("R = 以止损距离为 1 的盈亏倍数；每个信号拆两半（1.5R / 2R），表里的 R 是两半合计。\n")

    L.append("## 总览\n")
    L.append("| 品种 | 信号数 | 胜率 | 每笔期望 | 95% 置信区间 | 累计 | 盈亏比(PF) | 最大回撤 | 最长连亏 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    all_tr = []
    for sym, (B, trades, funnel, blocked, eq) in results.items():
        all_tr += trades
        L.append(fmt_stats_row(sym, stats(trades)))
    all_tr.sort(key=lambda x: x["t_in"])
    s_all = stats(all_tr)
    L.append(fmt_stats_row("**合计**", s_all))
    L.append("")
    L.append(f"**结论**：{verdict(s_all)}\n")

    if s_all:
        half = len(all_tr) // 2
        s1, s2 = stats(all_tr[:half]), stats(all_tr[half:])
        L.append("## 前后两半（样本外一致性）\n")
        L.append("规则没有用任何一段数据调过参，但前后两半结果方向不一致 = 结果主要是运气。\n")
        L.append("| 区段 | 信号数 | 胜率 | 每笔期望 | 95% 置信区间 | 累计 | 盈亏比(PF) | 最大回撤 | 最长连亏 |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        L.append(fmt_stats_row("前半", s1))
        L.append(fmt_stats_row("后半", s2))
        L.append("")
        L.append("## 出场细节\n")
        L.append(f"- 1.5R 目标命中率 {s_all['tp1']:.1f}% · 2R 目标命中率 {s_all['tp2']:.1f}% · "
                 f"被移动止损（EMA20）带出的半仓 {s_all['trail']:.1f}%")
        L.append(f"- 平均止损距离 {s_all['stop_pct']:.2f}% · 平均持仓 {s_all['bars']:.1f} 根 M5")
        for d, name in ((1, "做多"), (-1, "做空")):
            sd = stats([x for x in all_tr if x["dir"] == d])
            if sd:
                L.append(f"- {name}：{sd['n']} 笔 · 胜率 {sd['wr']:.1f}% · 期望 {sd['exp']:+.3f}R")
        L.append("")

    L.append("## 信号漏斗（规则有多严）\n")
    L.append("每根 K 线上各条件单独成立的次数 → 四条同时成立 → 过滤后真正开仓。\n")
    L.append("| 品种 | K 线数 | 天数 | L1 | L2 | L3 | L4 | 多:全满足 | S1 | S2 | S3 | S4 | 空:全满足 | 开仓 | 每周信号 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for sym, (B, trades, funnel, blocked, eq) in results.items():
        days = (B["t"][-1] - B["t"][0]) / 86400 if B["t"] else 0
        fl, fs = funnel["L"], funnel["S"]
        L.append(f"| {sym} | {len(B['t'])} | {days:.0f} | " + " | ".join(map(str, fl)) + " | "
                 + " | ".join(map(str, fs)) + f" | {len(trades)} | {len(trades) / max(days / 7, 1e-9):.2f} |")
    L.append("")
    L.append("被过滤的信号：\n")
    L.append("| 品种 | 横盘缠绕 | 同一交叉已交易 | 止损无效 | 止损太窄(点差) | 摆动点太远 | 当日熔断 |")
    L.append("|---|---|---|---|---|---|---|")
    for sym, (B, trades, funnel, blocked, eq) in results.items():
        b = blocked
        L.append(f"| {sym} | {b['chop']} | {b['cross_used']} | {b['stop_invalid']} | {b['stop_too_tight']} "
                 f"| {b['stop_too_far']} | {b['daily_loss']} |")
    L.append("")

    L.append(f"## 资金曲线（每品种独立 ${args.equity:,.0f} 起，每笔风险 {args.risk:.1f}%，不受最小手数限制）\n")
    L.append("| 品种 | 期末资金 | 收益 |")
    L.append("|---|---|---|")
    for sym, (B, trades, funnel, blocked, eq) in results.items():
        L.append(f"| {sym} | ${eq:,.2f} | {(eq / args.equity - 1) * 100:+.1f}% |")
    L.append("")

    if all_tr:
        L.append("## 最近 15 笔\n")
        L.append("| 入场(UTC) | 品种 | 方向 | 入场价 | 止损% | 半仓1 | 半仓2 | 合计R |")
        L.append("|---|---|---|---|---|---|---|---|")
        sym_of = {}
        for sym, (B, trades, *_r) in results.items():
            for x in trades:
                sym_of[id(x)] = sym
        for x in all_tr[-15:]:
            (w1, r1), (w2, r2) = x["legs"]
            L.append(f"| {dt.datetime.utcfromtimestamp(x['t_in']):%m-%d %H:%M} | {sym_of[id(x)]} | "
                     f"{'多' if x['dir'] > 0 else '空'} | {x['entry']:.2f} | {x['stop_pct']:.2f}% | "
                     f"{w1} {r1:+.2f} | {w2} {r2:+.2f} | {x['r']:+.2f} |")
        L.append("")
    L.append("*研究/学习用途，不构成投资建议。*")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default=os.environ.get("CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT"))
    ap.add_argument("--months", type=int, default=int(os.environ.get("CRYPTO_MONTHS", "6")))
    ap.add_argument("--csv", help="离线 CSV(t,o,h,l,c,v),给了就不联网")
    ap.add_argument("--spread-pct", type=float, default=float(os.environ.get("CRYPTO_SPREAD_PCT", "0.03")))
    ap.add_argument("--fee-pct", type=float, default=float(os.environ.get("CRYPTO_FEE_PCT", "0.0")))
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--risk", type=float, default=1.0)
    ap.add_argument("--out", default="reports/crypto_scalper_backtest.md")
    args = ap.parse_args()

    results = {}
    if args.csv:
        sources = {os.path.basename(args.csv): lambda: load_csv(args.csv)}
        label = f"CSV {args.csv}"
    else:
        sources = {s.strip().upper(): (lambda s=s.strip().upper(): fetch_binance(s, args.months))
                   for s in args.symbols.split(",") if s.strip()}
        ms = month_list(args.months)
        label = f"币安现货 M5 · {ms[0][0]}-{ms[0][1]:02d} ~ {ms[-1][0]}-{ms[-1][1]:02d}"

    for sym, load in sources.items():
        B = load()
        if len(B["t"]) < WARMUP + 100:
            print(f"[skip] {sym}: 只有 {len(B['t'])} 根 K 线")
            continue
        trades, funnel, blocked, eq = simulate(B, args.spread_pct, args.fee_pct, args.equity, args.risk)
        s = stats(trades)
        print(f"[{sym}] bars={len(B['t'])} trades={len(trades)} "
              + (f"wr={s['wr']:.1f}% exp={s['exp']:+.3f}R total={s['total']:+.1f}R" if s else ""))
        results[sym] = (B, trades, funnel, blocked, eq)

    if not results:
        print("没有可用数据")
        return 1
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(report(results, args, label))
    print(f"报告 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
