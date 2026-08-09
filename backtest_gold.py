#!/usr/bin/env python3
"""GoldScalper 策略回测(Python 复刻,跑在 GitHub Actions 上取真实黄金行情)。

**为什么需要它**:我没有 MT5、没有策略测试器,不可能给你"执行了 100 笔、
胜率 70%"这种数字 —— 那只能是编的。这个脚本用真实历史行情跑一遍同样的规则,
给出**真实**的成交数、胜率、净利、回撤。难看也照报。

⚠️ **它不等于 MT5 策略测试器**,差异必须说清楚:
   1. 用 K 线回测,不是 tick 级。EA 在实盘里按 tick 判断保本/追踪,这里只能
      按 K 线的 OHLC 近似。
   2. 同一根 K 线里同时触及止损和止盈时,OHLC 判不出先后 —— **一律按止损算**。
      默认成"先到止盈"是回测造假的头号手法,能把垃圾策略美化成圣杯。
   3. 点差按固定值扣;真实点差会在数据前后放大数倍(EA 里的点差过滤器
      在这里无法完全还原)。
   4. 无滑点、无隔夜利息(黄金多头通常付息,实盘会更差一点)。
   结论:这份回测的结果是**乐观上界**。实盘只会更差,不会更好。

用法:
    python3 backtest_gold.py                 # 默认 1h / 2 年
    python3 backtest_gold.py --interval 15m --range 60d
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from urllib import request as urlrequest

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")

# --- 与 EA 对齐的参数(改这里等于改 EA 的 input) ---------------------------
EQUITY0        = float(os.environ.get("GOLD_EQUITY", "200"))
RISK_PCT       = float(os.environ.get("GOLD_RISK_PCT", "1.0"))
MAX_RISK_PCT   = float(os.environ.get("GOLD_MAX_RISK_PCT", "2.0"))
SPREAD_USD     = float(os.environ.get("GOLD_SPREAD", "0.30"))
MAX_SPREAD     = float(os.environ.get("GOLD_MAX_SPREAD", "0.50"))
MIN_STOP_SPRDX = 8.0
FAST, SLOW, TREND = 20, 50, 200
RSI_P, ATR_P   = 14, 14
RSI_BUY_MAX, RSI_SELL_MIN = 70.0, 30.0
ATR_STOP_MULT  = 1.2
REWARD_RISK    = 1.5
SWING_LOOKBACK = 100
SWING_WING     = 2
CONTRACT_OZ    = 100.0     # XAUUSD 合约 100 oz
# XAUUSD.sml 的最小手是 **0.001**(0.1盎司),不是标准合约的 0.01。
# 之前按 0.01 算,得出"$200 做不了黄金"——对这个品种是错的。
MIN_LOT  = float(os.environ.get("GOLD_MIN_LOT", "0.001"))
LOT_STEP = float(os.environ.get("GOLD_LOT_STEP", "0.001"))
USE_BREAKEVEN  = True
# >0 = 固定止损(美元金价距离),覆盖 ATR 模式。参考口径:30 "pips" = $3.00
FIXED_STOP_USD = float(os.environ.get("GOLD_FIXED_STOP", "0"))


# ------------------------------- 数据 ---------------------------------------
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
    o, h, l, c = q.get("open") or [], q.get("high") or [], q.get("low") or [], q.get("close") or []
    bars = []
    for i, t in enumerate(ts):
        try:
            oo, hh, ll, cc = o[i], h[i], l[i], c[i]
        except IndexError:
            continue
        if None in (oo, hh, ll, cc):
            continue      # 带 None 的整根丢掉,不做前值填充 —— 填充=凭空造K线
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
    sig = ema_series(line, 9)
    return line, sig


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
    """i 之前的分型高低点 -> 阻力/支撑。右侧必须有 wing 根确认。"""
    lo_i = max(SWING_WING + 1, i - SWING_LOOKBACK)
    res, sup = None, None
    for j in range(lo_i, i - SWING_WING):
        win = bars[j - SWING_WING:j + SWING_WING + 1]
        if bars[j]["h"] >= max(b["h"] for b in win):
            res = bars[j]["h"] if res is None else max(res, bars[j]["h"])
        if bars[j]["l"] <= min(b["l"] for b in win):
            sup = bars[j]["l"] if sup is None else min(sup, bars[j]["l"])
    return res, sup


# ------------------------------- 手数 ---------------------------------------
def lots_for(equity, stop_dist):
    """0.01 手 = 1 oz -> 价格每动 $1 盈亏 $1/0.01手。"""
    if stop_dist <= 0:
        return 0.0, 0.0
    per_lot = stop_dist * CONTRACT_OZ          # 1.0 手的美元风险
    risk = equity * min(RISK_PCT, MAX_RISK_PCT) / 100.0
    raw = risk / per_lot
    lots = int(raw / LOT_STEP) * LOT_STEP      # 向下取整
    if lots < MIN_LOT:
        lots = MIN_LOT
    actual = lots * per_lot
    if actual > equity * MAX_RISK_PCT / 100.0:
        return 0.0, actual                     # 超上限 -> 这笔不做
    return round(lots, 6), actual


# ------------------------------- 回测 ---------------------------------------
def run(bars):
    closes = [b["c"] for b in bars]
    ef, es, et = ema_series(closes, FAST), ema_series(closes, SLOW), ema_series(closes, TREND)
    rsi = rsi_series(closes, RSI_P)
    mline, msig = macd_series(closes)
    atr = atr_series(bars, ATR_P)

    equity = EQUITY0
    peak = equity
    max_dd = 0.0
    trades = []
    pos = None
    skipped_risk = 0

    start = max(TREND, SWING_LOOKBACK + SWING_WING + 2, ATR_P + 2)

    for i in range(start, len(bars) - 1):
        bar = bars[i]

        # ---- 持仓:用**下一根**K线判定出场 ----------------------------
        if pos:
            nb = bars[i + 1]
            hit_sl = (nb["l"] <= pos["sl"]) if pos["dir"] > 0 else (nb["h"] >= pos["sl"])
            hit_tp = (nb["h"] >= pos["tp"]) if pos["dir"] > 0 else (nb["l"] <= pos["tp"])

            exit_px = None
            if hit_sl and hit_tp:
                exit_px = pos["sl"]      # 一根K线里都碰到 -> 按亏损算(见文件头)
            elif hit_tp:
                exit_px = pos["tp"]
            elif hit_sl:
                exit_px = pos["sl"]
            elif USE_BREAKEVEN:
                # 到 1R 把止损移到开仓价 + 点差
                r = abs(pos["entry"] - pos["sl0"])
                prof = (nb["c"] - pos["entry"]) * pos["dir"]
                if r > 0 and prof >= r:
                    be = pos["entry"] + SPREAD_USD * pos["dir"]
                    if (pos["dir"] > 0 and be > pos["sl"]) or (pos["dir"] < 0 and be < pos["sl"]):
                        pos["sl"] = be

            if exit_px is not None:
                gross = (exit_px - pos["entry"]) * pos["dir"] * pos["lots"] * CONTRACT_OZ
                cost = SPREAD_USD * pos["lots"] * CONTRACT_OZ      # 进场已按 ask/bid 扣
                pnl = gross - cost
                equity += pnl
                peak = max(peak, equity)
                max_dd = max(max_dd, peak - equity)
                trades.append({
                    "t_in": pos["t"], "t_out": bars[i + 1]["t"], "dir": pos["dir"],
                    "entry": pos["entry"], "exit": exit_px, "lots": pos["lots"],
                    "pnl": round(pnl, 2), "r": round(pnl / pos["risk"], 2) if pos["risk"] else 0,
                    "reason": pos["reason"], "win": pnl > 0,
                })
                pos = None
            continue

        # ---- 入场判断(用已收盘的 bar i) -------------------------------
        if None in (rsi[i], atr[i]) or atr[i] <= 0:
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

        buf = max(atr[i] * 0.15, SPREAD_USD * 2)
        brk_up = up and bar["c"] > res + buf
        brk_dn = dn and bar["c"] < sup - buf
        pb_up = up and bar["c"] <= ef[i] + atr[i] * 0.5 and bar["c"] > es[i]
        pb_dn = dn and bar["c"] >= ef[i] - atr[i] * 0.5 and bar["c"] < es[i]

        d, reason = 0, ""
        if (brk_up or pb_up) and rsi[i] < RSI_BUY_MAX and macd_up:
            d, reason = 1, ("breakout" if brk_up else "pullback")
        elif (brk_dn or pb_dn) and rsi[i] > RSI_SELL_MIN and macd_dn:
            d, reason = -1, ("breakout" if brk_dn else "pullback")
        if d == 0:
            continue

        if FIXED_STOP_USD > 0:
            # 固定紧止损模式(参考资料的口径:"25~30 pips",按 $0.10/pip = $2.5~3.0)。
            # 和 ATR 模式是两条完全不同的路:ATR 止损在 $200 上超风险上限做不了,
            # 固定 $3 止损风险只有 1.5% —— 但它只有黄金 H1 波动的 0.3 倍,
            # 会不会被噪音扫穿是个实证问题,不是嘴上能定的。
            dist = FIXED_STOP_USD
        else:
            dist = max(atr[i] * ATR_STOP_MULT, SPREAD_USD * MIN_STOP_SPRDX)
        lots, would_risk = lots_for(equity, dist)
        if lots <= 0:
            skipped_risk += 1
            continue

        entry = bars[i + 1]["o"] + SPREAD_USD * d / 2   # 下一根开盘进,付半个点差
        pos = {"dir": d, "entry": entry, "sl": entry - dist * d,
               "sl0": entry - dist * d, "tp": entry + dist * REWARD_RISK * d,
               "lots": lots, "risk": lots * dist * CONTRACT_OZ,
               "t": bars[i + 1]["t"], "reason": reason}

    return trades, equity, max_dd, skipped_risk


def report(bars, trades, equity, max_dd, skipped, label):
    if not bars:
        return "无数据"
    t0 = dt.datetime.fromtimestamp(bars[0]["t"], dt.timezone.utc)
    t1 = dt.datetime.fromtimestamp(bars[-1]["t"], dt.timezone.utc)
    days = (t1 - t0).days
    n = len(trades)
    wins = sum(1 for t in trades if t["win"])
    wr = round(wins / n * 100, 1) if n else None
    net = round(equity - EQUITY0, 2)
    total_r = round(sum(t["r"] for t in trades), 2)
    exp_r = round(total_r / n, 3) if n else None
    streak = worst = 0
    for t in trades:
        streak = 0 if t["win"] else streak + 1
        worst = max(worst, streak)

    L = [f"### {label}", "",
         f"- 数据区间:{t0:%Y-%m-%d} → {t1:%Y-%m-%d}（{days} 天，{len(bars)} 根K线）",
         f"- **成交笔数:{n}**",
         f"- **胜率:{wr if wr is not None else '—'}%**（{wins} 胜 / {n - wins} 负）",
         f"- **净利:${net}**（起始 ${EQUITY0} → 结束 ${round(equity,2)}）",
         f"- 累计 R:{total_r} · 每笔期望:**{exp_r if exp_r is not None else '—'} R**",
         f"- 最大回撤:${round(max_dd,2)} · 最长连亏:{worst} 笔",
         f"- 因风险超上限被拒绝的信号:{skipped} 个", ""]
    if n < 30:
        L += [f"> ⚠️ 只有 {n} 笔,样本不足以下结论。", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", default="GC=F")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--range", dest="rng", default="2y")
    ap.add_argument("--out", default="reports/gold_backtest.md")
    ap.add_argument("--fixed-stop", type=float, default=None,
                    help="固定止损(金价美元距离),如 3.0 = 30pips@$0.10")
    ap.add_argument("--rr", type=float, default=None, help="盈亏比,覆盖默认")
    a = ap.parse_args()

    global FIXED_STOP_USD, REWARD_RISK
    if a.fixed_stop is not None: FIXED_STOP_USD = a.fixed_stop
    if a.rr is not None:         REWARD_RISK = a.rr

    try:
        bars = fetch(a.symbol, a.interval, a.rng)
    except Exception as e:
        print(f"[gold-backtest] 取数失败: {e}")
        return 1
    if len(bars) < 300:
        print(f"[gold-backtest] K线不足({len(bars)}),放弃")
        return 1

    trades, equity, dd, skipped = run(bars)
    stop_desc = (f"固定${FIXED_STOP_USD:.2f}" if FIXED_STOP_USD > 0
                 else f"ATR×{ATR_STOP_MULT}")
    label = f"{a.symbol} · {a.interval} · {a.rng} · 止损{stop_desc} · RR 1:{REWARD_RISK}"
    md = report(bars, trades, equity, dd, skipped, label)

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    header = ("# GoldScalper 回测（真实历史行情）\n\n"
              f"*生成于 {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}*\n\n"
              "⚠️ 这是 Python 复刻的 K 线级回测，**不等于 MT5 策略测试器**：\n"
              "同一根K线同时触及止损止盈时一律按**止损**计；点差按固定值扣，\n"
              "真实点差会在数据前后放大数倍；无滑点、无隔夜利息。\n"
              "**这份结果是乐观上界，实盘只会更差。**\n\n")
    with open(a.out, "w") as f:
        f.write(header + md)
    print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
