# 在你自己的电脑上跑「Binance ETH 交易机器人」(先测试网 demo)

这套东西在**你自己的电脑上**盯着 ETH,按现有的做多 scalping 策略自动在 **Binance 现货**买卖。
**窗口开着就交易,关掉就停** —— 电脑关机时它不下单。先用**测试网(假钱)**跑通,再谈真钱。

## 先把话说清楚(很重要)

- **默认是测试网(Spot Testnet),假钱,零风险。** 用来验证「拿数据 → 生成信号 → 下单」整条链路跑得通。
- **是那段代码在盯盘,不是我本人。** 它每 15 分钟拉一次真实 ETH 行情、算指标、决定买卖。你把窗口关了,它就停了。
- **⚠️ 持仓只有在程序运行时才有止损保护。** 现在的止损是「程序每轮检查价格、跌破就发市价平仓」——**止损靠程序在跑才生效**。所以:
  **关电脑前,先确认程序已经停、并且手里没有未平仓的 ETH。** 每一轮和退出时,窗口都会打印当前持仓;想一键清仓见文末「关机前必做」。
- **只做多、无杠杆(现货)。** 和云端那个 Alpaca crypto 盘一样的逻辑,换成 Binance 而已,策略一行没改。
- **价格永远取真实市场价**(api.binance.com),即使在测试网。因为信号是按真实行情算的,止损/止盈也必须盯真实行情;测试网只负责「假装成交」。所以测试网里的盈亏数字只说明「下单通了」,不代表真实收益。

---

## ⚡ 懒人版(5 步)

1. 拿测试网 key(第一步)
2. 装 Python + 依赖(第二步)
3. 把 `binance_keys.example.bat` 复制成 `binance_keys.bat`,填进你的 key(第三步)
4. 先空跑一次看逻辑:命令行里 `python run_binance_local.py --dry-run --once`
5. 正式跑测试网:**双击 `run_binance.bat`**,窗口别关

下面是每一步的详细说明。

---

## 一、拿 Binance 测试网 API key(约 2 分钟)

1. 打开 **https://testnet.binance.vision/**(这是币安**现货测试网**,不是真交易所)。
2. 点 **Log In with GitHub**,用你的 GitHub 账号登录。
3. 登录后点 **Generate HMAC_SHA256 Key**。
4. 页面会给你 **API Key** 和 **Secret Key**。**Secret 只显示这一次**,马上复制保存好。
5. 测试网账户自带一堆假币(假的 USDT/ETH/BTC 等),不用充值。

> 注意:币安**会不定期清空测试网**(余额和 key 都可能被重置)。如果哪天连不上或余额没了,回这个网站**重新生成 key**、并删掉本地的 `binance_baseline.json` 重来即可。

## 二、装 Python 和依赖(约 3 分钟,只做一次)

1. 到 python.org 下载 **Python 3.11+**,安装时**务必勾选「Add Python to PATH」**。
2. 装完打开命令提示符(cmd),`python --version` 能看到版本号即可。
3. 进到本项目文件夹装依赖:
   ```
   cd C:\ai4trade-bot
   pip install -r requirements-binance.txt
   ```
   (双击 `run_binance.bat` 时它也会自动帮你装,这步可跳过。)

## 三、填入你的 key

1. 把 **`binance_keys.example.bat`** 复制一份,改名为 **`binance_keys.bat`**。
2. 用记事本打开 `binance_keys.bat`,把你第一步拿到的 key 填进去:
   ```
   set BINANCE_API_KEY=你的测试网APIKey
   set BINANCE_API_SECRET=你的测试网Secret
   set BINANCE_PAPER=true
   ```
3. 保存。`binance_keys.bat` 已被 `.gitignore` 排除,**不会被提交、不会泄露**。

> 不用 Windows?在 Mac/Linux 的终端里 `export BINANCE_API_KEY=...`、`export BINANCE_API_SECRET=...`、`export BINANCE_PAPER=true` 即可,见文末。

## 四、先空跑一次(不下单,先看逻辑)

在项目文件夹里:
```
python run_binance_local.py --dry-run --once
```
你会看到它依次:拉 ETH/BTC 行情 → 生成信号 → 「[DRY] ...」打印它**本来会下的单**,但不真的下。确认没报错就行。

## 五、正式跑测试网

**双击 `run_binance.bat`**(或命令行 `python run_binance_local.py`)。
- 第一次会自动做一次「基线快照」:把你测试网账户现有的假币记下来,**这些预置的币永远不会被机器人当成持仓卖掉**,它只买卖自己新开的仓。
- 之后它每 **15 分钟**跑一轮。**这个窗口开着,它就一直交易;关掉窗口 = 停。**
- 想改频率:`python run_binance_local.py --interval 5`(每 5 分钟)。

就这样。下面是日常使用。

---

## 六、怎么看 / 怎么停

- **看**:每轮结论打印在窗口里;详细报告在 `reports/live_trader_binance/` 里按日期存;持仓账本是 `live_trader_binance_state.json`。测试网订单也能在 testnet.binance.vision 网页上看到。
- **停**:关掉窗口,或在窗口里按 **Ctrl+C**。停了就不再下任何单。

## 七、关机前必做 ⚠️

因为止损靠程序在跑才生效,**关电脑前**请:
1. 先停掉运行器(关窗口 / Ctrl+C);
2. 确认手里**没有未平仓的 ETH**。不确定就跑一次一键清仓:
   ```
   python run_binance_local.py --flatten --once
   ```
   它会把机器人开的仓全部市价平掉(只平它自己开的,不动你别的币)。

> 想做到「关机也有止损保护 / 24 小时不间断」,那是下一步:开仓时在 Binance 挂一个**交易所端的止损单**(即使程序停了、电脑关了,交易所也会替你止损)。这需要改一点引擎,等你把测试网这套跑顺、确认靠谱了跟我说,我再帮你做。

## 八、上真钱(务必先在测试网跑够)

确认测试网跑顺、报告看得懂之后,再考虑真钱:

1. 到 **binance.com**(真交易所)你的账户里创建一个 **API key**,权限**只开「现货交易」,别开提现**;建议绑定 IP 白名单。
2. 编辑 `binance_keys.bat`,换成真实 key,并打开双保险:
   ```
   set BINANCE_API_KEY=你的真实APIKey
   set BINANCE_API_SECRET=你的真实Secret
   set BINANCE_PAPER=false
   set BINANCE_I_UNDERSTAND_REAL_MONEY=yes
   ```
   两个都设对了才会真下单,防止手滑。
3. **删掉旧的 `binance_baseline.json`**,让它对真账户重新快照一次(这样它只交易新开的仓,不碰你账户里已有的币)。
4. 用**小钱**先跑几天(比如把 `BOOK_EQUITY` 调小:`set BOOK_EQUITY=50`)。

> 你所在地区能不能用 binance.com、需不需要 KYC,请自行确认。美国用户是另一个站点(Binance.US),币种和接口都不同。

## 九、Mac / Linux 怎么跑

不用 `.bat`,直接在终端:
```
pip install -r requirements-binance.txt
export BINANCE_API_KEY=你的测试网APIKey
export BINANCE_API_SECRET=你的测试网Secret
export BINANCE_PAPER=true
python run_binance_local.py            # 循环跑,Ctrl+C 停
```

## 十、出问题排查

| 现象 | 多半原因 / 解决 |
|------|----------------|
| `Missing BINANCE_API_KEY ...` | key 没设。检查 `binance_keys.bat` 填了没、`run_binance.bat` 有没有 `call` 到它。 |
| `python-binance not installed` | 没装依赖。`pip install -r requirements-binance.txt`。 |
| `Timestamp for this request ...` | 电脑时钟不准。程序已自动对齐服务器时间;若仍报错,同步一下系统时间。 |
| `notional ... below Binance min` | 单子太小(低于交易所最小金额)。调大 `BOOK_EQUITY` 或减少同时持仓数。 |
| 连不上 / 余额消失 | 测试网被币安重置了。回 testnet.binance.vision 重新生成 key,删掉 `binance_baseline.json`。 |

---

*研究/学习用途,不构成投资建议。加密货币波动极大,杠杆或真钱交易可能损失全部本金。测试网跑得好不代表真钱能赚。*
