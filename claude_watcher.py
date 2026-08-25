#!/usr/bin/env python3
"""claude_watcher —— 让 Claude 在**事件发生时**看一眼 K 线，而不是一直看。

先说清楚这个程序为什么长这样：

Claude 不是常驻进程，做不到"一直盯盘"。能常驻的是这个 Python 程序。
它的分工是：

    这个程序      常驻，每分钟读一次盘，用**确定性规则**判断有没有值得问的事
    Claude API    只在触发时被调用一次，看一眼最近的K线，给一个有界的结论
    EA            实时执行与风控，完全不依赖上面两者

为什么不逐 tick 调 LLM：一次调用约 2~5 秒、按 token 计费。黄金一天几万个 tick，
既做不到也没意义 —— 而且真要逐 tick 判断的东西，本来就该写成 EA 里的规则。

Claude 能回的只有三件事，而且只能往"更保守"的方向：
    halt        暂停开新仓
    block_dir   禁止某个方向
    ok          什么都不做
它**不能**下单、不能改风险、不能碰真实账户开关。EA 那边还有一层钳位。

用法：
    pip install MetaTrader5 anthropic
    set ANTHROPIC_API_KEY=sk-ant-...
    python claude_watcher.py

要在 MT5 那边把 InpUseCommandFile 设为 true 才会生效。
"""
import os
import sys
import time
from datetime import datetime, timedelta, timezone

SYMBOL      = os.environ.get("SG_SYMBOL", "XAUUSD.sml")
POLL_SEC    = int(os.environ.get("SG_POLL_SEC", "60"))
CMD_TTL_MIN = int(os.environ.get("SG_CMD_TTL_MIN", "10"))
MODEL       = os.environ.get("SG_MODEL", "claude-sonnet-5")

# 冷却：同一类事件在这个时间内不重复问，避免刷 API 账单
COOLDOWN_SEC = int(os.environ.get("SG_COOLDOWN_SEC", "600"))


def mt5_connect():
    import MetaTrader5 as mt5
    if not mt5.initialize():
        sys.exit(f"MT5 连接失败: {mt5.last_error()}")
    return mt5


def files_dir(mt5):
    """MT5 的 Files 目录 —— EA 读指令文件的地方。"""
    info = mt5.terminal_info()
    return os.path.join(info.data_path, "MQL5", "Files")


def snapshot(mt5, bars=40):
    """给 Claude 看的东西：最近的K线 + 持仓 + 当日战绩。保持紧凑。"""
    import MetaTrader5 as m
    r5 = mt5.copy_rates_from_pos(SYMBOL, m.TIMEFRAME_M5, 0, bars)
    r1 = mt5.copy_rates_from_pos(SYMBOL, m.TIMEFRAME_M1, 0, bars)
    if r5 is None or r1 is None:
        return None

    def fmt(rates, label):
        out = [f"{label}（最新在最后，格式 时:分 O H L C）:"]
        for x in rates[-bars:]:
            t = datetime.fromtimestamp(int(x['time']), tz=timezone.utc)
            out.append(f"  {t:%H:%M} {x['open']:.2f} {x['high']:.2f} "
                       f"{x['low']:.2f} {x['close']:.2f}")
        return "\n".join(out)

    pos = mt5.positions_get(symbol=SYMBOL) or []
    poslines = [f"  {'BUY' if p.type == 0 else 'SELL'} {p.volume} @ {p.price_open:.2f} "
                f"SL {p.sl:.2f} 浮盈 ${p.profit:.2f}" for p in pos]

    tick = mt5.symbol_info_tick(SYMBOL)
    spread = (tick.ask - tick.bid) if tick else 0.0

    return (f"品种 {SYMBOL}  现价 {tick.bid:.2f}/{tick.ask:.2f}  点差 ${spread:.2f}\n\n"
            + fmt(r1, "M1") + "\n\n" + fmt(r5, "M5") + "\n\n"
            + ("当前持仓:\n" + "\n".join(poslines) if poslines else "当前无持仓"))


def should_ask(mt5, state):
    """确定性触发器 —— 决定"值不值得问 Claude"。这一层不用 LLM。"""
    import MetaTrader5 as m
    now = time.time()
    if now - state.get("last_ask", 0) < COOLDOWN_SEC:
        return None

    since = datetime.now(timezone.utc) - timedelta(hours=6)
    deals = mt5.history_deals_get(since, datetime.now(timezone.utc) + timedelta(hours=1)) or []
    closed = [d for d in deals if d.symbol == SYMBOL and d.entry == m.DEAL_ENTRY_OUT]

    # 触发 1：连亏
    streak = 0
    for d in reversed(closed):
        if d.profit < 0:
            streak += 1
        else:
            break
    if streak >= 3:
        return f"最近连续 {streak} 笔亏损"

    # 触发 2：近一小时净亏超过阈值
    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
    recent = [d.profit for d in closed if d.time >= hour_ago]
    if recent and sum(recent) < -10:
        return f"近一小时净亏 ${sum(recent):.2f}（{len(recent)} 笔）"

    # 触发 3：点差异常
    tick = mt5.symbol_info_tick(SYMBOL)
    if tick and (tick.ask - tick.bid) > 1.0:
        return f"点差异常 ${tick.ask - tick.bid:.2f}"

    return None


PROMPT = """你在看一个黄金(XAUUSD) M5 剥头皮 EA 的实时盘面。

触发原因：{reason}

{snap}

只回一行，格式必须是下面三种之一，不要解释、不要多余文字：
    ok
    halt|<不超过30字的理由>
    block_dir=-1|<理由>      （禁止做空）
    block_dir=1|<理由>       （禁止做多）

判断依据只看K线本身：最近的推进方向、是否正在反转、是否处在一段无方向的震荡里。
拿不准就回 ok —— 不确定时不干预，比乱干预好。"""


def ask_claude(reason, snap):
    from anthropic import Anthropic
    client = Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=100,
        messages=[{"role": "user",
                   "content": PROMPT.format(reason=reason, snap=snap)}])
    return msg.content[0].text.strip().splitlines()[0].strip()


def write_cmd(path, halt=False, block_dir=0, note=""):
    """写指令文件。expires 用**服务器时间**（EA 那边比的是 TimeCurrent）。"""
    import MetaTrader5 as mt5
    tick = mt5.symbol_info_tick(SYMBOL)
    server_now = datetime.fromtimestamp(tick.time, tz=timezone.utc)
    exp = server_now + timedelta(minutes=CMD_TTL_MIN)
    body = (f"# 由 claude_watcher.py 写入 {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"expires={exp:%Y.%m.%d %H:%M:%S}\n"
            f"halt={1 if halt else 0}\n"
            f"block_dir={block_dir}\n"
            f"note={note}\n")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="ascii", errors="replace") as f:
        f.write(body)
    os.replace(tmp, path)          # 原子替换，EA 不会读到写了一半的文件
    print(f"  -> 已写入指令 halt={halt} block_dir={block_dir} 有效至 {exp:%H:%M:%S}(服务器)")


def parse(reply):
    """把 Claude 的回复解析成有界指令。看不懂就当 ok —— 绝不猜。"""
    r = reply.strip().lower()
    if r.startswith("halt"):
        return True, 0, reply.split("|", 1)[-1][:60] if "|" in reply else "halt"
    if r.startswith("block_dir=-1"):
        return False, -1, reply.split("|", 1)[-1][:60] if "|" in reply else "no short"
    if r.startswith("block_dir=1"):
        return False, 1, reply.split("|", 1)[-1][:60] if "|" in reply else "no long"
    return False, 0, ""


def main():
    mt5 = mt5_connect()
    cmd_path = os.path.join(files_dir(mt5), "XAUUSD_ScalperGuard_cmd.txt")
    print(f"指令文件: {cmd_path}")
    print(f"轮询 {POLL_SEC}s | 冷却 {COOLDOWN_SEC}s | 指令有效期 {CMD_TTL_MIN} 分钟")
    print("MT5 那边记得把 InpUseCommandFile 设为 true。\n")

    state = {}
    while True:
        try:
            reason = should_ask(mt5, state)
            if reason:
                snap = snapshot(mt5)
                if snap:
                    print(f"[{datetime.now():%H:%M:%S}] 触发：{reason}")
                    reply = ask_claude(reason, snap)
                    print(f"  Claude: {reply}")
                    halt, bdir, note = parse(reply)
                    state["last_ask"] = time.time()
                    if halt or bdir:
                        write_cmd(cmd_path, halt, bdir, note)
                    else:
                        print("  -> ok，不干预")
        except KeyboardInterrupt:
            break
        except Exception as e:
            # 看盘程序不能因为一次异常就死掉 —— EA 那边不依赖它，但它自己要活着
            print(f"[{datetime.now():%H:%M:%S}] 异常（已忽略）：{e}")
        time.sleep(POLL_SEC)

    print("退出。")


if __name__ == "__main__":
    main()
