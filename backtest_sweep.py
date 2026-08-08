#!/usr/bin/env python3
"""一次抓数,跑多组配置对比 -> reports/sweep.md。

单次回测只能回答「当前这套行不行」。要回答「怎么改才行」,需要在**同一段行情**上
并排比较多个变体——不同周期、开关信号失效离场等等。

行情只抓一次,所有配置共用,所以差异全部来自配置本身,不来自数据。

⚠️ 这是参数搜索,天然带过拟合风险:在同一段两个月的数据上试得越多,
   越容易挑到一个「碰巧好看」的组合。所以报告里明确标注:
   - 只有当某个变体**大幅**优于其他,才值得当成发现,而不是排行榜第一名;
   - 毛利(扣费前)是否为正,比净利更能说明「有没有方向性优势」——
     净利可以靠减少交易次数来改善,毛利不行。
"""

import argparse
import datetime as dt
import importlib
import math
import os
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import backtest_crypto as BT      # noqa: E402
import quotes_crypto as Q         # noqa: E402

REPORT = ROOT / "reports" / "sweep.md"

# 每个变体:(名字, 回测参数, 信号层门槛覆盖)。刻意保持少而有针对性——
# 组合爆炸只会让过拟合更严重。
#
# 「激进」不是一个刻度,而是几件不同的事:允许横盘入场、不要求成交量、
# 容忍更高的 RSI/%B(敢追)、多开几个仓。分开测才知道哪一项值得放宽、
# 哪一项一放就亏——合在一起调,只会得到一个说不清为什么的数字。
BASE_1H = dict(tf=12, no_signal_exit=True)      # 目前实盘在用的配置
VARIANTS = [
    ("① 当前实盘(1h,不用信号失效离场)", BASE_1H, {}),
    ("② +允许横盘入场",                 BASE_1H, {"ALLOW_FLAT_TREND": "yes"}),
    ("③ +不要求成交量",                 BASE_1H, {"MIN_VOL_RATIO": "0"}),
    # 完全不看量明确有害(毛利 -$18.23),但 1.0 也挡掉了 8 个币里的 4 个。
    # 中间档没测过 —— 先放进扫描,别靠猜。
    ("③b 量比门槛降到 0.8",             BASE_1H, {"MIN_VOL_RATIO": "0.8"}),
    ("③c 量比门槛降到 0.6",             BASE_1H, {"MIN_VOL_RATIO": "0.6"}),
    ("④ +敢追高(RSI 85/%B 0.98)",       BASE_1H, {"RSI_OVERBOUGHT": "85", "PCTB_OVERBOUGHT": "0.98"}),
    ("⑤ +空间门槛降到 0.8%",            BASE_1H, {"MIN_TARGET_ROOM": "0.008"}),
    ("⑥ 全部放宽(最激进)",              BASE_1H, {"ALLOW_FLAT_TREND": "yes", "MIN_VOL_RATIO": "0",
                                                  "RSI_OVERBOUGHT": "85", "PCTB_OVERBOUGHT": "0.98",
                                                  "MIN_TARGET_ROOM": "0.008"}),
    ("⑦ 全部放宽 + 5m(最快最激进)",     dict(tf=1, no_signal_exit=True),
                                        {"ALLOW_FLAT_TREND": "yes", "MIN_VOL_RATIO": "0",
                                         "RSI_OVERBOUGHT": "85", "PCTB_OVERBOUGHT": "0.98",
                                         "MIN_TARGET_ROOM": "0.008"}),
]


def base_args(a) -> SimpleNamespace:
    return SimpleNamespace(fee=a.fee, book=a.book, names=a.names,
                           floor_usd=a.floor_usd, giveback=a.giveback,
                           min_hold=a.min_hold, min_rr=1.0, max_move=0.035,
                           tf=1, no_signal_exit=False, label="")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--fee", type=float, default=0.0020)
    ap.add_argument("--book", type=float, default=200.0)
    ap.add_argument("--names", type=int, default=2)
    ap.add_argument("--floor-usd", type=float, default=0.50)
    ap.add_argument("--giveback", type=float, default=0.006)
    ap.add_argument("--min-hold", type=float, default=20.0)
    a = ap.parse_args()

    raw, errors = {}, {}
    for sym in Q.WATCHLIST:
        try:
            bars = BT.fetch_bars(sym, a.days)
            if len(bars) < 200:
                errors[sym] = f"only {len(bars)} bars"
                continue
            raw[sym] = bars
        except Exception as e:
            errors[sym] = str(e)[:100]
    if not raw:
        print("no data fetched:", errors)
        return 1

    span = next(iter(raw.values()))
    lines = ["# 回测对比（同一段行情，多组配置）", "",
             f"生成于 {dt.datetime.utcnow().isoformat(timespec='seconds')}Z",
             f"数据 {dt.datetime.utcfromtimestamp(span[0]['t']).strftime('%Y-%m-%d')} ~ "
             f"{dt.datetime.utcfromtimestamp(span[-1]['t']).strftime('%Y-%m-%d')}"
             f"，{len(raw)} 个币，每个 {len(span)} 根 5m K 线",
             f"手续费 {a.fee*100:.2f}%/边 · 本金 ${a.book:.0f} · {a.names} 个仓 · "
             f"保底 ${a.floor_usd:.2f}", ""]
    if errors:
        lines += ["> ⚠️ 取数失败：" + "；".join(f"{k}({v})" for k, v in errors.items()), ""]

    lines += ["| 配置 | 笔数 | 毛利 | 手续费 | **净利** | 胜率 | 期望值/笔 ± 95%区间 |",
              "|---|---:|---:|---:|---:|---:|---:|"]

    results = []
    for name, over, gates in VARIANTS:
        args = base_args(a)
        for k, v in over.items():
            setattr(args, k, v)
        # 信号层门槛靠环境变量 + reload 生效,这样回测走的仍然是实盘那份代码,
        # 而不是回测里另写一套判定。
        for k in ("ALLOW_FLAT_TREND", "MIN_VOL_RATIO", "RSI_OVERBOUGHT",
                  "PCTB_OVERBOUGHT", "MIN_TARGET_ROOM", "RSI_MOMO_MIN"):
            os.environ.pop(k, None)
        os.environ.update(gates)
        importlib.reload(BT.G)
        trades = []
        for sym, bars in raw.items():
            trades += BT.simulate(sym, BT.resample(bars, args.tf), args)
        if not trades:
            lines.append(f"| {name} | 0 | — | — | — | — | 一笔未开 |")
            results.append((name, 0, 0.0, 0.0, 0.0))
            continue
        n = len(trades)
        gross = sum(t["gross"] for t in trades)
        fees = sum(t["fees"] for t in trades)
        net = sum(t["net"] for t in trades)
        wr = sum(1 for t in trades if t["net"] > 0) / n * 100
        # 单笔盈亏波动很大,所以「期望值」本身带着不小的不确定性。
        # 标准误 = 单笔标准差 / sqrt(笔数);95% 区间约为 ±1.96 个标准误。
        # 不给出这个区间,就会把 286 笔上 +$2.36 的毛利当成发现——
        # 那其实每笔不到一分钱,完全落在噪音里。
        nets = [t["net"] for t in trades]
        sd = statistics.stdev(nets) if n > 1 else 0.0
        se = sd / math.sqrt(n) if n else 0.0
        ci = 1.96 * se
        lines.append(f"| {name} | {n} | ${gross:+.2f} | ${fees:.2f} | "
                     f"**${net:+.2f}** | {wr:.0f}% | ${net/n:+.4f} ± {ci:.4f} |")
        results.append((name, n, gross, fees, net, net / n, se))

    lines.append("")
    scored = [r for r in results if r[1] > 0]
    if scored:
        base = scored[0]                      # 第一个变体固定是「当前实盘配置」
        best = max(scored, key=lambda r: r[5])
        lines += ["## 结论", ""]

        # 「最好的」和「当前的」之间的差,有没有超出噪音?
        # 两个独立均值之差的标准误 = sqrt(se1^2 + se2^2)。
        diff = best[5] - base[5]
        diff_se = math.sqrt(best[6] ** 2 + base[6] ** 2)
        significant = abs(diff) > 1.96 * diff_se and diff > 0
        lines += [f"- 期望值最高：**{best[0]}**（${best[5]:+.4f}/笔）",
                  f"- 当前实盘：{base[0]}（${base[5]:+.4f}/笔）",
                  f"- 差距 ${diff:+.4f}/笔，噪音幅度 ±${1.96*diff_se:.4f}/笔", ""]
        if significant:
            lines += ["**这个差距超出了噪音范围，值得采用。**", ""]
        else:
            lines += ["**这个差距落在噪音范围内 —— 不要据此改配置。**", "",
                      "  在同一段数据上试多个组合，总会有一个排第一。排第一不等于更好；"
                      "  只有差距大到噪音解释不了，才算发现。换一段行情，"
                      "  「赢家」很可能就换人了。", ""]

        pos_gross = [r for r in scored if r[2] > 0]
        if pos_gross:
            names = "、".join(f"{r[0]}（毛利 ${r[2]:+.2f}，{r[1]} 笔）" for r in pos_gross)
            lines += [f"- 毛利为正：{names}", "",
                      "  毛利为正才说明信号对方向有预测力。但要看**每笔多少**："
                      "  几百笔上只赚一两块，等于每笔一分钱，和零没有区别。", ""]
        else:
            lines += ["- **没有任何一个配置的毛利为正。**", "",
                      "  也就是说：这些调整都改变不了「信号对方向没有预测力」这个事实。"
                      "  手续费只是让亏损更快，不是亏损的原因。", ""]

    text = "\n".join(lines)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
