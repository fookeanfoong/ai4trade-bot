# 在 MT5 上运行加密货币 EA（CryptoEmaMacdScalper）

M5 周期的「EMA + MACD 动量剥头皮」EA，只做 BTC、ETH、SOL 等前 10 大币种。规则说明见
[`mql5/CryptoEmaMacdScalper.md`](mql5/CryptoEmaMacdScalper.md)，参数预设见 [`presets/crypto/`](presets/crypto/README.md)。

## ⚡ 一行命令（推荐，和黄金一样）

PowerShell 里粘贴运行（先关掉 MetaEditor 里打开的这个 EA）：

```powershell
irm "https://raw.githubusercontent.com/fookeanfoong/ai4trade-bot/claude/epic-hawking-tl5tac/mql5/update_crypto_mt5.ps1" | iex
```

然后在 MetaEditor 里按 F7 编译（应显示 0 errors）→ 挂到 BTCUSD M5 图表 → 加载 `CryptoEmaMacd_default.set`。

回测报告：`reports/crypto_scalper_backtest.md`（由 GitHub Actions 用币安真实 M5 数据生成）。

## ⚡ 一键版（要先下载整个仓库）

先下载整个仓库（`git clone`，或在 GitHub 上点 `Code → Download ZIP` 后解压），然后：

1. **打开 MT5 并登录**（至少打开过一次，数据文件夹才会生成）
2. **双击 `install_crypto_ea.bat`**，它会自动：
   - 找到你电脑上所有 MT5 终端
   - 把 EA 复制到 `MQL5\Experts`
   - 把 preset 复制到 `MQL5\Presets`
   - 调用 MetaEditor 编译。编译失败会打印日志，截图发给我
3. MT5 导航器里右键「EA 交易」→ 刷新，然后打开 **BTCUSD 的 M5 图表**，把 EA 拖上去，在「输入」里加载 `CryptoEmaMacd_default.set`
4. 确认工具栏的「算法交易」是绿色的，图表左上角会出现 L1–L4 / S1–S4 检查表
5. （可选）装监测器：
   - 先装 Python，双击 `install_mt5_monitor.bat`（和黄金共用）
   - 双击 `run_crypto_monitor.bat` 试运行一次
   - 右键 `schedule_crypto_monitor.bat` → 以管理员身份运行，设成每 30 分钟自动跑一次
   - Telegram 推送沿用 `monitor_config.bat` 里的设置

## 上实盘前必须做

- **先回测**：在策略测试器里选「每个 tick 基于真实 tick」，用 BTCUSD M5 跑至少 3 个月。测试器里没有经济日历，新闻过滤只对 `InpManualNews` 生效。
- **再上模拟盘**，攒到 20 笔以上再看监测器的结论。
- **点差**：BTC CFD 的点差各家券商差别很大，按你券商的实际点差调整 `InpMaxSpreadPct`。
- **最小手数**：账户小的话，最小手数下的风险可能超过 2%，这时 EA 会拒单，并在日志里写明原因。
- **ETF、监管类公告**不在 MT5 经济日历里，需要手动填进 `InpManualNews`，格式为 `2026.10.15 12:30;...`（服务器时间）。

## 文件一览

| 文件 | 作用 |
|---|---|
| `mql5/CryptoEmaMacdScalper.mq5` | EA 本体 |
| `presets/crypto/*.set` | 参数预设 |
| `mql5/update_crypto_mt5.ps1` | **一行命令安装/更新**(见上方 irm 命令),同黄金的 update_mt5.ps1 |
| `install_crypto_ea.bat` | 一键安装 + 编译(需要整个仓库) |
| `install_crypto_ea.ps1` | **单文件**安装脚本(Windows PowerShell),EA 源码内嵌,不需要仓库 |
| `install_crypto_ea.sh` | **单文件**安装脚本(Mac/Linux + Wine),EA 源码内嵌 |
| `run_crypto_monitor.bat` | 手动运行一次监测器 |
| `schedule_crypto_monitor.bat` | 设置每 30 分钟自动运行（任务名 `CryptoEA_Monitor`） |
| `crypto_monitor_config.bat` | 监测器参数（magic、品种、输出文件） |

*仅供研究和学习，不构成投资建议。加密货币杠杆交易可能亏掉全部本金。*
