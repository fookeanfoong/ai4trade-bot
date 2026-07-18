# 接入 Alpaca（推荐）— 纯云端,电脑关机也跑

Alpaca 是**纯云端 REST API,没有本地网关**(不像 Moomoo 要挂 OpenD、IBKR 要挂
IB Gateway)。所以 paper(和以后真钱)的交易可以**直接跑在 GitHub Actions 上**——
你什么机器都不用管,电脑关机照跑。它还支持**碎股**(小到约 $1),所以 $200 的小账本
也能买 SPY 这种贵价股。

> **默认全程是 paper(假钱)。** 代码里两道锁:不设 `ALPACA_PAPER=false` +
> `ALPACA_I_UNDERSTAND_REAL_MONEY=yes`,就**永远不会**下真钱单。

---

## 第一步(你来做):拿一个免费 paper key

1. 去 alpaca.markets 注册(paper 账户**只要 email,不用入金、不用身份验证**)。
2. 进 Dashboard,切到 **Paper Trading**,生成 **API Key**。你会得到两串:
   - `API Key ID`(像 `PK....`)
   - `API Secret Key`(只显示一次,记下来)
3. **不要把 key 贴进聊天或提交进 Git。** 下一步把它们存进 GitHub Secrets。

## 第二步(你来做):把 key 存进 GitHub Secrets

仓库页面 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**,
加两个:

| Secret 名 | 值 |
|-----------|-----|
| `ALPACA_API_KEY_ID` | 你的 API Key ID |
| `ALPACA_API_SECRET_KEY` | 你的 API Secret Key |

存好后告诉我一声——GitHub Actions 里的 `live-trade`(paper)步骤下次跑就会自动接上,
**在云端自动交易 paper,你电脑不用开**。

> 在此之前,那个步骤会检测到没 key,自己安静跳过(不会让流水线失败)。

---

## 本地想手动试(可选)

不装也行(云端会跑)。想在自己电脑上试:
```bash
pip install -r requirements-alpaca.txt
export BROKER=alpaca
export ALPACA_API_KEY_ID=<你的>            # 别提交进 Git
export ALPACA_API_SECRET_KEY=<你的>
export ALPACA_PAPER=true                    # paper(默认)
export BOOK_EQUITY=200                       # 逻辑账本,按 $200 计划下单
export RISK_PCT=0.05                          # 每笔止损最多亏账本 5%

python live_trader.py --check                 # 只连,打印账户+持仓
python live_trader.py --test-order SPY --qty 1   # 下 1 笔 paper 市价单验证链路
python live_trader.py --dry-run               # 干跑逻辑,不真下单
python live_trader.py                          # 真的在 paper 上跑一个周期
```

---

## 关于 $200 小账户的两个现实(重要)

**1. 小于 $2,000 = 现金账户** → **1x、只能做多、卖出后 T+1 结算**。
想要 **2x 杠杆 + 做空**,得入金 **≥ $2,000**(≈ RM9,400)。这个 $2k+ 也正好是你
"月赚 1000-2000 马币"目标所需的现实本金——$200 只够验证系统,不够那个目标。
- 想开做空:入金到 ≥$2k 开保证金账户后,设 `ENABLE_SHORT=yes`。

**2. PDT 规则:** 账户 < $25,000 时,保证金账户的日内往返(当天买当天卖)5 个交易日
限 3 次。现金账户不受 PDT 限,但受结算时间限。频繁日内要留意。

碎股默认开(`ALLOW_FRACTIONAL` 对 Alpaca 默认 `yes`),所以 $200 也能按名义金额买贵价股。

---

## 怎么切真钱(验证达标后)

**先满足你自己定的验证条件:** paper 连续 ≥ 4 周、≥ 20 笔、净盈利、无数据/下单错误。

达标后:
1. 在 Alpaca 开**真实账户**(填 W-8BEN),入金(从马来西亚:CurrencyCloud 或美元电汇,
   手续费约 1.5% 封顶 $40;详见 Alpaca 官网入金页)。
2. 生成**真实账户**的 API key,更新 GitHub Secrets(或本地 env)。
3. 把环境切成真钱(两把锁都要开,否则代码拒单):
   ```bash
   export ALPACA_PAPER=false
   export ALPACA_I_UNDERSTAND_REAL_MONEY=yes
   ```

真钱前把杠杆认知摆正:真实美股保证金 ~2x,想要更高只能碰 CFD/期货,风险大很多。
先用真实 2x 把策略跑顺。

---

## 安全提醒
- **API key 只放 GitHub Secrets 或本地 env,永远不要提交进 Git、不要贴聊天。**
- 真钱自动交易 = 半夜没人看着代码也会下单。务必先在 paper 证明它稳。
- 万一 key 泄露,去 Alpaca Dashboard **regenerate** 作废旧 key。
