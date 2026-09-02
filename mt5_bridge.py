#!/usr/bin/env python3
"""MT5 桥 —— 在你装了 MetaTrader 5 的 Windows 电脑上跑,盯黄金 EA 的真实成交。

它做四件事,每次运行一遍(用 Windows 任务计划程序每 15~30 分钟跑一次):

  1. 连上正在运行的 MT5 终端,读黄金 EA(magic 20260809)的真实历史成交
  2. 把成交折算成 R 倍数,写进 gold_journal.json(和 forex 日志同结构)
  3. 调 gold_health 判断:HALT / RETHINK / OK / WATCH / ACCUMULATE
  4. 结论是 HALT 或 RETHINK 时 **提醒你**(控制台 + 文件 + 可选 Telegram 推到手机),
     并告诉你该换哪个经过验证的 preset(见 presets/gold/)

## 重要的诚实说明

- 这个脚本**只能在装了 MT5 的机器上跑**(MetaTrader5 这个库是 Windows-only,
  而且需要 MT5 终端开着)。在 Linux / 云端跑不了 —— 那是它连不到你 MT5 的原因。
- 它**默认只提醒,不自动改 EA 的参数**。EA 的 preset 是 MT5 的 input 参数,要真的
  「自己换」需要给 EA 加一段读外部文件的代码(第二步,见 SETUP_MT5_MONITOR.md)。
  在那之前,收到提醒后由你手动在 MT5 里加载对应的 .set 预设。
- 电脑关机时这个脚本不跑、EA 也不跑;但已有持仓的止损在券商服务器上依然有效。

## 用法

    python mt5_bridge.py                 # 正常:连 MT5、更新日志、判断、必要时提醒
    python mt5_bridge.py --mock sample_journal.json   # 无 MT5,用假数据测判断逻辑
    python mt5_bridge.py --days 60       # 回看多少天的成交(默认 90)

## 环境变量(都可选)

    MT5_LOGIN / MT5_PASSWORD / MT5_SERVER   显式登录(默认用终端已登录的账户)
    MT5_TERMINAL_PATH                        terminal64.exe 路径(默认自动找)
    GOLD_MAGIC        EA 的 magic(默认 20260809);设 0 = 不按 magic 过滤,统计所有黄金成交
    GOLD_SYMBOLS      只统计这些品种(逗号分隔,大小写不敏感);不设=自动识别含 xau/gold 的品种
    NOMINAL_STOP_USD  读不到订单止损时的兜底止损金额(默认 3.0,和 EA 默认一致)
    TELEGRAM_TOKEN / TELEGRAM_CHAT_ID        配了就把提醒推到手机 Telegram(免费)

*研究/学习用途,不构成投资建议。黄金杠杆交易可能损失全部本金。*
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import gold_health

JOURNAL = os.environ.get("GOLD_JOURNAL_FILE", "gold_journal.json")
ALERT_FILE = os.environ.get("GOLD_ALERT_FILE", "reports/gold_alert.txt")
# magic:默认只统计 GoldScalper EA(20260809)下的单。设 GOLD_MAGIC=0 = 不按 magic 过滤,
# 统计所有黄金成交(手动单、别的 EA 都算)。
MAGIC = int(os.environ.get("GOLD_MAGIC", "20260809"))
# 品种:默认自动识别任何含 "xau" 或 "gold" 的品种(兼容各家券商命名,如 xauusd.sml / XAUUSD / GOLD)。
# 想只统计特定品种就设 GOLD_SYMBOLS=xauusd.sml(逗号分隔多个,大小写不敏感)。
_SYMBOLS_ENV = os.environ.get("GOLD_SYMBOLS", "").strip()
SYMBOLS = [s.strip().lower() for s in _SYMBOLS_ENV.split(",") if s.strip()] if _SYMBOLS_ENV else None
NOMINAL_STOP_USD = float(os.environ.get("NOMINAL_STOP_USD", "3.0"))


def is_gold(symbol: str) -> bool:
    """判断一个品种是不是黄金。默认按 xau/gold 子串;设了 GOLD_SYMBOLS 就按精确名单。"""
    s = (symbol or "").lower()
    if SYMBOLS is not None:
        return s in SYMBOLS
    return "xau" in s or "gold" in s


# ─────────────────────────────────────────────────────────────────────────────
#  从 MT5 读成交并折算成 R
# ─────────────────────────────────────────────────────────────────────────────
def read_mt5_trades(days: int):
    """连 MT5,返回和 journal 同结构的 entries 列表。只在有 MetaTrader5 时可用。"""
    try:
        import MetaTrader5 as mt5
    except ImportError:
        sys.exit("✗ 没装 MetaTrader5 库。在装了 MT5 的 Windows 上运行:\n"
                 "    pip install MetaTrader5\n"
                 "  或用 --mock 模式在没有 MT5 的机器上测试判断逻辑。")

    # 连接(优先用终端已登录的账户;有 MT5_LOGIN 就显式登录)
    path = os.environ.get("MT5_TERMINAL_PATH")
    ok = mt5.initialize(path) if path else mt5.initialize()
    if not ok:
        sys.exit(f"✗ 连不上 MT5 终端:{mt5.last_error()}\n"
                 "  确认 MT5 已打开、已登录,且『工具→选项→EA交易→允许算法交易』已勾选。")

    login = os.environ.get("MT5_LOGIN")
    if login:
        if not mt5.login(int(login),
                         password=os.environ.get("MT5_PASSWORD", ""),
                         server=os.environ.get("MT5_SERVER", "")):
            mt5.shutdown()
            sys.exit(f"✗ MT5 登录失败:{mt5.last_error()}")

    acct = mt5.account_info()
    if acct is None:
        mt5.shutdown()
        sys.exit(f"✗ 读不到账户信息:{mt5.last_error()}")
    print(f"[mt5] 已连接 #{acct.login} @ {acct.server} · 净值 {acct.equity} {acct.currency}")

    to = dt.datetime.now()
    frm = to - dt.timedelta(days=days)
    deals = mt5.history_deals_get(frm, to)
    if deals is None:
        deals = ()

    # 每个品种的 money-per-price-unit-per-lot = tick_value / tick_size
    def money_per_price(symbol, volume, price_dist):
        info = mt5.symbol_info(symbol)
        if info and info.trade_tick_size:
            return price_dist * (info.trade_tick_value / info.trade_tick_size) * volume
        # 兜底:XAUUSD 常见口径 0.01 手 → $1 价格波动 $1 盈亏
        return price_dist * 100.0 * volume

    # 订单止损:position_id -> sl(用来算风险)
    orders = mt5.history_orders_get(frm, to) or ()
    sl_by_pos = {}
    for o in orders:
        if getattr(o, "sl", 0) and o.position_id:
            sl_by_pos.setdefault(o.position_id, o.sl)

    # 按 position_id 归拢开仓/平仓 deal
    pos = {}
    for d in deals:
        if MAGIC and d.magic != MAGIC:
            continue
        if not is_gold(d.symbol):
            continue
        p = pos.setdefault(d.position_id, {"symbol": d.symbol, "in": None,
                                           "out_profit": 0.0, "out_time": None,
                                           "out_price": None})
        if d.entry == mt5.DEAL_ENTRY_IN:
            p["in"] = d
        else:  # OUT / OUT_BY / INOUT
            p["out_profit"] += d.profit + d.commission + d.swap
            p["out_time"] = d.time
            p["out_price"] = d.price

    entries = []
    for pid, p in pos.items():
        din, = (p["in"],) if p["in"] else (None,)
        if din is None or p["out_time"] is None:
            continue  # 还没平仓,或数据不全 → 跳过
        volume = din.volume
        open_price = din.price
        direction = "long" if din.type == mt5.DEAL_TYPE_BUY else "short"

        # 风险:优先用订单止损,读不到就用兜底止损金额
        sl = sl_by_pos.get(pid)
        if sl and sl > 0:
            risk_money = money_per_price(p["symbol"], volume, abs(open_price - sl))
        else:
            risk_money = money_per_price(p["symbol"], volume, NOMINAL_STOP_USD)
        if risk_money <= 0:
            continue

        r = p["out_profit"] / risk_money
        state = "won" if p["out_profit"] > 0 else "lost"
        entries.append({
            "id": f"{p['symbol']}|GoldScalper|{pid}",
            "instrument": p["symbol"],
            "plan": "GoldScalper EA",
            "direction": direction,
            "signal_time": dt.datetime.fromtimestamp(din.time, dt.timezone.utc)
                             .isoformat(timespec="seconds"),
            "entry": open_price,
            "stop": sl or None,
            "mt5_lots": volume,
            "state": state,
            "exit_time": dt.datetime.fromtimestamp(p["out_time"], dt.timezone.utc)
                           .isoformat(timespec="seconds"),
            "exit_price": p["out_price"],
            "r_multiple": round(r, 3),
            "profit_ccy": round(p["out_profit"], 2),
        })

    mt5.shutdown()
    entries.sort(key=lambda e: e["exit_time"])
    magic_desc = f"magic {MAGIC}" if MAGIC else "所有 magic"
    print(f"[mt5] 读到 {len(entries)} 笔已平仓的黄金成交({magic_desc},近 {days} 天)")
    if not entries:
        print("[mt5] 提示:读到 0 笔。可能原因——")
        print("      1) 这些黄金单不是 GoldScalper EA 下的 → 设环境变量 GOLD_MAGIC=0 再跑,统计所有黄金成交")
        print("      2) 最近还没有已平仓的黄金单(未平仓的不计入)")
        print("      3) 品种名不含 xau/gold → 设 GOLD_SYMBOLS=你的品种名")
    return entries


# ─────────────────────────────────────────────────────────────────────────────
#  提醒
# ─────────────────────────────────────────────────────────────────────────────
PRESET_ADVICE = {
    "HALT": "→ 建议:在 MT5 图表上**卸下 GoldScalper EA**(或把 InpDailyLossPct 调到很小)。"
            "不要靠调止损/盈亏比续命。",
    "SWITCH": "→ 建议:换用 presets/gold/ 里经过验证的备选 preset(在 MT5『EA属性→输入』里"
              "『加载』对应的 .set 文件),或考虑改入场逻辑。",
}


def send_telegram(text: str) -> bool:
    token = os.environ.get("TELEGRAM_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    try:
        import urllib.parse
        import urllib.request
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        with urllib.request.urlopen(url, data=data, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"[alert] Telegram 推送失败:{e}")
        return False


def alert(state, headline, advice, s):
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    hint_line = PRESET_ADVICE.get(
        "HALT" if state == "HALT" else ("SWITCH" if state == "RETHINK" else ""), "")
    n = s["n"] if s else 0
    exp = s["exp"] if s else "—"
    body = (f"⚠️ 黄金 EA 策略提醒 · {state}\n"
            f"{headline}\n"
            f"实盘 {n} 笔,每笔期望 {exp}R\n"
            f"{advice}\n{hint_line}\n（{now}）")
    print("\n" + "=" * 60 + "\n" + body + "\n" + "=" * 60)
    os.makedirs(os.path.dirname(ALERT_FILE), exist_ok=True)
    with open(ALERT_FILE, "w", encoding="utf-8") as f:
        f.write(body + "\n")
    if send_telegram(body):
        print("[alert] 已推送到 Telegram")


# ─────────────────────────────────────────────────────────────────────────────
#  主流程
# ─────────────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="MT5 黄金 EA 健康监测桥")
    ap.add_argument("--mock", metavar="JOURNAL",
                    help="无 MT5:直接用这个 journal 文件测判断逻辑")
    ap.add_argument("--days", type=int, default=90, help="回看多少天成交(默认 90)")
    args = ap.parse_args()

    if args.mock:
        entries = gold_health.load(args.mock).get("entries", [])
        print(f"[mock] 从 {args.mock} 读到 {len(entries)} 笔")
    else:
        entries = read_mt5_trades(args.days)
        with open(JOURNAL, "w", encoding="utf-8") as f:
            json.dump({"entries": entries,
                       "updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")},
                      f, ensure_ascii=False, indent=2)
        print(f"[mt5] 已写入 {JOURNAL}")

    s = gold_health.stats(entries)
    state, headline, advice, hint = gold_health.verdict(s)

    # 写健康报告
    text = gold_health.render(s, state, headline, advice)
    os.makedirs(os.path.dirname(gold_health.OUT), exist_ok=True)
    with open(gold_health.OUT, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"[gold-health] {state} · {headline}")
    if hint in ("HALT", "SWITCH"):
        alert(state, headline, advice, s)
    else:
        print("[gold-health] 无需动作,EA 保持当前 preset 继续跑。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
