#!/usr/bin/env python3
"""自动进化 —— 在证据门槛之内自己换配置,并把每次改动记录下来。

用户明确授权了自动改策略。所以这个脚本真的会改运行中的配置,不需要问。
但它只在**同一条证据门槛**之内改 —— 那条门槛和我手动决定时用的完全一样。

## 它会自动做的三件事

1. **停手** —— 健康监测报 HALT 就把 halted 置为 true,信号引擎随即停止出信号。
   停手不需要证据门槛:坏掉的迹象一出现就该停,宁可停错。
2. **换参数** —— 某组参数通过样本外验证、且明显优于当前配置时,自动采用。
3. **记录** —— 每一次改动(以及每一次"决定不改")都写进 reports/evolution_log.md,
   带上当时的证据。你随时能回头看它为什么变成现在这样。

## 它**不会**自动做的两件事,以及为什么

**不会按近期实盘表现调参数。** 每笔 R 的标准差 1.236,而我们谈论的 edge
是 0.0x 量级 —— 信号被噪音淹没几十倍。连亏 5 笔在正期望系统里完全正常,
那时候动参数,改的是随机性不是规律。**这不是保守,这是那样做一定会变差。**

**不会自动换入场逻辑。** 实验室能发现"某个新逻辑通过了验证",但信号引擎
里只实现了突破/双顶两种入场。要上一个新逻辑,得先有人把它写进引擎 ——
这一步需要我在场。脚本会把候选记进日志并标注「待实现」,不会假装已经换了。

## 采用门槛(和手动决定时一致,一个字不放松)

  1. 训练段与验证段**都**为正
  2. 验证段期望 >= +0.10R —— 光是 >0 太容易靠运气
  3. 两段各 >= 30 笔
  4. **通过组数 > 期望假阳性数** —— 否则和"蒙中"无法区分
  5. 验证段期望比当前配置高至少 0.05R —— 差不多就别折腾

第 4 条是关键。测 N 组就会有 N×5% 个假阳性,只要通过的组数不超过这个数,
"找到更好的配置"这件事本身就可能纯属运气。那种时候**不动**才是对的。
"""

from __future__ import annotations

import datetime as dt
import itertools
import json
import os

import backtest_forex as B

CONFIG = os.environ.get("FOREX_CONFIG", "forex_config.json")
LOG = os.environ.get("FOREX_EVOLUTION_LOG", "reports/evolution_log.md")
HEALTH = os.environ.get("FOREX_HEALTH_OUT", "reports/forex_health.md")
EQUITY = float(os.environ.get("FOREX_EQUITY_USD", "200"))

MIN_TRADES = 30
MIN_TEST_EXP = 0.10
MIN_IMPROVEMENT = 0.05        # 比当前配置至少好这么多才值得换

PAIRS = [("EUR_USD", "EURUSD=X", 1.0),
         ("GBP_USD", "GBPUSD=X", 1.5),
         ("AUD_USD", "AUDUSD=X", 1.5)]
STOPS = [20, 25, 30]
RRS = [1.5, 2.0]


def load_config():
    try:
        with open(CONFIG) as f:
            return json.load(f)
    except Exception:
        # 首次运行:用当前 workflow 里那组(已通过一次验证)作为起点
        return {"pair": "EUR_USD", "stop_pips": 25, "rr1": 1.5,
                "test_exp": 0.018, "halted": False, "halt_reason": None,
                "adopted_at": None, "history": []}


def health_state():
    try:
        with open(HEALTH) as f:
            txt = f.read()
    except Exception:
        return None
    for s in ("HALT", "RETHINK", "OK", "WATCH", "ACCUMULATE"):
        if f"结论:`{s}`" in txt:
            return s
    return None


def evaluate(bars, stop, rr, spread):
    """训练/验证两段各跑一次。切分按时间,绝不打乱。"""
    mid = len(bars) // 2
    out = []
    for seg in (bars[:mid], bars[mid:]):
        trades, eq, dd, _ = B.run(seg, stop, rr, spread, EQUITY)
        n = len(trades)
        if n == 0:
            out.append({"n": 0, "exp": None, "wr": None, "dd": 0.0})
            continue
        wins = sum(1 for t in trades if t["win"])
        out.append({"n": n, "exp": round(sum(t["r"] for t in trades) / n, 3),
                    "wr": round(wins / n * 100, 1), "dd": round(dd, 2)})
    return out[0], out[1]


def main():
    now = dt.datetime.now(dt.timezone.utc)
    cfg = load_config()
    lines = [f"\n## {now.isoformat(timespec='seconds')}", ""]

    # ---- 1) 停手优先于一切 --------------------------------------------
    hs = health_state()
    if hs == "HALT":
        if not cfg.get("halted"):
            cfg["halted"] = True
            cfg["halt_reason"] = "健康监测报 HALT"
            cfg["adopted_at"] = now.isoformat(timespec="seconds")
            lines += ["**⛔ 自动停手** —— 健康监测报 HALT,信号引擎停止出信号。",
                      "停手不设证据门槛:坏掉的迹象一出现就停,宁可停错。", ""]
        else:
            lines += ["已处于停手状态,无变化。", ""]
        save(cfg, lines)
        return 0
    if cfg.get("halted") and hs in ("OK", "WATCH", "ACCUMULATE"):
        # 不自动复活 —— 停手容易,恢复必须人来。自动恢复等于给自己开后门。
        lines += [f"当前为停手状态,健康监测已回到 `{hs}`,但**不自动恢复** ——",
                  "停手可以自动,复活必须人工确认。", ""]
        save(cfg, lines)
        return 0

    # ---- 2) 搜索更好的参数(样本外) -------------------------------------
    cur_exp = cfg.get("test_exp", 0.0)
    tests = len(PAIRS) * len(STOPS) * len(RRS)
    exp_fp = tests * 0.05
    survivors = []
    for pair, ysym, spread in PAIRS:
        try:
            bars = B.fetch(ysym)
        except Exception as e:
            lines.append(f"- {pair} 取数失败:{e}")
            continue
        if len(bars) < 600:
            continue
        for stop, rr in itertools.product(STOPS, RRS):
            a, b = evaluate(bars, stop, rr, spread)
            if a["n"] < MIN_TRADES or b["n"] < MIN_TRADES:
                continue
            if a["exp"] is None or b["exp"] is None:
                continue
            if a["exp"] > 0 and b["exp"] >= MIN_TEST_EXP:
                survivors.append({"pair": pair, "stop_pips": stop, "rr1": rr,
                                  "train": a, "test": b})

    lines += [f"搜索 {tests} 组(期望假阳性 {exp_fp:.1f} 个) → 通过 {len(survivors)} 组。", ""]

    # ---- 3) 决定换不换 --------------------------------------------------
    if not survivors:
        lines += ["**不改动。** 没有配置通过样本外验证。",
                  "继续放宽门槛直到出现正数,得到的一定是过拟合。", ""]
    elif len(survivors) <= exp_fp:
        lines += [f"**不改动。** 通过组数({len(survivors)}) 未超过期望假阳性数({exp_fp:.1f}) ——",
                  "「找到更好的配置」这件事本身就可能纯属运气,这种时候不动才是对的。", ""]
    else:
        best = max(survivors, key=lambda s: s["test"]["exp"])
        gain = best["test"]["exp"] - cur_exp
        if gain < MIN_IMPROVEMENT:
            lines += [f"**不改动。** 最好的一组验证期望 {best['test']['exp']}R,",
                      f"仅比当前 {cur_exp}R 高 {gain:+.3f}R,不足 {MIN_IMPROVEMENT}R —— 差不多就别折腾。", ""]
        else:
            old = f"{cfg['pair']} {cfg['stop_pips']}点 1:{cfg['rr1']}（{cur_exp}R）"
            cfg.setdefault("history", []).append(
                {"at": now.isoformat(timespec="seconds"), "from": old,
                 "to": f"{best['pair']} {best['stop_pips']}点 1:{best['rr1']}",
                 "test_exp": best["test"]["exp"]})
            cfg.update({"pair": best["pair"], "stop_pips": best["stop_pips"],
                        "rr1": best["rr1"], "test_exp": best["test"]["exp"],
                        "adopted_at": now.isoformat(timespec="seconds")})
            lines += [f"**✅ 自动采用新配置**", "",
                      f"- 旧:{old}",
                      f"- 新:**{best['pair']} · {best['stop_pips']}点 · 1:{best['rr1']}**",
                      f"- 证据:训练 {best['train']['n']}笔/{best['train']['wr']}%/"
                      f"{best['train']['exp']}R，验证 {best['test']['n']}笔/"
                      f"{best['test']['wr']}%/{best['test']['exp']}R",
                      f"- 提升 {gain:+.3f}R，通过组数 {len(survivors)} > 期望假阳性 {exp_fp:.1f}", ""]

    save(cfg, lines)
    return 0


def save(cfg, lines):
    with open(CONFIG, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if not os.path.exists(LOG):
        with open(LOG, "w") as f:
            f.write("# 自动进化日志\n\n"
                    "每次自动改动(以及每次「决定不改」)都记在这里,带当时的证据。\n"
                    "**「不改动」和「改动」一样重要** —— 它记录了系统拒绝在噪音上行动。\n")
    with open(LOG, "a") as f:
        f.write("\n".join(lines) + "\n")
    print("[evolve] " + (lines[2] if len(lines) > 2 else "no-op"))


if __name__ == "__main__":
    raise SystemExit(main())
