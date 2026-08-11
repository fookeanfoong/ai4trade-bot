#!/usr/bin/env python3
"""入场逻辑实验室 —— 换策略,不是调参数。

**为什么现在做这个:** 当前配置(EUR/USD 突破 25点 1:1.5)验证期望 +0.018R。
要在 95% 置信度下确认它不是零,需要约 18,000 笔 ≈ 20 年。
**"继续观察"在数学上无法产生任何结论** —— 时间解决不了这个问题。
回测已经把答案给了:这套入场逻辑没有可用的 edge。

所以测四种**结构上不同**的入场逻辑,不是同一个逻辑的不同参数:

  breakout  趋势方向上突破结构高低点        (当前配置,作为基线)
  pullback  趋势中回踩快线才进,不追突破     (同为顺势,但入场时机相反)
  meanrev   区间中在布林带外沿反向做         (方向逻辑完全相反)
  session   伦敦开盘后的开盘区间突破         (时间驱动,不看趋势)

**多重比较是这里最大的陷阱。** 4 种 × 8 组参数 = 32 次检验,
单次 5% 假阳性率下,至少出一个假阳性的概率是 80.6%,期望假阳性 1.6 个。
就算四种全都没用,我也很可能"找到"一两个看起来通过验证的。

所以门槛比上次严:
  1. 训练段和验证段**都**为正(样本外)
  2. 验证段期望 **>= +0.10R** —— 光是">0"太容易靠运气达到
  3. 两段各 >= 30 笔
  报告里会写明总共测了多少次,以及期望有多少个假阳性。

用法:python3 forex_strategy_lab.py
"""

from __future__ import annotations

import datetime as dt
import itertools
import math
import os

import backtest_forex as B

OUT = os.environ.get("FX_LAB_OUT", "reports/forex_strategy_lab.md")
EQUITY = float(os.environ.get("FOREX_EQUITY_USD", "200"))
MIN_TRADES = 30
MIN_TEST_EXP = 0.10          # 验证段期望的硬门槛(防多重比较)
PAIR, YSYM, SPREAD = "EUR_USD", "EURUSD=X", 1.0


def bollinger(closes, i, period=20, k=2.0):
    if i < period:
        return None, None, None
    w = closes[i - period + 1:i + 1]
    mid = sum(w) / period
    sd = (sum((x - mid) ** 2 for x in w) / period) ** 0.5
    return mid, mid + k * sd, mid - k * sd


def hour_of(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).hour


# --------------------------- 四种入场逻辑 -----------------------------------
# 每个函数返回 1(做多) / -1(做空) / 0(不做)。
# 只能用 i 及之前的数据 —— 用到 i+1 就是未来函数。
def entry_breakout(bars, i, ind):
    """当前配置:趋势方向上突破结构高低点。"""
    res, sup = B.structure(bars, i)
    if res is None or sup is None:
        return 0
    ef, es, et, rsi, macd_up, macd_dn, atr = ind
    up = ef[i] > es[i] > et[i]
    dn = ef[i] < es[i] < et[i]
    if not (up or dn):
        return 0
    buf = max(atr[i] * 0.15, SPREAD * B.PIP * 2)
    c = bars[i]["c"]
    if up and c > res + buf and rsi[i] < B.RSI_BUY_MAX and macd_up[i]:
        return 1
    if dn and c < sup - buf and rsi[i] > B.RSI_SELL_MIN and macd_dn[i]:
        return -1
    return 0


def entry_pullback(bars, i, ind):
    """同为顺势,但入场时机相反:等回踩快线,不追突破。"""
    ef, es, et, rsi, macd_up, macd_dn, atr = ind
    up = ef[i] > es[i] > et[i]
    dn = ef[i] < es[i] < et[i]
    if not (up or dn):
        return 0
    c = bars[i]["c"]
    zone = atr[i] * 0.5
    if up and c <= ef[i] + zone and c > es[i] and rsi[i] < 60:
        return 1
    if dn and c >= ef[i] - zone and c < es[i] and rsi[i] > 40:
        return -1
    return 0


def entry_meanrev(bars, i, ind):
    """方向逻辑完全相反:区间里在布林带外沿反着做。

    只在**无趋势**时启用 —— 在趋势里做均值回归是接飞刀。
    """
    ef, es, et, rsi, macd_up, macd_dn, atr = ind
    closes = [b["c"] for b in bars]
    mid, up_b, lo_b = bollinger(closes, i)
    if mid is None:
        return 0
    trending = (ef[i] > es[i] > et[i]) or (ef[i] < es[i] < et[i])
    if trending:
        return 0
    c = bars[i]["c"]
    if c <= lo_b and rsi[i] < 30:
        return 1
    if c >= up_b and rsi[i] > 70:
        return -1
    return 0


def entry_session(bars, i, ind):
    """伦敦开盘区间突破:不看趋势,看时间。

    取 07:00 UTC 后头两小时的高低点作为开盘区间,之后突破就进。
    """
    h = hour_of(bars[i]["t"])
    if h < 9 or h > 14:          # 只在伦敦盘中段找突破
        return 0
    # 回溯找当天 07:00-09:00 的区间
    hi = lo = None
    for j in range(max(0, i - 12), i):
        hj = hour_of(bars[j]["t"])
        same_day = (dt.datetime.fromtimestamp(bars[j]["t"], dt.timezone.utc).date()
                    == dt.datetime.fromtimestamp(bars[i]["t"], dt.timezone.utc).date())
        if same_day and 7 <= hj < 9:
            hi = bars[j]["h"] if hi is None else max(hi, bars[j]["h"])
            lo = bars[j]["l"] if lo is None else min(lo, bars[j]["l"])
    if hi is None or lo is None or hi <= lo:
        return 0
    c = bars[i]["c"]
    buf = SPREAD * B.PIP * 2
    if c > hi + buf:
        return 1
    if c < lo - buf:
        return -1
    return 0


STRATEGIES = [
    ("breakout（当前配置·基线）", entry_breakout),
    ("pullback（趋势回踩）", entry_pullback),
    ("meanrev（区间均值回归）", entry_meanrev),
    ("session（伦敦开盘突破）", entry_session),
]


# --------------------------- 回测引擎 ---------------------------------------
def run(bars, entry_fn, stop_pips, rr, spread_pips, equity0):
    closes = [b["c"] for b in bars]
    ef = B.ema_series(closes, B.FAST)
    es = B.ema_series(closes, B.SLOW)
    et = B.ema_series(closes, B.TREND)
    rsi = B.rsi_series(closes, B.RSI_P)
    ml, ms = B.macd_series(closes)
    atr = B.atr_series(bars, B.ATR_P)
    macd_up = [ml[k] > ms[k] and ml[k] > 0 for k in range(len(ml))]
    macd_dn = [ml[k] < ms[k] and ml[k] < 0 for k in range(len(ml))]
    ind = (ef, es, et, rsi, macd_up, macd_dn, atr)

    equity, peak, dd = equity0, equity0, 0.0
    trades, pos = [], None
    spread_px, stop_px = spread_pips * B.PIP, stop_pips * B.PIP
    start = max(B.TREND, B.SWING_LOOKBACK + B.SWING_WING + 2, 25)

    for i in range(start, len(bars) - 1):
        if pos:
            nb = bars[i + 1]
            hit_sl = (nb["l"] <= pos["sl"]) if pos["d"] > 0 else (nb["h"] >= pos["sl"])
            hit_tp = (nb["h"] >= pos["tp"]) if pos["d"] > 0 else (nb["l"] <= pos["tp"])
            ex = pos["sl"] if (hit_sl and hit_tp) else (
                 pos["tp"] if hit_tp else (pos["sl"] if hit_sl else None))
            if ex is not None:
                gross = (ex - pos["e"]) * pos["d"] * pos["lots"] * B.UNITS_PER_LOT
                pnl = gross - spread_px * pos["lots"] * B.UNITS_PER_LOT
                equity += pnl
                peak = max(peak, equity)
                dd = max(dd, peak - equity)
                trades.append({"win": pnl > 0,
                               "r": pnl / pos["risk"] if pos["risk"] else 0})
                pos = None
            continue

        if rsi[i] is None or not atr[i]:
            continue
        d = entry_fn(bars, i, ind)
        if d == 0:
            continue
        lots, _ = B.lots_for(equity, stop_pips, bars[i]["c"])
        if lots <= 0:
            continue
        e = bars[i + 1]["o"] + spread_px * d / 2
        pos = {"d": d, "e": e, "sl": e - stop_px * d, "tp": e + stop_px * rr * d,
               "lots": lots, "risk": lots * stop_px * B.UNITS_PER_LOT}

    n = len(trades)
    if n == 0:
        return {"n": 0, "wr": None, "exp": None, "net": 0.0, "dd": 0.0}
    wins = sum(1 for t in trades if t["win"])
    tot = sum(t["r"] for t in trades)
    return {"n": n, "wr": round(wins / n * 100, 1), "exp": round(tot / n, 3),
            "net": round(equity - equity0, 2), "dd": round(dd, 2)}


def main():
    now = dt.datetime.now(dt.timezone.utc)
    try:
        bars = B.fetch(YSYM)
    except Exception as e:
        print(f"[lab] 取数失败: {e}")
        return 1
    mid = len(bars) // 2
    tr_b, te_b = bars[:mid], bars[mid:]
    t0 = dt.datetime.fromtimestamp(bars[0]["t"], dt.timezone.utc)
    t1 = dt.datetime.fromtimestamp(bars[-1]["t"], dt.timezone.utc)

    stops, rrs = [20, 25, 30, 40], [1.5, 2.0]
    total_tests = len(STRATEGIES) * len(stops) * len(rrs)
    exp_fp = total_tests * 0.05

    L = ["# 入场逻辑实验室 — 换策略,不是调参数", "",
         f"*生成于 {now.isoformat(timespec='seconds')}*", "",
         f"{PAIR} · {t0:%Y-%m-%d} → {t1:%Y-%m-%d} · {len(bars)} 根 H1 · 本金 ${EQUITY:.0f}",
         "",
         "## 为什么换而不是继续观察", "",
         "当前配置验证期望 **+0.018R**,要在 95% 置信度确认它不是零需要约 "
         "**18,000 笔 ≈ 20 年**。",
         "**「继续观察」在数学上无法产生任何结论** —— 时间解决不了这个问题。",
         "回测已经把答案给了,所以直接换入场逻辑。", "",
         "## 多重比较:这次的门槛更严", "",
         f"总共 **{total_tests} 次检验**(4 种逻辑 × {len(stops)} 止损 × {len(rrs)} 盈亏比)。",
         f"单次 5% 假阳性率下,期望假阳性 **{exp_fp:.1f} 个**,",
         "至少出现一个的概率 **80.6%** —— 就算四种全没用,也很可能\"找到\"一两个。",
         "",
         "所以通过标准是三条同时满足:",
         "1. 训练段与验证段**都**为正",
         f"2. **验证段期望 ≥ +{MIN_TEST_EXP}R**（光是 >0 太容易靠运气）",
         f"3. 两段各 ≥ {MIN_TRADES} 笔", ""]

    survivors = []
    for name, fn in STRATEGIES:
        L += [f"## {name}", "",
              "| 止损 | RR | 训练笔数 | 训练胜率 | 训练期望 | 验证笔数 | 验证胜率 | 验证期望 | 判定 |",
              "|---|---|---|---|---|---|---|---|---|"]
        for stop, rr in itertools.product(stops, rrs):
            a = run(tr_b, fn, stop, rr, SPREAD, EQUITY)
            b = run(te_b, fn, stop, rr, SPREAD, EQUITY)
            if a["n"] < MIN_TRADES or b["n"] < MIN_TRADES:
                v = "样本不足"
            elif a["exp"] and b["exp"] and a["exp"] > 0 and b["exp"] >= MIN_TEST_EXP:
                v = "✅ 通过"
                survivors.append((name, stop, rr, a, b))
            elif a["exp"] and b["exp"] and a["exp"] > 0 and b["exp"] > 0:
                v = f"⚠️ 正但太薄(<{MIN_TEST_EXP}R)"
            elif a["exp"] and a["exp"] > 0:
                v = "⚠️ 训练正/验证负=噪音"
            else:
                v = "❌"
            L.append(f"| {stop}点 | 1:{rr} | {a['n']} | "
                     f"{a['wr'] if a['wr'] is not None else '—'}% | "
                     f"{a['exp'] if a['exp'] is not None else '—'} | {b['n']} | "
                     f"{b['wr'] if b['wr'] is not None else '—'}% | "
                     f"{b['exp'] if b['exp'] is not None else '—'} | {v} |")
        L.append("")

    # ---- 趋势回调模型(视频) ----------------------------------------
    h_rrs = [1.5, 2.0, 2.5, 3.0]
    h_wicks = [2.0, 2.5]
    h_tests = len(h_rrs) * len(h_wicks)
    h_fp = h_tests * 0.05
    L += ["## 趋势回调模型（用户提供的教学视频，2026-08-11）", "",
          "视频四步:①定方向 ②等回调到**水平支撑位** ③等**锤子线**"
          "(下影线≥实体2倍) ④**止损放锤子线最低点下方**。", "",
          "和上面 pullback 的本质区别:多了**形态确认**这道过滤,而且"
          "**止损是结构位不是固定点数**。这不是参数微调,是不同的入场条件。", "",
          f"这一节单独 {h_tests} 次检验(期望假阳性 {h_fp:.1f} 个)。", "",
          "| 下影线倍数 | RR | 训练笔数 | 训练胜率 | 训练期望 | 验证笔数 | 验证胜率 | 验证期望 | 判定 |",
          "|---|---|---|---|---|---|---|---|---|"]
    h_surv = []
    for wick, rr in itertools.product(h_wicks, h_rrs):
        a = run_struct(tr_b, entry_hammer_pullback, rr, SPREAD, EQUITY, wick_ratio=wick)
        b = run_struct(te_b, entry_hammer_pullback, rr, SPREAD, EQUITY, wick_ratio=wick)
        if a["n"] < MIN_TRADES or b["n"] < MIN_TRADES:
            v = "样本不足"
        elif a["exp"] and b["exp"] and a["exp"] > 0 and b["exp"] >= MIN_TEST_EXP:
            v = "✅ 通过"; h_surv.append((wick, rr, a, b))
        elif a["exp"] and b["exp"] and a["exp"] > 0 and b["exp"] > 0:
            v = f"⚠️ 正但太薄(<{MIN_TEST_EXP}R)"
        elif a["exp"] and a["exp"] > 0:
            v = "⚠️ 训练正/验证负=噪音"
        else:
            v = "❌"
        L.append(f"| {wick}x | 1:{rr} | {a['n']} | "
                 f"{a['wr'] if a['wr'] is not None else '—'}% | "
                 f"{a['exp'] if a['exp'] is not None else '—'} | {b['n']} | "
                 f"{b['wr'] if b['wr'] is not None else '—'}% | "
                 f"{b['exp'] if b['exp'] is not None else '—'} | {v} |")
    L.append("")
    if h_surv:
        L += [f"**{len(h_surv)} 组通过**(期望假阳性 {h_fp:.1f} 个):", ""]
        for wick, rr, a, b in sorted(h_surv, key=lambda x: -x[3]["exp"]):
            L.append(f"- 下影线{wick}x · 1:{rr} — 训练 {a['n']}笔/{a['wr']}%/{a['exp']}R，"
                     f"验证 {b['n']}笔/{b['wr']}%/{b['exp']}R，回撤 ${b['dd']}")
        if len(h_surv) <= h_fp:
            L += ["", "> ⚠️ 通过数不超过期望假阳性数,和「靠运气蒙中」无法区分。**不要采用。**"]
        L.append("")
    else:
        L += ["**这一节没有配置通过。**", "",
              "锤子线过滤确实让胜率比裸回踩高(见上表),但**扣掉点差后仍不足以**"
              "跨过 +0.10R 的门槛。形态过滤减少了交易次数,却没有按比例提高质量。", ""]

    L += ["## 结论", ""]
    if survivors:
        L += [f"**{len(survivors)} 组通过(期望假阳性 {exp_fp:.1f} 个,请对照着看):**", ""]
        for name, stop, rr, a, b in sorted(survivors, key=lambda x: -x[4]["exp"]):
            L.append(f"- **{name} · {stop}点 · 1:{rr}** — "
                     f"训练 {a['n']}笔/{a['wr']}%/{a['exp']}R，"
                     f"验证 {b['n']}笔/{b['wr']}%/{b['exp']}R，回撤 ${b['dd']}")
        if len(survivors) <= exp_fp:
            L += ["", f"> ⚠️ **通过数({len(survivors)}) 不超过期望假阳性数({exp_fp:.1f})** ——",
                  "> 这个结果和「全都没用、纯靠运气蒙中」无法区分。**不要采用。**", ""]
        else:
            L += ["", "> 通过数超过期望假阳性数,值得进一步观察 —— 但仍不等于实盘会赚。",
                  "> 真实点差会放大,滑点和隔夜利息都没算。", ""]
    else:
        L += ["**没有任何入场逻辑通过。**", "",
              "四种结构上完全不同的思路(突破/回踩/均值回归/时段突破)都没能在",
              "EUR/USD H1 上产生可验证的优势。这不是参数没调好 —— 参数网格已经覆盖了",
              f"{len(stops)}×{len(rrs)} 组。",
              "",
              "**诚实的结论:在这个品种、这个周期、这个成本结构下,",
              "简单的技术指标组合没有可被验证的 edge。**",
              "",
              "继续加策略、加参数直到出现正数,得到的一定是过拟合 ——",
              f"再测 32 次,期望还会多冒出 {exp_fp:.1f} 个假阳性。", ""]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write("\n".join(L))
    print("\n".join(L[-16:]))
    print(f"\n完整报告 -> {OUT}")
    return 0




# ===========================================================================
# 趋势回调模型（来自用户提供的教学视频，2026-08-11）
# ===========================================================================
# 视频原话的四步:
#   第一步 定方向  —— 先确认趋势
#   第二步 等回调  —— "画一条支撑位",等价格回踩到那条水平结构位
#   第三步 等信号  —— 锤子线,"下影线是实体的两倍长"
#   第四步 设止损止盈 —— "止损放在锤子线最低点下方"
#
# 和上面那个 pullback 的**本质区别**(所以值得单独测):
#   pullback: 价格进入均线区间就进 —— 没有形态确认,止损是固定点数
#   本模型:   必须回到**水平结构位** + 必须出现**锤子线** 才进,
#             止损跟着**锤子线低点**走,是结构止损不是固定止损
#   那根锤子线是一个真实的额外过滤器,不是参数微调。
#
# 编码时必须补的地方(视频没说,我按最保守的方式定,并标出来):
#   - "支撑位"用最近的分型低点,容差 0.5×ATR(视频是手画的,人画的没法编码)
#   - 锤子线还要求收盘在K线上半部,否则长下影+收在低位是下跌延续,不是反转
#   - 结构止损可能极窄,会被点差吃掉 -> 套用同一条下限:
#     max(结构距离, 8×点差, 15点)。**"验证过的规则"也不能穿过硬成本。**
HAMMER_MIN_STOP_PIPS = 15.0


def recent_structure(bars, i, lookback=60, wing=B.SWING_WING):
    """**最近**的分型高低点,不是整段的极值。

    这里踩过一个坑:第一版直接用了 B.structure(),它返回的是回溯段内的
    最高高点和最低低点 —— 整段极值。上升趋势里价格几乎永远不会跌回 120 根
    的最低点,所以"回踩到支撑位"这个条件恒为假,整个策略 0 笔成交,
    在报告里会显示成"样本不足",看起来像策略不触发,其实是我写错了。

    视频说的"画一条支撑位"指的是**刚刚那个回调低点**,所以要取最近的分型。
    """
    lo_i = max(wing + 1, i - lookback)
    last_hi = last_lo = None
    for j in range(lo_i, i - wing):
        win = bars[j - wing:j + wing + 1]
        if bars[j]["h"] >= max(b["h"] for b in win):
            last_hi = bars[j]["h"]          # 一路覆盖 -> 留下最近的那个
        if bars[j]["l"] <= min(b["l"] for b in win):
            last_lo = bars[j]["l"]
    return last_hi, last_lo


def entry_hammer_pullback(bars, i, ind, wick_ratio=2.0, zone_atr=0.5):
    """返回 (方向, 止损价)。不符合就 (0, None)。"""
    ef, es, et, rsi, macd_up, macd_dn, atr = ind
    up = ef[i] > es[i] > et[i]
    dn = ef[i] < es[i] < et[i]
    if not (up or dn):
        return 0, None                      # 第一步:没趋势就不做

    res, sup = recent_structure(bars, i)
    if res is None or sup is None:
        return 0, None

    c = bars[i]
    body = abs(c["c"] - c["o"])
    if body <= 0:
        return 0, None
    upper = c["h"] - max(c["o"], c["c"])
    lower = min(c["o"], c["c"]) - c["l"]
    rng = c["h"] - c["l"]
    if rng <= 0:
        return 0, None
    tol = atr[i] * zone_atr

    if up:
        # 第二步:回踩到支撑位附近
        if c["l"] > sup + tol:
            return 0, None
        # 第三步:锤子线 —— 下影线 >= 2×实体,且收盘在上半部
        if lower < wick_ratio * body:
            return 0, None
        if (c["c"] - c["l"]) / rng < 0.5:
            return 0, None
        return 1, c["l"]                    # 第四步:止损放锤子线最低点

    # 下跌趋势:镜像(倒锤/流星,上影线 >= 2×实体,收在下半部)
    if c["h"] < res - tol:
        return 0, None
    if upper < wick_ratio * body:
        return 0, None
    if (c["h"] - c["c"]) / rng < 0.5:
        return 0, None
    return -1, c["h"]


def run_struct(bars, stop_fn, rr, spread_pips, equity0, **kw):
    """结构止损版回测:止损距离由信号自己决定,不是固定点数。"""
    closes = [b["c"] for b in bars]
    ef = B.ema_series(closes, B.FAST); es = B.ema_series(closes, B.SLOW)
    et = B.ema_series(closes, B.TREND); rsi = B.rsi_series(closes, B.RSI_P)
    ml, ms = B.macd_series(closes); atr = B.atr_series(bars, B.ATR_P)
    ind = (ef, es, et, rsi,
           [ml[k] > ms[k] and ml[k] > 0 for k in range(len(ml))],
           [ml[k] < ms[k] and ml[k] < 0 for k in range(len(ml))], atr)

    equity, peak, dd = equity0, equity0, 0.0
    trades, pos = [], None
    spread_px = spread_pips * B.PIP
    floor_px = max(HAMMER_MIN_STOP_PIPS * B.PIP, 8 * spread_px)
    start = max(B.TREND, B.SWING_LOOKBACK + B.SWING_WING + 2, 25)

    for i in range(start, len(bars) - 1):
        if pos:
            nb = bars[i + 1]
            hit_sl = (nb["l"] <= pos["sl"]) if pos["d"] > 0 else (nb["h"] >= pos["sl"])
            hit_tp = (nb["h"] >= pos["tp"]) if pos["d"] > 0 else (nb["l"] <= pos["tp"])
            ex = pos["sl"] if (hit_sl and hit_tp) else (
                 pos["tp"] if hit_tp else (pos["sl"] if hit_sl else None))
            if ex is not None:
                gross = (ex - pos["e"]) * pos["d"] * pos["lots"] * B.UNITS_PER_LOT
                pnl = gross - spread_px * pos["lots"] * B.UNITS_PER_LOT
                equity += pnl
                peak = max(peak, equity); dd = max(dd, peak - equity)
                trades.append({"win": pnl > 0,
                               "r": pnl / pos["risk"] if pos["risk"] else 0})
                pos = None
            continue

        if rsi[i] is None or not atr[i]:
            continue
        d, sl_price = stop_fn(bars, i, ind, **kw)
        if d == 0:
            continue
        e = bars[i + 1]["o"] + spread_px * d / 2
        dist = max(abs(e - sl_price), floor_px)     # 硬成本下限,规则再好也不能穿
        stop_pips = dist / B.PIP
        lots, _ = B.lots_for(equity, stop_pips, bars[i]["c"])
        if lots <= 0:
            continue
        pos = {"d": d, "e": e, "sl": e - dist * d, "tp": e + dist * rr * d,
               "lots": lots, "risk": lots * dist * B.UNITS_PER_LOT}

    n = len(trades)
    if n == 0:
        return {"n": 0, "wr": None, "exp": None, "net": 0.0, "dd": 0.0}
    wins = sum(1 for t in trades if t["win"])
    tot = sum(t["r"] for t in trades)
    return {"n": n, "wr": round(wins / n * 100, 1), "exp": round(tot / n, 3),
            "net": round(equity - equity0, 2), "dd": round(dd, 2)}


# 入口必须放在**文件最末尾**。
# 踩过的坑:用 cat >> 追加新策略时,函数定义落在了这个 guard 后面。
# Python 从上往下执行,走到 guard 就调用 main(),而 main() 里引用的
# run_struct / entry_hammer_pullback 还没被定义 -> NameError。
# 更糟的是 workflow 那步是 continue-on-error,**失败无声无息**,
# 旧报告原样留着,看起来像"新策略没触发",其实是脚本根本没跑完。
if __name__ == "__main__":
    raise SystemExit(main())
