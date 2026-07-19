#!/usr/bin/env python3
"""从机器人真实的已平仓记录生成「透明战绩」数据。

用法:  python3 pwa/build_track_record.py

读取根目录 state.json 的 trade_log(真实已平仓交易),算出胜率/累计盈亏/每笔明细
和一条累计盈亏曲线,写到 pwa/data/track_record.json。

⚠️ 这是**真实**数据,不做任何美化。若当前是净亏损,页面也会如实显示 ——
   这正是合规且建立信任的做法。是否对外展示由你在 config.js 里开关。
"""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pwa", "data", "track_record.json")

REASON_ZH = {
    "GR-STOP": "止损离场",
    "TREND-BREAK": "趋势转弱离场",
    "NEWS-RISK": "新闻风控离场",
    "TP": "止盈",
    "TRAIL": "移动止盈",
    "SIGNAL_INVALIDATED_EXIT": "信号失效离场",
}


def load_trades():
    trades = []
    with open(os.path.join(ROOT, "state.json"), "r", encoding="utf-8") as f:
        st = json.load(f)
    for t in st.get("trade_log", []):
        closed = str(t.get("closed_at", ""))
        trades.append({
            "ticker": t.get("sym"),
            "pnl_usd": round(float(t.get("pnl_usd", 0)), 2),
            "pnl_pct": round(float(t.get("pnl_pct", 0)) * 100, 2),
            "reason": REASON_ZH.get(t.get("reason"), t.get("reason") or "—"),
            "date": closed[:10],
        })
    trades.sort(key=lambda x: x["date"])
    return trades


def main():
    trades = load_trades()
    wins = [t for t in trades if t["pnl_usd"] > 0]
    losses = [t for t in trades if t["pnl_usd"] < 0]
    breakeven = [t for t in trades if t["pnl_usd"] == 0]
    net = round(sum(t["pnl_usd"] for t in trades), 2)

    curve, cum = [], 0.0
    for t in trades:
        cum = round(cum + t["pnl_usd"], 2)
        curve.append({"date": t["date"], "cum": cum})

    days = sorted({t["date"] for t in trades})
    data = {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "note": "以下为模拟盘真实已平仓记录,未做任何美化。过往表现不代表未来结果。",
        "summary": {
            "trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "net_pnl": net,
            "best": max((t["pnl_usd"] for t in trades), default=0),
            "worst": min((t["pnl_usd"] for t in trades), default=0),
            "days": len(days),
            "first_date": days[0] if days else None,
            "last_date": days[-1] if days else None,
        },
        "curve": curve,
        "trades": list(reversed(trades)),  # 最新在前
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    s = data["summary"]
    print(f"wrote {OUT}: {s['trades']} trades, {s['wins']}W/{s['losses']}L, net ${s['net_pnl']}")


if __name__ == "__main__":
    main()
