#!/usr/bin/env python3
"""黄金「顺势回调K线」策略研究 —— 真实历史行情 + 样本外验证 + 蒙特卡洛。

给 mql5/GoldPullback.mq5 定参数用。规则与 EA 一一对应(改一边就要改另一边):

  方向(大周期,只看已收盘的K线):
      H1 执行 -> H4 定方向;M15/M30 执行 -> H1 定方向
      多头 = 大周期 EMA50 > EMA200 且 EMA50 比 3 根前高
  回调(执行周期):
      - 执行周期 EMA20 > EMA50(同向)
      - 前 12 根的最高点到最近 3 根最低点,回撤 >= depth × ATR(真回调,不是横盘)
      - 回调最低点碰到 EMA20(+0.1ATR 以内),但没跌破 EMA50 - 0.5ATR(结构没坏)
      - 触发K线之前 4 根里至少 2 根阴线(真正的"回调K线")
  触发(刚收盘那根 = 确认K线):
      阳线、收在K线上部 40% 以内、收在 EMA20 之上,并且满足下面其一:
        pin bar:下影 >= 40% 全长;或 吞没:实体吞掉前一根阴线实体
      K线全长 <= 2.0 ATR(新闻大K线不追)
  进场:
      stop  = 在确认K线高点 + 0.05ATR 挂买入止损单,2 根K线内不成交就撤
      market= 下一根开盘直接进
  止损:最近 3 根最低点 - 0.2ATR;距离 < 0.5ATR 就放宽到 0.5ATR;> 2.5ATR 放弃
  止盈:RR × 止损距离;浮盈到 be × R 移保本(+0.1R);持仓超过 24 小时收盘平
  纪律:只在 UTC 07-17 开新单;一天最多 2 笔;当天亏一笔就收工;同时只持 1 单
  空头完全镜像。

成本口径(保守):点差 $0.30(开平各付一半),止损/止损单成交再加 $0.05 滑点;
同一根K线同时碰到止损和止盈 -> 按止损;成交那根K线不算止盈、但算止损。
**这是乐观上界之下的保守估计,仍然不是 MT5 tick 级回测。**

用法:
    python3 gold_pullback_research.py              # 取 Yahoo GC=F(Actions 上跑)
    python3 gold_pullback_research.py --synthetic  # 随机游走自测,只验证代码能跑
"""

from __future__ import annotations

import argparse
import datetime as dt
import itertools
import json
import math
import os
import random

import backtest_gold as B

OUT_MD = os.environ.get("GOLD_PB_OUT", "reports/gold_pullback.md")
OUT_JSON = os.environ.get("GOLD_PB_JSON", "reports/gold_pullback.json")

SPREAD = 0.30          # 美元金价距离
SLIP = 0.05            # 止损类成交滑点
OZ_PER_TRADE = 2.0     # 0.02 手 × 100oz
TRAIN_FRAC = 0.6
MIN_TRADES = 30

# 固定不搜(避免参数越搜越多=过拟合),只搜下面 GRID 里的
FIXED = dict(
    ema_fast=20, ema_mid=50, htf_fast=50, htf_slow=200, atr_p=14,
    swing_lb=12, pb_bars=3, touch_buf=0.1, zone_below=0.5,
    min_bear=2, bear_look=4, close_pos=0.6, wick_min=0.4, max_range_atr=2.0,
    trig_buf=0.05, valid_bars=2, sl_buf=0.2, min_stop_atr=0.5, max_stop_atr=2.5,
    be_lock=0.1, max_hold_hours=24, sess_start=7, sess_end=17,
    max_trades_day=2, max_losses_day=1,
)
GRID = dict(
    entry=["stop", "market"],
    rr=[1.5, 2.0, 2.5],
    depth=[0.8, 1.2],
    be=[1.0, 0.0],
)
# 第 2 轮:第 1 轮训练期全部为负。看训练期诊断后只改两件事(有交易逻辑,不是乱试):
#   side  : 2024-26 黄金是大牛市,逆势做空可能是主要亏损来源 -> 试"只做多"
#   stop  : 第 1 轮 61% 的单子打止损,止损离回调低点太近 -> 试"放宽到结构外 0.5ATR、最小 1ATR"
# 注意:第 2 轮是在看过第 1 轮验证结果之后设计的,证据强度弱于第 1 轮,最终要靠模拟盘前向验证。
GRID2 = dict(
    side=["both", "long"],
    stop=["tight", "wide"],
    rr=[1.5, 2.0],
    entry=["stop", "market"],
)
STOPS = {"tight": dict(sl_buf=0.2, min_stop_atr=0.5), "wide": dict(sl_buf=0.5, min_stop_atr=1.0)}


# ------------------------------------------------------------------ 数据
def resample(bars, sec):
    out = []
    for b in bars:
        k = b["t"] // sec * sec
        if out and out[-1]["t"] == k:
            o = out[-1]
            o["h"] = max(o["h"], b["h"]); o["l"] = min(o["l"], b["l"]); o["c"] = b["c"]
        else:
            out.append({"t": k, "o": b["o"], "h": b["h"], "l": b["l"], "c": b["c"]})
    return out


def synthetic(n, sec, seed=7):
    rnd = random.Random(seed)
    t0 = int(dt.datetime(2024, 9, 23, tzinfo=dt.timezone.utc).timestamp())
    px, bars, drift = 2600.0, [], 0.0
    for i in range(n):
        if i % 300 == 0:
            drift = rnd.uniform(-0.4, 0.4)
        o = px
        c = o + drift + rnd.gauss(0, 4)
        h = max(o, c) + abs(rnd.gauss(0, 2))
        l = min(o, c) - abs(rnd.gauss(0, 2))
        bars.append({"t": t0 + i * sec, "o": o, "h": h, "l": l, "c": c})
        px = c
    return bars


# ------------------------------------------------------------------ 准备指标
def prepare(bars, sec, htf_sec, P):
    closes = [b["c"] for b in bars]
    ind = {
        "ef": B.ema_series(closes, P["ema_fast"]),
        "em": B.ema_series(closes, P["ema_mid"]),
        "atr": B.atr_series(bars, P["atr_p"]),
    }
    htf = resample(bars, htf_sec)
    hc = [b["c"] for b in htf]
    hf, hs = B.ema_series(hc, P["htf_fast"]), B.ema_series(hc, P["htf_slow"])
    # 每根执行K线对应"已经收盘"的最后一根大周期K线
    hatr = B.atr_series(htf, P["atr_p"])
    trend = [0] * len(bars)
    sep = [0.0] * len(bars)     # 大周期 EMA 分离度(以大周期 ATR 计):小 = 横盘
    j = -1
    for i, b in enumerate(bars):
        close_i = b["t"] + sec
        while j + 1 < len(htf) and htf[j + 1]["t"] + htf_sec <= close_i:
            j += 1
        if j >= max(P["htf_slow"], 3):
            if hf[j] > hs[j] and hf[j] > hf[j - 3]:
                trend[i] = 1
            elif hf[j] < hs[j] and hf[j] < hf[j - 3]:
                trend[i] = -1
            if hatr[j]:
                sep[i] = abs(hf[j] - hs[j]) / hatr[j]
    ind["trend"] = trend
    ind["sep"] = sep
    return ind


# ------------------------------------------------------------------ 信号
def signal(bars, ind, i, P, depth):
    """bar i 刚收盘。返回 (方向, 止损价, 确认K线高/低) 或 None。"""
    a = ind["atr"][i]
    if a is None or a <= 0 or i < P["swing_lb"] + P["bear_look"] + 2:
        return None
    d = ind["trend"][i]
    if d == 0 or ind["sep"][i] < P.get("htf_sep", 0.0):
        return None
    b, pb = bars[i], bars[i - 1]
    ef, em = ind["ef"][i], ind["em"][i]
    rng = b["h"] - b["l"]
    if rng <= 0 or rng > P["max_range_atr"] * a:
        return None
    recent = bars[i - P["pb_bars"] + 1:i + 1]
    prior = bars[i - P["swing_lb"]:i]
    look = bars[i - P["bear_look"]:i]

    if d > 0:
        if not ef > em:
            return None
        lo = min(x["l"] for x in recent)
        if max(x["h"] for x in prior) - lo < depth * a:
            return None
        if not (lo <= ef + P["touch_buf"] * a and lo >= em - P["zone_below"] * a):
            return None
        if sum(1 for x in look if x["c"] < x["o"]) < P["min_bear"]:
            return None
        if not (b["c"] > b["o"] and b["c"] > ef and (b["c"] - b["l"]) / rng >= P["close_pos"]):
            return None
        pin = (min(b["o"], b["c"]) - b["l"]) / rng >= P["wick_min"]
        engulf = pb["c"] < pb["o"] and b["c"] >= pb["o"] and b["o"] <= pb["c"]
        if not (pin or engulf):
            return None
        return 1, lo - P["sl_buf"] * a, b["h"]
    else:
        if not ef < em:
            return None
        hi = max(x["h"] for x in recent)
        if hi - min(x["l"] for x in prior) < depth * a:
            return None
        if not (hi >= ef - P["touch_buf"] * a and hi <= em + P["zone_below"] * a):
            return None
        if sum(1 for x in look if x["c"] > x["o"]) < P["min_bear"]:
            return None
        if not (b["c"] < b["o"] and b["c"] < ef and (b["h"] - b["c"]) / rng >= P["close_pos"]):
            return None
        pin = (b["h"] - max(b["o"], b["c"])) / rng >= P["wick_min"]
        engulf = pb["c"] > pb["o"] and b["c"] <= pb["o"] and b["o"] >= pb["c"]
        if not (pin or engulf):
            return None
        return -1, hi + P["sl_buf"] * a, b["l"]


# ------------------------------------------------------------------ 回测
def day_of(t):
    return t // 86400


def hour_of(t):
    return (t // 3600) % 24


def run(bars, ind, sec, P, lo_i, hi_i):
    hs = SPREAD / 2
    max_hold = max(1, int(P["max_hold_hours"] * 3600 / sec))
    trades, pos, pend = [], None, None
    day, day_n, day_loss = None, 0, 0

    for i in range(max(lo_i, 1), hi_i):
        b = bars[i]
        if day_of(b["t"]) != day:
            day, day_n, day_loss = day_of(b["t"]), 0, 0

        # ---- 挂单:成交 / 失效
        if pend and not pos:
            d = pend["dir"]
            filled = (b["h"] + hs >= pend["lvl"]) if d > 0 else (b["l"] - hs <= pend["lvl"])
            if filled:
                entry = pend["lvl"] + SLIP * d
                pos = dict(dir=d, entry=entry, sl=pend["sl"], dist=abs(entry - pend["sl"]),
                           t=b["t"], i=i, be_done=False)
                pos["tp"] = entry + P["rr"] * pos["dist"] * d
                day_n += 1
                pend = None
                # 成交那根K线:只判止损(保守)
                hit_sl = (b["l"] - hs <= pos["sl"]) if d > 0 else (b["h"] + hs >= pos["sl"])
                if hit_sl:
                    trades.append(close(pos, pos["sl"] - SLIP * d, b["t"], "SL"))
                    day_loss += 1
                    pos = None
                continue
            pend["left"] -= 1
            hit_inv = (b["l"] <= pend["sl"]) if d > 0 else (b["h"] >= pend["sl"])
            if pend["left"] <= 0 or hit_inv:
                pend = None

        # ---- 持仓管理
        if pos:
            d = pos["dir"]
            hit_sl = (b["l"] - hs <= pos["sl"]) if d > 0 else (b["h"] + hs >= pos["sl"])
            hit_tp = (b["h"] - hs >= pos["tp"]) if d > 0 else (b["l"] + hs <= pos["tp"])
            ex = None
            if hit_sl:
                ex = (pos["sl"] - SLIP * d, "SL" if not pos["be_done"] else "BE")
            elif hit_tp:
                ex = (pos["tp"], "TP")
            elif i - pos["i"] >= max_hold:
                ex = (b["c"] - hs * d, "TIME")
            if ex:
                tr = close(pos, ex[0], b["t"], ex[1])
                trades.append(tr)
                if tr["r"] < 0:
                    day_loss += 1
                pos = None
            else:
                if P["be"] > 0 and not pos["be_done"]:
                    fav = (b["h"] - hs - pos["entry"]) if d > 0 else (pos["entry"] - b["l"] - hs)
                    if fav >= P["be"] * pos["dist"]:
                        pos["sl"] = pos["entry"] + P["be_lock"] * pos["dist"] * d
                        pos["be_done"] = True
                continue

        # ---- 新信号(bar i 已收盘)
        if pos or pend or i + 1 >= hi_i:
            continue
        hr = hour_of(b["t"] + sec)
        if not (P["sess_start"] <= hr < P["sess_end"]):
            continue
        if day_n >= P["max_trades_day"] or day_loss >= P["max_losses_day"]:
            continue
        s = signal(bars, ind, i, P, P["depth"])
        if not s:
            continue
        d, sl, ext = s
        if P.get("side") == "long" and d < 0:
            continue
        a = ind["atr"][i]
        if P["entry"] == "stop":
            lvl = ext + P["trig_buf"] * a * d
            ref = lvl
        else:
            ref = bars[i + 1]["o"] + hs * d
        dist = abs(ref - sl)
        if dist < P["min_stop_atr"] * a:
            sl = ref - P["min_stop_atr"] * a * d
            dist = P["min_stop_atr"] * a
        if dist > P["max_stop_atr"] * a:
            continue
        if P["entry"] == "stop":
            pend = dict(dir=d, lvl=lvl, sl=sl, left=P["valid_bars"])
        else:
            nb = bars[i + 1]
            pos = dict(dir=d, entry=ref, sl=sl, dist=dist, t=nb["t"], i=i + 1, be_done=False)
            pos["tp"] = ref + P["rr"] * dist * d
            day_n += 1
    return trades


def close(pos, px, t, why):
    d = pos["dir"]
    move = (px - pos["entry"]) * d - SPREAD / 2      # 平仓付另一半点差
    return {"t_in": pos["t"], "t_out": t, "dir": d, "r": round(move / pos["dist"], 3),
            "usd": round(move * OZ_PER_TRADE, 2), "stop_usd": round(pos["dist"], 2), "why": why}


# ------------------------------------------------------------------ 统计
def stats(trades, days):
    n = len(trades)
    if n == 0:
        return {"n": 0}
    rs = [t["r"] for t in trades]
    wins = sum(1 for r in rs if r > 0)
    gp = sum(r for r in rs if r > 0)
    gl = -sum(r for r in rs if r < 0)
    eq = peak = dd = 0.0
    streak = worst = 0
    for r in rs:
        eq += r; peak = max(peak, eq); dd = max(dd, peak - eq)
        streak = streak + 1 if r < 0 else 0
        worst = max(worst, streak)
    usd = sum(t["usd"] for t in trades)
    peak_u = eq_u = dd_u = 0.0
    for t in trades:
        eq_u += t["usd"]; peak_u = max(peak_u, eq_u); dd_u = max(dd_u, peak_u - eq_u)
    stops = sorted(t["stop_usd"] for t in trades)
    why = {}
    for t in trades:
        why[t["why"]] = why.get(t["why"], 0) + 1
    return {
        "n": n, "wr": round(wins / n * 100, 1), "exp": round(sum(rs) / n, 3),
        "sum_r": round(sum(rs), 1), "pf": round(gp / gl, 2) if gl > 0 else None,
        "dd_r": round(dd, 1), "streak": worst, "usd": round(usd, 2), "dd_usd": round(dd_u, 2),
        "per_week": round(n / max(days / 7, 1e-9), 2),
        "stop_med": stops[len(stops) // 2], "stop_p90": stops[int(len(stops) * 0.9) - 1 if len(stops) > 1 else 0],
        "why": why,
    }


def monte_carlo(rs, n_trades=100, sims=5000, seed=1):
    rnd = random.Random(seed)
    finals, dds = [], []
    for _ in range(sims):
        eq = peak = dd = 0.0
        for _ in range(n_trades):
            eq += rs[rnd.randrange(len(rs))]
            peak = max(peak, eq); dd = max(dd, peak - eq)
        finals.append(eq); dds.append(dd)
    finals.sort(); dds.sort()
    q = lambda v, p: v[min(len(v) - 1, int(len(v) * p))]
    return {"p_loss": round(sum(1 for f in finals if f < 0) / sims * 100, 1),
            "final_p5": round(q(finals, 0.05), 1), "final_p50": round(q(finals, 0.5), 1),
            "dd_p50": round(q(dds, 0.5), 1), "dd_p95": round(q(dds, 0.95), 1)}


def fmt_row(tag, s):
    if not s or s.get("n", 0) == 0:
        return f"| {tag} | 0 | — | — | — | — | — |"
    return (f"| {tag} | {s['n']} | {s['wr']}% | {s['exp']:+.3f} | {s['pf']} | "
            f"{s['dd_r']} | {s['per_week']} |")


# ------------------------------------------------------------------ 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    a = ap.parse_args()

    datasets = [("H1", "1h", "2y", 3600, 4 * 3600),
                ("M30", "30m", "60d", 1800, 3600),
                ("M15", "15m", "60d", 900, 3600)]
    data = {}
    for name, iv, rng, sec, hsec in datasets:
        try:
            bars = synthetic(12000 if sec == 3600 else 4000, sec) if a.synthetic \
                else B.fetch("GC=F", iv, rng)
        except Exception as e:
            print(f"[{name}] 取数失败: {e}")
            continue
        if len(bars) < 1500:
            print(f"[{name}] K线不足 {len(bars)}")
            continue
        data[name] = (bars, sec, hsec)
        print(f"[{name}] {len(bars)} 根")

    if "H1" not in data:
        print("没有 H1 数据,无法研究")
        return 1

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
    L = ["# 黄金「顺势回调K线」策略研究", "", f"*生成于 {now}*" + (" · ⚠️ 合成数据自测" if a.synthetic else ""), "",
         "规则见 `gold_pullback_research.py` 文件头,与 `mql5/GoldPullback.mq5` 一一对应。",
         f"成本:点差 ${SPREAD}、止损滑点 ${SLIP};同根K线碰止损+止盈按止损。"
         f"金额按 **0.02 手 = 2oz**(金价每动 $1 = $2)。", "",
         "**方法**:H1 两年数据按时间切成 前60%(训练,只在这里挑参数)/ 后40%(验证,只跑一次)。",
         "挑参数只看训练;验证那列是它从没见过的行情。再拿同一组参数去 M30/M15 近60天跑一遍做交叉检查。", ""]

    bars, sec, hsec = data["H1"]
    base = dict(FIXED)
    ind = prepare(bars, sec, hsec, base)
    cut = int(len(bars) * TRAIN_FRAC)
    warm = 4 * base["htf_slow"] + 50
    d_tr = (bars[cut]["t"] - bars[warm]["t"]) / 86400
    d_va = (bars[-1]["t"] - bars[cut]["t"]) / 86400
    t0 = lambda i: dt.datetime.fromtimestamp(bars[i]["t"], dt.timezone.utc).strftime("%Y-%m-%d")
    L += [f"## H1 参数网格(训练 {t0(warm)}→{t0(cut)} / 验证 {t0(cut)}→{t0(len(bars)-1)})", "",
          "| 进场 | RR | 回调深度 | 保本 | 训练笔数 | 训练胜率 | 训练期望R | 验证笔数 | 验证胜率 | 验证期望R | 验证PF |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    rows = []
    for combo in itertools.product(*GRID.values()):
        P = dict(base, **dict(zip(GRID.keys(), combo)))
        tr = stats(run(bars, ind, sec, P, warm, cut), d_tr)
        va = stats(run(bars, ind, sec, P, cut, len(bars)), d_va)
        rows.append((P, tr, va))
    rows.sort(key=lambda x: -(x[1].get("exp", -9) if x[1].get("n", 0) >= MIN_TRADES else -9))
    for P, tr, va in rows:
        g = lambda s, k: s.get(k, "—") if s.get("n", 0) else "—"
        L.append(f"| {P['entry']} | {P['rr']} | {P['depth']} | {P['be'] or '关'} | {tr['n']} | {g(tr,'wr')} | "
                 f"{g(tr,'exp')} | {va['n']} | {g(va,'wr')} | {g(va,'exp')} | {g(va,'pf')} |")

    best = next((r for r in rows if r[1].get("n", 0) >= MIN_TRADES), rows[0])
    P, tr, va = best
    ok = tr.get("n", 0) >= MIN_TRADES and va.get("n", 0) >= 20 and tr.get("exp", -1) > 0 and va.get("exp", -1) > 0
    L += ["", f"**按训练期挑出的配置**:进场={P['entry']} · RR={P['rr']} · 回调深度={P['depth']}ATR · 保本={P['be'] or '关'}",
          f"→ 验证期 {va.get('n',0)} 笔,期望 {va.get('exp','—')}R —— " +
          ("✅ **训练、验证两边都为正**" if ok else "❌ **验证没过**:这组规则在没见过的行情上不赚钱,不应上实盘"), ""]

    # ---- 诊断(只看训练期):亏在哪个方向
    diag = run(bars, ind, sec, P, warm, cut)
    L += ["## 第 1 轮诊断(只看训练期)", "",
          "| 方向 | 笔数 | 胜率 | 期望R | PF | 最大回撤R | 每周笔数 |", "|---|---|---|---|---|---|---|",
          fmt_row("做多", stats([t for t in diag if t["dir"] > 0], d_tr)),
          fmt_row("做空", stats([t for t in diag if t["dir"] < 0], d_tr)), ""]

    # ---- 第 2 轮
    L += ["## 第 2 轮:只做多? 放宽结构止损?(回调深度 1.0ATR · 1R 保本)", "",
          "> 第 2 轮是看过第 1 轮验证结果后设计的,即使两边都为正,证据也弱于一次命中。",
          "> 真正的裁判是模拟盘前向跑 30 笔以上。", "",
          "| 方向 | 止损 | RR | 进场 | 训练笔数 | 训练胜率 | 训练期望R | 验证笔数 | 验证胜率 | 验证期望R | 验证PF |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    rows2 = []
    for combo in itertools.product(*GRID2.values()):
        q = dict(zip(GRID2.keys(), combo))
        P2 = dict(base, depth=1.0, be=1.0, **STOPS[q["stop"]], **q)
        tr2 = stats(run(bars, ind, sec, P2, warm, cut), d_tr)
        va2 = stats(run(bars, ind, sec, P2, cut, len(bars)), d_va)
        rows2.append((P2, tr2, va2))
    rows2.sort(key=lambda x: -(x[1].get("exp", -9) if x[1].get("n", 0) >= MIN_TRADES else -9))
    for P2, tr2, va2 in rows2:
        g = lambda s, k: s.get(k, "—") if s.get("n", 0) else "—"
        L.append(f"| {'只多' if P2['side']=='long' else '多空'} | {'宽' if P2['stop']=='wide' else '紧'} | {P2['rr']} | "
                 f"{P2['entry']} | {tr2['n']} | {g(tr2,'wr')} | {g(tr2,'exp')} | {va2['n']} | {g(va2,'wr')} | "
                 f"{g(va2,'exp')} | {g(va2,'pf')} |")
    P, tr, va = next((r for r in rows2 if r[1].get("n", 0) >= MIN_TRADES), rows2[0])
    ok = tr.get("n", 0) >= MIN_TRADES and va.get("n", 0) >= 20 and tr.get("exp", -1) > 0 and va.get("exp", -1) > 0
    L += ["", f"**第 2 轮按训练期挑出**:{'只做多' if P['side']=='long' else '多空都做'} · "
              f"{'宽' if P['stop']=='wide' else '紧'}止损 · RR={P['rr']} · 进场={P['entry']}",
          f"→ 验证期 {va.get('n',0)} 笔,期望 {va.get('exp','—')}R —— " +
          ("✅ **训练、验证两边都为正**" if ok else "❌ **验证没过**"), ""]

    full = run(bars, ind, sec, P, warm, len(bars))
    d_full = (bars[-1]["t"] - bars[warm]["t"]) / 86400
    sf = stats(full, d_full)
    L += ["## 选定配置 · 全部两年明细(H1)", "",
          "| 区间 | 笔数 | 胜率 | 期望R | PF | 最大回撤R | 每周笔数 |", "|---|---|---|---|---|---|---|",
          fmt_row("训练", tr), fmt_row("验证", va), fmt_row("全部", sf), ""]
    if sf.get("n"):
        L += [f"- 0.02 手合计盈亏:**${sf['usd']}** · 最大回撤 ${sf['dd_usd']} · 最长连亏 {sf['streak']} 笔",
              f"- 止损距离中位数 ${sf['stop_med']}(= 风险 ${round(sf['stop_med']*OZ_PER_TRADE,2)}/笔),"
              f"90% 分位 ${sf['stop_p90']}(= ${round(sf['stop_p90']*OZ_PER_TRADE,2)})",
              f"- 出场方式:{sf['why']}", ""]
        mc = monte_carlo([t["r"] for t in full])
        L += ["## 蒙特卡洛:把这两年的成交顺序打乱 5000 次,模拟接下来 100 笔", "",
              f"- 100 笔后亏钱的概率:**{mc['p_loss']}%**",
              f"- 100 笔累计 R:中位数 {mc['final_p50']}R,最差 5% 情况 {mc['final_p5']}R",
              f"- 最大回撤:中位数 {mc['dd_p50']}R,最差 5% 情况 **{mc['dd_p95']}R**"
              f"(按中位止损 ≈ ${round(mc['dd_p95']*sf['stop_med']*OZ_PER_TRADE)})", ""]
    else:
        mc = {}

    # ---- 合成配置:去掉纪律(每日笔数/亏损收工/时段)会怎样
    NO_DISC = dict(max_trades_day=999, max_losses_day=999, sess_start=0, sess_end=24)
    combos = [
        ("选定配置(有纪律)", dict(P)),
        ("选定配置 · 去掉纪律", dict(P, **NO_DISC)),
        ("多空都做 · 去掉纪律", dict(P, side="both", **NO_DISC)),
        ("突破挂单进场 · 去掉纪律", dict(P, entry="stop", **NO_DISC)),
    ]
    L += ["## 合成配置对比:去掉纪律(每天笔数上限 / 亏一笔收工 / 交易时段)", "",
          "| 配置 | 区间 | 笔数 | 胜率 | 期望R | PF | 最大回撤R | 每周笔数 |",
          "|---|---|---|---|---|---|---|---|"]
    merged = {}
    for tag, Pc in combos:
        rows_c = {}
        for part, lo_i, hi_i, dd_ in (("训练", warm, cut, d_tr), ("验证", cut, len(bars), d_va),
                                      ("全部", warm, len(bars), d_full)):
            rows_c[part] = stats(run(bars, ind, sec, Pc, lo_i, hi_i), dd_)
            L.append(fmt_row(f"{tag} | {part}", rows_c[part]))
        merged[tag] = rows_c
    L.append("")

    # ---- 第 3 轮:参数稳健性(range 设定) + 横盘过滤
    # 每个参数在默认值附近试几档。**只用训练期**挑:
    #   平滑分 = 该档和左右相邻档的训练期望的平均 -> 选"一片高原"的中间,不选孤立尖峰
    # 按参数逐个做(坐标下降,一遍),然后验证期只看不挑。
    SENS = [
        ("htf_sep", "横盘过滤:大周期EMA分离 ≥ N×ATR", [0.0, 0.5, 1.0, 1.5, 2.0]),
        ("depth", "回调深度(ATR)", [0.6, 0.8, 1.0, 1.2, 1.5]),
        ("max_range_atr", "确认K线最大长度(ATR)", [1.5, 2.0, 2.5, 3.0]),
        ("zone_below", "可跌破EMA50幅度(ATR)", [0.3, 0.5, 0.8]),
        ("touch_buf", "碰EMA20容差(ATR)", [0.0, 0.1, 0.25]),
        ("sl_buf", "止损在结构外(ATR)", [0.3, 0.5, 0.7]),
        ("min_stop_atr", "最小止损(ATR)", [0.75, 1.0, 1.25]),
        ("max_stop_atr", "最大止损(ATR),超过放弃", [1.5, 2.0, 2.5, 3.0]),
        ("rr", "盈亏比 RR", [1.5, 2.0, 2.5]),
        ("be", "保本触发(R)", [0.75, 1.0, 1.5]),
        ("max_hold_hours", "最长持仓(小时)", [12, 24, 48]),
    ]
    P3 = dict(P, entry="stop", **NO_DISC)
    L += ["## 第 3 轮:range 设定稳健性 + 横盘过滤", "",
          "每个参数在默认值附近试几档,其它参数不动。**只用训练期**挑值:",
          "取「这一档 + 左右相邻档」训练期望的平均(平滑分),选高原的中间,不选孤立尖峰。",
          "验证期只看不挑。⭐ = 选中的值。", ""]
    sens_out = {}
    for key, label, vals in SENS:
        res = []
        for v in vals:
            Pv = dict(P3, **{key: v})
            tr_ = stats(run(bars, ind, sec, Pv, warm, cut), d_tr)
            va_ = stats(run(bars, ind, sec, Pv, cut, len(bars)), d_va)
            res.append((v, tr_, va_))
        ex = [r[1].get("exp", -1) if r[1].get("n", 0) >= MIN_TRADES else -1 for r in res]
        smooth = [sum(ex[max(0, k - 1):k + 2]) / len(ex[max(0, k - 1):k + 2]) for k in range(len(ex))]
        pick = max(range(len(vals)), key=lambda k: (smooth[k], -abs(k - len(vals) // 2)))
        P3[key] = vals[pick]
        sens_out[key] = {"picked": vals[pick],
                         "rows": [{"v": v, "train": t, "valid": w} for v, t, w in res]}
        L += [f"**{label}**", "",
              "| 值 | 训练笔数 | 训练期望R | 平滑分 | 验证笔数 | 验证期望R |", "|---|---|---|---|---|---|"]
        for k, (v, t, w) in enumerate(res):
            L.append(f"| {v}{' ⭐' if k == pick else ''} | {t.get('n', 0)} | {t.get('exp', '—')} | "
                     f"{smooth[k]:+.3f} | {w.get('n', 0)} | {w.get('exp', '—')} |")
        L.append("")

    tr3 = stats(run(bars, ind, sec, P3, warm, cut), d_tr)
    va3 = stats(run(bars, ind, sec, P3, cut, len(bars)), d_va)
    full3 = run(bars, ind, sec, P3, warm, len(bars))
    sf3 = stats(full3, d_full)
    ok3 = tr3.get("n", 0) >= MIN_TRADES and va3.get("n", 0) >= 15 and tr3.get("exp", -1) > 0 and va3.get("exp", -1) > 0
    L += ["### 第 3 轮最终配置", "",
          "| 区间 | 笔数 | 胜率 | 期望R | PF | 最大回撤R | 每周笔数 |", "|---|---|---|---|---|---|---|",
          fmt_row("训练", tr3), fmt_row("验证", va3), fmt_row("全部", sf3), "",
          ("✅ 训练、验证两边为正" if ok3 else "❌ 验证没过"), ""]
    mc3 = {}
    if sf3.get("n"):
        mc3 = monte_carlo([t["r"] for t in full3])
        L += [f"- 0.02 手合计盈亏 **${sf3['usd']}** · 最大回撤 ${sf3['dd_usd']} · 最长连亏 {sf3['streak']} 笔",
              f"- 止损中位数 ${sf3['stop_med']}(≈ ${round(sf3['stop_med']*OZ_PER_TRADE, 2)}/笔),"
              f"90% 分位 ${sf3['stop_p90']}(≈ ${round(sf3['stop_p90']*OZ_PER_TRADE, 2)})",
              f"- 出场:{sf3['why']}",
              f"- 蒙特卡洛(100 笔):亏钱概率 **{mc3['p_loss']}%** · 最大回撤中位 {mc3['dd_p50']}R · "
              f"最差 5% **{mc3['dd_p95']}R**", ""]
    final = {k: P3[k] for k in ("entry", "rr", "depth", "be", "side", "sl_buf", "min_stop_atr", "max_stop_atr",
                                 "max_range_atr", "zone_below", "touch_buf", "htf_sep", "max_hold_hours")}
    L += ["```", "最终参数: " + json.dumps(final, ensure_ascii=False), "```", ""]

    cross = {}
    for name in ("M30", "M15"):
        if name not in data:
            continue
        b2, s2, h2 = data[name]
        P2 = dict(P, max_hold_hours=P["max_hold_hours"] // 2)
        ind2 = prepare(b2, s2, h2, P2)
        w2 = h2 // s2 * P2["htf_slow"] + 50
        st = stats(run(b2, ind2, s2, P2, w2, len(b2)), (b2[-1]["t"] - b2[w2]["t"]) / 86400)
        cross[name] = st
    if cross:
        L += ["## 交叉检查:同一组参数换周期(近 60 天,完全没参与挑参数)", "",
              "| 周期 | 笔数 | 胜率 | 期望R | PF | 最大回撤R | 每周笔数 |", "|---|---|---|---|---|---|---|"]
        L += [fmt_row(k, v) for k, v in cross.items()] + [""]

    L += ["---", "*研究/学习用途,不构成投资建议。历史回测不代表未来。*"]
    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write("\n".join(L) + "\n")
    with open(OUT_JSON, "w") as f:
        json.dump({"generated": now, "synthetic": a.synthetic, "passed": ok,
                   "params": {k: P[k] for k in ("entry", "rr", "depth", "be", "side", "stop", "sl_buf", "min_stop_atr") if k in P}, "train": tr, "valid": va, "full": sf,
                   "monte_carlo": mc, "cross": cross, "merged": merged,
                   "round3": {"final": final, "train": tr3, "valid": va3, "full": sf3, "passed": ok3, "monte_carlo": mc3, "sens": sens_out}}, f, ensure_ascii=False, indent=1)
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
