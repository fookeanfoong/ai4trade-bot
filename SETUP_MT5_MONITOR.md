# 在你自己的电脑上装「黄金 EA 监测器」

这套东西盯着你 MT5 里的黄金 EA(GoldScalper),判断策略还灵不灵,**不灵就提醒你换 preset**。

## 先把话说清楚(很重要)

- 这个监测器**跑在你自己的 Windows 电脑上**,不是在云端。因为读 MT5 的库(`MetaTrader5`)
  只能在装了 MT5 的 Windows 上、且 MT5 开着的时候用 —— 别人的服务器读不到你的 MT5。
- **电脑关机时**:EA 不交易、监测器不跑。但你已有持仓的**止损在券商服务器上依然有效**,
  不会失控。想做到真正 24 小时不间断,得把 MT5 装到一台**不关机的 VPS** 上(要花点钱),
  然后把下面的步骤在 VPS 上照做一遍。
- 默认是**提醒你手动换 preset**,不自动改 EA。全自动是第二步(见文末)。

---

## 一、准备(只做一次)

1. **MT5 已装好、已登录**你的账户(OANDA_Global-Demo 或你自己的账户)。
2. **黄金 EA 已挂在 XAUUSD 图表上**,左上角是笑脸,且工具栏「算法交易」是绿的。
3. **允许算法交易**:MT5 菜单 `工具 → 选项 → EA交易 →` 勾上「允许算法交易」。

## 二、装 Python(约 3 分钟)

1. 到 python.org 下载 Python 3.11+,安装时**务必勾选「Add Python to PATH」**。
2. 装完打开「命令提示符(cmd)」,输入 `python --version` 能看到版本号就行。

## 三、拿到这套代码

- 会用 git 的:`git clone https://github.com/fookeanfoong/ai4trade-bot.git`
- 不会的:在 GitHub 仓库页点 `Code → Download ZIP`,解压到比如 `C:\ai4trade-bot`。

然后在 cmd 里进到这个文件夹:
```
cd C:\ai4trade-bot
pip install MetaTrader5
```

## 四、开启手机推送(免费,强烈建议)

这样电脑开着、EA 出信号时,你**手机也能收到提醒**:

1. 手机装 **MetaTrader 5** App,登录同一个账户。
2. App 里 `设置 → 聊天与消息`,记下你的 **MetaQuotes ID**。
3. 电脑 MT5:`工具 → 选项 → 通知`,勾「启用推送通知」,填入手机的 MetaQuotes ID,测试一下。

> 这一步让 **EA 的交易提醒**推到手机。监测器自己的「换 preset 提醒」走下面的 Telegram(可选)。

## 五、(可选)让监测器把提醒推到手机 Telegram

不想配就跳过 —— 提醒会打印在窗口里,也会写进 `reports/gold_alert.txt`。想要手机收到:

1. 手机 Telegram 搜 `@BotFather` → 发 `/newbot` → 拿到一个 **token**。
2. 给你的新 bot 发一句话,然后浏览器打开
   `https://api.telegram.org/bot<你的token>/getUpdates`,里面的 `chat.id` 就是你的 **chat id**。
3. 运行前设两个环境变量(cmd 里):
   ```
   set TELEGRAM_TOKEN=你的token
   set TELEGRAM_CHAT_ID=你的chatid
   ```

## 六、先手动跑一次

MT5 开着,在 `C:\ai4trade-bot` 里:
```
python mt5_bridge.py
```
应该看到类似 `[mt5] 已连接 #12345 ...` 和一行结论(`ACCUMULATE / OK / WATCH / RETHINK / HALT`)。
- 结论和详细报告写在 `reports/gold_health.md`
- 需要动作时,提醒写在 `reports/gold_alert.txt`(并推到 Telegram,如已配)

> 没有 MT5 也想看逻辑?用假数据试:`python mt5_bridge.py --mock 某个journal.json`

## 七、让它每 30 分钟自动跑(Windows 任务计划程序)

1. 开始菜单搜「任务计划程序」→「创建基本任务」。
2. 触发器:选「每天」,之后在「属性 → 触发器 → 编辑」里勾「重复任务间隔 30 分钟,持续 1 天」。
3. 操作:「启动程序」
   - 程序:`python`
   - 参数:`mt5_bridge.py`
   - 起始于:`C:\ai4trade-bot`
4. 确定。以后只要电脑开着 + MT5 开着,它就自动盯。

---

## 八、收到提醒后怎么办

| 提醒 | 你做什么 |
|------|---------|
| `RETHINK` | 在 MT5 给 EA **加载 `presets/gold/defensive.set`**(EA属性→输入→加载),亏得慢一点继续攒样本。 |
| `HALT` | **把 EA 从图表上卸下**(拖走或右键删除)。别调参续命。持仓止损仍在券商生效。 |
| `OK` / `WATCH` / `ACCUMULATE` | 什么都不用做,保持现状。 |

preset 的说明见 `presets/gold/README.md`。

## 九、想做到「自己换」(全自动,第二步)

现在 EA 的参数是 MT5 的 `input`,不读外部文件,所以只能提醒你手动换。要全自动,需要:
1. 给 `GoldScalper.mq5` 加一段:`OnInit()` / 定时器里读一个 `preset.json`,把参数覆盖进去;
2. 让 `mt5_bridge.py` 在 `RETHINK` 时把对应 preset 写成 `preset.json`。

这一步要改 EA 并重新编译,风险也更高(自动改运行中的策略)。等你把上面这套跑顺、
确认提醒靠谱之后,跟我说一声,我再帮你做第二步。

*研究/学习用途,不构成投资建议。黄金杠杆交易可能损失全部本金。*
