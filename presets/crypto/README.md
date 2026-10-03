# 加密货币 EA preset（CryptoEmaMacdScalper）

这里放 CryptoEmaMacdScalper EA 的 preset（`.set` 文件）。用法和 `presets/gold/` 一样。
`install_crypto_ea.bat` 会把这两个文件分别复制成 `CryptoEmaMacd_default.set` 和 `CryptoEmaMacd_defensive.set`，放进 MT5 的 `MQL5\Presets` 文件夹。

> ⚠️ 和黄金不同：这两套参数**还没有回测验证过**。`default` 只是把系统规则原样写成参数，并不代表它能赚钱。

## 有哪些 preset

| 文件 | 内容 | 什么时候用 |
|------|--------|-----------|
| `default.set` | M5 · EMA20/50 · MACD(12,26,9) · 放量 1.5 倍 · 目标 1.5R/2R · 风险 1% | 回测和正常运行。等于 EA 的出厂参数 |
| `defensive.set` | 风险 0.5% · 当日亏 2% 熔断 · 放量要求 2 倍 · 点差和止损过滤更严 · 新闻前后各 60 分钟不交易 | 刚上模拟盘、监测器报 `RETHINK`，或碰上大新闻周 |

## 监测器结论对应的操作

`run_crypto_monitor.bat` 复用了黄金的监测器（`mt5_bridge.py` / `gold_health.py`），只统计 magic 为 20261003 的单。
报告里有些文字写着「黄金」，那是复用代码留下的，判断逻辑本身是通用的。

| 结论 | 该做什么 |
|------|---------|
| `ACCUMULATE` | 样本不到 20 笔，什么都别动 |
| `OK` / `WATCH` | 保持当前 preset，**别调参数** |
| `RETHINK` | 换成 `defensive.set`，或者重新审视入场逻辑 |
| `HALT` | **卸下 EA**，回到研究阶段 |

对冲账户里，一个信号会开两单（一单 1.5R、一单 2R），监测器会把它们算成 2 笔。

## 在 MT5 里加载 preset

EA 属性 → **输入** → **加载** → 选择 `CryptoEmaMacd_default.set` → 确定。

*仅供研究和学习，不构成投资建议。加密货币杠杆交易可能亏掉全部本金。*
