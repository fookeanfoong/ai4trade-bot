#!/usr/bin/env python3
"""外汇策略回测 + 品种稳定性筛选 + 样本外验证。

**为什么现在才做这个:** 黄金那套做了样本外验证,外汇这套没有 ——
20点止损、1:2、突破+回踩这些规则是按经验写的,从没被数据检验过。
在没验证过的规则上加杠杆,等于把一个未知数乘以 10。

两件事一起做:

1. **品种稳定性筛选** —— "稳定"不是感觉,是可量化的两个数:
   - 波动率 ATR% = ATR / 价格,越低越稳
   - 成本占比 = 点差 / 典型止损,越低越好
   两者要一起看:波动太低的品种走不出止盈,点差占比高的品种赚的都给了券商。

2. **样本外验证** —— 每个品种的数据按时间切两半:前半找参数,后半只跑一次。
   只有两边都为正的才算数。训练正/验证负 = 噪音,不是规律。

只测 XXX_USD(美元计价)的品种。USD/JPY、USD/CHF 这类的每点价值随汇率变动,
本地算不准 —— 与其给一个悄悄错掉的数字,不如不测。

用法:python3 backtest_forex.py
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import os
from urllib import request as urlrequest

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

OUT = os.environ.get("FX_RESEARCH_OUT", "reports/forex_research.md")
EQUITY = float(os.environ.get("FOREX_EQUITY_USD", "200"))
RISK_PCT = float(os.environ.get("FOREX_RISK_PCT", "1.0"))
MAX_RISK_PCT = 2.0
MAX_LEVERAGE = float(os.environ.get("FOREX_MAX_LEVERAGE", "10"))
MIN_TRADES = 25

# 只放美元计价的主要货币对 —— 0.01 手 = $0.10/点,换算不需要额外汇率。
# (symbol, yahoo, 典型点差pips)
PAIRS = [
    ("EUR_USD", "EURUSD=X", 1.0),
    ("GBP_USD", "GBPUSD=X", 1.5),
    ("AUD_USD", "AUDUSD=X", 1.5),
    ("NZD_USD", "NZDUSD=X", 2.0),
]

PIP = 0.0001
UNITS_PER_LOT = 100_000
MIN_LOT, LOT_STEP = 0.01, 0.01

FAST, SLOW, TREND = 20, 50, 200
RSI_P, ATR_P = 14, 14
SWING_LOOKBACK, SWING_WING = 120, 2
RSI_BUY_MAX, RSI_SELL_MIN = 70.0, 30.0


# ------------------------------- 数据 ---------------------------------------
def fetch(ysym, interval="1h", rng="2y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
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
            continue          # 带 None 整根丢掉,不前值填充
        bars.append({"t": int(t), "o": float(oo), "h": float(hh),
                     "l": float(ll), "c": float(cc)})
    bars.sort(key=lambda b: b["t"])
    return bars


# ------------------------------- 指标 ---------------------------------------
def ema_series(v, p):
    if not v:
        return []
    k = 2 / (p + 1)
    out = [v[0]]
    for x in v[1:]:
        out.append(x * k + out[-1] * (1 - k))
    return out


def rsi_series(c, p=14):
    n = len(c)
    out = [None] * n
    if n < p + 1:
        return out
    d = [c[i] - c[i - 1] for i in range(1, n)]
    up = sum(x for x in d[:p] if x > 0) / p
    dn = -sum(x for x in d[:p] if x < 0) / p
    out[p] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
    for i, x in enumerate(d[p:], start=p + 1):
        up = (up * (p - 1) + (x if x > 0 else 0)) / p
        dn = (dn * (p - 1) + (-x if x < 0 else 0)) / p
        out[i] = 100.0 if dn == 0 else 100 - 100 / (1 + up / dn)
    return out


def macd_series(c):
    ef, es = ema_series(c, 12), ema_series(c, 26)
    line = [a - b for a, b in zip(ef, es)]
    return line, ema_series(line, 9)


def atr_series(bars, p=14):
    n = len(bars)
    out = [None] * n
    if n < p + 1:
        return out
    trs = [max(bars[i]["h"] - bars[i]["l"],
               abs(bars[i]["h"] - bars[i - 1]["c"]),
               abs(bars[i]["l"] - bars[i - 1]["c"])) for i in range(1, n)]
    a = sum(trs[:p]) / p
    out[p] = a
    for i, t in enumerate(trs[p:], start=p + 1):
        a = (a * (p - 1) + t) / p
        out[i] = a
    return out


def structure(bars, i):
    lo_i = max(SWING_WING + 1, i - SWING_LOOKBACK)
    res = sup = None
    for j in range(lo_i, i - SWING_WING):
        win = bars[j - SWING_WING:j + SWING_WING + 1]
        if bars[j]["h"] >= max(b["h"] for b in win):
            res = bars[j]["h"] if res is None else max(res, bars[j]["h"])
        if bars[j]["l"] <= min(b["l"] for b in win):
            sup = bars[j]["l"] if sup is None else min(sup, bars[j]["l"])
    return res, sup


# ------------------------------- 稳定性 -------------------------------------
def stability(bars, spread_pips):
    """把「稳定」拆成可量的两个数,而不是凭印象选品种。"""
    atr = atr_series(bars, ATR_P)
    vals = [a for a in atr[-500:] if a]
    if not vals:
        return None
    atr_avg = sum(vals) / len(vals)
    price = bars[-1]["c"]
    atr_pips = atr_avg / PIP
    # 波动率:ATR 占价格的比例(可跨品种比较)
    atr_pct = atr_avg / price * 100
    # 日内波动的稳定度:ATR 的变异系数,越小说明波动本身越稳定
    mean = atr_avg
    var = sum((a - mean) ** 2 for a in vals) / len(vals)
    cv = (var ** 0.5) / mean if mean else 0
    return {"atr_pips": round(atr_pips, 1), "atr_pct": round(atr_pct, 4),
            "atr_cv": round(cv, 3),
            "spread_pips": spread_pips,
            # 成本占比:20点止损里点差占多少 —— 小账户真正的敌人
            "cost_ratio_pct": round(spread_pips / 20.0 * 100, 1)}


# ------------------------------- 手数 ---------------------------------------
def lots_for(equity, stop_pips, price):
    usd_per_pip_per_lot = UNITS_PER_LOT * PIP          # XXX_USD: $10/点/标准手
    risk = equity * min(RISK_PCT, MAX_RISK_PCT) / 100.0
    per_lot = stop_pips * usd_per_pip_per_lot
    if per_lot <= 0:
        return 0.0, 0.0
    lots = int((risk / per_lot) / LOT_STEP) * LOT_STEP
    if lots < MIN_LOT:
        lots = MIN_LOT
    actual = lots * per_lot
    if actual > equity * MAX_RISK_PCT / 100.0:
        return 0.0, actual
    # 杠杆闸:名义 = 手数 × 100,000 × 价格
    notional = lots * UNITS_PER_LOT * price
    if notional > equity * MAX_LEVERAGE:
        return 0.0, actual
    return round(lots, 2), actual


# ------------------------------- 回测 ---------------------------------------
def run(bars, stop_pips, rr, spread_pips, equity0):
    closes = [b["c"] for b in bars]
    ef, es, et = (ema_series(closes, FAST), ema_series(closes, SLOW),
                  ema_series(closes, TREND))
    rsi = rsi_series(closes, RSI_P)
    mline, msig = macd_series(closes)
    atr = atr_series(bars, ATR_P)

    equity, peak, max_dd = equity0, equity0, 0.0
    trades, pos, skipped = [], None, 0
    spread_px = spread_pips * PIP
    stop_px = stop_pips * PIP
    start = max(TREND, SWING_LOOKBACK + SWING_WING + 2, ATR_P + 2)

    for i in range(start, len(bars) - 1):
        bar = bars[i]
        if pos:
            nb = bars[i + 1]
            hit_sl = (nb["l"] <= pos["sl"]) if pos["d"] > 0 else (nb["h"] >= pos["sl"])
            hit_tp = (nb["h"] >= pos["tp"]) if pos["d"] > 0 else (nb["l"] <= pos["tp"])
            ex = None
            if hit_sl and hit_tp:
                ex = pos["sl"]        # 同一根里都碰到 -> 按亏损算
            elif hit_tp:
                ex = pos["tp"]
            elif hit_sl:
                ex = pos["sl"]
            if ex is not None:
                gross = (ex - pos["e"]) * pos["d"] * pos["lots"] * UNITS_PER_LOT
                cost = spread_px * pos["lots"] * UNITS_PER_LOT
                pnl = gross - cost
                equity += pnl
                peak = max(peak, equity)
                max_dd = max(max_dd, peak - equity)
                trades.append({"pnl": round(pnl, 2), "win": pnl > 0,
                               "r": round(pnl / pos["risk"], 3) if pos["risk"] else 0})
                pos = None
            continue

        if rsi[i] is None or not atr[i]:
            continue
        res, sup = structure(bars, i)
        if res is None or sup is None:
            continue
        up = ef[i] > es[i] > et[i]
        dn = ef[i] < es[i] < et[i]
        if not (up or dn):
            continue
        macd_up = mline[i] > msig[i] and mline[i] > 0
        macd_dn = mline[i] < msig[i] and mline[i] < 0
        buf = max(atr[i] * 0.15, spread_px * 2)

        d = 0
        if up and bar["c"] > res + buf and rsi[i] < RSI_BUY_MAX and macd_up:
            d = 1
        elif dn and bar["c"] < sup - buf and rsi[i] > RSI_SELL_MIN and macd_dn:
            d = -1
        if d == 0:
            continue

        lots, would = lots_for(equity, stop_pips, bar["c"])
        if lots <= 0:
            skipped += 1
            continue
        entry = bars[i + 1]["o"] + spread_px * d / 2
        pos = {"d": d, "e": entry, "sl": entry - stop_px * d,
               "tp": entry + stop_px * rr * d, "lots": lots,
               "risk": lots * stop_px * UNITS_PER_LOT}

    return trades, equity, max_dd, skipped


def summarize(trades, equity, equity0, dd):
    n = len(trades)
    if n == 0:
        return {"n": 0, "wr": None, "exp": None, "net": 0.0, "dd": 0.0}
    wins = sum(1 for t in trades if t["win"])
    tot_r = sum(t["r"] for t in trades)
    return {"n": n, "wr": round(wins / n * 100, 1),
            "exp": round(tot_r / n, 3), "net": round(equity - equity0, 2),
            "dd": round(dd, 2)}


# ------------------------------- 主流程 -------------------------------------
def main():
    now = dt.datetime.now(dt.timezone.utc)
    stops = [15, 20, 25, 30]
    rrs = [1.5, 2.0]

    L = ["# 外汇策略研究 — 稳定性筛选 + 样本外验证", "",
         f"*生成于 {now.isoformat(timespec='seconds')}*", "",
         f"本金 ${EQUITY:.0f} · 单笔风险 {RISK_PCT}%(硬上限 {MAX_RISK_PCT}%) · "
         f"杠杆上限 {MAX_LEVERAGE:g}x",
         "",
         "**这套外汇规则此前从未被回测过** —— 20点止损、1:2、突破入场都是按经验写的。",
         "在没验证过的规则上加杠杆,等于把一个未知数乘以 10。这份报告补上验证。",
         "",
         "方法:每个品种按时间切两半,前半找参数、后半只跑一次。",
         f"只有**两边都为正**且各自 ≥{MIN_TRADES} 笔的配置才算数。", ""]

    # ---- 稳定性筛选 ----
    L += ["## 一、品种稳定性(用数据量,不靠印象)", "",
          "| 品种 | ATR(点) | ATR/价格% | ATR变异系数 | 点差 | 点差占20点止损 |",
          "|---|---|---|---|---|---|"]
    data = {}
    for name, ysym, spread in PAIRS:
        try:
            bars = fetch(ysym)
        except Exception as e:
            L.append(f"| {name} | 取数失败:{e} | | | | |")
            continue
        if len(bars) < 600:
            L.append(f"| {name} | K线不足({len(bars)}) | | | | |")
            continue
        data[name] = (bars, spread)
        s = stability(bars, spread)
        L.append(f"| {name} | {s['atr_pips']} | {s['atr_pct']}% | {s['atr_cv']} | "
                 f"{spread} | {s['cost_ratio_pct']}% |")
    L += ["",
          "> **ATR变异系数**越小 = 波动本身越稳定(不会忽大忽小)。",
          "> **点差占比**越小 = 成本吃掉的利润越少。两个都要看:",
          "> 波动太低的品种走不到止盈,点差占比高的品种赚的都给了券商。", ""]

    # ---- 样本外验证 ----
    L += ["## 二、样本外验证", ""]
    survivors = []
    for name, (bars, spread) in data.items():
        mid = len(bars) // 2
        tr_b, te_b = bars[:mid], bars[mid:]
        t0 = dt.datetime.fromtimestamp(bars[0]["t"], dt.timezone.utc)
        t1 = dt.datetime.fromtimestamp(bars[-1]["t"], dt.timezone.utc)
        L += [f"### {name}（{t0:%Y-%m-%d} → {t1:%Y-%m-%d}）", "",
              "| 止损 | RR | 训练笔数 | 训练胜率 | 训练期望 | 验证笔数 | 验证胜率 | 验证期望 | 判定 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for stop, rr in itertools.product(stops, rrs):
            ta, ea, da, _ = run(tr_b, stop, rr, spread, EQUITY)
            tb, eb, db, _ = run(te_b, stop, rr, spread, EQUITY)
            a = summarize(ta, ea, EQUITY, da)
            b = summarize(tb, eb, EQUITY, db)
            if a["n"] < MIN_TRADES or b["n"] < MIN_TRADES:
                verdict = "样本不足"
            elif a["exp"] and b["exp"] and a["exp"] > 0 and b["exp"] > 0:
                verdict = "✅ 两边为正"
                survivors.append((name, stop, rr, a, b))
            elif a["exp"] and a["exp"] > 0:
                verdict = "⚠️ 训练正/验证负 = 噪音"
            else:
                verdict = "❌"
            L.append(f"| {stop}点 | 1:{rr} | {a['n']} | "
                     f"{a['wr'] if a['wr'] is not None else '—'}% | "
                     f"{a['exp'] if a['exp'] is not None else '—'} | {b['n']} | "
                     f"{b['wr'] if b['wr'] is not None else '—'}% | "
                     f"{b['exp'] if b['exp'] is not None else '—'} | {verdict} |")
        L.append("")

    L += ["## 结论", ""]
    if survivors:
        L += [f"**{len(survivors)} 组通过样本外验证:**", ""]
        for name, stop, rr, a, b in sorted(survivors, key=lambda x: -x[4]["exp"]):
            L.append(f"- **{name} · {stop}点止损 · RR1:{rr}** — "
                     f"训练 {a['n']}笔/{a['wr']}%/{a['exp']}R，"
                     f"验证 {b['n']}笔/{b['wr']}%/{b['exp']}R，"
                     f"验证净利 ${b['net']}，最大回撤 ${b['dd']}")
        L += ["", "> 通过验证 ≠ 实盘会赚。真实点差会在数据前后放大,滑点和隔夜利息没算。", ""]
    else:
        L += ["**没有任何配置通过样本外验证。**", "",
              "继续加密参数网格直到出现正数,得到的一定是过拟合。",
              "诚实的结论:**当前这套外汇入场逻辑没有可验证的优势** ——",
              "要改的是入场条件本身,不是止损、盈亏比或杠杆。",
              "",
              "**在这种情况下加杠杆是最糟的选择**:杠杆放大的是每笔的结果,",
              "不改变期望的符号。负期望 × 10倍杠杆 = 更快归零。", ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L[-20:]))
    print(f"\n完整报告 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
