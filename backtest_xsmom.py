#!/usr/bin/env python3
"""横截面动量回测 + 买入持有对照 -> reports/xsmom.md。

**为什么换这个方向**:8 组参数扫描证明了 RSI/布林带/EMA 那套指标在加密上
毛利≈0——它对「接下来会涨还是会跌」没有预测力。继续调参数是在优化一个零。

横截面动量不预测涨跌,只做**排序**:每隔一段时间,把 8 个币按过去一段的
涨幅排名,买最强的 K 个,持有到下次调仓。它赌的是「强者恒强」这个在股票、
商品、外汇上被反复验证过的因子,而不是赌方向。

**必须带上的对照组**(我们一直缺这个):
  - 等权买入持有全部 8 个币
  - 单独买入持有 BTC
如果策略跑不赢「什么都不做」,它就是负价值——这个对照能立刻戳穿
「看起来在赚钱其实只是行情在涨」的假象。

⚠️ 诚实的先验:学术上的横截面动量是**多空**的(买最强、卖最弱),这样才中性。
   Alpaca 加密不能做空,所以这里只能做多头一半,等于「市场beta + 动量倾斜」。
   熊市里它一样亏——这不是 bug,是只能做多的结构性限制。
"""

import argparse
import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import backtest_crypto as BT       # noqa: E402  复用取数与重采样
import quotes_crypto as Q          # noqa: E402

REPORT = ROOT / "reports" / "xsmom.md"


def equity_curve_stats(curve: list) -> dict:
    """从净值曲线算总收益和最大回撤。最大回撤比收益更能说明能不能睡着觉。"""
    if not curve:
        return {"ret": 0.0, "mdd": 0.0}
    peak, mdd = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        mdd = max(mdd, (peak - v) / peak if peak else 0.0)
    return {"ret": (curve[-1] / curve[0] - 1) * 100, "mdd": mdd * 100}


def buy_and_hold(series: dict, book: float, fee: float) -> dict:
    """等权买入持有:开头买,结尾卖,中间不动。手续费只付一次往返。"""
    syms = list(series)
    per = book / len(syms)
    curve = []
    n = min(len(v) for v in series.values())
    for i in range(n):
        total = sum(per * (series[s][i] / series[s][0]) for s in syms)
        curve.append(total)
    end = curve[-1] * (1 - fee) - book * fee
    return {"final": end, "pnl": end - book, **equity_curve_stats(curve)}


def run_xsmom(series: dict, args) -> dict:
    """每 rebalance 根 K 线调一次仓,持有涨幅排名前 top_k 的币。"""
    syms = list(series)
    n = min(len(v) for v in series.values())
    cash = args.book
    holdings = {}                 # sym -> qty
    curve, rebalances, turnover = [], 0, 0.0

    for i in range(args.lookback, n - 1):
        # 估值(用当根收盘价)
        value = cash + sum(q * series[s][i] for s, q in holdings.items())
        curve.append(value)

        if (i - args.lookback) % args.rebalance:
            continue

        # 排名只用到第 i 根为止的数据,成交用第 i+1 根开盘 —— 不偷看未来
        scores = {}
        for s in syms:
            past = series[s][i - args.lookback]
            if past > 0:
                scores[s] = series[s][i] / past - 1.0
        if not scores:
            continue
        ranked = sorted(scores, key=scores.get, reverse=True)
        want = [s for s in ranked[:args.top_k] if scores[s] > args.min_mom]

        # 全部卖出再买入(简单但会高估换手成本,属于保守方向)
        for s, q in list(holdings.items()):
            px = series[s][i + 1]
            cash += q * px * (1 - args.fee)
            turnover += q * px
        holdings.clear()
        if want:
            per = cash / len(want)
            for s in want:
                px = series[s][i + 1]
                qty = (per / px) * (1 - args.fee)
                holdings[s] = qty
                cash -= per
                turnover += per
        rebalances += 1

    final = cash + sum(q * series[s][n - 1] for s, q in holdings.items())
    curve.append(final)
    return {"final": final, "pnl": final - args.book, "rebalances": rebalances,
            "turnover": turnover, **equity_curve_stats(curve)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--fee", type=float, default=0.0020)
    ap.add_argument("--book", type=float, default=200.0)
    ap.add_argument("--tf", type=int, default=12, help="12 = 1h bars")
    ap.add_argument("--top-k", type=int, default=2)
    ap.add_argument("--min-mom", type=float, default=0.0,
                    help="动量低于这个值就空仓(0 = 只要求为正)")
    args = ap.parse_args()

    raw, errors = {}, {}
    for sym in Q.WATCHLIST:
        try:
            bars = BT.resample(BT.fetch_bars(sym, args.days), args.tf)
            if len(bars) < 100:
                errors[sym] = f"only {len(bars)} bars"
                continue
            raw[sym] = [b["c"] for b in bars]
        except Exception as e:
            errors[sym] = str(e)[:100]
    if len(raw) < 3:
        print("not enough data:", errors)
        return 1
    n = min(len(v) for v in raw.values())
    series = {s: v[:n] for s, v in raw.items()}

    lines = ["# 横截面动量回测（含买入持有对照）", "",
             f"生成于 {dt.datetime.utcnow().isoformat(timespec='seconds')}Z",
             f"{len(series)} 个币 · {n} 根 {5*args.tf} 分钟 K 线 · "
             f"手续费 {args.fee*100:.2f}%/边 · 本金 ${args.book:.0f}", ""]
    if errors:
        lines += ["> ⚠️ 取数失败：" + "；".join(f"{k}({v})" for k, v in errors.items()), ""]

    bh = buy_and_hold(series, args.book, args.fee)
    btc = (buy_and_hold({"BTC": series["BTC"]}, args.book, args.fee)
           if "BTC" in series else None)

    lines += ["| 策略 | 期末 | 盈亏 | 收益率 | 最大回撤 | 调仓次数 |",
              "|---|---:|---:|---:|---:|---:|",
              f"| **等权买入持有（对照）** | ${bh['final']:.2f} | ${bh['pnl']:+.2f} | "
              f"{bh['ret']:+.1f}% | {bh['mdd']:.1f}% | 1 |"]
    if btc:
        lines.append(f"| **只买 BTC 持有（对照）** | ${btc['final']:.2f} | ${btc['pnl']:+.2f} | "
                     f"{btc['ret']:+.1f}% | {btc['mdd']:.1f}% | 1 |")

    results = []
    for lb, rb in [(24, 24), (48, 24), (72, 24), (168, 24), (168, 168)]:
        args.lookback, args.rebalance = lb, rb
        if lb + 10 >= n:
            continue
        r = run_xsmom(series, args)
        results.append(((lb, rb), r))
        lines.append(f"| 动量 回看{lb}根/调仓{rb}根 | ${r['final']:.2f} | ${r['pnl']:+.2f} | "
                     f"{r['ret']:+.1f}% | {r['mdd']:.1f}% | {r['rebalances']} |")
    lines.append("")

    if results:
        best = max(results, key=lambda kv: kv[1]["pnl"])
        beat_bh = best[1]["pnl"] > bh["pnl"]
        beat_btc = (best[1]["pnl"] > btc["pnl"]) if btc else True
        lines += ["## 结论", ""]
        lines.append(f"- 最好的动量配置：回看 {best[0][0]} 根 / 调仓 {best[0][1]} 根，"
                     f"盈亏 ${best[1]['pnl']:+.2f}")
        if beat_bh and beat_btc:
            lines += ["", "- **跑赢了两个对照组。** 这是目前为止第一个值得继续往下看的结果，"
                      "但仍需在另一段时间窗上验证——一次胜出可能只是这段行情恰好合适。"]
        else:
            worse = []
            if not beat_bh:
                worse.append(f"等权买入持有（${bh['pnl']:+.2f}）")
            if btc and not beat_btc:
                worse.append(f"只买 BTC（${btc['pnl']:+.2f}）")
            lines += ["", f"- **跑输了{'、'.join(worse)}。**", "",
                      "  也就是说：这套主动交易还不如什么都不做。所有的调仓、手续费、"
                      "复杂度都是在做负贡献。"]
        lines += ["", "> ⚠️ 只做多的横截面动量 = 市场beta + 动量倾斜，"
                  "行情整体下跌时它一定亏。学术上的动量因子是多空对冲的，"
                  "而 Alpaca 加密不能做空，这一半的结构性限制去不掉。", ""]

    text = "\n".join(lines)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8")
    print(text)
    print(f"\nwrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
