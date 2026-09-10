#!/usr/bin/env python3
"""黄金实时读盘信号 -> signals_gold.json / signals_gold.md。

**这条链路是干什么的**:把 `backtest_gold.py` 里那套**已经回测过**的 GoldScalper
入场规则,拿最新的 GC=F 行情跑一遍,输出「当前该做多 / 做空 / 观望」+ 入场参考、
止损、目标、置信度。让你(或 App)每次刷新都能看到一个带纪律的读盘结果。

**为什么是复用而不是另写一套指标**:这个仓库的纪律是「只发回测过的信号」。
所以这里 import backtest_gold,直接用它的 fetch / EMA / RSI / MACD / ATR / 结构分型
和入场判断——一个字都不改。改规则请去改 backtest_gold.py(等于改 EA 的 input),
两边永远一致,不会出现「回测一套、实盘信号另一套」的裂缝。

**默认参数**用样本外唯一勉强验证为正的那组(见 gold_health.py):
    M15 · 固定 $3 止损 · RR 1:2 —— 验证段 40.5% 胜率 / 每笔 +0.091R
可用环境变量覆盖(GOLD_INTERVAL / GOLD_FIXED_STOP / 通过 backtest_gold 的 REWARD_RISK)。

**事件封锁**:读 news_gold.json 的 blackout_recommended。CPI/非农/FOMC 当天一律
转「观望」——数据发布时 $3 止损是纸糊的(滑点跳过去,实际亏损 $8~$15)。

⚠️ 老实话,必须写在前面:
  · +0.091R 的期望极薄,单笔 R 标准差约 1.48 —— 要上千笔才能 95% 确认它不是零。
  · 所以这里的「置信度」是**信号相对强弱**,不是胜率,更不是「预测」。
  · 没有任何人能准确预测金价方向。这是有纪律的读盘辅助,不是盈利保证。
  · 黄金带杠杆,可能损失全部本金。方向判断的最终责任在你。

用法:
    python3 generate_signals_gold.py            # 取真实行情(需在能连 Yahoo 的环境,如 Actions)
    python3 generate_signals_gold.py --selftest # 用合成K线自测逻辑(不联网)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path

import backtest_gold as B

ROOT = Path(__file__).resolve().parent
OUT_JSON = ROOT / "signals_gold.json"
OUT_MD = ROOT / "signals_gold.md"
NEWS_JSON = ROOT / "news_gold.json"

# ── 默认跑「样本外唯一验证为正」的那组:M15 · 固定$3止损 · RR1:2 ──────────────
INTERVAL = os.environ.get("GOLD_INTERVAL", "15m")
RANGE = os.environ.get("GOLD_RANGE", "60d")
SYMBOL = os.environ.get("GOLD_SYMBOL", "GC=F")
EQUITY = float(os.environ.get("GOLD_EQUITY", "200"))
LONG_ONLY = bool(os.environ.get("LONG_ONLY"))       # 只做多(很多散户不方便做空)

# 把验证过的参数灌进 backtest_gold(REWARD_RISK / FIXED_STOP 就是 EA 的 input)。
B.FIXED_STOP_USD = float(os.environ.get("GOLD_FIXED_STOP", "3.0"))
B.REWARD_RISK = float(os.environ.get("GOLD_RR", "2.0"))
B.EQUITY0 = EQUITY

# 样本外验证基线(和 gold_health.py 一致),用来把置信度钉在现实里。
BASE_EXP_R = 0.091
BASE_WR = 40.5

DISCLAIMER = (
    "算法根据公开行情(GC=F)自动生成的读盘辅助,复用 backtest_gold 的回测规则。"
    "样本外每笔期望仅 +0.091R,需上千笔才统计显著 —— 这里的置信度是**信号相对强弱,"
    "不是胜率,更不是预测**。不构成投资建议或收益承诺。黄金杠杆交易可能损失全部本金,"
    "方向判断的最终责任在你。"
)


def load_blackout():
    """从 news_gold.json 读今天是否有高影响事件(有 = 别开新仓)。"""
    try:
        d = json.loads(NEWS_JSON.read_text(encoding="utf-8"))
        return bool(d.get("blackout_recommended")), list(d.get("high_impact_events") or [])
    except Exception:
        return False, []


def make_synthetic(direction="up", n=400):
    """自测用:造一段带趋势的合成K线,让 EMA20>50>200 排列成立、并触发回踩买点。

    不联网,只为验证 evaluate() 这段逻辑能跑通、字段齐全。绝不用于真实信号。
    """
    import random
    random.seed(7)
    bars = []
    px = 2000.0
    t0 = int(dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc).timestamp())
    slope = 0.6 if direction == "up" else -0.6
    for i in range(n):
        # 趋势 + 噪音;最后几根做一个回踩(靠近均线)以触发 pullback 买点
        drift = slope
        if i > n - 6:
            drift = -slope * 0.7 if direction == "up" else -slope * 0.7
        px = max(1.0, px + drift + random.uniform(-1.2, 1.2))
        o = px + random.uniform(-0.5, 0.5)
        h = max(o, px) + abs(random.uniform(0, 0.8))
        l = min(o, px) - abs(random.uniform(0, 0.8))
        c = px
        bars.append({"t": t0 + i * 900, "o": o, "h": h, "l": l, "c": c})
    return bars


def evaluate(bars):
    """在**最后一根已收盘K线**上跑 backtest_gold 的入场规则,给出当前读盘。

    返回 dict(方向 / 触发类型 / 指标快照 / 入场·止损·目标 / 置信度 / 观察位)。
    """
    n = len(bars)
    need = max(B.TREND, B.SWING_LOOKBACK + B.SWING_WING + 2, B.ATR_P + 2) + 3
    if n < need:
        return {"read": "wait", "label": "观望", "reason": f"K线不足({n}<{need}),无法判定趋势", "enough": False}

    closes = [b["c"] for b in bars]
    ef = B.ema_series(closes, B.FAST)     # EMA20
    es = B.ema_series(closes, B.SLOW)     # EMA50
    et = B.ema_series(closes, B.TREND)    # EMA200
    rsi = B.rsi_series(closes, B.RSI_P)
    mline, msig = B.macd_series(closes)
    atr = B.atr_series(bars, B.ATR_P)

    i = n - 2                              # 最后一根**已收盘**的K线(n-1 可能还在走)
    if None in (rsi[i], atr[i]) or atr[i] <= 0:
        return {"read": "wait", "label": "观望", "reason": "指标未就绪(ATR/RSI)", "enough": False}

    res, sup = B.structure(bars, i)
    price = closes[-1]                      # 最新价(可能是未收盘那根)
    c = closes[i]

    up = ef[i] > es[i] > et[i]
    dn = ef[i] < es[i] < et[i]
    macd_up = mline[i] > msig[i] and mline[i] > 0
    macd_dn = mline[i] < msig[i] and mline[i] < 0
    buf = max(atr[i] * 0.15, B.SPREAD_USD * 2)

    # 触发位(即使当前没触发,也告诉用户「站上/跌破哪里」就成立)
    brk_up_lvl = (res + buf) if res is not None else None
    brk_dn_lvl = (sup - buf) if sup is not None else None
    pb_up_hi = ef[i] + atr[i] * 0.5        # 回踩做多区上沿

    brk_up = up and res is not None and c > res + buf
    pb_up = up and c <= ef[i] + atr[i] * 0.5 and c > es[i]
    brk_dn = dn and sup is not None and c < sup - buf
    pb_dn = dn and c >= ef[i] - atr[i] * 0.5 and c < es[i]

    long_ok = (brk_up or pb_up) and rsi[i] < B.RSI_BUY_MAX and macd_up
    short_ok = (brk_dn or pb_dn) and rsi[i] > B.RSI_SELL_MIN and macd_dn

    # 止损距离:和回测完全同一段逻辑
    if B.FIXED_STOP_USD > 0:
        dist = B.FIXED_STOP_USD
    else:
        dist = max(atr[i] * B.ATR_STOP_MULT, B.SPREAD_USD * B.MIN_STOP_SPRDX)

    snap = {
        "price": round(price, 2),
        "ema20": round(ef[i], 2), "ema50": round(es[i], 2), "ema200": round(et[i], 2),
        "rsi": round(rsi[i], 1),
        "macd_line": round(mline[i], 3), "macd_sig": round(msig[i], 3),
        "macd_hist": round(mline[i] - msig[i], 3),
        "atr": round(atr[i], 2),
        "resistance": round(res, 2) if res is not None else None,
        "support": round(sup, 2) if sup is not None else None,
        "regime": "多头排列" if up else ("空头排列" if dn else "无趋势/交织"),
        "stop_dist": round(dist, 2), "rr": B.REWARD_RISK,
        "brk_up_lvl": round(brk_up_lvl, 2) if brk_up_lvl else None,
        "brk_dn_lvl": round(brk_dn_lvl, 2) if brk_dn_lvl else None,
        "pb_up_hi": round(pb_up_hi, 2),
    }

    def plan(direction):
        d = 1 if direction == "long" else -1
        entry = price + B.SPREAD_USD * d / 2.0
        sl = entry - dist * d
        tp = entry + dist * B.REWARD_RISK * d
        lots, risk = B.lots_for(EQUITY, dist)
        return {
            "entry": round(entry, 2), "stop": round(sl, 2), "target": round(tp, 2),
            "lots": round(lots, 6), "risk_usd": round(risk, 2),
        }

    # ── 方向判定 ────────────────────────────────────────────────────────
    if long_ok and not (LONG_ONLY and False):
        trig = "突破" if brk_up else "回踩"
        conf = _confidence("long", brk_up, rsi[i], mline[i] - msig[i])
        r = {"read": "long", "label": "做多倾向", "trigger": trig, "confidence": conf}
        r.update(plan("long"))
    elif short_ok and not LONG_ONLY:
        trig = "突破" if brk_dn else "回踩"
        conf = _confidence("short", brk_dn, rsi[i], mline[i] - msig[i])
        r = {"read": "short", "label": "做空倾向", "trigger": trig, "confidence": conf}
        r.update(plan("short"))
    elif short_ok and LONG_ONLY:
        r = {"read": "wait", "label": "观望", "trigger": None, "confidence": 0.0,
             "reason": "出现做空条件,但已设 LONG_ONLY(只做多),跳过。"}
    elif up:
        r = {"read": "wait", "label": "观望·偏多", "trigger": None, "confidence": 0.30,
             "reason": f"多头排列但未触发。站上 {snap['brk_up_lvl']} 破位、"
                       f"或回踩到 {snap['ema50']}~{snap['pb_up_hi']} 区且 MACD 转多才成立。"}
    elif dn:
        r = {"read": "wait", "label": "观望·偏空", "trigger": None, "confidence": 0.30,
             "reason": f"空头排列但未触发。跌破 {snap['brk_dn_lvl']}、"
                       f"或反抽到 {snap['ema50']} 下方且 MACD 转空才成立。"}
    else:
        r = {"read": "wait", "label": "观望·无趋势", "trigger": None, "confidence": 0.0,
             "reason": "EMA20/50/200 未形成单边排列,GoldScalper 不在震荡里开仓。"}

    r["enough"] = True
    r["snapshot"] = snap
    return r


def _confidence(direction, is_breakout, rsi_v, macd_hist):
    """老实版置信度:基线 0.50,几个确认各加一点点,**硬顶 0.62**。

    这不是胜率。样本外胜率就 40.5%。这只是「几个条件同时成立的相对强弱」。
    钉这么低是故意的——+0.091R 的薄 edge 撑不起更高的数字,给高了就是骗人。
    """
    conf = 0.50
    if is_breakout:
        conf += 0.04                       # 破位比回踩确定性略高
    if direction == "long" and 50 <= rsi_v < B.RSI_BUY_MAX:
        conf += 0.03
    if direction == "short" and B.RSI_SELL_MIN < rsi_v <= 50:
        conf += 0.03
    if (direction == "long" and macd_hist > 0) or (direction == "short" and macd_hist < 0):
        conf += 0.03
    return round(min(conf, 0.62), 2)


def render_md(res, blackout, events, now, data_ok=True):
    L = [f"# 黄金读盘信号 — {now:%Y-%m-%d %H:%M} UTC", "",
         f"**品种** {SYMBOL} · **周期** {INTERVAL} · **本金** ${EQUITY:.0f} · "
         f"**止损** ${B.FIXED_STOP_USD:.1f} · **盈亏比** 1:{B.REWARD_RISK:g}", ""]

    if not data_ok:
        L += ["> ⚠️ **取数失败**:当前环境连不到 Yahoo(GC=F)。这个脚本要在能联网的环境跑",
              "> (GitHub Actions runner)。本地/沙箱直连不到行情,信号无法生成。", "",
              "---", "", f"*{DISCLAIMER}*"]
        return "\n".join(L)

    if blackout:
        L += [f"## ⛔ 事件封锁中 — 强制观望", "",
              f"今日检测到高影响事件:**{'、'.join(events) if events else '未具名'}**。",
              "> 数据发布前后 **不开新仓**。$3 止损在数据时刻会被**跳过去**(滑点),",
              "> 实际亏损可能是 $8~$15。方向留到尘埃落定后再看。", ""]

    if not res.get("enough"):
        L += [f"## 观望 — {res.get('reason','数据不足')}", "", "---", "", f"*{DISCLAIMER}*"]
        return "\n".join(L)

    s = res["snapshot"]
    read_icon = {"long": "🟢", "short": "🔴", "wait": "⚪"}.get(res["read"], "⚪")
    decision = "观望(封锁)" if blackout else res["label"]

    L += [f"## {read_icon} 当前读盘:**{decision}**", ""]
    if res.get("confidence"):
        L.append(f"- 信号强度(**非胜率**):`{res['confidence']}`" +
                 (f" · 触发方式:{res['trigger']}" if res.get("trigger") else ""))
    if res.get("reason"):
        L.append(f"- 说明:{res['reason']}")
    L.append("")

    # 行情快照
    L += ["### 行情快照", "",
          f"- 最新价:**${s['price']}** · 形态:**{s['regime']}**",
          f"- 均线:EMA20 `{s['ema20']}` / EMA50 `{s['ema50']}` / EMA200 `{s['ema200']}`",
          f"- RSI(14):`{s['rsi']}` · MACD 柱:`{s['macd_hist']}` · ATR(14):`${s['atr']}`",
          f"- 阻力:**${s['resistance']}** · 支撑:**${s['support']}**", ""]

    # 交易方案(只有明确方向且不在封锁时才给具体价位)
    if res["read"] in ("long", "short") and not blackout:
        side = "做多" if res["read"] == "long" else "做空"
        L += [f"### 参考方案 · {side}", "",
              f"- 入场参考:**${res['entry']}**",
              f"- 止损:**${res['stop']}**(距离 ${s['stop_dist']})· "
              f"目标:**${res['target']}**(1:{s['rr']:g})",
              f"- 仓位参考:**{res['lots']} 手**(XAUUSD,0.001手=0.1oz)· 风险 ≈ ${res['risk_usd']}", ""]
    else:
        # 没触发也给「看哪个位」
        watch = []
        if s.get("brk_up_lvl"):
            watch.append(f"站上 **${s['brk_up_lvl']}** = 破位做多候选")
        if s.get("brk_dn_lvl"):
            watch.append(f"跌破 **${s['brk_dn_lvl']}** = 破位做空候选")
        if watch:
            L += ["### 观察位", "", *[f"- {w}" for w in watch], ""]

    L += ["---", "",
          f"> 样本外基线:胜率 {BASE_WR}% · 每笔期望 +{BASE_EXP_R}R —— 极薄,别当预测用。", "",
          f"*{DISCLAIMER}*"]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="用合成K线自测逻辑(不联网)")
    a = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    blackout, events = load_blackout()

    if a.selftest:
        print("[selftest] 用合成上升趋势K线跑 evaluate() ...")
        bars = make_synthetic("up")
        res = evaluate(bars)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        bars = make_synthetic("down")
        print("[selftest] 下降趋势:", evaluate(bars).get("label"))
        return 0

    data_ok = True
    res = {"enough": False, "read": "wait", "label": "观望"}
    try:
        bars = B.fetch(SYMBOL, INTERVAL, RANGE)
        if len(bars) < 300:
            data_ok, res = True, {"enough": False, "read": "wait", "label": "观望",
                                  "reason": f"K线不足({len(bars)})"}
        else:
            res = evaluate(bars)
    except Exception as e:
        data_ok = False
        res = {"enough": False, "read": "wait", "label": "观望", "reason": f"取数失败:{e}"}

    # 封锁时强制观望(方向读盘仍写进 JSON 供参考,但决策是观望)
    decision = "wait" if blackout else res.get("read", "wait")

    out = {
        "updated_at": now.isoformat(timespec="seconds"),
        "symbol": SYMBOL, "interval": INTERVAL, "range": RANGE,
        "equity": EQUITY, "fixed_stop_usd": B.FIXED_STOP_USD, "reward_risk": B.REWARD_RISK,
        "generator": "generate_signals_gold.py (复用 backtest_gold 规则)",
        "data_ok": data_ok,
        "blackout": blackout, "high_impact_events": events,
        "decision": decision,                 # 机器最终决策(封锁时=wait)
        "read": res.get("read"),              # 纯技术读盘(不含封锁)
        "label": ("观望(事件封锁)" if blackout else res.get("label")),
        "confidence": res.get("confidence", 0.0),
        "trigger": res.get("trigger"),
        "reason": res.get("reason"),
        "plan": {k: res[k] for k in ("entry", "stop", "target", "lots", "risk_usd")
                 if k in res} or None,
        "snapshot": res.get("snapshot"),
        "baseline": {"oos_win_rate_pct": BASE_WR, "oos_exp_r": BASE_EXP_R},
        "note": DISCLAIMER,
    }
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MD.write_text(render_md(res, blackout, events, now, data_ok), encoding="utf-8")

    print(f"[gold-signal] decision={decision} read={res.get('read')} "
          f"conf={res.get('confidence')} blackout={blackout} data_ok={data_ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
