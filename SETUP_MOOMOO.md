# 接入 Moomoo — 从"我自己的模拟盘"到"真 broker 模拟盘",再到真钱

这一步的目的:用 **Moomoo 的 paper trading(模拟盘)** 验证**真实下单链路**——
认证、下单、成交、查持仓/资金。这些是我内部的 `signal_sim.py` 测不到的。
等 Moomoo 模拟盘也稳定盈利,切真钱只要改**一个环境变量**。

> **默认全程是模拟盘(假钱)。** 代码里有两道锁,不设 `MOOMOO_TRADE_PWD` +
> `MOOMOO_I_UNDERSTAND_REAL_MONEY=yes` 就**永远不会**下真钱单。

---

## ⚠️ 必须先懂的架构现实

你的 Python **不直接连** Moomoo 服务器。它连的是 **OpenD**——一个网关程序,
必须在**同一台机器**上一直开着 + 保持登录(默认 `127.0.0.1:11111`),由 OpenD
去连 Moomoo。

**后果:这套东西不能跑在 GitHub Actions 上**(用完即毁的临时机器、无法持续登录)。
所以分工是:

| 组件 | 跑在哪 | 作用 |
|------|--------|------|
| 分析流水线(quotes.py / news.py / signal_sim.py) | GitHub Actions(已在跑) | 产出 `signals.json` + `quotes.json` |
| **OpenD + moomoo_paper_trader.py** | **一台一直开的机器**(你的 PC 或便宜 VPS) | 读上面的信号 → 真实下单到 Moomoo |

那台机器需要:能开机联网、装 Python、能 `git pull` 这个仓库拿到最新 `signals.json`。
如果你的 PC 会关机,就租一台最便宜的 VPS(月费几美元)专门挂 OpenD——不然"电脑关机也能交易"做不到。

---

## 一次性设置

### 1. 开 Moomoo 账户 + 开通 paper trading + API 权限
- 在 Moomoo App 里开好账户,找到 **Paper Trading / 模拟交易** 账户(美股)。
- 在官网申请 **OpenAPI** 权限(免费)。

### 2. 下载并运行 OpenD(在那台一直开的机器上)
- 从 Moomoo OpenAPI 页面下载 **OpenD**(有 Windows / Mac / Linux 版,Linux 版可跑在 VPS 上,命令行即可)。
- 启动 OpenD,用你的 Moomoo 账号**登录**。保持它开着。它会监听 `127.0.0.1:11111`。

### 3. 装依赖(同一台机器)
```bash
git clone https://github.com/fookeanfoong/ai4trade-bot.git
cd ai4trade-bot
pip install -r requirements-moomoo.txt
```

### 4. 设置环境变量
```bash
export MOOMOO_TRD_ENV=SIMULATE          # 模拟盘(默认)。真钱才改 REAL
export MOOMOO_HOST=127.0.0.1
export MOOMOO_PORT=11111
export MOOMOO_SECURITY_FIRM=FUTUINC     # ← 关键!按你的账户所属券商设(见下)
export BROKER=moomoo                    # 让通用交易器 live_trader.py 选 Moomoo
export BOOK_EQUITY=200                  # 逻辑账本,按 $200 计划下单(不按模拟盘的虚拟余额)
export RISK_PCT=0.05                    # 每笔止损最多亏账本 5%
export LEVERAGE_CAP=2.0                 # 真实美股保证金约 2x(不是模拟盘的 10x)
```

> 注:交易入口是通用的 `live_trader.py`,用 `BROKER=moomoo` 选 Moomoo 适配器。
> (如果你后来改用 Alpaca,只需 `BROKER=alpaca` + Alpaca 的 key,见 `SETUP_ALPACA.md`。)

**`MOOMOO_SECURITY_FIRM` 怎么填**(填错会连不到你的账户):
| 你的账户 | 值 |
|----------|-----|
| 美国 Moomoo (Futu Inc) | `FUTUINC` |
| 香港 Futu Securities | `FUTUSECURITIES` |
| 新加坡 | `FUTUSG` |
| 澳洲 | `FUTUAU` |

> 马来西亚账户请以 App/OpenD 里显示的券商实体为准;若上面没有对应值,连的时候会报
> "Unknown MOOMOO_SECURITY_FIRM",报错信息里会提示可选值,按提示改即可。

---

## 分三步验证(强烈按顺序来)

**第 1 步 — 只连不交易**,确认链路通:
```bash
python live_trader.py --check
```
应打印你的账户资金和当前持仓。连不上就检查 OpenD 是否开着 + 登录 + security_firm 是否对。

**第 2 步 — 下一笔极小的模拟单**,确认下单/成交/查持仓整条路:
```bash
python live_trader.py --test-order XLE --qty 1
```
(`--test-order` 只在 SIMULATE 下允许,REAL 会被拒绝。)之后去 App 的模拟盘里应能看到这 1 股。

**第 3 步 — 干跑一个完整周期**(套用信号 + 风控,但不真的下单):
```bash
python live_trader.py --dry-run
```
看它打算怎么做。确认逻辑对了,再去掉 `--dry-run` 让它真的在模拟盘下单。

---

## 让它自动跑(在那台机器上)

用 cron(Linux/Mac)每 10 分钟跑一次(美股时段):
```cron
*/10 13-20 * * 1-5   cd /path/to/ai4trade-bot && git pull -q && BROKER=moomoo MOOMOO_TRD_ENV=SIMULATE python live_trader.py >> moomoo.log 2>&1
```
`git pull` 先拿到 GitHub Actions 刚更新的 `signals.json` / `quotes.json`,再据此在模拟盘执行。

---

## 什么时候、怎么切真钱

**先满足验证条件**(你自己定的:不要有失误才上真钱):
- Moomoo **模拟盘**连续跑 ≥ 4 周
- ≥ 20 笔成交
- 净盈利、无数据/下单错误

满足后切真钱**只改一处**:
```bash
export MOOMOO_TRD_ENV=REAL
export MOOMOO_TRADE_PWD=<你的交易密码>
export MOOMOO_I_UNDERSTAND_REAL_MONEY=yes
```
两把锁少一把,代码就拒绝下真钱单——防手滑。

真钱前也请把杠杆认知摆正:真实美股保证金 ~2x,想要更高只能碰 CFD/期货,风险大很多。
先用真实 2x 把策略跑顺,别一上来就上高杠杆。

---

## 安全提醒
- **交易密码 / API 凭证只放在那台机器的环境变量或本地文件里,永远不要提交进 Git。**
- 真钱自动交易 = 半夜没人看着时,代码也会自己下单。务必先在模拟盘证明它稳。
- `moomoo_trader_state.json` 是本地运行状态,不必提交。
