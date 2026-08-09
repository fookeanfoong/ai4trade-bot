#!/usr/bin/env python3
"""外汇信号引擎 — 把「方案 A 顺势突破回踩 / 方案 B 双顶拒绝」写成代码。

为什么要代码化:手动盯盘时最大的亏损来源不是看错方向,是心理面 ——
摸顶、追单、扛单、报复性交易。这些在代码里都不存在。代码只会在
「触发条件 + 至少 2 个确认信号」同时成立时才输出一个有效信号,否则输出「等待」。

它**只生成信号,不下单**。下单要显式跑 live_trader / 或自己拿 broker_oanda 执行。
这是故意的:先让它在模拟盘上跑够 20 笔,你再决定要不要接真钱。

方案 A(顺势做多 · 突破回踩)
  触发: 最近一根 **已收盘** H4 收在阻力上方(带缓冲)
  确认: RSI>55 / 无顶背离 / EMA20>EMA50 且价格站上 EMA20 / MACD 柱连续两根走高
  入场: 回踩阻力(挂 Buy Limit)   止损: 结构低点下方   TP: 2R / 3.5R

方案 B(逆势做空 · 双顶拒绝)
  触发: 价格再上阻力区但 H4 收盘失败(长上影/收回区下方)
  确认: **RSI 顶背离(必需)** / MACD 柱缩短 / 阻力区被触及 >=2 次
  入场: 阻力下沿(挂 Sell Limit) 止损: 形态高点上方  TP: 2R / 3.5R
  仓位: 顺势方案的一半 —— 逆势本来就是低胜率高赔率的活

用法:
    python3 generate_signals_forex.py                    # 用 OANDA 实时 K 线
    python3 generate_signals_forex.py --candles f.json   # 用本地 K 线(离线自测)
    FOREX_PAIRS=EUR_USD,GBP_USD python3 generate_signals_forex.py

免责:研究/学习用途,不构成投资建议。外汇保证金杠杆高,可能损失全部本金。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

OUT_JSON = "signals_forex.json"
OUT_MD = "signals_forex.md"
EVENTS_FILE = "forex_events.json"

PAIRS = [p.strip().upper() for p in
         os.environ.get("FOREX_PAIRS", "EUR_USD").split(",") if p.strip()]
GRANULARITY = os.environ.get("FOREX_GRANULARITY", "H4")
# yahoo = 免费行情,不需要券商账户(默认);oanda = 走 v20 API(需要 fxTrade 账户)
DATA_SOURCE = os.environ.get("FOREX_DATA_SOURCE", "yahoo").lower()
CANDLE_COUNT = int(os.environ.get("FOREX_CANDLE_COUNT", "300"))

# --- 风险参数:整个系统里最重要的三行 ---------------------------------------
EQUITY_USD = float(os.environ.get("FOREX_EQUITY_USD", "200"))
RISK_PCT = float(os.environ.get("FOREX_RISK_PCT", "1.0"))
RISK_PCT_HARD_CAP = 2.0      # 超过 2% 直接夹回来。小账户连亏 5 笔就该还在牌桌上。

RR1 = 2.0                    # TP1 的回报风险比(用户要求 >= 1:2)
RR2 = 3.5                    # TP2
MIN_CONFIRMATIONS = 2        # 触发之外,还需要几个确认信号

# 找结构高低点的回溯根数。要随周期调:H4 的 60 根 = 10 天,H1 的 60 根只有
# 2.5 天,太短找不出像样的结构,所以 H1 要开大。
SWING_LOOKBACK = int(os.environ.get("FOREX_SWING_LOOKBACK", "60"))
SWING_WING = 2               # 分型左右各几根
BLACKOUT_HOURS = float(os.environ.get("FOREX_BLACKOUT_HOURS", "12"))

# --- 两条护栏。没有它们,风险模型在极端行情下会反过来咬你 --------------------
# 1) 止损下限:纯按 ATR 缩放,在低波动时段会算出 10 pips 的止损。EUR/USD 点差
#    1~2 pips,10 pips 止损里有 20% 是点差,剩下的会被日内噪音随手扫掉。
#    真实成本决定下限,不是波动率。
MIN_STOP_PIPS = float(os.environ.get("FOREX_MIN_STOP_PIPS", "15"))
SPREAD_STOP_MULT = 8.0       # 止损至少要有 8 倍点差的容身空间
# 2) 杠杆上限:units = 风险 / 止损距离 —— 止损越窄,单位数越大。5 pips 的止损
#    会算出 40000 单位($44k 名义),$200 本金上就是 200 倍杠杆,订单不是被拒
#    就是一根针爆仓。风险模型必须让位给保证金现实。
MAX_LEVERAGE = float(os.environ.get("FOREX_MAX_LEVERAGE", "20"))


# ------------------------------- 指标 ---------------------------------------
# 和 quotes_crypto.py 保持同一套实现口径(Wilder RSI、EMA 用首值播种)。
def ema_series(vals, period):
    if not vals:
        return []
    k = 2 / (period + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi_series(closes, period=14):
    """逐根的 RSI 序列 —— 背离判断需要历史值,只返回最后一个数不够用。"""
    n = len(closes)
    out = [None] * n
    if n < period + 1:
        return out
    deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
    seed = deltas[:period]
    up = sum(d for d in seed if d > 0) / period
    down = -sum(d for d in seed if d < 0) / period
    out[period] = 100.0 if down == 0 else 100 - 100 / (1 + up / down)
    for i, d in enumerate(deltas[period:], start=period + 1):
        up = (up * (period - 1) + (d if d > 0 else 0.0)) / period
        down = (down * (period - 1) + (-d if d < 0 else 0.0)) / period
        out[i] = 100.0 if down == 0 else 100 - 100 / (1 + up / down)
    return out


def macd(closes, fast=12, slow=26, signal=9):
    if len(closes) < slow + signal:
        return None
    ef, es = ema_series(closes, fast), ema_series(closes, slow)
    line = [f - s for f, s in zip(ef, es)]
    sig = ema_series(line, signal)
    hist = [l - s for l, s in zip(line, sig)]
    return {"line": line, "signal": sig, "hist": hist}


def atr(candles, period=14):
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h, l, pc = candles[i]["h"], candles[i]["l"], candles[i - 1]["c"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    a = sum(trs[:period]) / period
    for t in trs[period:]:
        a = (a * (period - 1) + t) / period       # Wilder 平滑
    return a


# ------------------------------- 结构 ---------------------------------------
def swing_points(candles, wing=SWING_WING, lookback=SWING_LOOKBACK):
    """分型高低点。返回 (highs, lows),每项是 (下标, 价格)。

    注意右侧也要 `wing` 根确认 —— 一个高点在右边还没走出来之前不算高点,
    这是画图时最容易自欺欺人的地方(事后看当然每个顶都很明显)。
    """
    n = len(candles)
    start = max(wing, n - lookback)
    highs, lows = [], []
    for i in range(start, n - wing):
        win = candles[i - wing:i + wing + 1]
        if candles[i]["h"] >= max(c["h"] for c in win):
            highs.append((i, candles[i]["h"]))
        if candles[i]["l"] <= min(c["l"] for c in win):
            lows.append((i, candles[i]["l"]))
    return highs, lows


def classify_structure(highs, lows):
    """HH/HL(上升) vs LH/LL(下降) vs 区间。"""
    if len(highs) < 2 or len(lows) < 2:
        return "数据不足", "无法判断"
    h1, h2 = highs[-2][1], highs[-1][1]
    l1, l2 = lows[-2][1], lows[-1][1]
    hh, hl = h2 > h1, l2 > l1
    lh, ll = h2 < h1, l2 < l1
    if hh and hl:
        return "上升趋势 (HH/HL)", "偏多"
    if lh and ll:
        return "下降趋势 (LH/LL)", "偏空"
    if lh and hl:
        return "收敛区间 (LH/HL)", "中性 — 等突破"
    return "震荡区间", "中性"


def rsi_bearish_divergence(candles, rsi_vals, highs):
    """顶背离:价格创等高/新高,但 RSI 没跟上。逆势做空的**唯一**入场理由。"""
    if len(highs) < 2:
        return False
    (i1, p1), (i2, p2) = highs[-2], highs[-1]
    r1, r2 = rsi_vals[i1], rsi_vals[i2]
    if r1 is None or r2 is None:
        return False
    return p2 >= p1 * 0.999 and r2 < r1 - 1.0


# ------------------------------- 事件 ---------------------------------------
def load_events(path=EVENTS_FILE):
    try:
        with open(path) as f:
            return json.load(f).get("events", [])
    except Exception:
        return []


def blackout(now, events, hours=BLACKOUT_HOURS):
    """高影响事件前 N 小时不开新仓。

    CPI/非农这种数据前的突破基本都是低质量突破 —— 方向对了都可能被反向抹掉,
    因为定价的是数据本身,不是图形。宁可错过,不可在数据前裸着。
    """
    hits = []
    for e in events:
        if str(e.get("impact", "")).lower() != "high":
            continue
        try:
            t = dt.datetime.fromisoformat(str(e["time_utc"]).replace("Z", "+00:00"))
        except Exception:
            continue
        delta_h = (t - now).total_seconds() / 3600.0
        if 0 <= delta_h <= hours:
            hits.append({"name": e.get("name", "?"), "in_hours": round(delta_h, 1),
                         "time_utc": e["time_utc"]})
    return hits


def fx_market_open(now):
    """外汇周末休市:周五 21:00 UTC 收,周日 21:00 UTC 开(夏令时会差 1 小时)。
    这是没有券商连接时的兜底判断;有 OANDA 连接时以它的 tradeable 为准。"""
    wd, hh = now.weekday(), now.hour       # 周一=0
    if wd == 5:
        return False
    if wd == 4 and hh >= 21:
        return False
    if wd == 6 and hh < 21:
        return False
    return True


# ------------------------------- 方案构建 -----------------------------------
def _rr(entry, stop, target):
    risk = abs(entry - stop)
    return round(abs(target - entry) / risk, 2) if risk else 0.0


def min_stop_px(pip, spread_pips):
    """止损的绝对下限:15 pips 与 8 倍点差取大。"""
    floor = MIN_STOP_PIPS * pip
    if spread_pips:
        floor = max(floor, SPREAD_STOP_MULT * spread_pips * pip)
    return floor


def build_plan_a(inst, candles, ind, levels, pip, risk_usd, floor_px=0.0):
    """顺势做多:突破 + 回踩。"""
    c = candles[-1]
    close, a = c["c"], ind["atr"]
    res = levels["resistance"]
    buffer_px = max(2 * pip, 0.15 * a)

    triggered = close > res + buffer_px
    conf = {
        f"{GRANULARITY}收盘破阻力": triggered,
        "RSI>55": (ind["rsi"] or 0) > 55,
        "无顶背离": not ind["bear_div"],
        "EMA20>EMA50且站上EMA20": ind["ema20"] > ind["ema50"] and close > ind["ema20"],
        "MACD柱连续两根走高": ind["hist_rising2"],
    }

    entry = res - 0.30 * a                      # 回踩「阻力转支撑」
    struct_low = levels["swing_low"]
    stop = min(struct_low - 0.20 * a, entry - 0.90 * a)
    stop = max(stop, entry - 1.50 * a)          # 止损太远就不值得做
    risk_px = max(entry - stop, floor_px)       # 再套一层绝对下限
    stop = entry - risk_px
    return {
        "name": "方案A · 顺势做多(突破回踩)",
        "direction": "long",
        "trigger": f"{GRANULARITY} 收盘 > {round(res + buffer_px, 5)}",
        "triggered": triggered,
        "entry": round(entry, 5), "stop": round(stop, 5),
        "tp1": round(entry + RR1 * risk_px, 5),
        "tp2": round(entry + RR2 * risk_px, 5),
        "rr1": RR1, "rr2": RR2,
        "stop_pips": round(risk_px / pip, 1),
        "risk_usd": round(risk_usd, 2),
        "size_factor": 1.0,
        "confirmations": conf,
        "confirmed": sum(1 for k, v in conf.items() if v and k != f"{GRANULARITY}收盘破阻力"),
        "invalidation": f"突破后 {GRANULARITY} 收回 {round(res, 5)} 下方 = 假突破,撤单转看方案B",
    }


def build_plan_b(inst, candles, ind, levels, pip, risk_usd, floor_px=0.0):
    """逆势做空:双顶拒绝。半仓。"""
    c = candles[-1]
    close, a = c["c"], ind["atr"]
    res = levels["resistance"]
    zone_lo = res - 0.30 * a

    rng = max(c["h"] - c["l"], 1e-9)
    upper_wick = (c["h"] - max(c["o"], c["c"])) / rng
    rejection = c["h"] >= zone_lo and close < res and upper_wick >= 0.45

    conf = {
        "阻力区拒绝K线": rejection,
        "RSI顶背离(必需)": ind["bear_div"],
        "MACD柱缩短": ind["hist_falling"],
        f"阻力区被触及>={2}次": levels["touches"] >= 2,
    }

    entry = zone_lo
    stop = res + 0.60 * a
    risk_px = max(stop - entry, floor_px)
    stop = entry + risk_px
    return {
        "name": "方案B · 逆势做空(双顶拒绝)",
        "direction": "short",
        "trigger": f"价格上探 {round(zone_lo, 5)}–{round(res, 5)} 后 {GRANULARITY} 收盘失败(长上影/吞没)",
        "triggered": rejection,
        "entry": round(entry, 5), "stop": round(stop, 5),
        "tp1": round(entry - RR1 * risk_px, 5),
        "tp2": round(entry - RR2 * risk_px, 5),
        "rr1": RR1, "rr2": RR2,
        "stop_pips": round(risk_px / pip, 1),
        "risk_usd": round(risk_usd * 0.5, 2),
        "size_factor": 0.5,
        "confirmations": conf,
        "confirmed": sum(1 for k, v in conf.items() if v and k != "阻力区拒绝K线"),
        "invalidation": f"{GRANULARITY} 收盘站上 {round(res + 0.30 * a, 5)} = 认错离场,翻回方案A",
        "mandatory_note": "没有 RSI 顶背离就不做 —— 逆势没有背离等于纯赌",
    }


def status_of(plan, market_open, blackouts):
    """信号状态机。任何一个否决项成立,就不可能变成『进场』。"""
    if not market_open:
        return "wait_market_closed"
    if blackouts:
        return "blocked_event"
    if plan["direction"] == "short" and not plan["confirmations"].get("RSI顶背离(必需)"):
        return "blocked_no_divergence"
    if not plan["triggered"]:
        return "armed"                       # 条件单待触发
    if plan["confirmed"] < MIN_CONFIRMATIONS:
        return "blocked_weak_confirmation"
    return "triggered"


# ------------------------------- 主流程 -------------------------------------
def analyze(inst, candles, risk_usd, broker=None):
    if len(candles) < 60:
        return {"instrument": inst, "error": f"K线不足({len(candles)}根),至少 60 根"}

    closes = [c["c"] for c in candles]
    pip = 0.01 if inst.endswith("_JPY") else 0.0001
    a = atr(candles)
    m = macd(closes)
    rsis = rsi_series(closes)
    if a is None or m is None:
        return {"instrument": inst, "error": "数据不足以计算 ATR/MACD"}

    e20, e50, e200 = (ema_series(closes, 20)[-1], ema_series(closes, 50)[-1],
                      ema_series(closes, 200)[-1] if len(closes) >= 200 else None)
    highs, lows = swing_points(candles)
    hist = m["hist"]

    res = max(h[1] for h in highs) if highs else max(c["h"] for c in candles[-SWING_LOOKBACK:])
    sup = min(l[1] for l in lows) if lows else min(c["l"] for c in candles[-SWING_LOOKBACK:])
    # 阻力区被触及的次数(触及 = 该根高点进入阻力区且与上次触及间隔 >=3 根)
    zone_lo = res - 0.30 * a
    touches, last_i = 0, -99
    for i, c in enumerate(candles[-SWING_LOOKBACK:]):
        if c["h"] >= zone_lo and i - last_i >= 3:
            touches += 1
            last_i = i

    ind = {
        "close": closes[-1],
        "rsi": round(rsis[-1], 1) if rsis[-1] is not None else None,
        "ema20": e20, "ema50": e50, "ema200": e200,
        "macd_hist": hist[-1],
        "hist_rising2": len(hist) >= 3 and hist[-1] > hist[-2] > hist[-3],
        "hist_falling": len(hist) >= 2 and hist[-1] < hist[-2],
        "macd_cross": "金叉" if m["line"][-1] > m["signal"][-1] else "死叉",
        "atr": a,
        "atr_pips": round(a / pip, 1),
        "bear_div": rsi_bearish_divergence(candles, rsis, highs),
    }
    levels = {
        "resistance": res,
        "support": sup,
        "swing_low": lows[-1][1] if lows else sup,
        "swing_high": highs[-1][1] if highs else res,
        "touches": touches,
    }
    struct, bias = classify_structure(highs, lows)

    ema_stack = "数据不足"
    if e200 is not None:
        if e20 > e50 > e200:
            ema_stack = "EMA20>EMA50>EMA200(多头排列)"
        elif e20 < e50 < e200:
            ema_stack = "EMA20<EMA50<EMA200(空头排列)"
        else:
            ema_stack = "均线缠绕(无排列)"

    spread = broker.spread_pips(inst) if broker else None
    floor_px = min_stop_px(pip, spread)

    return {
        "instrument": inst,
        "last_candle_time": candles[-1]["time"],
        "price": round(closes[-1], 5),
        "spread_pips": spread,
        "min_stop_pips": round(floor_px / pip, 1),
        "structure": struct,
        "bias": bias,
        "ema_stack": ema_stack,
        "indicators": {
            "rsi14": ind["rsi"],
            "macd": f"{ind['macd_cross']} / 柱={round(ind['macd_hist'], 6)}",
            "ema20": round(e20, 5), "ema50": round(e50, 5),
            "ema200": round(e200, 5) if e200 else None,
            "atr14_pips": ind["atr_pips"],
            "rsi_bearish_divergence": ind["bear_div"],
        },
        "levels": {
            "resistance": round(res, 5),
            "support": round(sup, 5),
            "zone_touches": touches,
        },
        "plans": [build_plan_a(inst, candles, ind, levels, pip, risk_usd, floor_px),
                  build_plan_b(inst, candles, ind, levels, pip, risk_usd, floor_px)],
        "_pip": pip,
    }


def size_plans(res, broker, equity):
    """给每个方案算单位数,再用杠杆上限夹一道。没有券商连接就按 XXX_USD 口径本地估算。"""
    inst = res["instrument"]
    for p in res.get("plans", []):
        risk = p["risk_usd"]
        dist = abs(p["entry"] - p["stop"])
        if dist <= 0:
            p["units"] = 0
            continue

        units = None
        if broker:
            try:
                units = broker.units_for_risk(inst, p["entry"], p["stop"], risk)
            except Exception as e:
                p["units_error"] = str(e)
        if units is None:
            if inst.endswith("_USD"):
                units = int(risk / dist)
            else:
                p["units"] = None
                p["units_error"] = "非美元计价品种需要券商汇率换算才能定量"
                continue

        # 杠杆护栏:名义价值 = 单位数 * 入场价(XXX_USD 直接就是美元)
        max_units = int((equity * MAX_LEVERAGE) / p["entry"]) if p["entry"] else 0
        if units > max_units:
            p["units_uncapped"] = units
            p["size_capped"] = (f"受 {MAX_LEVERAGE:g}x 杠杆上限限制,由 {units} 降到 "
                                f"{max_units} 单位;实际风险随之降到 "
                                f"${round(max_units * dist, 2)}(低于计划的 ${risk})")
            units = max_units
        p["units"] = units
        p["notional_usd"] = round(units * p["entry"], 2)
        p["leverage"] = round(units * p["entry"] / equity, 1) if equity else None
        p["actual_risk_usd"] = round(units * dist, 2)

        # ---- MT5 手数口径 --------------------------------------------------
        # 手动执行是在 MT5 上点的,那边按「手」下单,不认单位数。
        # 1 标准手 = 100,000 单位;最小 0.01 手 = 1,000 单位。
        lots = int(units / 1000) / 100.0          # 向下取整到 0.01
        p["mt5_lots"] = lots
        min_lot_risk = 1000 * dist                # 0.01 手能亏多少(USD计价品种)
        p["mt5_min_lot_risk_usd"] = round(min_lot_risk, 2)
        p["mt5_min_lot_risk_pct"] = round(min_lot_risk / equity * 100, 2) if equity else None
        if lots < 0.01:
            # 算出来不足 0.01 手 —— MT5 下不了,只能要么放弃、要么就用 0.01 手。
            # 判定标准是**硬上限(2%)**,不是这个方案的计划风险:按计划风险卡的话,
            # 半仓的方案B几乎每次都会被拦(0.75% 也算超),工具就废了。
            stop_pips = round(dist / (0.01 if inst.endswith("_JPY") else 0.0001), 1)
            pct = (min_lot_risk / equity * 100) if equity else None
            if pct is not None and pct > RISK_PCT_HARD_CAP:
                p["mt5_blocked"] = (
                    f"MT5 最小 0.01 手在 {stop_pips} pips 止损下要亏 "
                    f"${round(min_lot_risk, 2)} = 本金的 {round(pct, 2)}%,"
                    f"超过 {RISK_PCT_HARD_CAP}% 硬上限 —— **这笔在 MT5 上不该做**"
                )
            else:
                p["mt5_note"] = (
                    f"算出来是 {round(units / 100000, 4)} 手,不足 MT5 最小的 0.01 手。"
                    f"用 0.01 手的话实际风险 ${round(min_lot_risk, 2)}"
                    f"({round(pct, 2) if pct else '?'}% ,计划是 ${risk})—— "
                    f"在 {RISK_PCT_HARD_CAP}% 硬上限内,可以做,但你要知道风险被放大了"
                )


def _bail(reason, now, equity, risk_pct):
    """取不到行情时的统一出口:写一个诚实的『等待』,而不是半份猜出来的信号。"""
    doc = {
        "updated_at": now.isoformat(timespec="seconds"),
        "error": reason,
        "decision": "wait",
        "note": "拿不到可核实的行情就不产生信号 —— 宁可不交易,也不按猜测的价位下单。",
        "pairs": [], "equity_usd": equity, "risk_pct": risk_pct,
        "risk_usd": round(equity * risk_pct / 100, 2),
        "granularity": GRANULARITY, "market_open": fx_market_open(now),
        "disclaimer": "研究用途,不构成投资建议。",
    }
    with open(OUT_JSON, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(OUT_MD, "w") as f:
        f.write(f"# 外汇信号 — {doc['updated_at']}\n\n"
                f"**决策:等待** — {reason}\n\n{doc['note']}\n")
    print(f"[forex] {reason} -> decision=wait")
    return 0


def render_md(doc):
    L = [f"# 外汇信号 — {doc['updated_at']}", ""]
    L.append(f"**账户** ${doc['equity_usd']} · **单笔风险** {doc['risk_pct']}% = "
             f"${doc['risk_usd']} · **周期** {doc['granularity']}")
    L.append(f"**市场** {'开市' if doc['market_open'] else '休市'} · "
             f"**决策** `{doc['decision']}`")
    if doc.get("blackouts"):
        names = ", ".join(f"{b['name']}({b['in_hours']}h后)" for b in doc["blackouts"])
        L.append(f"> ⛔ **事件封锁期**:{names} —— 不开新仓")
    L.append("")
    for r in doc["pairs"]:
        if r.get("error"):
            L += [f"## {r['instrument']}", f"错误:{r['error']}", ""]
            continue
        L += [f"## {r['instrument']} — {r['price']}", "",
              f"- 结构:**{r['structure']}** · 情绪:{r['bias']}",
              f"- 均线:{r['ema_stack']}",
              f"- RSI(14):{r['indicators']['rsi14']} · MACD:{r['indicators']['macd']}"
              f" · ATR(14):{r['indicators']['atr14_pips']} pips",
              f"- 阻力:**{r['levels']['resistance']}**(触及 {r['levels']['zone_touches']} 次)"
              f" · 支撑:**{r['levels']['support']}**",
              f"- RSI顶背离:{'是' if r['indicators']['rsi_bearish_divergence'] else '否'}", ""]
        for p in r["plans"]:
            L += [f"### {p['name']} — `{p['status']}`",
                  f"- 触发:{p['trigger']}",
                  f"- 入场 **{p['entry']}** · 止损 **{p['stop']}**({p['stop_pips']} pips)"
                  f" · TP1 **{p['tp1']}**(1:{p['rr1']}) · TP2 **{p['tp2']}**(1:{p['rr2']})",
                  f"- 仓位:**MT5 {p.get('mt5_lots', '?')} 手**"
                  f"({p.get('units', '?')} 单位 · 名义 ${p.get('notional_usd', '?')}"
                  f" · {p.get('leverage', '?')}x)· 风险 ${p.get('actual_risk_usd', p['risk_usd'])}",]
            if p.get("mt5_blocked"):
                L.append(f"  - ⛔ {p['mt5_blocked']}")
            if p.get("mt5_note"):
                L.append(f"  - ⚠️ {p['mt5_note']}")
            if p.get("size_capped"):
                L.append(f"  - ⚠️ {p['size_capped']}")
            L += [
                  "- 确认:" + " / ".join(
                      f"{'✅' if v else '❌'}{k}" for k, v in p["confirmations"].items()),
                  f"- 否决:{p['invalidation']}", ""]
    L += ["---", f"*{doc['disclaimer']}*"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candles", help="离线 K 线 JSON: {\"EUR_USD\": [{o,h,l,c,time}...]}")
    ap.add_argument("--dry-run", action="store_true", default=True,
                    help="只生成信号,永不下单(默认且目前唯一模式)")
    ap.add_argument("--now", help="覆盖当前 UTC 时间(ISO格式),用于自测/回放")
    args = ap.parse_args()

    now = (dt.datetime.fromisoformat(args.now.replace("Z", "+00:00"))
           if args.now else dt.datetime.now(dt.timezone.utc))
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    risk_pct = min(RISK_PCT, RISK_PCT_HARD_CAP)
    if RISK_PCT > RISK_PCT_HARD_CAP:
        print(f"[warn] FOREX_RISK_PCT={RISK_PCT} 超过硬上限,已夹到 {risk_pct}%",
              file=sys.stderr)

    broker, candle_src = None, {}
    equity = EQUITY_USD
    if args.candles:
        with open(args.candles) as f:
            candle_src = json.load(f)
        market_open = fx_market_open(now)
    elif DATA_SOURCE == "yahoo":
        # 默认路线:免费行情,不需要任何券商账户。
        # 马来西亚的 OANDA 账户会被分到 Global Markets(BVI),而官方文档明写
        # v20 API 对该分支不开放 —— 所以行情必须和券商解耦。
        try:
            import fx_data
            for inst in PAIRS:
                candle_src[inst] = fx_data.candles(inst, GRANULARITY, CANDLE_COUNT)
            market_open = fx_market_open(now)
        except Exception as e:
            return _bail(f"Yahoo 取数失败: {e}", now, equity, risk_pct)
    else:
        try:
            import broker_oanda
            if not broker_oanda.OANDA_AVAILABLE:
                raise RuntimeError("未配置 OANDA_TOKEN / OANDA_ACCOUNT_ID")
            broker = broker_oanda.OandaBroker()
            broker.connect()
            acct = broker.account()
            if acct.get("equity"):
                equity = acct["equity"]      # 以券商真实净值为准,而不是写死的 200
            for inst in PAIRS:
                candle_src[inst] = broker.candles(inst, GRANULARITY, CANDLE_COUNT)
            market_open = broker.is_market_open(PAIRS[0])
            if market_open is None:
                market_open = fx_market_open(now)
        except Exception as e:
            return _bail(f"取数失败: {e}", now, equity, risk_pct)

    risk_usd = round(equity * risk_pct / 100, 2)
    blackouts = blackout(now, load_events())

    results = []
    for inst in PAIRS:
        cs = candle_src.get(inst) or []
        r = analyze(inst, cs, risk_usd, broker)
        if not r.get("error"):
            size_plans(r, broker, equity)
            for p in r["plans"]:
                p["status"] = status_of(p, market_open, blackouts)
            r.pop("_pip", None)
        results.append(r)

    live = [p for r in results for p in r.get("plans", []) if p.get("status") == "triggered"]
    decision = "enter" if live else "wait"

    # ---- 学习回路 ---------------------------------------------------------
    # 执行是手动的,机器人看不到你做了什么。所以它追踪**自己发出的信号**的结局:
    # 记下每个 triggered 信号,之后用后续 K 线回放判定成交/止盈/止损。
    # 这样不需要你汇报任何东西,就能积累出「这套规则到底行不行」的证据。
    try:
        import forex_journal
        jr = forex_journal.load()
        newly = 0
        for r in results:
            if r.get("error"):
                continue
            for p in r.get("plans", []):
                if p.get("status") == "triggered":
                    if forex_journal.record(jr, r, p, r["last_candle_time"]):
                        newly += 1
        resolved = forex_journal.update(jr, candle_src, now)
        st = forex_journal.stats(jr["entries"])
        print(f"[journal] 新记录 {newly} · 本次判出结局 {resolved} · "
              f"累计 {st['signals']} 个信号 / 已了结 {st['closed']} "
              f"/ 胜率 {st['win_rate']}% / 累计 {st['total_r']}R")
    except Exception as e:
        print(f"[journal] 学习回路失败(不影响信号): {e}", file=sys.stderr)

    doc = {
        "updated_at": now.isoformat(timespec="seconds"),
        "granularity": GRANULARITY,
        "market_open": bool(market_open),
        "equity_usd": round(equity, 2),
        "risk_pct": risk_pct,
        "risk_usd": risk_usd,
        "blackouts": blackouts,
        "decision": decision,
        "actionable_count": len(live),
        "pairs": results,
        "note": ("没有『触发 + >=2 确认』的方案一律 wait。宁可漏掉,也不硬凑交易 —— "
                 "小账户死于频繁交易,不死于错过行情。"),
        "disclaimer": "研究/学习用途,不构成投资建议或收益承诺。外汇保证金杠杆高,可能损失全部本金。",
    }
    with open(OUT_JSON, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    with open(OUT_MD, "w") as f:
        f.write(render_md(doc))

    print(f"[forex] {decision} · pairs={len(results)} · actionable={len(live)} · "
          f"risk=${risk_usd} · market={'open' if market_open else 'closed'}")
    for r in results:
        if r.get("error"):
            print(f"  {r['instrument']}: {r['error']}")
        else:
            for p in r["plans"]:
                print(f"  {r['instrument']} {p['name'][:12]} -> {p['status']} "
                      f"(确认 {p['confirmed']}/{MIN_CONFIRMATIONS})")
    if broker:
        broker.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
