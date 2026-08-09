# 外汇模块(OANDA + EUR/USD H4)

给 **$200 本金** 的外汇信号引擎。和股票/加密两本账完全隔离:独立的 broker
适配器、独立的信号文件、独立的 workflow,不碰 `live_trader.py` 的任何状态。

> **它现在只生成信号,不下单。** 这是故意的 —— 先在模拟盘上跑够 20 笔,
> 你自己看过 `signals_forex.md` 的判断质量,再决定要不要接执行。

---

## 为什么必须是 OANDA(不是 MT5 随便找个券商)

这不是偏好问题,是数学问题。46 点止损,想把单笔风险控制在 1%($2):

| 平台 | 最小下单量 | 46 点止损实亏 | 占 $200 |
|---|---|---|---|
| 一般 MT4/MT5 券商 | 0.01 手 = $0.10/点 | **$4.60** | **2.3%** ❌ |
| OANDA(按单位) | 435 单位 = $0.0435/点 | **$2.00** | **1.0%** ✅ |

**在最小手数 0.01 的平台上,$200 本金根本无法执行 1% 风险。** 换平台是唯一解,
调参调不出来。OANDA 最小 1 单位,无最低入金。

---

## ⚠️ 必须是 fxTrade 账户,不是 MT4/MT5 账户

OANDA 有两套互不相通的账户体系,这是最容易踩的坑:

| | 账户号长相 | 能用 v20 API 吗 |
|---|---|---|
| **fxTrade / fxTrade Practice** | `101-011-1234567-001` | ✅ **本模块要的就是它** |
| MT4 / MT5(`webmt5-globaldemo…`) | `1715551949`(纯数字) | ❌ v20 API 看不到这个账户 |

v20 REST API 只服务 **v20 交易账户**。MT5 那套是独立的平台,没有 REST API ——
要驱动它得用 `MetaTrader5` Python 包,而那个包**必须**有一台 Windows 机器常开着
跑 MT5 桌面终端。GitHub Actions 是无头 Linux,跑不了,「你的电脑可以关机」这个
前提直接没了。

**所以:如果你手上是 MT5 demo,请另外去开一个 fxTrade Practice 账户。**
入口:[oanda.com](https://www.oanda.com) → Try Demo / 免费模拟账户
(注意选 **fxTrade**,不要选 MetaTrader)。

## 5 分钟接好

1. 开一个 **fxTrade Practice(模拟)** 账户 —— 免费、免入金。
2. 登录 fxTrade 网页版 → **My Services → Manage API Access** → 生成 Personal Access Token。
3. 拿到账户号,形如 `101-011-1234567-001`(开头是 `101-` = practice;`001-` = 真钱)。
4. 本仓库 → **Settings → Secrets and variables → Actions → New repository secret**,
   加两个:

   | Name | Value |
   |---|---|
   | `OANDA_TOKEN` | 上一步生成的 token |
   | `OANDA_ACCOUNT_ID` | `101-011-1234567-001` |

5. **Actions** 标签 → `forex-signals` → **Run workflow** 跑一次。

跑完仓库里会多出 `signals_forex.md`(给人看)和 `signals_forex.json`(给程序看)。

本地自检:

```bash
export OANDA_TOKEN=... OANDA_ACCOUNT_ID=...
python3 broker_oanda.py            # 打印账户/报价/点差,验证鉴权
python3 generate_signals_forex.py  # 生成信号
```

---

## 两套方案(代码里的规则)

### 方案 A · 顺势做多(突破回踩)
- **触发**:最近一根**已收盘** H4 收在阻力上方(缓冲 = max(2 pips, 0.15×ATR))
- **确认**(需 ≥2):RSI>55 / 无顶背离 / EMA20>EMA50 且站上 EMA20 / MACD 柱连两根走高
- **入场** 回踩阻力(`阻力 − 0.30×ATR`),**止损** 结构低点下方,**TP** 2R / 3.5R
- **否决**:突破后 H4 收回阻力下方 = 假突破,撤单

### 方案 B · 逆势做空(双顶拒绝)
- **触发**:上探阻力区后 H4 收盘失败(上影 ≥45%)
- **确认**:**RSI 顶背离(必需,没有就不做)** / MACD 柱缩短 / 阻力区触及 ≥2 次
- **入场** 阻力下沿,**止损** 形态高点上方,**TP** 2R / 3.5R
- **仓位减半** —— 逆势本来就是低胜率高赔率的活

**没有「触发 + ≥2 确认」的方案一律 `wait`。** 小账户死于频繁交易,不死于错过行情。

---

## 三道护栏(比信号本身更重要)

| 护栏 | 默认 | 为什么 |
|---|---|---|
| `FOREX_RISK_PCT` | 1.0%,**硬上限 2%** | 调到 5% 会被代码夹回 2%。连亏 10 笔还剩 $180 |
| `FOREX_MIN_STOP_PIPS` | 15 pips(且 ≥8×点差) | 纯按 ATR 缩放会在低波动时段算出 10 pips 止损,点差占 20%,必被噪音扫掉 |
| `FOREX_MAX_LEVERAGE` | 20x | `units = 风险/止损距离`,止损越窄单位越大。5 pips 止损会算出 40000 单位($46k 名义 / 232x)—— 风险模型必须让位给保证金现实 |

另有**事件封锁**:`forex_events.json` 里 `impact: high` 的事件前 12 小时不开新仓。
CPI/非农前的突破基本都是低质量突破 —— 方向对了都可能被数据反向抹掉。

> ⚠️ `forex_events.json` 里的时间来自公开周报,且**原文的星期几与真实日历对不上**
> (2026-08-12 是周三,原文写周二)。上线前务必到 ForexFactory 或券商日历核对,
> 把 `verify: true` 改掉。

---

## 执行层(`live_trader_forex.py`)

**出场策略:TP1 全平(吃小赢面广)。** 到 TP1 整仓走人,固定 1:2,不留尾仓、
不移保本、不追 TP2。

这个选择有个很大的架构红利:因为不需要「到 TP1 再动手」,**止损和止盈在挂单的
同时就交给 OANDA**,变成券商侧的 GTC 委托。于是 GitHub Actions 挂了、runner 被
回收、脚本再没跑过 —— 你的止损止盈**依然在券商那里活着**。换成「移保本+让利润跑」,
出场就依赖机器人按时醒来,它不醒就是裸单。对跑在免费 CI 上的 $200 账户,这个
差别比多赚的那点 R 重要得多。

入场是**限价挂单**(回踩才进,不追价),24 小时不成交自动撤销 —— 挂了三天才等到的
行情,和当初生成它的那根 K 线已经没关系了。

**总开关**:`.github/workflows/forex_signals.yml` 里的 `FOREX_EXECUTE`。
默认 `"no"` = 只打印「我本来会下什么单」;改成 `"yes"` 才真的挂单。

| 护栏 | 默认 |
|---|---|
| `FOREX_MAX_OPEN` | 2 个持仓 |
| `FOREX_MAX_PENDING` | 2 张挂单 |
| `FOREX_ORDER_EXPIRY_HOURS` | 24h |
| 幂等指纹 | 品种+方案+**K线时间** —— workflow 重跑不会下双倍仓位 |

## 接真钱之前

1. **模拟盘跑满 20 笔**,看 `signals_forex.md` 的判断是否站得住。
2. 真钱要**两把锁**:`OANDA_ENV=live` **且** `OANDA_I_UNDERSTAND_REAL_MONEY=yes`,
   并换成 live(非 practice)的 token。少一个就会被 `broker_oanda.py` 拦下。
3. **不要设周收益目标。** 有目标就会重仓,重仓就会归零。README 里那句
   「$400/week on $100 ≈ 400% 周收益率 — 不可能实现」对外汇同样成立。
4. 美国居民注意:多数离岸券商不接受开户,且有 FIFO、禁止对冲、主要货币对
   50:1 杠杆上限等限制。OANDA 有美国实体。

---

*研究/学习用途,不构成投资建议或收益承诺。外汇保证金交易杠杆高、风险大,可能损失全部本金。*
