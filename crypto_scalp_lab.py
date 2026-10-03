#!/usr/bin/env python3
"""加密货币快进快出策略实验室 —— 网上流传的剥头皮策略,逐个用真实 M5 数据验证。

**流程(防止「挑出来的最好」只是运气)**
  1. 取最近 N 个完整月的币安现货 M5 数据(BTC/ETH/SOL,带真实成交量)
  2. 时间切成两段:前 2/3 = 样本内(IS),后 1/3 = 样本外(OOS)
  3. 每个策略只有一小组参数(≤ 6 组),**只看 IS** 选出最好的一组
  4. 选定的参数在 OOS 上**只跑一次**,不再调
  5. IS 和 OOS 都为正的策略才算「通过」,才值得加进 EA

**候选策略(都来自公开资料,规则见各 build_* 函数)**
  emamacd   当前 EA 规则(EMA20/50 交叉 + MACD + 回踩形态 + 放量),作为基线
  vwap_ema  EMA8/21 与 VWAP 同向排列,回踩快线出反转K线
  ema3_srsi 3EMA(8/14/50) 排列 + StochRSI K 穿 D(TradingView 公开策略,ATR 止损止盈)
  bb_rsi    收盘跌出布林下轨后收回带内 + RSI 超卖,回中轨离场(均值回归)
  rsi2      EMA200 顺势 + RSI(2) 极值回调,收盘越过 EMA5 离场(Connors 式)
  squeeze   TTM Squeeze:布林带缩进 Keltner 后放开,按动量方向突破
  supertrend Supertrend 翻色且顺 EMA200,反向翻色离场

**所有策略共用同一套执行**:信号K收盘后、下一根开盘市价进;必带止损;
同根同时触及止损止盈按止损计;点差按固定百分比扣(多空各付半个);
「快进快出」= 每个策略都有时间止损(最多持有 N 根)。

⚠️ K 线级回测,乐观上界。实盘只会更差。

用法:
    python3 crypto_scalp_lab.py                     # BTC/ETH/SOL 最近 12 个完整月
    python3 crypto_scalp_lab.py --months 6 --spread-pct 0.04
    python3 crypto_scalp_lab.py --csv a.csv         # 离线(t,o,h,l,c,v)
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys

import backtest_crypto_scalper as base

MIN_IS_TRADES = 30          # IS 少于这么多笔的参数组不参与「选最好」
MAX_STOP_PCT = 2.0          # 止损超过价格的 % 就不做(和 EA 同思路)
MIN_STOP_SPREAD_X = 3.0     # 止损至少是点差的几倍


# =============================== 指标 ========================================
def ema(v, p):
    return base.ema(v, p)


def sma(v, p):
    return base.sma(v, p)


def rolling_std(v, p):
    n, out = len(v), [0.0] * len(v)
    s = s2 = 0.0
    for i, x in enumerate(v):
        s += x; s2 += x * x
        if i >= p:
            y = v[i - p]; s -= y; s2 -= y * y
        k = min(i + 1, p)
        m = s / k
        out[i] = math.sqrt(max(s2 / k - m * m, 0.0))
    return out


def rsi(c, p):
    n = len(c)
    out = [50.0] * n
    g = l = 0.0
    for i in range(1, n):
        ch = c[i] - c[i - 1]
        up, dn = max(ch, 0.0), max(-ch, 0.0)
        if i <= p:
            g += up / p; l += dn / p
        else:
            g = (g * (p - 1) + up) / p
            l = (l * (p - 1) + dn) / p
        out[i] = 100.0 if l == 0 else 100.0 - 100.0 / (1.0 + g / l)
    return out


def atr(h, l, c, p=14):
    n = len(c)
    out = [0.0] * n
    a = 0.0
    for i in range(n):
        tr = h[i] - l[i] if i == 0 else max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
        a = tr if i == 0 else (a * (p - 1) + tr) / p
        out[i] = a
    return out


def rolling_max(v, p):
    return [max(v[max(0, i - p + 1):i + 1]) for i in range(len(v))]


def rolling_min(v, p):
    return [min(v[max(0, i - p + 1):i + 1]) for i in range(len(v))]


def stoch_rsi(c, rsi_p=14, st_p=14, k_s=3, d_s=3):
    r = rsi(c, rsi_p)
    hi, lo = rolling_max(r, st_p), rolling_min(r, st_p)
    raw = [(r[i] - lo[i]) / (hi[i] - lo[i]) * 100 if hi[i] > lo[i] else 50.0 for i in range(len(r))]
    k = sma(raw, k_s)
    return k, sma(k, d_s)


def vwap_daily(B):
    """按 UTC 自然日重置的 VWAP(加密货币 24/7,没有「开盘」,通行做法是 UTC 0 点重置)。"""
    out, pv, vv, day = [], 0.0, 0.0, None
    for t, h, l, c, v in zip(B["t"], B["h"], B["l"], B["c"], B["v"]):
        d = t // 86400
        if d != day:
            day, pv, vv = d, 0.0, 0.0
        tp = (h + l + c) / 3
        pv += tp * v; vv += v
        out.append(pv / vv if vv > 0 else c)
    return out


def supertrend(h, l, c, p=7, m=2.0):
    a = atr(h, l, c, p)
    n = len(c)
    trend = [1] * n
    line = [0.0] * n
    fu = fl = 0.0
    for i in range(n):
        hl2 = (h[i] + l[i]) / 2
        bu, bl = hl2 + m * a[i], hl2 - m * a[i]
        if i == 0:
            fu, fl = bu, bl
        else:
            fu = bu if (bu < fu or c[i - 1] > fu) else fu
            fl = bl if (bl > fl or c[i - 1] < fl) else fl
            if trend[i - 1] == 1:
                trend[i] = -1 if c[i] < fl else 1
            else:
                trend[i] = 1 if c[i] > fu else -1
        line[i] = fl if trend[i] == 1 else fu
    return trend, line


class Ind:
    """每个品种只算一次的指标缓存。"""
    def __init__(self, B):
        self.B = B
        self._c = {}

    def get(self, key, fn):
        if key not in self._c:
            self._c[key] = fn()
        return self._c[key]

    def ema(self, p):  return self.get(("ema", p), lambda: ema(self.B["c"], p))
    def atr(self, p=14): return self.get(("atr", p), lambda: atr(self.B["h"], self.B["l"], self.B["c"], p))
    def rsi(self, p):  return self.get(("rsi", p), lambda: rsi(self.B["c"], p))
    def sma(self, p):  return self.get(("sma", p), lambda: sma(self.B["c"], p))
    def std(self, p):  return self.get(("std", p), lambda: rolling_std(self.B["c"], p))
    def vwap(self):    return self.get(("vwap",), lambda: vwap_daily(self.B))
    def srsi(self):    return self.get(("srsi",), lambda: stoch_rsi(self.B["c"]))
    def st(self, p, m): return self.get(("st", p, m), lambda: supertrend(self.B["h"], self.B["l"], self.B["c"], p, m))
    def hh(self, p):   return self.get(("hh", p), lambda: rolling_max(self.B["h"], p))
    def ll(self, p):   return self.get(("ll", p), lambda: rolling_min(self.B["l"], p))


# =============================== 策略 ========================================
# 每个 build_* 返回 (sig, exitL, exitS, max_bars):
#   sig[i]   = None 或 (方向, 止损距离, 止盈R倍数或None)   —— 在第 i 根收盘时成立
#   exitL[j] = 多单在第 j 根收盘时是否离场(exitS 同理)
#   max_bars = 时间止损(根)

def swing_stop(B, i, d, look, buf):
    if d > 0:
        return B["c"][i] - min(B["l"][i - look + 1:i + 1]) + buf
    return max(B["h"][i - look + 1:i + 1]) - B["c"][i] + buf


def build_emamacd(I, p):
    B = I.B
    R = base.Rules(B)
    n = len(B["c"])
    sig = [None] * n
    for i in range(base.WARMUP, n):
        for d in (1, -1):
            ck = R.evaluate(i, d)
            if all(ck[:4]) and R.chop_crosses(i) <= base.MAX_CROSSES_IN_CHOP:
                buf = B["c"][i] * base.SL_BUFFER_PCT / 100
                sig[i] = (d, swing_stop(B, i, d, base.SWING_LOOKBACK, buf), p["rr"])
    f = [False] * n
    return sig, f, f, p["maxb"]


def build_vwap_ema(I, p):
    B = I.B
    o, h, l, c = B["o"], B["h"], B["l"], B["c"]
    ef, es, vw, a = I.ema(p["fast"]), I.ema(21), I.vwap(), I.atr()
    n = len(c)
    sig = [None] * n
    for i in range(60, n):
        up = ef[i] > es[i] > vw[i]
        dn = ef[i] < es[i] < vw[i]
        stop = (lambda d: swing_stop(B, i, d, 3, a[i] * 0.1)) if p["stop"] == "swing" else (lambda d: a[i] * 1.0)
        if up and l[i] <= ef[i] and c[i] > ef[i] and c[i] > o[i]:
            sig[i] = (1, stop(1), p["rr"])
        elif dn and h[i] >= ef[i] and c[i] < ef[i] and c[i] < o[i]:
            sig[i] = (-1, stop(-1), p["rr"])
    exitL = [ef[j] < es[j] for j in range(n)]
    exitS = [ef[j] > es[j] for j in range(n)]
    return sig, exitL, exitS, 24


def build_ema3_srsi(I, p):
    B = I.B
    c = B["c"]
    e8, e14, e50, a = I.ema(8), I.ema(14), I.ema(50), I.atr()
    k, dd = I.srsi()
    n = len(c)
    sig = [None] * n
    for i in range(60, n):
        kx_up = k[i] > dd[i] and k[i - 1] <= dd[i - 1]
        kx_dn = k[i] < dd[i] and k[i - 1] >= dd[i - 1]
        if p["zone"]:
            kx_up = kx_up and k[i - 1] < 20
            kx_dn = kx_dn and k[i - 1] > 80
        if e8[i] > e14[i] > e50[i] and kx_up and c[i] > e8[i]:
            sig[i] = (1, a[i] * p["sl"], p["tp"] / p["sl"])
        elif e8[i] < e14[i] < e50[i] and kx_dn and c[i] < e8[i]:
            sig[i] = (-1, a[i] * p["sl"], p["tp"] / p["sl"])
    f = [False] * n
    return sig, f, f, p.get("maxb", 24)


def build_bb_rsi(I, p):
    B = I.B
    c = B["c"]
    mid, sd, r, a, e200 = I.sma(20), I.std(20), I.rsi(14), I.atr(), I.ema(200)
    n = len(c)
    sig = [None] * n
    for i in range(210, n):
        lo1, lo0 = mid[i - 1] - 2 * sd[i - 1], mid[i] - 2 * sd[i]
        hi1, hi0 = mid[i - 1] + 2 * sd[i - 1], mid[i] + 2 * sd[i]
        long_ok = c[i - 1] < lo1 and c[i] > lo0 and min(r[i - 1], r[i]) < 30
        short_ok = c[i - 1] > hi1 and c[i] < hi0 and max(r[i - 1], r[i]) > 70
        if p["trend"]:
            long_ok = long_ok and c[i] > e200[i]
            short_ok = short_ok and c[i] < e200[i]
        if long_ok:
            sig[i] = (1, a[i] * p["sl"], None)
        elif short_ok:
            sig[i] = (-1, a[i] * p["sl"], None)
    exitL = [c[j] >= mid[j] for j in range(n)]       # 回到中轨就走
    exitS = [c[j] <= mid[j] for j in range(n)]
    return sig, exitL, exitS, 12


def build_rsi2(I, p):
    B = I.B
    c = B["c"]
    r2, e200, e5, a = I.rsi(2), I.ema(200), I.ema(5), I.atr()
    n = len(c)
    th = p["th"]
    sig = [None] * n
    for i in range(210, n):
        if c[i] > e200[i] and r2[i] < th:
            sig[i] = (1, a[i] * p["sl"], None)
        elif c[i] < e200[i] and r2[i] > 100 - th:
            sig[i] = (-1, a[i] * p["sl"], None)
    exitL = [c[j] > e5[j] for j in range(n)]
    exitS = [c[j] < e5[j] for j in range(n)]
    return sig, exitL, exitS, 12


def build_squeeze(I, p):
    B = I.B
    c = B["c"]
    mid, sd, a = I.sma(20), I.std(20), I.atr(20)
    kc_mid = I.ema(20)
    hh, ll = I.hh(20), I.ll(20)
    n = len(c)
    on = [(mid[i] - 2 * sd[i] > kc_mid[i] - 1.5 * a[i]) and (mid[i] + 2 * sd[i] < kc_mid[i] + 1.5 * a[i])
          for i in range(n)]
    mom = [c[i] - ((hh[i] + ll[i]) / 2 + mid[i]) / 2 for i in range(n)]
    sig = [None] * n
    for i in range(60, n):
        fired = on[i - 1] and not on[i] and all(on[i - k] for k in range(1, p["min_on"] + 1))
        if not fired:
            continue
        if mom[i] > 0 and mom[i] > mom[i - 1]:
            sig[i] = (1, a[i] * p["sl"], p["tp"] / p["sl"])
        elif mom[i] < 0 and mom[i] < mom[i - 1]:
            sig[i] = (-1, a[i] * p["sl"], p["tp"] / p["sl"])
    f = [False] * n
    return sig, f, f, 24


def build_supertrend(I, p):
    B = I.B
    c = B["c"]
    tr, line = I.st(p["p"], p["m"])
    e200 = I.ema(200)
    n = len(c)
    sig = [None] * n
    for i in range(210, n):
        if tr[i] == 1 and tr[i - 1] == -1 and c[i] > e200[i]:
            sig[i] = (1, c[i] - line[i], p["rr"])
        elif tr[i] == -1 and tr[i - 1] == 1 and c[i] < e200[i]:
            sig[i] = (-1, line[i] - c[i], p["rr"])
    exitL = [tr[j] == -1 for j in range(n)]
    exitS = [tr[j] == 1 for j in range(n)]
    return sig, exitL, exitS, 36


# ---- 1 分钟快进快出(M1)候选 -------------------------------------------------
def build_m1_ribbon(I, p):
    """EMA 8>13>21>34 排列 + 阳线收在所有 EMA 之上;收盘跌回 EMA8 下方离场。"""
    B = I.B
    o, c = B["o"], B["c"]
    e8, e13, e21, e34, a = I.ema(8), I.ema(13), I.ema(21), I.ema(34), I.atr()
    n = len(c)
    sig = [None] * n
    for i in range(60, n):
        if e8[i] > e13[i] > e21[i] > e34[i] and c[i] > o[i] and c[i] > e8[i] and o[i] <= e8[i]:
            stop = (c[i] - e34[i] + a[i] * 0.2) if p["stop"] == "ema34" else swing_stop(B, i, 1, 3, a[i] * 0.2)
            sig[i] = (1, stop, p["rr"])
        elif e8[i] < e13[i] < e21[i] < e34[i] and c[i] < o[i] and c[i] < e8[i] and o[i] >= e8[i]:
            stop = (e34[i] - c[i] + a[i] * 0.2) if p["stop"] == "ema34" else swing_stop(B, i, -1, 3, a[i] * 0.2)
            sig[i] = (-1, stop, p["rr"])
    exitL = [c[j] < e8[j] for j in range(n)]
    exitS = [c[j] > e8[j] for j in range(n)]
    return sig, exitL, exitS, 15


def build_m1_bb_rsi4(I, p):
    """RSI(4) 极值 + 收盘跌出布林(20,2)后收回带内;回中轨离场,止损放在最近 3 根极值外。"""
    B = I.B
    c = B["c"]
    mid, sd, r4, a = I.sma(20), I.std(20), I.rsi(4), I.atr()
    n = len(c)
    lo_th, hi_th = p["th"], 100 - p["th"]
    sig = [None] * n
    for i in range(30, n):
        lo1, lo0 = mid[i - 1] - 2 * sd[i - 1], mid[i] - 2 * sd[i]
        hi1, hi0 = mid[i - 1] + 2 * sd[i - 1], mid[i] + 2 * sd[i]
        if c[i - 1] < lo1 and c[i] > lo0 and r4[i - 1] < lo_th:
            sig[i] = (1, swing_stop(B, i, 1, 3, a[i] * p["buf"]), None)
        elif c[i - 1] > hi1 and c[i] < hi0 and r4[i - 1] > hi_th:
            sig[i] = (-1, swing_stop(B, i, -1, 3, a[i] * p["buf"]), None)
    exitL = [c[j] >= mid[j] for j in range(n)]
    exitS = [c[j] <= mid[j] for j in range(n)]
    return sig, exitL, exitS, 10


def build_m1_vwap_fade(I, p):
    """价格偏离 VWAP 超过 k 个标准差 + 出现反向K线 → 反向做,回到 VWAP 离场。"""
    B = I.B
    o, c = B["o"], B["c"]
    vw, a = I.vwap(), I.atr()
    dev = [c[i] - vw[i] for i in range(len(c))]
    sd = I.get(("devstd", 60), lambda: rolling_std(dev, 60))
    n = len(c)
    k = p["k"]
    sig = [None] * n
    for i in range(120, n):
        if sd[i] <= 0:
            continue
        if dev[i] < -k * sd[i] and c[i] > o[i]:
            sig[i] = (1, a[i] * p["sl"], None)
        elif dev[i] > k * sd[i] and c[i] < o[i]:
            sig[i] = (-1, a[i] * p["sl"], None)
    exitL = [c[j] >= vw[j] for j in range(n)]
    exitS = [c[j] <= vw[j] for j in range(n)]
    return sig, exitL, exitS, 15


def build_m1_spike_fade(I, p):
    """插针反转:K 线全长 >= m×ATR、成交量 >= 2×均量、影线占全长 >= 60% → 顺影线反方向进;止损在针尖外。"""
    B = I.B
    o, h, l, c, v = B["o"], B["h"], B["l"], B["c"], B["v"]
    a = I.atr()
    vavg = I.get(("vavg", 20), lambda: [sum(v[max(0, i - 20):i]) / max(1, min(i, 20)) for i in range(len(v))])
    n = len(c)
    sig = [None] * n
    for i in range(30, n):
        rng = h[i] - l[i]
        if rng < p["m"] * a[i - 1] or v[i] < 2.0 * vavg[i] or rng <= 0:
            continue
        lower, upper = min(o[i], c[i]) - l[i], h[i] - max(o[i], c[i])
        buf = a[i - 1] * 0.1
        if lower >= 0.6 * rng:
            sig[i] = (1, c[i] - l[i] + buf, p["rr"])
        elif upper >= 0.6 * rng:
            sig[i] = (-1, h[i] - c[i] + buf, p["rr"])
    f = [False] * n
    return sig, f, f, 10


STRATEGIES = {
    "emamacd": ("当前 EA:EMA20/50+MACD+回踩形态+放量(基线)", build_emamacd, [
        {"rr": 1.5, "maxb": 48}, {"rr": 1.0, "maxb": 24}, {"rr": 2.0, "maxb": 48}]),
    "vwap_ema": ("VWAP + EMA 回踩(8/21 与 VWAP 同向,回踩快线反转K)", build_vwap_ema, [
        {"fast": f, "stop": s, "rr": rr} for f in (8,) for s in ("swing", "atr") for rr in (1.0, 1.5, 2.0)]),
    "ema3_srsi": ("3EMA(8/14/50) + StochRSI 交叉,ATR 止损止盈", build_ema3_srsi, [
        {"sl": 3.0, "tp": 2.0, "zone": False}, {"sl": 1.5, "tp": 1.5, "zone": False},
        {"sl": 1.0, "tp": 1.5, "zone": False}, {"sl": 3.0, "tp": 2.0, "zone": True},
        {"sl": 1.5, "tp": 1.5, "zone": True}, {"sl": 1.0, "tp": 1.5, "zone": True}]),
    "ema3_srsi_fast": ("3EMA+StochRSI 同信号,出场更快(小止盈 / 短时间止损)", build_ema3_srsi, [
        {"sl": 3.0, "tp": 1.0, "zone": True, "maxb": 8}, {"sl": 3.0, "tp": 1.0, "zone": True, "maxb": 4},
        {"sl": 1.5, "tp": 1.0, "zone": True, "maxb": 8}, {"sl": 1.5, "tp": 1.0, "zone": True, "maxb": 4},
        {"sl": 3.0, "tp": 2.0, "zone": True, "maxb": 8}, {"sl": 2.0, "tp": 1.5, "zone": True, "maxb": 6}]),
    "bb_rsi": ("布林带(20,2)外收回 + RSI 超买超卖,回中轨离场", build_bb_rsi, [
        {"sl": s, "trend": t} for s in (1.0, 1.5, 2.0) for t in (False, True)]),
    "rsi2": ("EMA200 顺势 + RSI(2) 极值回调,收盘越过 EMA5 离场", build_rsi2, [
        {"th": th, "sl": s} for th in (5, 10) for s in (1.5, 2.5)]),
    "squeeze": ("TTM Squeeze 放开 + 动量方向突破", build_squeeze, [
        {"min_on": m, "sl": s, "tp": tp} for m in (3, 6) for (s, tp) in ((1.0, 1.5), (1.5, 2.0), (1.0, 2.0))]),
    "supertrend": ("Supertrend 翻色 + EMA200 顺势,反向翻色离场", build_supertrend, [
        {"p": 7, "m": 2.0, "rr": None}, {"p": 7, "m": 2.0, "rr": 2.0},
        {"p": 10, "m": 3.0, "rr": None}, {"p": 10, "m": 3.0, "rr": 2.0}]),
    "m1_ribbon": ("M1 EMA带(8/13/21/34)顺势,阳线站上全部 EMA,跌回 EMA8 离场", build_m1_ribbon, [
        {"stop": st, "rr": rr} for st in ("swing", "ema34") for rr in (1.0, 1.5, 2.0)]),
    "m1_bb_rsi4": ("M1 RSI(4)+布林带外收回,回中轨离场", build_m1_bb_rsi4, [
        {"th": th, "buf": b} for th in (10, 20) for b in (0.2, 0.5, 1.0)]),
    "m1_vwap_fade": ("M1 VWAP 偏离 k 个标准差反向,回 VWAP 离场", build_m1_vwap_fade, [
        {"k": k, "sl": sl} for k in (2.0, 2.5, 3.0) for sl in (1.5, 3.0)]),
    "m1_spike_fade": ("M1 插针反转(放量长影线,止损在针尖外)", build_m1_spike_fade, [
        {"m": m, "rr": rr} for m in (2.0, 3.0) for rr in (0.7, 1.0, 1.5)]),
}


# =============================== 执行 ========================================
def simulate(B, built, spread_pct):
    sig, exitL, exitS, maxb = built
    o, h, l, c, t = B["o"], B["h"], B["l"], B["c"], B["t"]
    n = len(c)
    trades = []
    i = base.WARMUP
    while i < n - 2:
        s = sig[i]
        if s is None:
            i += 1
            continue
        d, sd, tpm = s
        j = i + 1
        hs = o[j] * spread_pct / 200.0
        entry = o[j] + d * hs
        if sd <= 0 or sd < 2 * hs * MIN_STOP_SPREAD_X or sd / entry * 100 > MAX_STOP_PCT:
            i += 1
            continue
        sl = entry - d * sd
        tp = entry + d * tpm * sd if tpm else None
        ex = None
        k = j
        while k < n:
            adv = (l[k] - hs) if d > 0 else (h[k] + hs)
            fav = (h[k] - hs) if d > 0 else (l[k] + hs)
            opn = (o[k] - hs) if d > 0 else (o[k] + hs)
            if (adv <= sl) if d > 0 else (adv >= sl):
                ex = (opn if ((opn < sl) if d > 0 else (opn > sl)) else sl)
                break
            if tp is not None and ((fav >= tp) if d > 0 else (fav <= tp)):
                ex = tp
                break
            if (exitL[k] if d > 0 else exitS[k]) or k - j + 1 >= maxb:
                ex = c[k] - d * hs
                break
            k += 1
        if ex is None:
            break
        trades.append((t[j], (ex - entry) * d / sd, d, k - j + 1))
        i = k
    return trades


def st(tr):
    n = len(tr)
    if n == 0:
        return {"n": 0, "wr": 0, "exp": 0, "lo": 0, "hi": 0, "total": 0, "pf": 0, "dd": 0, "bars": 0}
    rs = [x[1] for x in tr]
    mu = sum(rs) / n
    sd = math.sqrt(sum((r - mu) ** 2 for r in rs) / (n - 1)) if n > 1 else 0
    se = sd / math.sqrt(n) if n > 1 else 0
    gp, gl = sum(r for r in rs if r > 0), -sum(r for r in rs if r < 0)
    peak = cum = dd = 0.0
    for r in rs:
        cum += r; peak = max(peak, cum); dd = max(dd, peak - cum)
    return {"n": n, "wr": sum(1 for r in rs if r > 0) / n * 100, "exp": mu, "lo": mu - 1.96 * se,
            "hi": mu + 1.96 * se, "total": sum(rs), "pf": gp / gl if gl > 0 else float("inf"), "dd": dd,
            "bars": sum(x[3] for x in tr) / n}


def row(label, s, extra=""):
    if s["n"] == 0:
        return f"| {label} | 0 | – | – | – | – | – | – |{extra}"
    pf = "∞" if s["pf"] == float("inf") else f"{s['pf']:.2f}"
    return (f"| {label} | {s['n']} | {s['wr']:.0f}% | {s['exp']:+.3f}R | [{s['lo']:+.2f}, {s['hi']:+.2f}] "
            f"| {s['total']:+.1f}R | {pf} | {s['bars']:.1f} |{extra}")


def pstr(p):
    return ", ".join(f"{k}={v}" for k, v in p.items())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbols", default="BTCUSDT,ETHUSDT,SOLUSDT")
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--csv")
    ap.add_argument("--spread-pct", type=float, default=0.04)
    ap.add_argument("--interval", default="5m", choices=["1m", "5m", "15m", "1h"],
                    help="K 线周期。周期越长止损越宽,点差占比越小")
    ap.add_argument("--max-stop-pct", type=float, default=None,
                    help="止损超过价格的 %% 就不做(默认 1m=1, 5m=2, 15m=3, 1h=5)")
    ap.add_argument("--only", help="只跑这些策略(逗号分隔)")
    ap.add_argument("--out", default="reports/crypto_scalp_lab.md")
    args = ap.parse_args()
    global MAX_STOP_PCT
    MAX_STOP_PCT = args.max_stop_pct or {"1m": 1.0, "5m": 2.0, "15m": 3.0, "1h": 5.0}[args.interval]

    data = {}
    if args.csv:
        data[os.path.basename(args.csv)] = base.load_csv(args.csv)
        label = f"CSV {args.csv}"
    else:
        for s in args.symbols.split(","):
            s = s.strip().upper()
            if s:
                data[s] = base.fetch_binance(s, args.months, args.interval)
        ms = base.month_list(args.months)
        tf = {"1m": "M1", "5m": "M5", "15m": "M15", "1h": "H1"}[args.interval]
        label = f"币安现货 {tf} · {ms[0][0]}-{ms[0][1]:02d} ~ {ms[-1][0]}-{ms[-1][1]:02d}"
    data = {k: v for k, v in data.items() if len(v["t"]) > base.WARMUP + 500}
    if not data:
        print("没有可用数据"); return 1

    t0 = min(B["t"][0] for B in data.values())
    t1 = max(B["t"][-1] for B in data.values())
    cut = t0 + (t1 - t0) * 2 // 3
    fmt = lambda x: dt.datetime.utcfromtimestamp(x).strftime("%Y-%m-%d")
    inds = {s: Ind(B) for s, B in data.items()}
    names = [x.strip() for x in args.only.split(",")] if args.only else list(STRATEGIES)

    results = []    # (name, desc, best_params, is_stats, oos_stats, grid_rows, oos_trades_by_sym, cost_rows)
    for name in names:
        desc, build, grid = STRATEGIES[name]
        grid_rows = []
        best = None
        for p in grid:
            trs = {s: simulate(data[s], build(inds[s], p), args.spread_pct) for s in data}
            is_tr = sorted([x for v in trs.values() for x in v if x[0] < cut])
            oos_tr = sorted([x for v in trs.values() for x in v if x[0] >= cut])
            s_is = st(is_tr)
            grid_rows.append((p, s_is))
            if s_is["n"] >= MIN_IS_TRADES and (best is None or s_is["exp"] > best[1]["exp"]):
                best = (p, s_is, st(oos_tr), trs)
        if best is None:
            results.append((name, desc, None, None, None, grid_rows, None, None))
            print(f"[{name}] 没有参数组在 IS 达到 {MIN_IS_TRADES} 笔")
            continue
        p, s_is, s_oos, trs = best
        # 成本敏感度:同一组参数,换点差再跑 OOS(快进快出的生死线)
        cost_rows = []
        for sp in (0.01, 0.02, 0.04, 0.08):
            tr2 = sorted([x for s in data for x in simulate(data[s], build(inds[s], p), sp) if x[0] >= cut])
            cost_rows.append((sp, st(tr2)))
        by_sym = {s: st([x for x in v if x[0] >= cut]) for s, v in trs.items()}
        results.append((name, desc, p, s_is, s_oos, grid_rows, by_sym, cost_rows))
        print(f"[{name}] best {pstr(p)} | IS n={s_is['n']} exp={s_is['exp']:+.3f} | "
              f"OOS n={s_oos['n']} exp={s_oos['exp']:+.3f}")

    # ------------------------------ 报告 ------------------------------
    L = ["# 加密货币快进快出策略实验室（真实历史行情）\n",
         f"*生成于 {dt.datetime.utcnow():%Y-%m-%dT%H:%MZ} · {label} · 品种 {', '.join(data)}*\n",
         f"样本内（选参数）：{fmt(t0)} ~ {fmt(cut)} · 样本外（只跑一次）：{fmt(cut)} ~ {fmt(t1)}\n",
         f"> 点差 {args.spread_pct:.3f}%（多空各付一半），止损上限 {MAX_STOP_PCT:.1f}% 价格，无手续费、无滑点。同根K线同时触及止损和止盈按**止损**计。",
         "> 每个策略只在**样本内**从 ≤6 组参数里挑最好的，**样本外只跑一次**。K 线级回测是乐观上界。\n",
         "R = 以止损距离为 1 的盈亏倍数。「持仓」= 平均持有 K 线根数（快进快出看这个）。\n",
         "## 结论：谁通过了\n",
         "通过 = 样本内期望 > 0 **且** 样本外期望 > 0。只有通过的才值得加进 EA。\n",
         "| 策略 | 选中参数 | 样本内 笔/期望 | 样本外 笔/胜率/期望 | 样本外 95% 区间 | 样本外 PF | 持仓 | 通过 |",
         "|---|---|---|---|---|---|---|---|"]
    passed = []
    for name, desc, p, s_is, s_oos, grid_rows, by_sym, cost_rows in results:
        if p is None:
            L.append(f"| {name} | – | 样本不足 | – | – | – | – | ❌ |")
            continue
        ok = s_is["exp"] > 0 and s_oos["exp"] > 0 and s_oos["n"] >= 15
        if ok:
            passed.append(name)
        pf = "∞" if s_oos["pf"] == float("inf") else f"{s_oos['pf']:.2f}"
        L.append(f"| {name} | {pstr(p)} | {s_is['n']} / {s_is['exp']:+.3f}R | {s_oos['n']} / {s_oos['wr']:.0f}% / "
                 f"{s_oos['exp']:+.3f}R | [{s_oos['lo']:+.2f}, {s_oos['hi']:+.2f}] | {pf} | {s_oos['bars']:.1f} | "
                 f"{'✅' if ok else '❌'} |")
    L.append("")
    L.append("**通过的策略**：" + ("、".join(passed) if passed else "**没有**。网上这些剥头皮策略在这段真实行情里扣掉点差后都不赚钱。") + "\n")

    for name, desc, p, s_is, s_oos, grid_rows, by_sym, cost_rows in results:
        L.append(f"## {name} — {desc}\n")
        L.append("样本内参数网格（只用来选参数）：\n")
        L.append("| 参数 | 笔数 | 胜率 | 期望 | 95% 区间 | 累计 | PF | 持仓 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for gp, gs in grid_rows:
            mark = " ⬅ 选中" if p is not None and gp == p else ""
            L.append(row(pstr(gp) + mark, gs))
        L.append("")
        if p is None:
            continue
        L.append("选中参数的样本外，分品种：\n")
        L.append("| 品种 | 笔数 | 胜率 | 期望 | 95% 区间 | 累计 | PF | 持仓 |")
        L.append("|---|---|---|---|---|---|---|---|")
        for s, ss in by_sym.items():
            L.append(row(s, ss))
        L.append("")
        L.append("点差敏感度（样本外）：" + " · ".join(f"{sp:.2f}% → {cs['exp']:+.3f}R（{cs['n']}笔）"
                                         for sp, cs in cost_rows) + "\n")
    L.append("*研究/学习用途，不构成投资建议。*")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"报告 → {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
