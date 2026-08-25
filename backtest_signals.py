#!/usr/bin/env python3
"""一次测清楚：到底有没有**任何**方向信号，在真实黄金上胜率能站上边？

背景：backtest_direction.py 测出当前方向逻辑（摆动结构+推进）胜率 49.1%，
1:1 盈亏比下必亏。但那只是一种定方向的方式。这个脚本把常见的方向依据
全列出来，用同一段两年数据、同一套 1:1 判定，排个名 —— 看有没有哪个过 55%。

每个方法都测两遍：
  · 顺着信号做（trend-following）
  · 反着信号做（mean-reversion / fade）
因为黄金 M5/1h 上很可能是**均值回归**占优，那样顺势全错、反着才对。

对最好的两三个，再看 1:1.5 和 1:2 赔率下的**期望值**（每笔平均 R），
因为真正能赚钱的不一定是胜率最高的，而是期望值为正的。

用法： python3 backtest_signals.py --interval 1h --range 2y
"""
import argparse, json, os
from datetime import datetime, timezone
from urllib import request as urlreq

UA=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

def fetch(symbol, interval, rng):
    url=(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
         f"?range={rng}&interval={interval}")
    req=urlreq.Request(url, headers={"User-Agent":UA,"Accept":"application/json"})
    with urlreq.urlopen(req,timeout=40) as r: p=json.loads(r.read().decode())
    res=p["chart"]["result"][0]; ts=res.get("timestamp") or []
    q=(res.get("indicators",{}).get("quote") or [{}])[0]
    o,h,l,c=q.get("open") or [],q.get("high") or [],q.get("low") or [],q.get("close") or []
    b=[]
    for i,t in enumerate(ts):
        try: oo,hh,ll,cc=o[i],h[i],l[i],c[i]
        except IndexError: continue
        if None in (oo,hh,ll,cc): continue
        b.append({"t":datetime.fromtimestamp(int(t),tz=timezone.utc),
                  "o":float(oo),"h":float(hh),"l":float(ll),"c":float(cc)})
    b.sort(key=lambda x:x["t"]); return b

def ema(bars, i, period):
    if i<period: return None
    k=2/(period+1); e=bars[i-period]["c"]
    for j in range(i-period+1,i+1): e=bars[j]["c"]*k+e*(1-k)
    return e

def atr(bars,i,period=14):
    if i<period: return None
    s=0
    for j in range(i-period+1,i+1):
        pc=bars[j-1]["c"]
        s+=max(bars[j]["h"]-bars[j]["l"],abs(bars[j]["h"]-pc),abs(bars[j]["l"]-pc))
    return s/period

def rsi(bars,i,period=14):
    if i<period: return None
    g=ls=0
    for j in range(i-period+1,i+1):
        d=bars[j]["c"]-bars[j-1]["c"]
        if d>0: g+=d
        else: ls-=d
    if g+ls==0: return 50
    return 100*g/(g+ls)

def swings(bars,i,lookback,strength):
    hi=[];lo=[];j=i-strength
    while j>=max(strength,i-lookback) and (len(hi)<2 or len(lo)<2):
        w=bars[j-strength:j+strength+1]
        if bars[j]["h"]==max(x["h"] for x in w) and len(hi)<2: hi.append(bars[j]["h"])
        if bars[j]["l"]==min(x["l"] for x in w) and len(lo)<2: lo.append(bars[j]["l"])
        j-=1
    return hi,lo

def structure(bars,i,lookback=60,strength=2):
    hi,lo=swings(bars,i,lookback,strength)
    if len(hi)<2 or len(lo)<2: return 0
    if hi[0]>hi[1] and lo[0]>lo[1]: return 1
    if hi[0]<hi[1] and lo[0]<lo[1]: return -1
    return 0

# ---- 各方向信号：返回 +1/-1/0 ----
def sig_struct_mom(bars,i,a):
    st=structure(bars,i); net=bars[i]["c"]-bars[i-6]["c"]
    mo=(1 if net>0 else -1) if abs(net)>=0.30*a else 0
    if st and mo: return st if st==mo else 0
    return mo or st
def sig_ema_cross(bars,i,a):
    f,s=ema(bars,i,20),ema(bars,i,50)
    if f is None or s is None: return 0
    return 1 if f>s else -1
def sig_htf_trend(bars,i,a):
    f,s=ema(bars,i,50),ema(bars,i,200)
    if f is None or s is None: return 0
    return 1 if f>s else -1
def sig_momentum(bars,i,a):
    net=bars[i]["c"]-bars[i-10]["c"]
    return (1 if net>0 else -1) if abs(net)>=0.5*a else 0
def sig_breakout(bars,i,a):
    hh=max(x["h"] for x in bars[i-20:i]); ll=min(x["l"] for x in bars[i-20:i])
    if bars[i]["c"]>hh: return 1
    if bars[i]["c"]<ll: return -1
    return 0
def sig_rsi(bars,i,a):
    r=rsi(bars,i)
    if r is None: return 0
    if r>55: return 1
    if r<45: return -1
    return 0
def sig_structure_only(bars,i,a):
    return structure(bars,i,lookback=120,strength=3)

SIGNALS={
 "结构+推进(当前)":sig_struct_mom,
 "EMA20/50交叉":sig_ema_cross,
 "EMA50/200趋势":sig_htf_trend,
 "10根净推进":sig_momentum,
 "20根突破":sig_breakout,
 "RSI动量":sig_rsi,
 "长周期结构":sig_structure_only,
}

def outcome(bars,i,d,dist,rr):
    """返回该笔的 R 倍数（赢=+rr, 亏=-1, 未结束=None）。"""
    e=bars[i]["c"]; tp=e+d*dist*rr; sl=e-d*dist
    for j in range(i+1,min(i+40,len(bars))):
        htp=bars[j]["h"]>=tp if d>0 else bars[j]["l"]<=tp
        hsl=bars[j]["l"]<=sl if d>0 else bars[j]["h"]>=sl
        if hsl and htp: return -1.0
        if hsl: return -1.0
        if htp: return float(rr)
    return None

def run(bars,sigfn,fade,rr=1.0):
    R=[]; last=0
    for i in range(200,len(bars)-1):
        a=atr(bars,i)
        if not a: continue
        d=sigfn(bars,i,a)
        if fade: d=-d
        if d==0 or d==last: continue
        last=d
        r=outcome(bars,i,d,0.5*a,rr)
        if r is not None: R.append(r)
    if not R: return (0,0.0,0.0)
    wins=sum(1 for x in R if x>0)
    return (len(R),100*wins/len(R),sum(R)/len(R))   # 笔数, 胜率%, 每笔期望R

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--symbol",default="GC=F")
    ap.add_argument("--interval",default="1h")
    ap.add_argument("--range",dest="rng",default="2y")
    a=ap.parse_args()
    bars=fetch(a.symbol,a.interval,a.rng)
    if len(bars)<400: raise SystemExit(f"数据不足 {len(bars)}")

    rows=[]
    for name,fn in SIGNALS.items():
        for fade in (False,True):
            n,wr,ev=run(bars,fn,fade)
            if n>=30:
                rows.append((name+("(反做)" if fade else "(顺做)"),n,wr,ev))
    rows.sort(key=lambda x:-x[2])   # 按胜率排

    out=[]
    out.append("# 方向信号大排查（真实黄金，1:1）\n")
    out.append(f"*生成于 {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}*\n")
    out.append(f"数据：**{a.symbol} · {a.interval} · {a.rng}** — {len(bars)} 根K线\n")
    out.append("> 每个信号顺做/反做各测一遍，对称 1:1（=$3落袋/$3止损）。")
    out.append("> 同根双触按亏算，偏保守。胜率>50%（扣成本后需≈53%）才可能赚。\n")
    out.append("## 全部信号，按胜率排\n")
    out.append("| 信号 | 笔数 | 胜率 | 每笔期望R |")
    out.append("|---|---|---|---|")
    for nm,n,wr,ev in rows:
        mark=" ✅" if wr>=53 else (" ~" if wr>=50 else "")
        out.append(f"| {nm} | {n} | **{wr:.1f}%**{mark} | {ev:+.3f} |")

    best=rows[0]
    out.append("\n## 结论\n")
    if best[2]>=53:
        out.append(f"> 最好的是 **{best[0]}**，胜率 {best[2]:.1f}% —— 站上了边。")
        out.append(f"> 下一步：用它当方向，再在 1:1.5 / 1:2 上验期望值。")
    elif best[2]>=50:
        out.append(f"> 最好的 **{best[0]}** 只有 {best[2]:.1f}%，擦线。扣点差滑点大概率仍不赚。")
    else:
        out.append(f"> **没有一个信号站上 50%。** 最高的 {best[0]} 也只有 {best[2]:.1f}%。")
        out.append(f"> 这强烈说明：黄金在 {a.interval} 上、用 1:1 的对称目标，"
                   f"方向就是不可预测的 —— 问题不在参数，在**赔率结构**。")
        out.append(f"> 出路是放弃 1:1，改用小止损放大赢（trend）或小赢高频（scalp with edge），"
                   f"而不是继续找方向。")

    # 顺带：把最好那个信号在不同赔率下的期望值列出来
    top=[r for r in rows[:3]]
    out.append("\n## 前三名在不同赔率下的每笔期望R\n")
    out.append("| 信号 | 1:1 | 1:1.5 | 1:2 |")
    out.append("|---|---|---|---|")
    for nm,_,_,_ in top:
        base=nm.replace("(反做)","").replace("(顺做)","")
        fade="(反做)" in nm
        fn=SIGNALS[base]
        evs=[]
        for rr in (1.0,1.5,2.0):
            _,_,ev=run(bars,fn,fade,rr); evs.append(ev)
        flag=" <- 正期望" if max(evs)>0 else ""
        out.append(f"| {nm} | {evs[0]:+.3f} | {evs[1]:+.3f} | {evs[2]:+.3f} |{flag}")

    os.makedirs("reports",exist_ok=True)
    with open("reports/signals_backtest.md","w",encoding="utf-8") as f:
        f.write("\n".join(out)+"\n")
    print("\n".join(out))

if __name__=="__main__": main()
