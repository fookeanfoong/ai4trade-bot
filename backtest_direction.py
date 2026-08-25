#!/usr/bin/env python3
"""只测一件事：EA 的**方向判断**到底有没有边。

不测入场形态、不测止盈止损细节 —— 那些都是在方向对了之后才谈的。
先回答最根本的问题：当 PriceActionDir 说"做多/做空"时，接下来价格
更可能往那个方向走吗？

做法（和 EA 的 PriceActionDir 一致）：
  摆动结构 MarketStructure：最近两个摆动高/低点，HH+HL=多，LH+LL=空
  近期净推进：最近 N 根收盘净变化，超过 k×ATR 才算有方向
  最终方向：两者一致->该方向；分歧->不做；一方不明->听另一方

判定胜负（对称 1:1，等价于 EA 的 $3 落袋 / $3 止损）：
  进场后，价格先摸到 +X 还是 -X。X 两边相等，所以**胜率纯粹反映方向质量**。
  X 的绝对值不影响胜率结论，取 0.5×ATR。

关键产出：整体胜率、做多/做空分别的胜率、**按季度分**（不同行情）。
胜率若在 50% 附近甚至更低，说明这套方向判断没有边 —— 那再怎么调
入场出场都是白费，因为 1:1 结构下胜率就是一切。

用法： python3 backtest_direction.py --interval 1h --range 2y
"""
import argparse, json, os
from datetime import datetime, timezone
from urllib import request as urlreq

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def fetch(symbol, interval, rng):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?range={rng}&interval={interval}")
    req = urlreq.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urlreq.urlopen(req, timeout=40) as r:
        p = json.loads(r.read().decode())
    res = p["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = (res.get("indicators", {}).get("quote") or [{}])[0]
    o,h,l,c = q.get("open") or [], q.get("high") or [], q.get("low") or [], q.get("close") or []
    bars=[]
    for i,t in enumerate(ts):
        try: oo,hh,ll,cc=o[i],h[i],l[i],c[i]
        except IndexError: continue
        if None in (oo,hh,ll,cc): continue
        bars.append({"t":datetime.fromtimestamp(int(t),tz=timezone.utc),
                     "o":float(oo),"h":float(hh),"l":float(ll),"c":float(cc)})
    bars.sort(key=lambda b:b["t"])
    return bars

def atr_at(bars, i, period=14):
    if i < period: return None
    trs=[]
    for j in range(i-period+1, i+1):
        pc=bars[j-1]["c"]
        trs.append(max(bars[j]["h"]-bars[j]["l"], abs(bars[j]["h"]-pc), abs(bars[j]["l"]-pc)))
    return sum(trs)/len(trs)

def swings(bars, i, lookback, strength):
    """返回 (最近两个摆动高, 最近两个摆动低)，从 i 往回找。"""
    hi=[]; lo=[]
    j=i-strength
    while j>=max(strength, i-lookback) and (len(hi)<2 or len(lo)<2):
        win=bars[j-strength:j+strength+1]
        if bars[j]["h"]==max(x["h"] for x in win) and len(hi)<2: hi.append(bars[j]["h"])
        if bars[j]["l"]==min(x["l"] for x in win) and len(lo)<2: lo.append(bars[j]["l"])
        j-=1
    return hi, lo

def market_structure(bars, i, lookback=60, strength=2):
    hi, lo = swings(bars, i, lookback, strength)
    if len(hi)<2 or len(lo)<2: return 0
    if hi[0]>hi[1] and lo[0]>lo[1]: return 1
    if hi[0]<hi[1] and lo[0]<lo[1]: return -1
    return 0

def direction(bars, i, atr, pa_bars, pa_min):
    st = market_structure(bars, i)
    mo = 0
    if i>=pa_bars and atr and atr>0:
        net = bars[i]["c"] - bars[i-pa_bars]["c"]
        if abs(net) >= pa_min*atr: mo = 1 if net>0 else -1
    if st!=0 and mo!=0: return st if st==mo else 0
    if mo!=0: return mo
    return st

def outcome(bars, i, dir_, dist):
    """进场后先摸 +dist 还是 -dist。看后续最多 24 根。"""
    entry = bars[i]["c"]
    tp = entry + dir_*dist
    sl = entry - dir_*dist
    for j in range(i+1, min(i+25, len(bars))):
        hit_tp = bars[j]["h"]>=tp if dir_>0 else bars[j]["l"]<=tp
        hit_sl = bars[j]["l"]<=sl if dir_>0 else bars[j]["h"]>=sl
        if hit_tp and hit_sl: return -1   # 同根两边都碰，保守算亏
        if hit_tp: return 1
        if hit_sl: return -1
    return 0   # 未结束，不计

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbol", default="GC=F")
    ap.add_argument("--interval", default="1h")
    ap.add_argument("--range", dest="rng", default="2y")
    ap.add_argument("--pa-bars", type=int, default=6)
    ap.add_argument("--pa-min", type=float, default=0.30)
    a=ap.parse_args()

    bars=fetch(a.symbol, a.interval, a.rng)
    if len(bars)<200: raise SystemExit(f"数据不足：{len(bars)} 根")

    trades=[]
    last_dir=0
    for i in range(60, len(bars)-1):
        atr=atr_at(bars,i)
        if not atr: continue
        d=direction(bars,i,atr,a.pa_bars,a.pa_min)
        if d==0: continue
        # 简单去重：同方向连续信号只在方向切换时进一次，避免同一段行情重复计数
        if d==last_dir: continue
        last_dir=d
        r=outcome(bars,i,d,0.5*atr)
        if r==0: continue
        trades.append({"t":bars[i]["t"],"dir":d,"win":r>0})

    def stat(sel):
        if not sel: return (0,0.0)
        w=sum(1 for x in sel if x["win"])
        return (len(sel), 100*w/len(sel))

    out=[]
    out.append("# 方向判断回测（只测方向有没有边）\n")
    out.append(f"*生成于 {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}*\n")
    out.append(f"数据：**{a.symbol} · {a.interval} · {a.rng}** — 共 {len(bars)} 根K线\n")
    out.append("> 对称 1:1 目标/止损（= EA 的 $3 落袋 / $3 止损）。")
    out.append("> 胜率就是一切：1:1 下胜率 >50%（扣成本后）才可能赚钱。")
    out.append("> 这是**K线级**近似，不等于 MT5 逐tick；同根双触按亏算，偏保守。\n")

    n,wr=stat(trades)
    out.append("## 一、整体\n")
    out.append(f"- 有效信号 **{n}** 笔，胜率 **{wr:.1f}%**")
    nl,wl=stat([x for x in trades if x["dir"]>0])
    ns,ws=stat([x for x in trades if x["dir"]<0])
    out.append(f"- 做多 {nl} 笔，胜率 **{wl:.1f}%**")
    out.append(f"- 做空 {ns} 笔，胜率 **{ws:.1f}%**")

    out.append("\n## 二、按季度（不同行情）\n")
    out.append("| 季度 | 笔数 | 胜率 | 多胜率 | 空胜率 |")
    out.append("|---|---|---|---|---|")
    from collections import defaultdict
    byq=defaultdict(list)
    for x in trades:
        byq[f"{x['t'].year}Q{(x['t'].month-1)//3+1}"].append(x)
    for q in sorted(byq):
        s=byq[q]; _,w=stat(s)
        _,wql=stat([x for x in s if x["dir"]>0]); _,wqs=stat([x for x in s if x["dir"]<0])
        out.append(f"| {q} | {len(s)} | {w:.0f}% | {wql:.0f}% | {wqs:.0f}% |")

    out.append("\n## 三、结论\n")
    if wr>=55:
        out.append(f"> 整体 {wr:.0f}% —— 方向判断**有边**。值得往入场/出场细节上继续调。")
    elif wr>=50:
        out.append(f"> 整体 {wr:.0f}% —— 擦着平衡线，扣掉点差滑点大概率不赚。方向逻辑还不够。")
    else:
        out.append(f"> 整体 {wr:.0f}% —— **低于抛硬币**。方向判断在这段数据上没有边，"
                   f"再调入场出场都是白费。这类结果通常说明：要么这套结构+推进的组合"
                   f"不适合黄金，要么该换更长的周期定方向。")
    # 多空差
    if n>0 and abs(wl-ws)>=15:
        out.append(f">\n> 多空差 {abs(wl-ws):.0f} 个百分点 —— 明显不对称，"
                   f"说明这段数据整体偏{'多' if wl>ws else '空'}，方向判断没能中性地两边都抓。")

    os.makedirs("reports", exist_ok=True)
    with open("reports/direction_backtest.md","w",encoding="utf-8") as f:
        f.write("\n".join(out)+"\n")
    print("\n".join(out))

if __name__=="__main__":
    main()
