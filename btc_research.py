#!/usr/bin/env python3
"""BTC 快进快出策略研究 — 带**样本外验证**,口径和 gold_research.py 一样。

对应的 EA 是 mql5/BTCScalper.mq5,这里是它的 Python 复刻。把几种网上常见的
BTC 剥头皮入场,跟你自己已有的逻辑放在同一把尺子上量:

  pullback   趋势回踩(GoldScalper 入场 B + 加密版 setup B):EMA 快>慢 且在趋势
             EMA 同侧,收盘回到快线附近,并且收出顺势 K 线确认;RSI 在 40~70
             (做空镜像为 30~60)的「甜区」里(NyaoScalper 的 RSI 甜区思路)
  breakout   结构突破(GoldScalper 入场 A):收盘突破分型阻力/支撑 + 缓冲
  meanrev    布林带超卖反弹/超买回落(你加密版的 setup A,这里做双向)
  pb+bo      pullback 和 breakout 同时开

所有入场共用的过滤器(网上的 BTC 剥头皮 + NyaoScalper 的风控思路):
  - VWAP 同侧:只在当日 VWAP 上方做多、下方做空(EMA9/21 + VWAP 是网上最常见的
    BTC 5 分钟剥头皮组合)
  - 死市过滤:ATR / 50 根平均 ATR < 0.7 就不做(NyaoScalper 的 Dead-Market Filter)
  - 点差/ATR:点差超过 ATR 的 25% 就不做(小波动里点差吃掉整笔利润)
  - 影线惩罚:信号 K 线的反向影线 > 实体 1.5 倍就不做(NyaoScalper 的 wick penalty)
  - 崩盘/暴涨保护:距 4 小时高点跌超 3% 不开多、距低点涨超 3% 不开空
    (来自你加密版的 crash circuit breaker)
  - 时段:只在 UTC 06~20(伦敦+纽约,BTC 流动性最好的时段)开仓
  - 冷却:亏损平仓后停 3 根 K 线
  - 时间止损:持有超过 MAX_HOLD 根就按收盘平掉 —— 「快进快出」写成规则

结果按 **R**(1R = 初始止损距离)计,已扣点差,所以和账户大小无关。

⚠️ 和 gold 回测一样的局限,结果是**乐观上界**:
   1. K 线级,不是 tick 级;同一根 K 线同时碰到止损和止盈,一律按止损算。
   2. 点差按固定值扣;周末/行情剧烈时 XM 的 BTC 点差会放大好几倍。
   3. 无滑点、无隔夜利息(XM 加密 CFD 的隔夜利息很贵,所以 EA 带时间止损)。
   4. Yahoo 的 BTC-USD 是现货综合价,不是 XM 的 BTCUSD# 报价;VWAP 用的是
      Yahoo 的成交量,EA 里只能用 tick volume。

用法:python3 btc_research.py
"""

from __future__ import annotations

import datetime as dt
import itertools
import os

import backtest_gold as B      # 复用取数 + 指标 + 分型结构,保证和黄金研究同一口径

OUT = os.environ.get("BTC_RESEARCH_OUT", "reports/btc_research.md")
SYMBOL = os.environ.get("BTC_SYMBOL", "BTC-USD")
SPREAD = float(os.environ.get("BTC_SPREAD", "30"))   # 美元;XM 真实点差请看 Market Watch
MIN_TRADES = 25

# ---- 与 EA 对齐的默认参数 -------------------------------------------------
FAST, SLOW, TREND = 9, 21, 100
RSI_P, ATR_P, BB_P, BB_K = 14, 14, 20, 2.0
RSI_LONG = (40.0, 70.0)          # 做多 RSI 甜区
RSI_SHORT = (30.0, 60.0)         # 做空 RSI 甜区
MR_RSI_LO, MR_RSI_HI = 30.0, 70.0
DEAD_RATIO = 0.7
MAX_SPREAD_ATR = 0.25
WICK_BODY_MAX = 1.5
CRASH_PCT = 3.0
MAX_HOLD = 12
COOLDOWN = 3                     # 亏损平仓后冷却几根
SESSION_UTC = (6, 20)            # ≈ EA 默认 9~23 服务器时间(XM 夏令 GMT+3)
BE_AT_R = 1.0
TRAIL_ATR = 1.0

# 研究用开关(ablation):验证「这个过滤器到底有没有用」
USE_VWAP = True
USE_DEAD = True
USE_WICK = True
USE_SESSION = True


# ------------------------------- 指标 ---------------------------------------
def sma(v, p):
    out = [None] * len(v)
    s = 0.0
    for i, x in enumerate(v):
        s += x
        if i >= p:
            s -= v[i - p]
        if i >= p - 1:
            out[i] = s / p
    return out


def bbands(c, p=BB_P, k=BB_K):
    mid = sma(c, p)
    up, lo = [None] * len(c), [None] * len(c)
    for i in range(p - 1, len(c)):
        w = c[i - p + 1:i + 1]
        m = mid[i]
        sd = (sum((x - m) ** 2 for x in w) / p) ** 0.5
        up[i], lo[i] = m + k * sd, m - k * sd
    return mid, up, lo


def daily_vwap(bars):
    """按 UTC 自然日重置的 VWAP。没有成交量的 K 线按等权处理。"""
    out = [None] * len(bars)
    day, pv, vv = None, 0.0, 0.0
    for i, b in enumerate(bars):
        d = b["t"] // 86400
        if d != day:
            day, pv, vv = d, 0.0, 0.0
        vol = b.get("v") or 1.0
        pv += (b["h"] + b["l"] + b["c"]) / 3 * vol
        vv += vol
        out[i] = pv / vv
    return out


def fetch(interval, rng):
    """backtest_gold.fetch 丢了成交量,这里补上(VWAP 要用)。"""
    import json
    from urllib import request as ur
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{SYMBOL}"
           f"?range={rng}&interval={interval}")
    req = ur.Request(url, headers={"User-Agent": B.BROWSER_UA, "Accept": "application/json"})
    with ur.urlopen(req, timeout=40) as r:
        res = json.loads(r.read().decode())["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    bars = []
    for i, t in enumerate(ts):
        try:
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            v = (q.get("volume") or [None] * len(ts))[i]
        except (IndexError, KeyError, TypeError):
            continue
        if None in (o, h, l, c):
            continue
        bars.append({"t": int(t), "o": float(o), "h": float(h), "l": float(l),
                     "c": float(c), "v": float(v or 0)})
    bars.sort(key=lambda b: b["t"])
    return bars


# ------------------------------- 回测 ---------------------------------------
def prepare(bars):
    c = [b["c"] for b in bars]
    atr = B.atr_series(bars, ATR_P)
    atr_avg = sma([a or 0.0 for a in atr], 50)
    mid, up, lo = bbands(c)
    bars_4h = None
    if len(bars) > 1:
        step = bars[1]["t"] - bars[0]["t"]
        bars_4h = max(2, int(4 * 3600 / max(step, 60)))
    return {
        "ef": B.ema_series(c, FAST), "es": B.ema_series(c, SLOW), "et": B.ema_series(c, TREND),
        "rsi": B.rsi_series(c, RSI_P), "atr": atr, "atr_avg": atr_avg,
        "bb_mid": mid, "bb_up": up, "bb_lo": lo, "vwap": daily_vwap(bars), "n4h": bars_4h,
    }


def signal(bars, ind, i, module, spread):
    """在已收盘的 bar i 上判断,返回 +1/-1/0。和 EA 的 TryEntry 一一对应。"""
    b = bars[i]
    atr, rsi = ind["atr"][i], ind["rsi"][i]
    if not atr or rsi is None or ind["atr_avg"][i] is None:
        return 0
    if USE_DEAD and ind["atr_avg"][i] > 0 and atr / ind["atr_avg"][i] < DEAD_RATIO:
        return 0
    if spread > atr * MAX_SPREAD_ATR:
        return 0
    if USE_SESSION:
        # EA 在新 K 线开盘时判断,所以看的是下一根的开盘时刻
        hr = bars[i + 1]["t"] // 3600 % 24
        if not (SESSION_UTC[0] <= hr < SESSION_UTC[1]):
            return 0

    ef, es, et = ind["ef"][i], ind["es"][i], ind["et"][i]
    vw = ind["vwap"][i]
    up = ef > es and b["c"] > et
    dn = ef < es and b["c"] < et

    body = abs(b["c"] - b["o"])
    upper_wick = b["h"] - max(b["c"], b["o"])
    lower_wick = min(b["c"], b["o"]) - b["l"]

    n4 = ind["n4h"]
    lo_i = max(0, i - n4 + 1)
    hi4 = max(x["h"] for x in bars[lo_i:i + 1])
    lo4 = min(x["l"] for x in bars[lo_i:i + 1])
    no_long = (hi4 - b["c"]) / hi4 * 100 > CRASH_PCT
    no_short = (b["c"] - lo4) / lo4 * 100 > CRASH_PCT

    long_ok = not no_long and (not USE_VWAP or b["c"] > vw)
    short_ok = not no_short and (not USE_VWAP or b["c"] < vw)
    if USE_WICK:
        if body > 0:
            long_ok = long_ok and upper_wick <= body * WICK_BODY_MAX
            short_ok = short_ok and lower_wick <= body * WICK_BODY_MAX
        else:
            long_ok = short_ok = False

    d = 0
    if module in ("pullback", "pb+bo"):
        zone = atr * 0.5
        if (up and long_ok and b["c"] <= ef + zone and b["c"] > es and b["c"] > b["o"]
                and RSI_LONG[0] <= rsi <= RSI_LONG[1]):
            d = 1
        elif (dn and short_ok and b["c"] >= ef - zone and b["c"] < es and b["c"] < b["o"]
                and RSI_SHORT[0] <= rsi <= RSI_SHORT[1]):
            d = -1
    if d == 0 and module in ("breakout", "pb+bo"):
        res, sup = B.structure(bars, i)
        if res is not None and sup is not None:
            buf = max(atr * 0.15, spread * 2)
            if up and long_ok and b["c"] > res + buf and rsi < RSI_LONG[1]:
                d = 1
            elif dn and short_ok and b["c"] < sup - buf and rsi > RSI_SHORT[0]:
                d = -1
    if d == 0 and module == "meanrev":
        lo, hi = ind["bb_lo"][i], ind["bb_up"][i]
        if lo is not None and hi is not None:
            # 反转不看 VWAP/趋势(本来就是逆势),但仍受崩盘保护:别接飞刀
            if not no_long and rsi < MR_RSI_LO and b["l"] <= lo and b["c"] > b["o"]:
                d = 1
            elif not no_short and rsi > MR_RSI_HI and b["h"] >= hi and b["c"] < b["o"]:
                d = -1
    return d


def run(bars, module, stop_atr, rr, spread, ind=None):
    """返回每笔的 R 列表(已扣点差)。"""
    ind = ind or prepare(bars)
    start = max(TREND, 102 + 4, 60, ind["n4h"] or 0)
    pos = None
    rs = []
    cool = -1                               # 亏损后到这个下标之前不开新仓
    for i in range(start, len(bars) - 1):
        nb = bars[i + 1]
        if pos:
            d = pos["d"]
            hit_sl = nb["l"] <= pos["sl"] if d > 0 else nb["h"] >= pos["sl"]
            hit_tp = nb["h"] >= pos["tp"] if d > 0 else nb["l"] <= pos["tp"]
            pos["held"] += 1
            px = None
            if hit_sl:                      # 同时碰到也按止损(保守)
                px = pos["sl"]
            elif hit_tp:
                px = pos["tp"]
            elif pos["held"] >= MAX_HOLD:   # 时间止损:按这根收盘平
                px = nb["c"]
            if px is not None:
                rs.append(((px - pos["entry"]) * d - spread) / pos["r"])
                if rs[-1] < 0:
                    cool = i + 1 + COOLDOWN
                pos = None
                continue
            # 保本 + 追踪:用这根 K 线的收盘更新,从下一根开始生效
            prof = (nb["c"] - pos["entry"]) * d
            if prof >= pos["r"] * BE_AT_R:
                be = pos["entry"] + spread * d
                tr = nb["c"] - ind["atr"][i + 1] * TRAIL_ATR * d
                new = max(be, tr) if d > 0 else min(be, tr)
                if (d > 0 and new > pos["sl"]) or (d < 0 and new < pos["sl"]):
                    pos["sl"] = new
            continue

        if i < cool:
            continue
        d = signal(bars, ind, i, module, spread)
        if d == 0:
            continue
        dist = max(ind["atr"][i] * stop_atr, spread * 4)
        entry = nb["o"]
        pos = {"d": d, "entry": entry, "r": dist, "sl": entry - dist * d,
               "tp": entry + dist * rr * d, "held": 0}
        # 进场这根 K 线本身也可能直接打到止损/止盈
        hit_sl = nb["l"] <= pos["sl"] if d > 0 else nb["h"] >= pos["sl"]
        hit_tp = nb["h"] >= pos["tp"] if d > 0 else nb["l"] <= pos["tp"]
        if hit_sl or hit_tp:
            px = pos["sl"] if hit_sl else pos["tp"]
            rs.append(((px - entry) * d - spread) / dist)
            if rs[-1] < 0:
                cool = i + 1 + COOLDOWN
            pos = None
    return rs


def stats(rs):
    n = len(rs)
    if not n:
        return {"n": 0, "wr": None, "exp": None, "dd": 0.0, "tot": 0.0}
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"n": n, "wr": round(sum(1 for r in rs if r > 0) / n * 100, 1),
            "exp": round(sum(rs) / n, 3), "dd": round(dd, 1), "tot": round(sum(rs), 1)}


def split(bars):
    mid = len(bars) // 2
    return bars[:mid], bars[mid:]


def fmt(s):
    return (f"{s['n']} | {s['wr'] if s['wr'] is not None else '—'}% | "
            f"{s['exp'] if s['exp'] is not None else '—'}")


def verdict(a, b):
    if a["n"] < MIN_TRADES or b["n"] < MIN_TRADES:
        return "样本不足", False
    if a["exp"] > 0 and b["exp"] > 0:
        return "✅ 两边为正", True
    if a["exp"] > 0:
        return "⚠️ 训练正/验证负 = 噪音", False
    return "❌", False


def main():
    datasets = [("M5", "5m", "60d"), ("M15", "15m", "60d"), ("H1", "1h", "2y")]
    modules = ["pullback", "breakout", "pb+bo", "meanrev"]
    stops = [1.0, 1.5]
    rrs = [1.5, 2.0]
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    L = ["# BTC 快进快出策略研究 — 样本外验证", "",
         f"*生成于 {now}* · 数据 {SYMBOL}(Yahoo)· 点差按 **${SPREAD:.0f}** 扣",
         "",
         "对应 EA:`mql5/BTCScalper.mq5`。结果按 **R** 计(1R = 初始止损距离,已扣点差),",
         "和账户大小无关。时间止损 = 持有 "
         f"{MAX_HOLD} 根 K 线。",
         "",
         "**方法**:每份数据按时间切两半 —— 前一半看参数,后一半只跑一次。",
         f"只有**两边都为正**、且各自 ≥{MIN_TRADES} 笔的配置才算数。",
         f"注意:这里一共试了 {len(modules) * len(stops) * len(rrs) * len(datasets)} 组,",
         "组数越多,纯靠运气「两边都为正」的概率越高 —— 通过的配置要再用新数据复核。",
         "",
         "> ⚠️ K 线级回测,同一根 K 线同时碰到止损止盈一律按止损;点差固定、无滑点、",
         "> 无隔夜利息;Yahoo 现货价 ≠ XM 的 BTCUSD# 报价。**结果是乐观上界。**",
         ""]

    survivors = []
    cache = {}
    for name, interval, rng in datasets:
        try:
            bars = fetch(interval, rng)
        except Exception as e:
            L += [f"## {name}", "", f"取数失败:{e}", ""]
            continue
        if len(bars) < 600:
            L += [f"## {name}", "", f"K线不足({len(bars)}),跳过", ""]
            continue
        cache[name] = bars
        tr, te = split(bars)
        ind_tr, ind_te = prepare(tr), prepare(te)
        atr = B.atr_series(bars, ATR_P)
        atr_last = next((a for a in reversed(atr) if a), 0)
        t0 = dt.datetime.fromtimestamp(bars[0]["t"], dt.timezone.utc)
        t1 = dt.datetime.fromtimestamp(bars[-1]["t"], dt.timezone.utc)
        L += [f"## {name}（{interval} / {rng}）", "",
              f"{t0:%Y-%m-%d} → {t1:%Y-%m-%d} · {len(bars)} 根 · 近期 ATR ≈ ${atr_last:,.0f}"
              f" · 点差占 ATR {SPREAD / atr_last * 100:.0f}%" if atr_last else "", "",
              "| 入场 | 止损 | RR | 训练笔数 | 训练胜率 | 训练期望R | 验证笔数 | 验证胜率 | 验证期望R | 验证回撤R | 判定 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for module, st, rr in itertools.product(modules, stops, rrs):
            a = stats(run(tr, module, st, rr, SPREAD, ind_tr))
            b = stats(run(te, module, st, rr, SPREAD, ind_te))
            v, ok = verdict(a, b)
            if ok:
                survivors.append((name, module, st, rr, a, b))
            L.append(f"| {module} | {st}×ATR | 1:{rr} | {fmt(a)} | {fmt(b)} | {b['dd']} | {v} |")
        L.append("")

    # ---- 通过者:点差敏感度 + 过滤器消融 --------------------------------
    if survivors:
        L += ["## 通过者的压力测试", "",
              "同一组参数,点差放大/缩小,以及逐个关掉过滤器 —— 看结论是否依赖某个假设。",
              "(全样本,不再切分。)", "",
              "| 配置 | 点差$15 | 点差$30 | 点差$60 | 去掉VWAP | 去掉死市过滤 | 去掉影线过滤 | 去掉时段 |",
              "|---|---|---|---|---|---|---|---|"]
        for name, module, st, rr, _, _ in survivors:
            bars = cache[name]
            ind = prepare(bars)
            cells = []
            for sp in (15.0, 30.0, 60.0):
                s = stats(run(bars, module, st, rr, sp, ind))
                cells.append(f"{s['n']}笔 {s['exp']}R")
            for flag in ("USE_VWAP", "USE_DEAD", "USE_WICK", "USE_SESSION"):
                globals()[flag] = False
                s = stats(run(bars, module, st, rr, SPREAD, ind))
                globals()[flag] = True
                cells.append(f"{s['n']}笔 {s['exp']}R")
            L.append(f"| {name} {module} {st}×ATR 1:{rr} | " + " | ".join(cells) + " |")
        L.append("")

    L += ["## 结论", ""]
    if survivors:
        L += [f"**{len(survivors)} 组配置通过了样本外验证:**", ""]
        for name, module, st, rr, a, b in survivors:
            L.append(f"- **{name} · {module} · 止损{st}×ATR · RR1:{rr}** — "
                     f"训练 {a['n']}笔/{a['wr']}%/{a['exp']}R,"
                     f"验证 {b['n']}笔/{b['wr']}%/{b['exp']}R,验证最大回撤 {b['dd']}R")
        L += ["", "> 通过样本外验证**不等于**实盘会赚,只说明它不是单纯拟合噪音。",
              "> 先在 XM 模拟账户 / MT5 策略测试器(真实 tick)里复核,再考虑实盘。", ""]
    else:
        L += ["**没有任何一组配置通过样本外验证。**", "",
              "诚实的结论:这些网上常见的 BTC 剥头皮入场,扣完点差后在这段行情里",
              "**没有可验证的优势**。继续加密参数网格直到出现正数只会得到过拟合。",
              "EA 可以挂模拟盘观察,不建议上实盘。", ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
