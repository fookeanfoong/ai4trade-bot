#!/usr/bin/env python3
"""外汇执行层 — 读 signals_forex.json,把 status=triggered 的方案挂成真单。

**策略选择:TP1 全平(吃小赢面广)。** 到 TP1 就整仓走人,1:2 的固定回报风险比,
不留尾仓、不移保本、不追 TP2。

这个选择带来一个很大的架构红利,值得说清楚:
    因为不需要「到 TP1 再动手」,止损和止盈可以在**挂单的同时**就交给 OANDA,
    变成券商侧的 GTC 委托。于是 —— GitHub Actions 挂了、runner 被回收、
    这个脚本再也没跑过,你的止损和止盈**依然在券商那里活着**。
    如果选的是「移保本 + 让利润跑」,出场就依赖机器人按时醒来,它不醒就是裸单。
    对一个跑在免费 CI 上的 $200 账户来说,这个差别比多赚的那点 R 重要得多。

执行链路:
    generate_signals_forex.py  ->  signals_forex.json  ->  本脚本  ->  OANDA 挂单
                                                                        |
                                            成交后止损/止盈由券商托管 ---+

三道安全锁(全部默认关闭/最严):
    1. FOREX_EXECUTE=yes        不设就是 dry-run,只打印不下单
    2. OANDA_ENV=live + OANDA_I_UNDERSTAND_REAL_MONEY=yes   才碰真钱(在 broker 里)
    3. 幂等指纹                 同一根 K 线的同一个方案,永远只下一次单

用法:
    python3 live_trader_forex.py              # dry-run,看它想干什么
    FOREX_EXECUTE=yes python3 live_trader_forex.py   # 真的挂单(模拟盘)
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

SIGNALS_FILE = os.environ.get("FOREX_SIGNALS_FILE", "signals_forex.json")
STATE_FILE = os.environ.get("FOREX_STATE_FILE", "live_trader_forex_state.json")
REPORT_DIR = os.environ.get("FOREX_REPORT_DIR", "reports/forex")

EXECUTE = os.environ.get("FOREX_EXECUTE", "no").lower() in ("yes", "true", "1")
MAX_OPEN = int(os.environ.get("FOREX_MAX_OPEN", "2"))        # 最多同时持有几个仓位
MAX_PENDING = int(os.environ.get("FOREX_MAX_PENDING", "2"))  # 最多同时挂几张单
ORDER_EXPIRY_H = float(os.environ.get("FOREX_ORDER_EXPIRY_HOURS", "24"))


def load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def save(path, doc):
    with open(path, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def fingerprint(inst, plan, candle_time):
    """幂等指纹:品种 + 方案 + **那根K线的时间**。

    workflow 每 4 小时跑一次,但重跑、手动触发、并发都可能让同一份信号被处理
    两次。指纹带上 K 线时间,就保证「同一根 K 线上的同一个方案」只会下一次单。
    没有这个,一次重跑就是双倍仓位 —— 风险模型直接失效。
    """
    return f"{inst}|{plan}|{candle_time}"


def main():
    now = dt.datetime.now(dt.timezone.utc)
    sig = load(SIGNALS_FILE, None)
    state = load(STATE_FILE, {"orders": {}, "history": []})
    log = []

    def say(msg):
        log.append(msg)
        print(msg)

    if not sig:
        say(f"[forex-exec] 读不到 {SIGNALS_FILE},不动作")
        return 0

    say(f"[forex-exec] {'执行模式' if EXECUTE else 'DRY-RUN(不下单)'} · "
        f"信号时间 {sig.get('updated_at')} · 决策 {sig.get('decision')}")

    # ---- 前置闸门:任何一条不满足就不开新仓 --------------------------------
    if sig.get("error"):
        say(f"[gate] 信号文件带错误({sig['error']}),不动作")
        return 0
    if not sig.get("market_open"):
        say("[gate] 外汇休市,不开新仓")
        return 0
    if sig.get("blackouts"):
        names = ", ".join(b["name"] for b in sig["blackouts"])
        say(f"[gate] 事件封锁期({names}),不开新仓")
        return 0
    if sig.get("decision") != "enter":
        say("[gate] 决策=wait,没有可执行方案 —— 这是常态,不是故障")
        return 0

    # ---- 连券商 -----------------------------------------------------------
    try:
        import broker_oanda
        if not broker_oanda.OANDA_AVAILABLE:
            say("[gate] 未配置 OANDA_TOKEN / OANDA_ACCOUNT_ID,不动作")
            return 0
        broker = broker_oanda.OandaBroker()
        broker.connect()
    except Exception as e:
        say(f"[error] 连接 OANDA 失败: {e}")
        return 1

    try:
        acct = broker.account()
        positions = broker.positions()
        pending = broker.orders()
        say(f"[acct] {acct['status']} · 净值 ${acct['equity']} · "
            f"持仓 {len(positions)} · 挂单 {len(pending)}")

        # ---- 对账:挂单成交了 / 仓位平掉了,把状态收敛回来 ------------------
        live_ids = {o["id"] for o in pending}
        held = {p["symbol"] for p in positions}
        for fp, rec in list(state.get("orders", {}).items()):
            if rec.get("status") != "pending":
                continue
            if rec["order_id"] in live_ids:
                continue
            # 不在挂单列表里了。别靠「有没有持仓」来猜 —— 成交后又被止盈平掉的
            # 单子既不在挂单里也不在持仓里,那样会被误记成「到期未成交」。
            # 直接问券商这张单的真实状态。
            st = None
            try:
                st = broker.order_state(rec["order_id"])
            except Exception:
                pass
            if st == "FILLED":
                rec["status"] = "filled"
            elif st == "CANCELLED":
                rec["status"] = "expired"
            elif st == "PENDING":
                continue                      # 券商说还挂着,别改
            else:
                rec["status"] = "filled" if rec["instrument"] in held else "unknown"
            rec["closed_at"] = now.isoformat(timespec="seconds")
            say(f"[reconcile] {rec['instrument']} {rec['plan']} 挂单 "
                f"{rec['order_id']} -> {rec['status']}")

        open_count = len(positions)
        pending_count = len(pending)

        # ---- 下单 ---------------------------------------------------------
        placed = 0
        for pair in sig.get("pairs", []):
            inst = pair.get("instrument")
            candle = pair.get("last_candle_time")
            for plan in pair.get("plans", []):
                if plan.get("status") != "triggered":
                    continue

                fp = fingerprint(inst, plan["name"], candle)
                if fp in state.get("orders", {}):
                    say(f"[skip] {inst} {plan['name'][:12]} 这根K线已下过单(幂等)")
                    continue
                if inst in held:
                    say(f"[skip] {inst} 已有持仓,不加仓")
                    continue
                if open_count >= MAX_OPEN:
                    say(f"[skip] 持仓已达上限 {MAX_OPEN}")
                    continue
                if pending_count >= MAX_PENDING:
                    say(f"[skip] 挂单已达上限 {MAX_PENDING}")
                    continue

                units = plan.get("units") or 0
                if units <= 0:
                    say(f"[skip] {inst} {plan['name'][:12]} 单位数={units}"
                        f"({plan.get('units_error', '无法定量')})")
                    continue

                # 做空 = 负单位数。方向搞反是这里最贵的一个 bug。
                signed = units if plan["direction"] == "long" else -units
                entry, sl, tp = plan["entry"], plan["stop"], plan["tp1"]

                say(f"[order] {inst} {plan['name'][:14]} {plan['direction']} "
                    f"{signed}单位 @ {entry} SL={sl} TP1={tp} "
                    f"(风险 ${plan.get('actual_risk_usd', plan['risk_usd'])}, "
                    f"到TP1 = {plan['rr1']}R 全平)")

                if not EXECUTE:
                    say("         ^ DRY-RUN,没有真的下单")
                    continue

                try:
                    resp = broker.limit_bracket(inst, signed, entry, sl, tp,
                                                ORDER_EXPIRY_H)
                    oid = str((resp.get("orderCreateTransaction") or {}).get("id", "?"))
                    state.setdefault("orders", {})[fp] = {
                        "order_id": oid, "instrument": inst, "plan": plan["name"],
                        "direction": plan["direction"], "units": signed,
                        "entry": entry, "stop": sl, "tp1": tp,
                        "risk_usd": plan.get("actual_risk_usd", plan["risk_usd"]),
                        "placed_at": now.isoformat(timespec="seconds"),
                        "candle": candle, "status": "pending",
                    }
                    pending_count += 1
                    placed += 1
                    say(f"         ✅ 挂单成功 id={oid},{ORDER_EXPIRY_H}h 未成交自动撤销")
                except Exception as e:
                    say(f"         ❌ 挂单失败: {e}")

        say(f"[done] 新挂单 {placed} 张")

        state["updated_at"] = now.isoformat(timespec="seconds")
        state["equity"] = acct["equity"]
        save(STATE_FILE, state)

        os.makedirs(REPORT_DIR, exist_ok=True)
        stamp = now.strftime("%Y-%m-%d")
        with open(f"{REPORT_DIR}/{stamp}.md", "a") as f:
            f.write(f"\n## {now.isoformat(timespec='seconds')}\n\n")
            f.write("\n".join(f"- {l}" for l in log) + "\n")
    finally:
        broker.disconnect()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
