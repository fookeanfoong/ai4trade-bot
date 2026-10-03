# CryptoEmaMacdScalper（M5 EMA + MACD 动量剥头皮 EA）

`CryptoEmaMacdScalper.mq5` 把「EMA + MACD 动量剥头皮系统」逐条翻译成 MT5 EA，没有加系统以外的指标。

## 规则 → 代码对照

| 规则 | 实现 | 相关参数 |
|---|---|---|
| L1/S1 EMA20 上穿/下穿 EMA50，当前仍在同侧 | 最近一次交叉方向正确，发生在最近 N 根内，且第 1 根收盘时 EMA20 仍在 EMA50 同侧 | `InpEmaCrossLookback=12` |
| L2/S2 MACD 线穿越信号线，柱转绿/红 | 最近 N 根内出现同向交叉，且柱（MACD − 信号）> 0 / < 0 | `InpMacdCrossLookback=3` |
| L3/S3 回踩/反弹至 EMA20 或 EMA50，并出现吞没、锤子线或射击之星 | 信号 K 的最低价（做空用最高价）落在 EMA ± 容差内，收盘不破 EMA50，且形态成立 | `InpTouchTolPct=0.10`、`InpWickRatio=2.0` |
| L4/S4 放量（S4 要求阴线） | 信号 K 成交量 ≥ 前 20 根均量 × 1.5 | `InpVolAvgBars`、`InpVolMult` |
| 收盘确认后入场 | 新 K 线出现后，用已收盘的第 1 根判断，然后市价入场 | — |
| 止损放在摆动点外 | 最近 10 根的最低/最高点 ± 缓冲（取点差和 0.05% 价格中较大的） | `InpSwingLookback`、`InpSLBufferPct` |
| 1.5R / 2R 两个目标 | 对冲账户拆成两单，各挂一个 TP；净额账户挂 2R，到 1.5R 时由 EA 平掉一半 | `InpTP1R`、`InpTP2R` |
| 强趋势时止损跟随 EMA20 | 连续 5 根收在 EMA20 同侧，止损移到 EMA20 ± 缓冲，只往有利方向移 | `InpTrailEMA20`、`InpTrendBars` |
| 风险 1–2% | 手数 = 净值 × 风险% ÷ 止损距离，硬上限 2%；最小手数下风险超标就拒单 | `InpRiskPercent`、`InpMaxRiskPercent` |
| 只做前 10 大币种 | 品种名不在白名单内，EA 拒绝加载 | `InpWhitelist` |
| 新闻前后不交易 | 用 MT5 经济日历屏蔽 USD 高影响事件前后 30 分钟；ETF 公告等日历没有的事件，手填 `InpManualNews` | `InpUseCalendar` 等 |
| 横盘缠绕不交易 | 最近 36 根内 EMA 交叉超过 1 次即放弃 | `InpChopLookback`、`InpMaxCrossesInChop` |
| 禁止过度交易 | 同一次 EMA 交叉只交易一次；同时只持有一组仓位；当日亏损 4% 熔断 | `InpOneTradePerCross`、`InpDailyLossPct` |

图表左上角会实时显示 L1–L4、S1–S4 的检查表（`[OK]`/`[X]` 加具体数值），格式和人工分析时一样。

## 安装

1. 把 `CryptoEmaMacdScalper.mq5` 复制到 MT5 的 `文件 → 打开数据文件夹 → MQL5/Experts/`
2. 在 MetaEditor 里打开并编译（F7）
3. 打开 BTCUSD（或券商对应的名字）的 **M5** 图表，把 EA 拖上去，勾选「允许算法交易」
4. 想收手机推送：在 `工具 → 选项 → 通知` 里填 MetaQuotes ID

## 上实盘前必须做

- **先回测，再模拟盘。** 四个条件同时满足的情况很少，可能连续几天不出单，这是正常的。在策略测试器里选「每个 tick 基于真实 tick」，跑 BTCUSD M5 至少 3 个月。测试器里没有经济日历，新闻过滤只对 `InpManualNews` 生效。
- **点差。** BTC CFD 的点差因券商而异，差别很大。`InpMaxSpreadPct=0.06%` 在 $60k 时约等于 $36，请按你券商的实际点差调整。
- **最小手数。** 账户小的话，最小手数（比如 0.01 BTC）下的风险可能超过 2%，EA 会拒单并在日志里写明原因。
- **成交量。** 多数 CFD 券商只提供 tick 成交量，所以默认用 tick 成交量；券商有真实成交量时，可以设 `InpUseRealVolume=true`。

研究和学习用途，不构成投资建议。
