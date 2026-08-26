//+------------------------------------------------------------------+
//|                                       XAUUSD_ScalperGuard.mq5     |
//|                                                                   |
//|  XAUUSD 短线交易机器人 —— 风控优先                                  |
//|  核心顺序：保护本金 > 追求利润 > 增加交易次数                        |
//|                                                                   |
//|  硬性规则（写死在代码里，无法被"想多赚一点"绕过）：                   |
//|    - 单笔风险 1%（默认）～2%（上限）                                 |
//|    - 每日盈利 +50 USD  -> 当天停止一切交易                          |
//|    - 每日亏损 -15 USD  -> 平掉持仓 + 当天停止一切交易                |
//|    - +20 保守模式 / +30 进一步收紧                                  |
//|    - 连亏 2 笔 -> 观察模式（信号门槛提高）                           |
//|    - 连亏 3 笔 -> 当天停止                                          |
//|    - 每日最多 10 笔                                                 |
//|    - 每一笔必须带止损；止损只能往盈利方向移动，永不放大               |
//|    - 禁止亏损加仓 / 马丁 / 摊平成本                                  |
//|    - 重大数据前后禁止开新仓                                          |
//|                                                                   |
//|  默认只允许在 DEMO 账户运行（InpAllowLiveAccount = false）           |
//+------------------------------------------------------------------+
#property copyright "XAUUSD ScalperGuard"
#property version   "2.00"
#property strict

// 编译时间戳 + 版本号。MT5 加载的是 .ex5 不是 .mq5 —— 只更新源码而没按 F7,
// 跑的就还是旧二进制。这一行让日志直接说清楚当前跑的是哪个 build,
// 不用再靠"报错文案对不对得上"去猜。
// 注意:MQL5 没有 C/C++ 的 __TIME__ 宏,而 __DATE__ 是 **datetime 类型**不是字符串,
// 所以 `__DATE__ " " __TIME__` 这种 C 写法在 MQL5 里是语法错误。
// MQL5 里带时间的编译戳只有 __DATETIME__,而且要用 TimeToString 转成文字。
#define SG_VERSION "2.0"
#define SG_BUILD   __DATETIME__

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

//==================================================================
// 输入参数
//==================================================================
input group "=== 安全闸门 ==="
input bool     InpAllowLiveAccount   = false;   // 允许在真实账户运行（默认 false = 只跑 Demo）
input long     InpMagic              = 20260812;// Magic Number
input bool     InpVerboseLog         = true;    // 详细日志（写入 Files\XAUUSD_ScalperGuard_log.csv）

input group "=== 资金 / 风险 ==="
// InpFixedLot > 0 时，**不再按风险反算手数**，每笔都用这个固定手数。
// 仍然必带止损、仍查保证金、仍守最小手/步长 —— 只是手数来源换了。
// ⚠️ 代价：止损距离每笔不同，固定手数下**每笔冒的美元数就不一样**了，
//    +2R/-1R 的干净结构会被打散（宽止损单亏得多、窄止损单亏得少）。
//    所以每笔的实际风险会写进 [OPEN] 日志，自己盯着。
input double   InpFixedLot           = 0.0;     // 固定手数（0=按风险%反算，>0=每笔都用它）

// 结构止损超过上限时：true=把止损收到上限照做（止损硬锁在 InpSlMaxUSD），
// false=放弃这笔（原行为）。高波动里结构止损常 >上限，false 会大量拒单。
// 用固定手数 + 固定金额止损时，通常要 true —— 否则设了 $10 止损却因为
// 结构要 $15 而一直不进场。
input bool     InpClampWideStop      = false;   // 结构止损过宽时收到上限而不是放弃

// 利润地板：净利**到过**这个金额之后，若回落到它以下就平仓。
// 和「到 $X 就卖」的区别 —— 它不砍上限：超过后继续涨就继续拿，只在
// **跌回地板**时才落袋。等于给已经到手的利润设一条只升不降的底线。
// "净"是真的净（PositionNetUSD：点差/隔夜/手续费已扣）。0=关闭。
input double   InpProfitFloorUSD     = 0.0;     // 利润地板($)，到过后跌回它以下就平仓，0=关闭
input double   InpRiskPctDefault     = 1.0;     // 默认单笔风险 %（账户余额）
input double   InpRiskPctMax         = 2.0;     // 单笔风险上限 %（仅最高质量信号）
input double   InpDailyProfitTarget  = 50.0;    // 每日盈利目标 USD -> 停止交易
input double   InpDailyMaxLoss       = 15.0;    // 每日最大亏损 USD -> 停止交易
input double   InpConservativeAt     = 20.0;    // 当日盈利达到该值 -> 保守模式
input double   InpReducedAt          = 30.0;    // 当日盈利达到该值 -> 进一步收紧
// 规格里的 +$50 / -$30 是按 $200 写的。搬到别的余额上会失真($10,000 账户的
// -$30 只有 0.3%,一笔就熔断)。这四个 >0 时改用**余额百分比**,覆盖上面的绝对值。
input double   InpDailyTargetPct     = 0.0;     // 每日目标 = 余额 %（0=用上面的绝对值）
input double   InpDailyMaxLossPct    = 0.0;     // 每日亏损上限 = 余额 %（0=用绝对值）
input double   InpConservativeAtPct  = 0.0;     // 保守模式触发 = 余额 %
input double   InpReducedAtPct       = 0.0;     // 收紧模式触发 = 余额 %
input int      InpMaxTradesPerDay    = 10;      // 每日最大交易笔数
// 这两个设 0（或负数）= **关闭该道熔断**。
// 注意不能靠"设成 0"来关：判断是 consecLoss >= 阈值，阈值为 0 时恒真，
// 会变成一开始就永久停手 —— 所以下面用 ConsecStopOn()/ConsecObserveOn() 显式判定。
input int      InpStopAfterConsecLoss= 3;       // 连亏 N 笔 -> 当天停止（0=关闭）
input int      InpObserveAfterConsecLoss = 2;   // 连亏 N 笔 -> 观察模式（0=关闭）
input double   InpMaxMarginPctPerPos = 35.0;    // 单仓占用保证金上限（占可用保证金 %）
input bool     InpUseFloatingInLimits= true;    // 日盈亏统计是否包含浮动盈亏
input bool     InpSmallAccountEscalate = true;  // 小账户救济：最小手开不了时，把风险上调至 InpRiskPctMax

input group "=== 固定金额目标（下注前就知道赚多少）==="
// InpTargetProfitUSD > 0 时，止盈不再按 R 倍数摆，而是**直接摆在赚到这个金额
// 的价位上**。EA 会按实际手数反算需要走多少美元金价，并写进日志。
//
// ⚠️ 必须和 InpRiskCapUSD 配套用，否则这是个陷阱：
//    风险 $100（$10,000 的 1%）配 $10 目标 = RR 1:0.1 = 保本胜率 91%。
//    要 RR 1:1 就把风险上限也设成 $10；要 1:2 就设 $5。
//    OnInit 会把这三个数和保本胜率一起算给你看。
input double   InpTargetProfitUSD    = 0.0;     // 每笔目标盈利($)，0=关闭，用 R 倍数止盈
input double   InpRiskCapUSD         = 0.0;     // 每笔风险硬上限($)，0=只用风险%

// InpQuickProfitUSD > 0 时:只要这笔仓位的**净盈亏**摸到这个金额,立刻市价平掉,
// 不等 TP、不等 R 倍数、不等追踪止损。
// "净"的口径(下面 PositionNetUSD 就是按这个算的):
//     POSITION_PROFIT —— 买单按 BID / 卖单按 ASK 计价,**点差已经扣在里面**
//   + POSITION_SWAP   —— 隔夜利息
//   + 该仓位已产生的 commission × 2 —— ×2 是给平仓那一笔留出手续费
// 所以设 1.5 的意思就是"到手 $1.5",不是"毛赚 $1.5"。
//
// ⚠️ 这东西会**大幅压低盈亏比**,必须配 InpRiskCapUSD 一起用:
//    赚 $1.5 / 亏 $10  = RR 1:0.15 -> 保本胜率 87%
//    赚 $1.5 / 亏 $1.5 = RR 1:1    -> 保本胜率 50%
//    OnInit 会把这两个数和保本胜率一起算给你看。
input double   InpQuickProfitUSD     = 0.0;     // 净赚到这个金额($)立刻平仓，0=关闭
// >0 时所有百分比都以这个数为基准,而不是终端里的真实余额。
// 用途:在 $10,000 演示账户上原样模拟 $200 的风险敞口,同时保留 A+/A/B 分级。
// 保证金检查不受影响 —— 那是券商的真实约束。
input double   InpVirtualBalanceUSD  = 0.0;     // 虚拟本金($)，0=用真实余额

input group "=== 交易时段 / 点差 / 流动性 ==="
input int      InpSessionStartHour   = 8;       // 交易时段开始（服务器时间，小时）
input int      InpSessionEndHour     = 21;      // 交易时段结束（服务器时间，小时）
input int      InpFlatAllBeforeHour  = 22;      // 该小时后强制清仓（服务器时间）
input double   InpMaxSpreadUSD       = 0.35;    // 最大允许点差（美元，黄金）
input double   InpSpreadVsATRMax     = 0.12;    // 点差 / ATR 上限（点差异常过滤）

input group "=== V2 评分与分级（10分制）==="
// 规格 §28/§29:Trend 0-2 / KeyLevel 0-2 / Liquidity 0-2 / Structure 0-2
//              / Momentum 0-1 / RR 0-1 = 满分 10
// 分级决定风险上限,而不是反过来 —— 风险由 setup 质量给,不由"想赚多少"给。
input bool     InpUseV2Scoring       = true;    // 启用 10 分制评分与分级
input int      InpScoreMinB          = 5;       // < 该分数 = C 级 = NO TRADE
input int      InpScoreMinA          = 7;       // >= 该分数 = A 级
input int      InpScoreMinAPlus      = 9;       // >= 该分数 = A+ 级
input double   InpRiskPctB           = 1.5;     // B 级(5-6分)风险上限 %
input double   InpRiskPctA           = 3.0;     // A 级(7-8分)风险上限 %
input double   InpRiskPctAPlus       = 5.0;     // A+级(9-10分)风险上限 %

input group "=== 方向判定与冲突处理 ==="
// 实测拦路的是 "趋势不一致 HTF=1 LTF=-1" —— 两个周期方向明确但相反。
// 那正是**回调**的定义,而入场 B 就叫"趋势回调",它等的就是这一刻。
// 原逻辑要求两周期同向,等于回调一发生就把自己的回调入场毙掉 ——
// 「市场结构冲突」「动量冲突」两道同理:回调时它们必然冲突。
//   0 = 两周期必须同向（原行为，最严）
//   1 = H1 定方向，M5 只影响评分不否决（回调入场才可能触发）
//   2 = 任一周期有方向即可（H1 有方向就听 H1，H1 中性才听 M5）
//   3 = M5 定方向，H1 只进评分不定方向
//   4 = **纯K线方向**：摆动结构优先，结构不明时看最近K线的净推进
//
// 模式 4 和 1/2/3 的区别在于**用什么读方向**：
//   1/2/3 都是 EMA 交叉 —— 平滑后的历史，转向必然滞后
//   4     是摆动高低点 —— K线本身的结构，价格行为的原生语言
//
// ⚠️ 模式 2 有一个不显眼的陷阱：它只在 **H1 完全中性** 时才轮到 M5。
//    而 InpHtfRequireCloseSide / InpHtfRequireSlope 都关掉之后，HtfTrend()
//    退化成纯粹的 "H1 EMA50 vs EMA200"，在一段趋势行情里能连续几周不翻面 ——
//    H1 永远不中性，M5 永远轮不到，方向恒定为一边。
//    结果就是：模式 2 名义上"任一周期有方向即可"，实际等同模式 1。
//    要真的两个方向都做，用模式 3；或者把上面那两个 H1 开关打开，
//    让 H1 在动能转弱时回到中性。
//
// 模式 3 下逆着 H1 的单子不会被特殊对待，但也不需要 ——
// 10 分制的 trend 维度自然会少给 1~2 分，等级降下来风险上限也跟着降。
input int      InpDirectionMode      = 0;
// true  = 结构/动量与方向冲突时**拒绝交易**（原行为）
// false = 冲突不否决，只记录进成交备注，由 10 分制评分去反映质量差异
input bool     InpConflictAsVeto     = true;

// 信号倒转：把最终方向翻过来，止损/止盈以入场价为轴**镜像反射**。
// 反射而不是重算，是为了让 R 距离与原信号**完全相同** —— 这样正反两次运行
// 的 R 倍数可以逐笔直接对比，差异只来自方向本身。
//
// ⚠️ 这是**诊断工具，不是赚钱开关**。原因是成本在两个方向上都要付：
//     原策略净值   = 毛期望 - 成本
//     倒转后净值   = -毛期望 - 成本
//   毛期望为 0（策略本身没边）时，两边都等于 -成本，**倒转照样亏**。
//   只有当原策略的毛期望**负得比成本还多**，倒转才可能转正。
//   换句话说：要靠倒转赚钱，你得先证明原策略是在**主动做错**，
//   而不只是"没赚到"。
//
// ⚠️ 倒转后止盈是镜像出来的，不再受前方关键位限制（那个限制只对原方向成立）。
input bool     InpInvertSignals      = false;   // 倒转信号方向（诊断用）

// 模式 4 用的"纯K线方向"参数。
// 均线交叉是**平滑后的历史**，方向永远滞后；摆动结构(HH/HL vs LH/LL)读的是
// K线本身的高低点，转向时反应快得多，而且是价格行为本来的语言。
// 结构都判不出方向时，退而看最近几根K线的净推进。
// 逆势闸门：方向定完之后再看一眼最近几根K线在往哪走。
// 摆动结构和均线一样，在**转折点上都是事后确认** —— InpSwingStrength=2 意味着
// 新的摆动低点要等右边再出 2 根K线才成立，所以价格在底部反转的那一刻，
// 结构读出来仍然是"更低高点+更低低点"=做空，于是一头撞进反弹里。
// 这道闸门不预测方向，只否决一件事：**要做空，可最近几根K线正在往上走**。
// 窗口用 **InpLTF（M5）** 而不是触发周期：M1 的 5 根只有 5 分钟，
// 一波一小时的反弹在那个窗口里根本看不见 —— 实盘就是这么把空单开在反弹里的。
input int      InpCounterMoveBars    = 5;       // 逆势检查看最近几根 LTF K线
input double   InpCounterMoveATR     = 0.50;    // 软阈值：逆向超过 ATR×该值 且 最新一根仍在继续 -> 否决
input double   InpCounterMoveHardATR = 1.00;    // 硬阈值：逆向超过 ATR×该值 -> 无条件否决，0=关闭

input int      InpPaBars             = 6;       // 近期净推进看最近几根 LTF K线
input double   InpPaMinATR           = 0.30;    // 净推进需超过 ATR × 该值才算有方向

input group "=== V2 多周期 ==="
input ENUM_TIMEFRAMES InpMTF         = PERIOD_M15;  // 中周期（找交易区域）
input bool     InpRequireMtfAgree    = false;   // M15 结构必须与方向一致才给分以外，还否决

input group "=== V2 结构位移 BOS / CHoCH ==="
// ⚠️ 这里用的是**我给的机械定义**,不是什么权威定义 —— 各家讲法互相矛盾,
//    所以必须把定义写死才能回测:
//      BOS  = 收盘价越过最近一个**已确认**的摆动高(向上)或摆动低(向下)
//      CHoCH= 在原本相反的结构里出现的第一次 BOS(即结构性质改变)
//    "已确认"= 该摆动点右侧已经走出 InpSwingStrength 根K线。
input bool     InpUseBOS             = true;    // 把 BOS/CHoCH 纳入结构评分
input double   InpBosBufferATR       = 0.05;    // BOS 需越过摆动点的缓冲 = ATR × 该值

input group "=== V2 波动率分档 ==="
// 规格 §13:High 降仓,Extreme 等结构稳定。用 ATR 与其自身均值的比值分档,
// 而不是拍绝对数 —— 金价从 $2000 涨到 $4400,绝对 ATR 早就不是一回事了。
input bool     InpUseVolRegime       = true;
input int      InpAtrAvgPeriod       = 96;      // ATR 均值回看根数（M5 下 96 根 = 8 小时）
input double   InpVolHighMult        = 1.60;    // ATR / 均值 超过 = High
input double   InpVolExtremeMult     = 2.40;    // 超过 = Extreme（停手）
input double   InpVolHighSizeMult    = 0.60;    // High 档仓位乘数

input group "=== 信号 / 结构 ==="
input ENUM_TIMEFRAMES InpHTF         = PERIOD_H1;  // 高时间周期（趋势）
input ENUM_TIMEFRAMES InpLTF         = PERIOD_M5;  // 交易时间周期

// 触发周期:只管"扣扳机的那根K线",不管方向。
// 趋势(EMA/ADX)、波动(ATR)、市场结构、关键位 —— 全部仍然在 InpLTF/InpHTF 上算,
// 换的只是"等哪根K线收盘才算数"和"回踩/影线看哪根"。
// InpLTF=M5 时,一个形态最长要等 5 分钟才被确认;设成 M1 就是 1 分钟。
// 代价是触发根的噪音更大 —— 结构止损会变窄,由 InpSlMinUSD 那道下限兜底。
// PERIOD_CURRENT(0) = 跟随 InpLTF,即保持原行为。
input ENUM_TIMEFRAMES InpEntryTF     = PERIOD_CURRENT;  // 触发周期，0=跟随 InpLTF
input int      InpEmaFastHTF         = 50;      // HTF 快线 EMA
input int      InpEmaSlowHTF         = 200;     // HTF 慢线 EMA
input int      InpEmaFastLTF         = 20;      // LTF 快线 EMA
input int      InpEmaSlowLTF         = 50;      // LTF 慢线 EMA
// true  = M5 趋势要求「均线多头排列 **且** 收盘价站在慢线正确一侧」
// false = 只看均线排列
// 注意这条会和入场 B(趋势回调)打架:回调稍深跌破 EMA50 时,LtfTrend 返回 0,
// 整个信号在 BuildSignal 开头就被"趋势不一致"毙掉 —— 而那正是回调入场想要的位置。
input bool     InpLtfRequireCloseSide= true;    // M5 趋势是否要求收盘价站在慢线一侧
// H1 原本要三个条件同时成立:快线>慢线、收盘>快线、快线还在上行。
// 实测 100% 的拒绝都是 "趋势不一致 HTF=0" —— 三条里缺任何一条 H1 就判"无趋势",
// 整个信号在 BuildSignal 开头就被毙掉。这两个开关把后两条降为可选。
input bool     InpHtfRequireCloseSide= true;    // H1 是否要求收盘价站在快线一侧
input bool     InpHtfRequireSlope    = true;    // H1 是否要求快线本身还在同向移动
input int      InpAtrPeriod          = 14;      // ATR 周期
input int      InpRsiPeriod          = 14;      // RSI 周期
input int      InpAdxPeriod          = 14;      // ADX 周期
input double   InpAdxMin             = 18.0;    // ADX 最低值（低于 = 横盘，不交易）
input int      InpSwingStrength      = 2;       // Swing 高低点强度（左右各 N 根）
input int      InpStructureLookback  = 60;      // 结构分析回看 K 线数
input int      InpBreakoutLookback   = 12;      // 突破/回踩确认窗口
input int      InpMinScore           = 5;       // 最低确认分（满分 7）
input double   InpAtrMinUSD          = 0.80;    // ATR 下限（低于 = 波动不足）
input double   InpAtrMaxUSD          = 8.00;    // ATR 上限（高于 = 波动异常）

input group "=== 市场质量闸门（横盘 / 假突破）==="
// false = 不否决交易，但**仍然计算并随成交记录下来**。
// 数据采集期这样设：让它开单，同时留下"当时行情质量如何"的标签，
// 事后才能回答「在高频假突破的行情里做的单是不是真的更差」——
// 直接关掉不记录的话，这个问题永远没有答案。
input bool     InpUseMarketQuality   = true;    // 质量不合格时是否**拒绝**交易
input double   InpMinRangeATR        = 2.5;     // 近 30 根区间至少 = ATR × 该值
input double   InpMaxSmallBodyPct    = 70.0;    // 小实体 K 线占比上限 %
input int      InpMaxFakeBreakouts   = 5;       // 近 25 根内失败突破次数上限

input group "=== 机构参考位（前日高低 / 亚洲区间 / 整数关口）==="
// 原策略只认 M5 分型摆动点。问题是 M5 上每隔几根就有一个,它们不是机构在看的位置。
// 真正被反复测试的是这几条**客观可算**的线:前一日高低点、亚洲盘区间高低、整数关口。
// 这三样都不需要人工标注,也不涉及任何"smart money"叙事 —— 纯粹是算出来的价格。
input bool     InpUseKeyLevels       = true;    // 把前日高低/亚洲区间/整数关口纳入关键位
input bool     InpUseRoundNumbers    = true;    // 整数关口（每 InpRoundStep 美元一条）
input double   InpRoundStep          = 50.0;    // 整数关口间距（$4400/$4450…）
// 亚洲盘区间的时间窗,用**服务器时间**。你的服务器是 UTC+3,所以 UTC 00:00-07:00
// 对应服务器 03:00-10:00。换经纪商要重算。
input int      InpAsiaStartHour      = 3;       // 亚洲盘开始（服务器时间）
input int      InpAsiaEndHour        = 10;      // 亚洲盘结束（服务器时间）

input group "=== 入场 C：流动性扫损后反手 ==="
// 这是专业圈引用最多、且**唯一能机械定义**的那个技巧:价格先刺穿一条众所周知的
// 关键位(扫掉挂在那里的止损),然后收回来。刺穿失败 = 那个方向没有承接。
// 只做**顺 H1 趋势**的扫损 —— 逆着高周期做扫损反手是另一套东西,不在这里。
input bool     InpUseSweepEntry      = true;    // 启用扫损反手入场
input double   InpSweepMinPenetration= 0.10;    // 刺穿深度至少 = ATR × 该值（太浅算噪音）
input double   InpSweepMaxPenetration= 1.50;    // 刺穿深度超过 = ATR × 该值 则算真突破，不反手

input group "=== 入场触发灵敏度 ==="
input double   InpTriggerTolATR      = 0.35;    // 回踩/回调的容差 = ATR × 该值
input double   InpBarCloseStrength    = 0.55;   // 确认K线收盘位置要求（收在区间的前 N）
input double   InpWickRejectPct       = 0.55;   // 影线占比超过该值即视为拒绝信号

input group "=== 止损 / 止盈 ==="
input double   InpSlAtrMult          = 1.2;     // 止损 = swing 之外 + ATR * 该系数
input double   InpSlMinUSD           = 1.20;    // 最小止损距离（美元）
input double   InpSlMaxUSD           = 6.00;    // 最大止损距离（美元）
input double   InpMinRR              = 1.5;     // 最低风险回报比（到下一个关键位）
// M5 上每隔几根就有一个小摆动高点。把**每一个**都当成硬顶去压缩 TP2，会算出
// RR=0.04 这种数字 —— 那不是阻力，是噪音，价格照穿不误。
// 只有距离 >= 该倍数 R 的关键位才算数，更近的一律忽略。
input double   InpLevelIgnoreR        = 1.0;    // 压缩止盈时，忽略近于该倍数 R 的关键位
input double   InpTP1_R              = 1.0;     // TP1 = 1R
input double   InpTP2_R              = 1.8;     // TP2 = 1.8R
input double   InpPartialClosePct    = 50.0;    // TP1 平仓比例 %
input double   InpBreakevenBufferATR = 0.05;    // 保本止损缓冲（ATR 倍数）
input double   InpTrailATRMult       = 1.0;     // TP1 后 ATR 追踪止损系数
input int      InpMaxHoldMinutes     = 120;     // 单笔最长持仓分钟数（短线）
input bool     InpExitOnMomentumFade = true;    // 动量衰竭提前离场
// 这两个门槛原先写死在 ManagePositions 里,是「快进快出」最直接的两个旋钮:
// 调低 = 更早落袋、持仓更短、胜率更高但每笔更小。
input double   InpFadeExitMinR       = 0.45;    // 动量衰竭离场的最低盈利(R)
input double   InpLevelExitMinR      = 0.70;    // 逼近关键位落袋的最低盈利(R)
// 实盘数据暴露的问题:11/18 笔出场是"逼近关键位提前平仓",R 倍数密集落在
// 0.70~0.82(也就是阈值本身),而计划 RR 均值 1.67 —— 实际只拿到计划目标的 48%。
// 原因:这个出场调的是 NearestResistance(cur, 0.0, ...),minDist 传 0,
// 于是**任何 M5 微型摆动点**都算"关键位"。趋势里价格上方永远有一个,
// 条件几乎恒真 —— 盈利一到 0.70R 就立刻被平掉,等于给每一笔赢家封了顶。
// 我给止盈定位加了 InpLevelIgnoreR 去噪,却在出场这条路径上漏了同一件事。
input bool     InpLevelExitKeyOnly   = false;   // 该出场只认机构参考位，不认 M5 微型摆动点

// 停滞离场:有利润、但价格在一个很窄的区间里来回磨,不上不下 —— 落袋。
//
// 和"固定金额到点就走"的关键区别:这条是**有条件的**。趋势还在走的单子不受影响,
// 只砍掉那些已经不再往前走的。所以它压缩的是持仓时间,不是盈亏比。
//
// 两个门槛缺一不可:
//   1) 利润门槛 —— InpStallMinUSD>0 用净美元(点差/手续费已扣),否则用 R 倍数
//   2) 停滞判定 —— 最近 InpStallMinutes 分钟的最高最低差 < ATR × InpStallRangeATR
//
// ⚠️ 窗口别设太短。黄金"一分钟没动"是**常态不是信号**:M1 的正常波幅本就只有
//    日 ATR 的几十分之一,1 分钟窗口几乎必然命中,那就退化成"到点就走"了。
//    默认 10 分钟。改之前先看 reports/gold_stall.md 里的实测命中率。
// 保本时机。原来保本和 TP1 绑在一起(都在 InpTP1_R)，这带来一个很贵的后果：
// 一笔走到 +0.9R 然后掉头，止损从没动过 —— 结果是 **-1.0R 全额亏损**。
// 明明赚着的单子最后亏钱，绝大多数是这么来的：一次 1.9R 的净摆动。
// InpBreakEvenR 把保本从 TP1 里拆出来，可以远早于 TP1 触发。
// 0 = 跟随 InpTP1_R（旧行为）。
input double   InpBreakEvenR         = 0.0;     // 达到该 R 即移保本，0=跟随 InpTP1_R

// 按**金额**触发保本。和 InpBreakEvenR 是"或"的关系，谁先到算谁。
//
// 为什么需要它：R 门槛在止损很宽时会失效。风险 $8 的单子，0.3R = $2.4，
// 看着不高；但同一个 0.3R 在风险 $4 的单子上只有 $1.2。而你关心的是
// "已经到手 $2 的单子不该再变成亏损" —— 那是个**金额**判断，不是 R 判断。
//
// 注意这条只**移动止损**，不平仓：赚到 $2 之后这笔单子不会再亏，但仍然能跑。
// 想到 $2 直接落袋的话用 InpQuickProfitUSD，那是另一回事（会压死盈亏比）。
input double   InpBreakEvenUSD       = 0.0;     // 净赚到该金额($)即移保本，0=关闭

// 回吐上限：曾经赚到过 InpGiveBackMinR，就不许把利润全吐回去。
// 和保本的区别 —— 保本守的是**入场价**，回吐守的是**曾经到过的最高点**。
// 一笔冲到 +1.5R 再退回 +0.1R，保本管不着(还在盈利)，回吐上限会在 +0.9R 就收手。
input double   InpGiveBackPct        = 0.0;     // 从最高盈利回吐超过该%即平仓，0=关闭
input double   InpGiveBackMinR       = 0.60;    // 最高盈利需先达到该 R，回吐上限才生效

input group "=== 停滞离场（有利润但走不动了）==="
input bool     InpExitOnStall        = false;   // 启用停滞离场
input int      InpStallMinutes       = 10;      // 停滞观察窗口（分钟）
input double   InpStallRangeATR      = 0.25;    // 窗口内高低差 < ATR × 该值 = 停滞
input double   InpStallMinUSD        = 0.0;     // 利润门槛($，净额)，0=改用下面的 R 门槛
input double   InpStallMinR          = 0.50;    // 利润门槛(R)，InpStallMinUSD=0 时生效
input bool     InpStallNeedNoNewExtreme = true; // 最新一根仍在创有利极值时，不算停滞

input group "=== 新闻过滤 ==="
input bool     InpUseNewsFilter      = true;    // 启用经济日历过滤
input int      InpNewsBeforeMin      = 30;      // 数据公布前 N 分钟禁止开仓
input int      InpNewsAfterMin       = 20;      // 数据公布后 N 分钟禁止开仓
input bool     InpNewsHighOnly       = true;    // 仅过滤高重要性事件
input string   InpManualNewsTimes    = "";      // 手动黑名单时间 "HH:MM,HH:MM"（服务器时间）
// 原新闻过滤只挡**新开仓** —— 它在 OnTick 的 IsNewBar 分支里,而 ManagePositions
// 更早就跑完了。也就是说已经持有的仓位会毫无保护地穿过 FOMC/CPI 这种事件:
// 那一下若跳空 $30,止损会被直接跨过,实际成交远差于挂单价。
// >0 时:事件前这么多分钟主动清仓离场,不赌跳空方向。
input int      InpFlatBeforeNewsMin  = 0;       // 重大数据前 N 分钟强制清仓（0=关闭）

input group "=== 加仓（默认关闭）==="
input bool     InpAllowAddOn         = false;   // 允许加仓（必须满足全部条件）

input group "=== 多仓并行（规格 §30）==="
// 与"加仓"是两回事:加仓 = 往同一笔盈利单上追;多仓 = 各自独立的 setup、
// 各自独立的止损。后者不违反"禁止亏损加仓",前提是总风险有上限。
input bool     InpAllowMultiPosition = false;   // 允许同时持有多笔独立仓位
input int      InpMaxPositions       = 3;       // 最大同时持仓数
input double   InpMaxCombinedRiskPct = 10.0;    // 所有持仓的在险金额合计上限（占净值 %）
input bool     InpAllowHedge         = false;   // 允许反向持仓（规格 §31 默认禁止）

input group "=== 宽松入场（路径 D，采样用）==="
// 前三条路径(突破回踩/趋势回调/扫损反手)都要求特定形态,实测"无有效突破/回踩触发"
// 长期是第一大拒绝原因。这条路径刻意放松:趋势和动量一致、价格没有过度偏离均线,
// 顺势收盘即可入场。
// **它一定会拉低平均质量** —— 所以单独标记路径,事后按路径分组对比期望值,
// 如果它是亏的就关掉,而不是让它混在别的路径里污染统计。
input bool     InpUseLooseEntry      = false;   // 启用宽松入场（路径 D）
input double   InpLooseMaxDistATR    = 1.20;    // 价格偏离快线超过 ATR × 该值 = 追高，不做

input group "=== 止损上限改为跟随 ATR ==="
// 固定 $15 的上限是按 ATR≈3.4 定的。ATR 涨到 7 时结构止损普遍 17~18,
// 于是全被"结构止损过宽"拒掉 —— 上限必须跟着波动走。
input double   InpSlMaxATRMult       = 0.0;     // >0 时上限 = max(InpSlMaxUSD, ATR × 该值)

input group "=== 监控 ==="
input bool     InpPushNotify        = true;    // 关键事件推送到手机（需在 工具->选项->通知 填 MetaQuotes ID）
input bool     InpWriteStatusJson   = true;    // 每 30 秒把状态快照写入 Files\XAUUSD_ScalperGuard_status.json

// 策略测试器里,实盘那套监控设施(每笔写 CSV、每 30 秒扫全历史做统计、写 status.json)
// 全是纯开销:2 年 M5 回测会产生几千笔成交,ReportTradeStats 每 30 个模拟秒扫一次
// **全部历史** —— 复杂度 O(总时长 × 成交数),优化跑批时能把几分钟的活拖成几小时。
// 默认在测试器里关掉这些;想在单次回测里留 CSV 供事后分析,把这项设为 false。
input bool     InpTesterQuiet       = true;    // 回测/优化时静默监控设施（强烈建议保持 true）

// 外部指令通道：读 Files\XAUUSD_ScalperGuard_cmd.txt。
// 由外部程序（claude_watcher.py）写入，用来做**规则没覆盖到**的临时干预。
//
// 刻意做成能力极小的通道 —— 它只能做三件事，而且只能往"更保守"的方向：
//     halt=1        暂停开新仓（已有持仓照常按规则管理）
//     block_dir=-1  禁止做空      block_dir=1  禁止做多
//     expires=...   过期时间，**必填**；过期或读不到就当没有指令
// 它**不能**：改风险百分比、改止损、开真实账户、直接下单。
// 这样即使外部程序出错或被人乱写，最坏结果是不交易，不是乱交易。
input bool     InpUseCommandFile    = false;   // 启用外部指令文件
input int      InpCommandMaxAgeMin  = 15;      // 指令文件最久允许多旧（分钟），超时即忽略

//==================================================================
// 全局
//==================================================================
CTrade        trade;
CPositionInfo pos;

// 运行环境。OnInit 里赋值一次,后面到处要用。
bool g_tester = false;      // 在策略测试器里(单次回测 或 优化)
bool g_optim  = false;      // 在参数优化里(此时连 Print/Comment 都是浪费)
bool g_quiet  = false;      // 静默监控设施 = g_tester && InpTesterQuiet

ENUM_TIMEFRAMES g_entryTF = PERIOD_M5;   // 实际生效的触发周期，OnInit 里定

// 多空计数（本次挂载以来）。100% 单边是最容易被忽略的故障 —— 它不报错，
// 只是让你以为"策略就是这样"。摆到面板上，一眼就能看出方向闸门是不是卡死了。
int g_dirBuy = 0, g_dirSell = 0;      // 方向判定为多/空的次数
int g_opnBuy = 0, g_opnSell = 0;      // 实际开出的多/空单数

int hEmaFastH, hEmaSlowH;      // HTF EMA
int hEmaFastL, hEmaSlowL;      // LTF EMA
int hAtrL, hRsiL, hAdxL;       // LTF 指标

datetime g_lastBarTime   = 0;
datetime g_dayStart      = 0;
string   g_lastNoTradeReason = "";
datetime g_lastReasonLog = 0;
string   g_logFile       = "XAUUSD_ScalperGuard_log.csv";
bool     g_dayHaltLogged = false;

// 点差画像：按服务器小时统计，用来回答「0.40 是常态还是尖峰」。
// 放宽阈值等于把成本吞回自己身上；正确做法是找出点差天然合格的时段去交易。
double   g_spSum[24], g_spMin[24], g_spMax[24];
long     g_spCnt[24], g_spOver[24];
int      g_lastSpHour   = -1;
// 开仓当时的市场质量结论。闸门关掉时这是唯一能事后复盘"该不该做这一单"的依据。
string   g_quality      = "";

// 拒绝原因分布。单行日志只能看到"最后一次因为什么没做",看不出**哪一道闸门
// 才是主要瓶颈**。按类别计数后,每小时输出一次分布,下一步该松哪里一目了然。
#define  RB_N 14
string   g_rbName[RB_N] = {"趋势不一致","结构冲突","动量冲突","ADX不足","无有效触发",
                           "RR不足","止损过宽","点差","时段","市场质量",
                           "手数/保证金","波动率","新闻","其他"};
long     g_rbHit[RB_N];

// 每日统计（全部从成交历史推导，重启后不会丢）
struct DayStats
{
   double realized;      // 当日已实现盈亏（含手续费/库存费）
   double floating;      // 当前浮动盈亏
   double total;         // 用于风控判断的盈亏
   int    trades;        // 当日已开仓笔数
   int    consecLoss;    // 当前连亏次数
};

// 信号
struct Signal
{
   int      dir;         // +1 买 / -1 卖 / 0 无
   int      score;       // 确认分（V2 下为 10 分制总分）
   string   grade;       // V2 分级 A+ / A / B / C
   double   riskCapPct;  // 该分级允许的风险上限 %
   string   scoreDetail; // 各维度得分明细
   double   entry;
   double   sl;
   double   tp1;
   double   tp2;
   double   rr;
   string   note;
};

//==================================================================
// 工具函数
//==================================================================
double Px(double v){ return NormalizeDouble(v, _Digits); }

double PointValuePerLot()
{
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0.0) return 0.0;
   return tv * (_Point / ts);          // 每手每 point 的美元价值
}

// 每手每 1.00 美元金价波动的盈亏
double MoneyPerLotPerDollar()
{
   double ppl = PointValuePerLot();
   if(_Point <= 0.0) return 0.0;
   return ppl / _Point;
}

// 手数小数位（兼容 0.01 / 0.001 步长的经纪商）
int VolDigits()
{
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st <= 0.0) st = 0.01;
   int d = 0;
   while(st < 1.0 - 1e-9 && d < 8) { st *= 10.0; d++; }
   return d;
}

// 向下取整到合法手数步长（只缩不放）
double FloorToStep(double vol)
{
   double st = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(st <= 0.0) st = 0.01;
   return NormalizeDouble(MathFloor(vol / st + 1e-8) * st, VolDigits());
}

double SpreadUSD()
{
   return (SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID));
}

double StopsLevelUSD()
{
   long lvl = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   return (double)lvl * _Point;
}

// 连亏熔断的开关判定。阈值 <=0 一律视为关闭，避免"0 = 恒真 = 永久停手"这个坑。
bool ConsecStopOn(int consecLoss)
{
   return (InpStopAfterConsecLoss > 0 && consecLoss >= InpStopAfterConsecLoss);
}
bool ConsecObserveOn(int consecLoss)
{
   return (InpObserveAfterConsecLoss > 0 && consecLoss >= InpObserveAfterConsecLoss);
}

datetime DayStart(datetime t)
{
   MqlDateTime st; TimeToStruct(t, st);
   st.hour = 0; st.min = 0; st.sec = 0;
   return StructToTime(st);
}

void LogLine(string tag, string msg)
{
   if(InpVerboseLog && !g_quiet)
   {
      // FILE_ANSI 会按系统代码页写中文(实测导出的是 GBK),换台机器就乱码。
      // 和 status.json 一样自己转 UTF-8 按二进制追加。
      string line = StringFormat("%s,%s,%s\r\n",
                                 TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), tag, msg);
      uchar bytes[];
      int n = StringToCharArray(line, bytes, 0, -1, CP_UTF8);
      if(n > 1)
      {
         int h = FileOpen(g_logFile, FILE_READ|FILE_WRITE|FILE_BIN);
         if(h != INVALID_HANDLE)
         {
            FileSeek(h, 0, SEEK_END);
            FileWriteArray(h, bytes, 0, n - 1);      // 去掉结尾的 0
            FileClose(h);
         }
      }
   }
   // 优化跑批时 MT5 本就压制 agent 日志,这里再省一层字符串开销。
   if(!g_optim) Print("[", tag, "] ", msg);
}

int ReasonBucket(string w)
{
   if(StringFind(w, "趋势不一致") >= 0) return 0;
   if(StringFind(w, "市场结构")   >= 0) return 1;
   if(StringFind(w, "动量")       >= 0) return 2;
   if(StringFind(w, "ADX")        >= 0) return 3;
   if(StringFind(w, "触发")       >= 0 || StringFind(w, "影线") >= 0 ||
      StringFind(w, "假突破迹象") >= 0 || StringFind(w, "swing") >= 0) return 4;
   if(StringFind(w, "风险回报")   >= 0) return 5;
   if(StringFind(w, "止损过宽")   >= 0) return 6;
   if(StringFind(w, "点差")       >= 0) return 7;
   if(StringFind(w, "时段")       >= 0 || StringFind(w, "周") >= 0) return 8;
   if(StringFind(w, "横盘")       >= 0 || StringFind(w, "高频假突破") >= 0) return 9;
   if(StringFind(w, "最小手")     >= 0 || StringFind(w, "保证金") >= 0 ||
      StringFind(w, "额度")       >= 0 || StringFind(w, "加仓") >= 0) return 10;
   if(StringFind(w, "ATR")        >= 0 || StringFind(w, "波动") >= 0) return 11;
   if(StringFind(w, "数据窗口")   >= 0 || StringFind(w, "新闻") >= 0) return 12;
   return 13;
}

void ReportReasons(string tag)
{
   long tot = 0;
   for(int i = 0; i < RB_N; i++) tot += g_rbHit[i];
   if(tot <= 0) return;

   // 按次数从多到少排，最大的瓶颈排最前面
   int idx[RB_N];
   for(int i = 0; i < RB_N; i++) idx[i] = i;
   for(int a2 = 0; a2 < RB_N - 1; a2++)
      for(int b2 = 0; b2 < RB_N - 1 - a2; b2++)
         if(g_rbHit[idx[b2]] < g_rbHit[idx[b2+1]])
         { int t = idx[b2]; idx[b2] = idx[b2+1]; idx[b2+1] = t; }

   string line = "";
   for(int i = 0; i < RB_N; i++)
   {
      int k = idx[i];
      if(g_rbHit[k] <= 0) continue;
      line += StringFormat("%s×%d(%.0f%%)  ", g_rbName[k], (int)g_rbHit[k],
                           100.0 * (double)g_rbHit[k] / (double)tot);
   }
   LogLine("REASONS", StringFormat("%s 共 %d 次未开仓 | %s", tag, (int)tot, line));
}

// NO-TRADE 原因去重，避免刷屏
void NoTrade(string reason)
{
   g_rbHit[ReasonBucket(reason)]++;      // 计数在去重**之前**，否则统计会失真
   if(reason != g_lastNoTradeReason || TimeCurrent() - g_lastReasonLog > 900)
   {
      g_lastNoTradeReason = reason;
      g_lastReasonLog     = TimeCurrent();
      LogLine("NO-TRADE", reason);
   }
}

bool IsNewBar(ENUM_TIMEFRAMES tf)
{
   datetime t = iTime(_Symbol, tf, 0);
   if(t == 0) return false;
   if(t != g_lastBarTime)
   {
      g_lastBarTime = t;
      return true;
   }
   return false;
}

double Buf(int handle, int buffer, int shift)
{
   double a[];
   if(CopyBuffer(handle, buffer, shift, 1, a) != 1) return 0.0;
   return a[0];
}

//==================================================================
// 虚拟本金：在大账户上模拟小账户
//==================================================================
// 决定风险敞口的从来不是终端里显示的余额,而是**每笔冒多少钱**。
// InpVirtualBalanceUSD > 0 时,所有按百分比算的东西(单笔风险、日内限额、
// 组合风险上限)都以这个数为基准 —— 于是仓位大小、最小手数约束、熔断节奏
// 都和真的那么大的账户一致,而分级(A+/A/B 各自的风险%)完整保留。
//
// 这比"用一个 InpRiskCapUSD 一刀切"好:后者把所有等级压成同一个金额,
// 等于把 V2 规格的分级体系废掉。
//
// **不影响保证金检查** —— 那是券商的真实约束,仍然用真实账户数据。
// 可用保证金 —— 虚拟本金模式下按虚拟规模算，而不是终端里的真实余额。
//
// 之前保证金检查故意用真实余额，理由是"保证金是券商的硬约束"。那句话本身没错，
// 但后果是 demo 上跑 $200 配置时保证金闸门**永远不触发**，而真的 $200 账户上
// 它会频繁触发 —— 而且拦掉的恰好是评分最高、仓位最大的 A+ 单。
// demo 因此系统性高估表现。既然目的是模拟真实 $200 账户，就得连这道约束一起模拟。
//
// 真实可用保证金仍然是硬上限：虚拟规模再大也不能超过券商实际允许的。
double EffectiveFreeMargin()
{
   double real = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   if(InpVirtualBalanceUSD <= 0.0) return real;

   double used = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;
      double m = 0.0;
      ENUM_ORDER_TYPE ot = (pos.PositionType() == POSITION_TYPE_BUY)
                           ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(OrderCalcMargin(ot, _Symbol, pos.Volume(), pos.PriceOpen(), m)) used += m;
   }
   double v = InpVirtualBalanceUSD - used;
   return MathMax(0.0, MathMin(v, real));
}

double EffectiveBalance()
{
   if(InpVirtualBalanceUSD > 0.0) return InpVirtualBalanceUSD;
   return AccountInfoDouble(ACCOUNT_BALANCE);
}

//==================================================================
// 日内限额：百分比优先
//==================================================================
// 规格 §21/§23 的 +$50 / -$30 是按 $200 账户写的。直接搬到别的余额上会失真,
// 所以只要设了百分比就用百分比 —— 同一份规格在 $200 和 $10,000 上语义一致。
double DailyTargetUSD()
{
   if(InpDailyTargetPct > 0.0)
      return EffectiveBalance() * InpDailyTargetPct / 100.0;
   return InpDailyProfitTarget;
}
double DailyMaxLossUSD()
{
   if(InpDailyMaxLossPct > 0.0)
      return EffectiveBalance() * InpDailyMaxLossPct / 100.0;
   return InpDailyMaxLoss;
}
double ConservativeAtUSD()
{
   if(InpConservativeAtPct > 0.0)
      return EffectiveBalance() * InpConservativeAtPct / 100.0;
   return InpConservativeAt;
}
double ReducedAtUSD()
{
   if(InpReducedAtPct > 0.0)
      return EffectiveBalance() * InpReducedAtPct / 100.0;
   return InpReducedAt;
}

//==================================================================
// 每日统计：从成交历史推导（重启 / 断线也不会重置）
//==================================================================
DayStats GetDayStats()
{
   DayStats s;
   s.realized = 0.0; s.floating = 0.0; s.total = 0.0;
   s.trades = 0; s.consecLoss = 0;

   g_dayStart = DayStart(TimeCurrent());

   // --- 已实现盈亏 + 笔数 + 连亏（按 position_id 聚合）---
   if(HistorySelect(g_dayStart, TimeCurrent() + 3600))
   {
      int total = HistoryDealsTotal();
      // 按 position_id 累计平仓盈亏，并记录最后成交时间用于排序
      ulong  pidArr[];   double pnlArr[];   datetime tArr[];
      ArrayResize(pidArr, 0); ArrayResize(pnlArr, 0); ArrayResize(tArr, 0);

      for(int i = 0; i < total; i++)
      {
         ulong tk = HistoryDealGetTicket(i);
         if(tk == 0) continue;
         if(HistoryDealGetInteger(tk, DEAL_MAGIC)  != InpMagic) continue;
         if(HistoryDealGetString(tk, DEAL_SYMBOL)  != _Symbol)  continue;

         long entry = HistoryDealGetInteger(tk, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_IN) { s.trades++; continue; }
         if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY && entry != DEAL_ENTRY_INOUT) continue;

         double p = HistoryDealGetDouble(tk, DEAL_PROFIT)
                  + HistoryDealGetDouble(tk, DEAL_SWAP)
                  + HistoryDealGetDouble(tk, DEAL_COMMISSION);
         s.realized += p;

         ulong    pid = (ulong)HistoryDealGetInteger(tk, DEAL_POSITION_ID);
         datetime dt  = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);

         int idx = -1;
         for(int k = 0; k < ArraySize(pidArr); k++) if(pidArr[k] == pid) { idx = k; break; }
         if(idx < 0)
         {
            idx = ArraySize(pidArr);
            ArrayResize(pidArr, idx + 1); ArrayResize(pnlArr, idx + 1); ArrayResize(tArr, idx + 1);
            pidArr[idx] = pid; pnlArr[idx] = 0.0; tArr[idx] = 0;
         }
         pnlArr[idx] += p;
         if(dt > tArr[idx]) tArr[idx] = dt;
      }

      // 按平仓时间排序后，从最近往回数连亏
      int n = ArraySize(pidArr);
      for(int a = 0; a < n - 1; a++)
         for(int b = 0; b < n - 1 - a; b++)
            if(tArr[b] > tArr[b+1])
            {
               datetime tt = tArr[b];   tArr[b]   = tArr[b+1];   tArr[b+1]   = tt;
               double   pp = pnlArr[b]; pnlArr[b] = pnlArr[b+1]; pnlArr[b+1] = pp;
               ulong    ii = pidArr[b]; pidArr[b] = pidArr[b+1]; pidArr[b+1] = ii;
            }
      for(int k = n - 1; k >= 0; k--)
      {
         if(pnlArr[k] < 0.0) s.consecLoss++;
         else break;
      }
   }

   // --- 浮动盈亏 ---
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;
      s.floating += pos.Profit() + pos.Swap();
   }

   s.total = s.realized + (InpUseFloatingInLimits ? s.floating : 0.0);
   return s;
}

int CountMyPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() == InpMagic && pos.Symbol() == _Symbol) n++;
   }
   return n;
}

// 现有持仓的方向（多仓下若方向不一致返回 0，用于禁止对冲）
int MyPositionDir()
{
   int d = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;
      int cur = (pos.PositionType() == POSITION_TYPE_BUY) ? 1 : -1;
      if(d == 0) d = cur;
      else if(d != cur) return 0;
   }
   return d;
}

bool HasOpenPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() == InpMagic && pos.Symbol() == _Symbol) return true;
   }
   return false;
}

void CloseAll(string reason)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;
      ulong tk = pos.Ticket();
      double pnl = pos.Profit() + pos.Swap();
      if(trade.PositionClose(tk))
      {
         LogLine("CLOSE", StringFormat("#%I64u 平仓 盈亏 $%.2f：%s", tk, pnl, reason));
         Push(StringFormat("平仓 #%I64u  盈亏 $%.2f  (%s)", tk, pnl, reason));
      }
      else
         LogLine("ERROR", StringFormat("#%I64u 平仓失败 %d %s", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription()));
   }
}

//==================================================================
// 过滤器
//==================================================================
bool SessionOk(string &why)
{
   MqlDateTime st; TimeToStruct(TimeCurrent(), st);
   if(st.day_of_week == 0 || st.day_of_week == 6) { why = "周末，无流动性"; return false; }
   // 周一开盘头一小时 / 周五尾盘：流动性差
   if(st.day_of_week == 1 && st.hour < InpSessionStartHour) { why = "周一开盘流动性不足"; return false; }
   if(st.day_of_week == 5 && st.hour >= InpFlatAllBeforeHour - 2) { why = "周五尾盘，不开新仓"; return false; }
   if(st.hour < InpSessionStartHour || st.hour >= InpSessionEndHour)
   { why = StringFormat("非交易时段（服务器 %02d:%02d）", st.hour, st.min); return false; }
   return true;
}

//------------------------------------------------------------------
// 点差画像
//------------------------------------------------------------------
void ResetSpreadHour(int h)
{
   if(h < 0 || h > 23) return;
   g_spSum[h] = 0.0; g_spCnt[h] = 0; g_spOver[h] = 0;
   g_spMin[h] = DBL_MAX; g_spMax[h] = 0.0;
}

void ReportSpreadHour(int h)
{
   if(h < 0 || h > 23 || g_spCnt[h] <= 0) return;
   double avg     = g_spSum[h] / (double)g_spCnt[h];
   double overPct = 100.0 * (double)g_spOver[h] / (double)g_spCnt[h];
   LogLine("SPREAD", StringFormat(
      "服务器 %02d:00-%02d:59 | 均 %.2f  最低 %.2f  最高 %.2f | 超过上限 %.2f 的时间占 %.0f%% | 样本 %d tick",
      h, h, avg, g_spMin[h], g_spMax[h], InpMaxSpreadUSD, overPct, (int)g_spCnt[h]));
}

// 每个 tick 都记一笔。跨小时时把上一小时的画像打出来 —— 一天 24 行，不刷屏。
void TrackSpread()
{
   MqlDateTime st; TimeToStruct(TimeCurrent(), st);
   int h = st.hour;
   if(h < 0 || h > 23) return;

   if(g_lastSpHour >= 0 && h != g_lastSpHour)
   {
      ReportSpreadHour(g_lastSpHour);
      ReportReasons("本日累计");       // 拒绝原因分布,和点差画像一起每小时一次
      ResetSpreadHour(h);              // 新的一小时从头统计
   }
   g_lastSpHour = h;

   double sp = SpreadUSD();
   if(sp <= 0.0) return;
   g_spSum[h] += sp;
   g_spCnt[h]++;
   if(sp < g_spMin[h]) g_spMin[h] = sp;
   if(sp > g_spMax[h]) g_spMax[h] = sp;
   if(sp > InpMaxSpreadUSD) g_spOver[h]++;
}

double SpreadAvgThisHour()
{
   int h = g_lastSpHour;
   if(h < 0 || h > 23 || g_spCnt[h] <= 0) return 0.0;
   return g_spSum[h] / (double)g_spCnt[h];
}

double SpreadOverPctThisHour()
{
   int h = g_lastSpHour;
   if(h < 0 || h > 23 || g_spCnt[h] <= 0) return 0.0;
   return 100.0 * (double)g_spOver[h] / (double)g_spCnt[h];
}

bool SpreadOk(double atr, string &why)
{
   double sp = SpreadUSD();
   // 拒绝原因要带上「本小时是什么水平」，否则你没法判断该等还是该换时段
   if(sp > InpMaxSpreadUSD)
   { why = StringFormat("点差过大 %.2f > %.2f（本小时均 %.2f，超标时间占 %.0f%%）",
                        sp, InpMaxSpreadUSD, SpreadAvgThisHour(), SpreadOverPctThisHour()); return false; }
   if(atr > 0.0 && sp / atr > InpSpreadVsATRMax)
   { why = StringFormat("点差/ATR 异常 %.3f > %.3f（点差 %.2f / ATR %.2f）",
                        sp / atr, InpSpreadVsATRMax, sp, atr); return false; }
   return true;
}

bool ManualNewsBlocked()
{
   if(StringLen(InpManualNewsTimes) == 0) return false;
   string parts[];
   int n = StringSplit(InpManualNewsTimes, ',', parts);
   MqlDateTime st; TimeToStruct(TimeCurrent(), st);
   int nowMin = st.hour * 60 + st.min;
   for(int i = 0; i < n; i++)
   {
      string p = parts[i];
      StringTrimLeft(p); StringTrimRight(p);
      string hm[];
      if(StringSplit(p, ':', hm) != 2) continue;
      int evMin = (int)StringToInteger(hm[0]) * 60 + (int)StringToInteger(hm[1]);
      if(nowMin >= evMin - InpNewsBeforeMin && nowMin <= evMin + InpNewsAfterMin) return true;
   }
   return false;
}

// 在 [now-afterMin, now+beforeMin] 窗口内是否存在高影响事件。
// 抽出来是为了让「挡新仓」和「事件前清仓」用同一套判断、不同的窗口。
bool NewsInWindow(int beforeMin, int afterMin, string &why)
{
   if(MQLInfoInteger(MQL_TESTER)) return false;      // 日历在策略测试器中不可用

   datetime from = TimeCurrent() - afterMin  * 60;
   datetime to   = TimeCurrent() + beforeMin * 60;

   string curr[3] = {"USD", "EUR", "XAU"};
   for(int c = 0; c < 3; c++)
   {
      MqlCalendarValue vals[];
      int n = CalendarValueHistory(vals, from, to, NULL, curr[c]);
      for(int i = 0; i < n; i++)
      {
         MqlCalendarEvent ev;
         if(!CalendarEventById(vals[i].event_id, ev)) continue;
         if(InpNewsHighOnly && ev.importance != CALENDAR_IMPORTANCE_HIGH) continue;
         if(!InpNewsHighOnly && ev.importance == CALENDAR_IMPORTANCE_NONE) continue;
         why = StringFormat("%s (%s) @ %s", ev.name, curr[c],
                            TimeToString(vals[i].time, TIME_MINUTES));
         return true;
      }
   }
   return false;
}

bool NewsBlocked(string &why)
{
   if(!InpUseNewsFilter) return false;
   if(ManualNewsBlocked()) { why = "手动新闻黑名单时间窗口内"; return true; }
   string ev = "";
   if(NewsInWindow(InpNewsBeforeMin, InpNewsAfterMin, ev))
   { why = "重大数据窗口：" + ev; return true; }
   return false;
}

// 事件前清仓。每个 tick 判断(不等新K线),因为要赶在事件之前而不是之后。
// 手动黑名单同样触发 —— 日历可能取不到数据,这是兜底。
bool NewsFlattenDue(string &why)
{
   if(InpFlatBeforeNewsMin <= 0) return false;
   if(ManualNewsBlocked()) { why = "手动黑名单时间窗口"; return true; }
   string ev = "";
   if(NewsInWindow(InpFlatBeforeNewsMin, 0, ev)) { why = ev; return true; }
   return false;
}

// 市场质量：横盘 / 高频假突破 检测（规则十五）
bool MarketQualityOk(double atr, string &why)
{
   int lookback = 30;

   // 1) 横盘：整段区间相对 ATR 太窄，或者小实体 K 线占比过高
   double hi = -DBL_MAX, lo = DBL_MAX;
   int    smallBody = 0;
   for(int i = 1; i <= lookback; i++)
   {
      double h = iHigh(_Symbol, InpLTF, i);
      double l = iLow (_Symbol, InpLTF, i);
      if(h > hi) hi = h;
      if(l < lo) lo = l;
      if(MathAbs(iClose(_Symbol, InpLTF, i) - iOpen(_Symbol, InpLTF, i)) < 0.25 * atr) smallBody++;
   }
   double range = hi - lo;
   if(range < InpMinRangeATR * atr)
   {
      why = StringFormat("横盘：%d 根 K 线区间仅 %.2f (< %.1f×ATR)", lookback, range, InpMinRangeATR);
      return false;
   }
   if(smallBody > lookback * InpMaxSmallBodyPct / 100.0)
   {
      why = StringFormat("横盘：%d/%d 根为小实体 K 线", smallBody, lookback);
      return false;
   }

   // 2) 高频假突破：反复刺穿前高/前低后收回
   int fakes = 0;
   for(int i = 1; i <= 25; i++)
   {
      double priorHi = -DBL_MAX, priorLo = DBL_MAX;
      for(int k = i + 1; k <= i + 10; k++)
      {
         double h = iHigh(_Symbol, InpLTF, k);
         double l = iLow (_Symbol, InpLTF, k);
         if(h > priorHi) priorHi = h;
         if(l < priorLo) priorLo = l;
      }
      double h1 = iHigh (_Symbol, InpLTF, i);
      double l1 = iLow  (_Symbol, InpLTF, i);
      double c1 = iClose(_Symbol, InpLTF, i);
      if(h1 > priorHi && c1 < priorHi) fakes++;
      if(l1 < priorLo && c1 > priorLo) fakes++;
   }
   if(fakes >= InpMaxFakeBreakouts)
   {
      why = StringFormat("高频假突破：近 25 根内出现 %d 次失败突破", fakes);
      return false;
   }

   why = StringFormat("质量正常（区间 %.2f=%.1f×ATR，小实体 %d/%d，假突破 %d）",
                      range, atr > 0.0 ? range / atr : 0.0, smallBody, lookback, fakes);
   return true;
}

//==================================================================
// 机构参考位：前日高低 / 亚洲盘区间 / 整数关口
//==================================================================
// 全部由价格算出,不需要人工标注、不涉及任何主观判断。
// 这几条线的意义不在于"神奇",而在于**很多人把止损挂在它们外面** ——
// 所以它们既是最可能被测试的目标位,也是最可能发生扫损的地方。
struct KeyLevels
{
   double pdh, pdl;        // 前一日高 / 低
   double asiaHi, asiaLo;  // 最近一个完整亚洲盘的高 / 低
   bool   asiaOk;
};

KeyLevels GetKeyLevels()
{
   KeyLevels k;
   k.pdh = iHigh(_Symbol, PERIOD_D1, 1);
   k.pdl = iLow (_Symbol, PERIOD_D1, 1);
   k.asiaHi = 0.0; k.asiaLo = 0.0; k.asiaOk = false;

   // 亚洲盘区间:从最近的已收盘 K 线往回扫 48 小时,取**最近一个完整**亚洲盘。
   // 用最近一个而不是"今天的",是因为今天的可能还没走完 —— 没走完的区间会
   // 随着时间不断变宽,拿它当参考位等于参考一个还在变的数。
   int    bars   = (int)MathMin(576, Bars(_Symbol, InpLTF) - 2);
   string wantDay = "";
   for(int i = 1; i <= bars; i++)
   {
      datetime bt = iTime(_Symbol, InpLTF, i);
      if(bt == 0) continue;
      MqlDateTime st; TimeToStruct(bt, st);
      if(st.hour < InpAsiaStartHour || st.hour >= InpAsiaEndHour) continue;

      string day = StringFormat("%04d-%02d-%02d", st.year, st.mon, st.day);
      if(wantDay == "")
      {
         // 第一个命中的亚洲盘时段属于哪一天,就锁定哪一天
         // 但若当前时间仍在该日的亚洲盘内,说明这段还没走完,跳到前一天
         MqlDateTime now; TimeToStruct(TimeCurrent(), now);
         string today = StringFormat("%04d-%02d-%02d", now.year, now.mon, now.day);
         bool   inAsiaNow = (now.hour >= InpAsiaStartHour && now.hour < InpAsiaEndHour);
         if(day == today && inAsiaNow) continue;      // 未完成,继续往回找
         wantDay = day;
      }
      if(day != wantDay) break;                       // 已经翻到更早一天,收工

      double h = iHigh(_Symbol, InpLTF, i);
      double l = iLow (_Symbol, InpLTF, i);
      if(!k.asiaOk) { k.asiaHi = h; k.asiaLo = l; k.asiaOk = true; }
      else          { if(h > k.asiaHi) k.asiaHi = h; if(l < k.asiaLo) k.asiaLo = l; }
   }
   return k;
}

// 距 price 上方最近的整数关口
double RoundAbove(double price)
{
   if(InpRoundStep <= 0.0) return 0.0;
   return MathCeil(price / InpRoundStep + 1e-9) * InpRoundStep;
}
double RoundBelow(double price)
{
   if(InpRoundStep <= 0.0) return 0.0;
   return MathFloor(price / InpRoundStep - 1e-9) * InpRoundStep;
}

// 把所有参考位汇总,取 price 上方 / 下方、且距离 >= minDist 的最近一条
bool KeyLevelAbove(double price, double minDist, double &lvl, string &name)
{
   KeyLevels k = GetKeyLevels();
   double cand[5]; string nm[5]; int n = 0;
   if(k.pdh    > 0.0) { cand[n] = k.pdh;    nm[n] = "前日高";   n++; }
   if(k.asiaOk)       { cand[n] = k.asiaHi; nm[n] = "亚洲高";   n++; }
   if(InpUseRoundNumbers) { double r = RoundAbove(price); if(r > 0.0) { cand[n] = r; nm[n] = "整数关口"; n++; } }

   bool found = false; double best = 0.0; string bn = "";
   for(int i = 0; i < n; i++)
   {
      if(cand[i] <= price) continue;
      if(cand[i] - price < minDist) continue;
      if(!found || cand[i] < best) { best = cand[i]; bn = nm[i]; found = true; }
   }
   lvl = best; name = bn;
   return found;
}

bool KeyLevelBelow(double price, double minDist, double &lvl, string &name)
{
   KeyLevels k = GetKeyLevels();
   double cand[5]; string nm[5]; int n = 0;
   if(k.pdl    > 0.0) { cand[n] = k.pdl;    nm[n] = "前日低";   n++; }
   if(k.asiaOk)       { cand[n] = k.asiaLo; nm[n] = "亚洲低";   n++; }
   if(InpUseRoundNumbers) { double r = RoundBelow(price); if(r > 0.0) { cand[n] = r; nm[n] = "整数关口"; n++; } }

   bool found = false; double best = 0.0; string bn = "";
   for(int i = 0; i < n; i++)
   {
      if(cand[i] >= price) continue;
      if(price - cand[i] < minDist) continue;
      if(!found || cand[i] > best) { best = cand[i]; bn = nm[i]; found = true; }
   }
   lvl = best; name = bn;
   return found;
}

//==================================================================
// 入场 C：流动性扫损后反手
//==================================================================
// 定义(全部可机械判定,无主观成分):
//   上一根已收盘 K 线的最高价**刺穿**了某条关键位,但收盘又回到该位之下
//   -> 那个方向的突破没有承接,挂在关键位上方的止损被扫了一遍
//   -> 顺 H1 趋势方向反手
// 刺穿深度设上下限:太浅是噪音,太深说明是真突破而不是扫损。
bool SweepEntry(int dir, double atr, double &refLevel, string &note)
{
   if(!InpUseSweepEntry || !InpUseKeyLevels) return false;

   double h1 = iHigh (_Symbol, g_entryTF, 1);
   double l1 = iLow  (_Symbol, g_entryTF, 1);
   double c1 = iClose(_Symbol, g_entryTF, 1);
   double o1 = iOpen (_Symbol, g_entryTF, 1);
   double minPen = InpSweepMinPenetration * atr;
   double maxPen = InpSweepMaxPenetration * atr;

   KeyLevels k = GetKeyLevels();
   double cand[6]; string nm[6]; int n = 0;

   if(dir > 0)
   {
      // 做多:要找**被向下刺穿又收回**的支撑
      if(k.pdl > 0.0) { cand[n] = k.pdl;    nm[n] = "前日低"; n++; }
      if(k.asiaOk)    { cand[n] = k.asiaLo; nm[n] = "亚洲低"; n++; }
      if(InpUseRoundNumbers) { double r = RoundBelow(o1); if(r > 0.0) { cand[n] = r; nm[n] = "整数关口"; n++; } }

      for(int i = 0; i < n; i++)
      {
         double lv = cand[i];
         double pen = lv - l1;                       // 刺穿深度
         if(pen < minPen || pen > maxPen) continue;  // 太浅=噪音,太深=真跌破
         if(c1 <= lv) continue;                      // 必须收回该位之上
         if(c1 <= o1) continue;                      // 且是一根阳线
         refLevel = lv;
         note = StringFormat("扫损反手：下破%s %.2f 后收回（刺穿 %.2f=%.2fATR）",
                             nm[i], lv, pen, atr > 0 ? pen / atr : 0.0);
         return true;
      }
   }
   else if(dir < 0)
   {
      if(k.pdh > 0.0) { cand[n] = k.pdh;    nm[n] = "前日高"; n++; }
      if(k.asiaOk)    { cand[n] = k.asiaHi; nm[n] = "亚洲高"; n++; }
      if(InpUseRoundNumbers) { double r = RoundAbove(o1); if(r > 0.0) { cand[n] = r; nm[n] = "整数关口"; n++; } }

      for(int i = 0; i < n; i++)
      {
         double lv = cand[i];
         double pen = h1 - lv;
         if(pen < minPen || pen > maxPen) continue;
         if(c1 >= lv) continue;
         if(c1 >= o1) continue;
         refLevel = lv;
         note = StringFormat("扫损反手：上破%s %.2f 后收回（刺穿 %.2f=%.2fATR）",
                             nm[i], lv, pen, atr > 0 ? pen / atr : 0.0);
         return true;
      }
   }
   return false;
}

//==================================================================
// 结构分析
//==================================================================
// 找最近的 swing high；shift 从 startShift 开始往回
bool FindSwingHigh(ENUM_TIMEFRAMES tf, int startShift, int lookback, int strength,
                   double &price, int &atShift)
{
   for(int i = startShift + strength; i < startShift + lookback; i++)
   {
      double h = iHigh(_Symbol, tf, i);
      bool ok = true;
      for(int k = 1; k <= strength; k++)
         if(iHigh(_Symbol, tf, i - k) >= h || iHigh(_Symbol, tf, i + k) >= h) { ok = false; break; }
      if(ok) { price = h; atShift = i; return true; }
   }
   return false;
}

bool FindSwingLow(ENUM_TIMEFRAMES tf, int startShift, int lookback, int strength,
                  double &price, int &atShift)
{
   for(int i = startShift + strength; i < startShift + lookback; i++)
   {
      double l = iLow(_Symbol, tf, i);
      bool ok = true;
      for(int k = 1; k <= strength; k++)
         if(iLow(_Symbol, tf, i - k) <= l || iLow(_Symbol, tf, i + k) <= l) { ok = false; break; }
      if(ok) { price = l; atShift = i; return true; }
   }
   return false;
}

// 最近的、位于 price 上方的 swing 高点（= 前方阻力）
// minDist：小于这个距离的关键位视为噪音、直接跳过。传 0 = 取真正最近的那个
// （持仓管理里的「逼近关键位就落袋」正需要最近的，所以那边传 0）。
bool NearestResistance(double price, double minDist, double &lvl)
{
   bool found = false; double best = 0.0;
   int str = InpSwingStrength + 1;
   int maxShift = InpStructureLookback * 2;
   for(int i = 1 + str; i < maxShift; i++)
   {
      double h = iHigh(_Symbol, InpLTF, i);
      if(h <= price + _Point) continue;
      if(h - price < minDist) continue;
      bool ok = true;
      for(int k = 1; k <= str; k++)
         if(iHigh(_Symbol, InpLTF, i - k) >= h || iHigh(_Symbol, InpLTF, i + k) >= h) { ok = false; break; }
      if(!ok) continue;
      if(!found || h < best) { best = h; found = true; }
   }
   lvl = best;
   return found;
}

// 最近的、位于 price 下方的 swing 低点（= 前方支撑）
bool NearestSupport(double price, double minDist, double &lvl)
{
   bool found = false; double best = 0.0;
   int str = InpSwingStrength + 1;
   int maxShift = InpStructureLookback * 2;
   for(int i = 1 + str; i < maxShift; i++)
   {
      double l = iLow(_Symbol, InpLTF, i);
      if(l >= price - _Point) continue;
      if(price - l < minDist) continue;
      bool ok = true;
      for(int k = 1; k <= str; k++)
         if(iLow(_Symbol, InpLTF, i - k) <= l || iLow(_Symbol, InpLTF, i + k) <= l) { ok = false; break; }
      if(!ok) continue;
      if(!found || l > best) { best = l; found = true; }
   }
   lvl = best;
   return found;
}

// 市场结构：+1 = HH/HL（多），-1 = LH/LL（空），0 = 混乱
int MarketStructure(ENUM_TIMEFRAMES tf)
{
   double h1, h2, l1, l2; int s1, s2, s3, s4;
   if(!FindSwingHigh(tf, 1, InpStructureLookback, InpSwingStrength, h1, s1)) return 0;
   if(!FindSwingHigh(tf, s1 + 1, InpStructureLookback, InpSwingStrength, h2, s2)) return 0;
   if(!FindSwingLow (tf, 1, InpStructureLookback, InpSwingStrength, l1, s3)) return 0;
   if(!FindSwingLow (tf, s3 + 1, InpStructureLookback, InpSwingStrength, l2, s4)) return 0;

   if(h1 > h2 && l1 > l2) return  1;
   if(h1 < h2 && l1 < l2) return -1;
   return 0;
}

// HTF 趋势
// 纯K线方向（模式 4）：
//   1) 触发周期的摆动结构 —— 更高高点+更高低点 = 多，反之 = 空
//   2) 退到 InpLTF 的结构
//   3) 两级结构都判不出来时，看最近 InpPaBars 根K线的净推进，
//      幅度要超过 InpPaMinATR × ATR 才算数（否则是横盘噪音）
int PriceActionDir(double atr)
{
   // 1) 摆动结构：更高高点+更高低点 = 多，反之 = 空
   int st = MarketStructure(g_entryTF);
   if(st == 0) st = MarketStructure(InpLTF);

   // 2) 近期净推进：用 InpLTF（不是触发周期）。M1 的几根只有几分钟，
   //    一波一小时的行情在那个窗口里看不见。
   int mo = 0;
   int n = MathMax(2, InpPaBars);
   double c1 = iClose(_Symbol, InpLTF, 1);
   double cn = iClose(_Symbol, InpLTF, n);
   if(c1 > 0.0 && cn > 0.0 && atr > 0.0)
   {
      double net = c1 - cn;
      if(MathAbs(net) >= InpPaMinATR * atr) mo = (net > 0.0) ? 1 : -1;
   }

   // 3) 两者分歧 -> **不做**。
   //    这是这个函数最要紧的一条。MarketStructure 回看 InpStructureLookback(60)
   //    根找摆动点，一波大跌之后它会在几小时里一直读"向下"，哪怕价格早已反弹回去 ——
   //    实盘就是这么在反弹途中连开空单的。结构和近期推进对不上时，
   //    正确答案是"看不清"，不是"听结构的"。
   if(st != 0 && mo != 0) return (st == mo) ? st : 0;
   if(mo != 0) return mo;      // 结构不明 -> 听近期推进
   return st;                  // 近期没推进 -> 听结构
}

int HtfTrend()
{
   double f = Buf(hEmaFastH, 0, 1);
   double s = Buf(hEmaSlowH, 0, 1);
   double fPrev = Buf(hEmaFastH, 0, 4);
   double c = iClose(_Symbol, InpHTF, 1);
   if(f <= 0.0 || s <= 0.0) return 0;
   bool upSide   = (!InpHtfRequireCloseSide || c > f);
   bool downSide = (!InpHtfRequireCloseSide || c < f);
   bool upSlope  = (!InpHtfRequireSlope     || f > fPrev);
   bool downSlope= (!InpHtfRequireSlope     || f < fPrev);
   if(f > s && upSide   && upSlope)   return  1;
   if(f < s && downSide && downSlope) return -1;
   return 0;
}

// LTF 趋势
int LtfTrend()
{
   double f = Buf(hEmaFastL, 0, 1);
   double s = Buf(hEmaSlowL, 0, 1);
   double c = iClose(_Symbol, InpLTF, 1);
   if(f <= 0.0 || s <= 0.0) return 0;
   if(f > s && (!InpLtfRequireCloseSide || c > s)) return  1;
   if(f < s && (!InpLtfRequireCloseSide || c < s)) return -1;
   return 0;
}

// 动量：+1 / -1 / 0
int Momentum()
{
   double rsi  = Buf(hRsiL, 0, 1);
   double rsiP = Buf(hRsiL, 0, 3);
   double plusDI  = Buf(hAdxL, 1, 1);
   double minusDI = Buf(hAdxL, 2, 1);
   if(rsi <= 0.0) return 0;
   if(rsi > 52.0 && rsi >= rsiP && plusDI  > minusDI) return  1;
   if(rsi < 48.0 && rsi <= rsiP && minusDI > plusDI)  return -1;
   return 0;
}

// 假突破检测：最近 N 根内是否出现"刺穿关键位后收回"的失败突破
bool FakeBreakoutAgainst(int dir, double level)
{
   for(int i = 1; i <= InpBreakoutLookback; i++)
   {
      double h = iHigh(_Symbol, g_entryTF, i);
      double l = iLow (_Symbol, g_entryTF, i);
      double c = iClose(_Symbol, g_entryTF, i);
      if(dir > 0 && h > level && c < level) return true;   // 上破失败
      if(dir < 0 && l < level && c > level) return true;   // 下破失败
   }
   return false;
}

// 长影线拒绝（做多时上影线过长 = 抛压）
bool WickRejection(int dir, int shift)
{
   double o = iOpen (_Symbol, g_entryTF, shift);
   double h = iHigh (_Symbol, g_entryTF, shift);
   double l = iLow  (_Symbol, g_entryTF, shift);
   double c = iClose(_Symbol, g_entryTF, shift);
   double rng = h - l;
   if(rng <= 0.0) return false;
   if(dir > 0) return ((h - MathMax(o, c)) / rng) > InpWickRejectPct;
   else        return ((MathMin(o, c) - l) / rng) > InpWickRejectPct;
}

// 触发条件：突破回踩 或 趋势回调确认
// 返回 true 并给出 note
bool EntryTrigger(int dir, double atr, double &refLevel, string &note)
{
   double swH, swL; int sH, sL;
   bool okH = FindSwingHigh(g_entryTF, 1, InpStructureLookback, InpSwingStrength, swH, sH);
   bool okL = FindSwingLow (g_entryTF, 1, InpStructureLookback, InpSwingStrength, swL, sL);

   double c1 = iClose(_Symbol, g_entryTF, 1);
   double o1 = iOpen (_Symbol, g_entryTF, 1);
   double h1 = iHigh (_Symbol, g_entryTF, 1);
   double l1 = iLow  (_Symbol, g_entryTF, 1);
   double ema20 = Buf(hEmaFastL, 0, 1);
   double tol   = InpTriggerTolATR * atr;

   if(dir > 0)
   {
      if(!okH) return false;
      refLevel = swH;

      // A) 有效突破 + 回踩确认
      bool broke = false;
      for(int i = 1; i <= InpBreakoutLookback; i++)
         if(iClose(_Symbol, g_entryTF, i) > swH + 0.10 * atr) { broke = true; break; }
      if(broke && l1 <= swH + tol && c1 > swH && c1 > o1)
      {
         if(FakeBreakoutAgainst(1, swH)) { note = "上破后出现假突破迹象"; return false; }
         if(WickRejection(1, 1))         { note = "回踩K线上影线过长"; return false; }
         note = "阻力突破 + 回踩确认";
         return true;
      }

      // B) 趋势回调至 EMA20 / 支撑，出现看涨拒绝
      if(okL && ema20 > 0.0)
      {
         bool pulled = (l1 <= ema20 + tol) || (l1 <= swL + tol && swL < c1);
         bool bull   = (c1 > o1) && ((c1 - l1) / MathMax(h1 - l1, _Point) > InpBarCloseStrength);
         if(pulled && bull)
         {
            if(WickRejection(1, 1)) { note = "回调K线上影线过长"; return false; }
            note = "趋势回调 + 支撑确认";
            return true;
         }
      }
   }
   else if(dir < 0)
   {
      if(!okL) return false;
      refLevel = swL;

      bool broke = false;
      for(int i = 1; i <= InpBreakoutLookback; i++)
         if(iClose(_Symbol, g_entryTF, i) < swL - 0.10 * atr) { broke = true; break; }
      if(broke && h1 >= swL - tol && c1 < swL && c1 < o1)
      {
         if(FakeBreakoutAgainst(-1, swL)) { note = "下破后出现假突破迹象"; return false; }
         if(WickRejection(-1, 1))         { note = "反抽K线下影线过长"; return false; }
         note = "支撑跌破 + 反抽确认";
         return true;
      }

      if(okH && ema20 > 0.0)
      {
         bool pulled = (h1 >= ema20 - tol) || (h1 >= swH - tol && swH > c1);
         bool bear   = (c1 < o1) && ((h1 - c1) / MathMax(h1 - l1, _Point) > InpBarCloseStrength);
         if(pulled && bear)
         {
            if(WickRejection(-1, 1)) { note = "反弹K线下影线过长"; return false; }
            note = "趋势反弹 + 阻力确认";
            return true;
         }
      }
   }
   return false;
}

//==================================================================
// V2：波动率分档（规格 §13）
//==================================================================
// 用 ATR 与**它自己的均值**的比值分档,不用绝对数。
// 金价从 $2000 到 $4400,同一个"$3 算不算大波动"早就不是一回事了。
// 0=Low 1=Normal 2=High 3=Extreme
int VolRegime(double atr, double &ratioOut)
{
   ratioOut = 1.0;
   if(!InpUseVolRegime || atr <= 0.0) return 1;

   double buf[];
   int n = InpAtrAvgPeriod;
   if(CopyBuffer(hAtrL, 0, 1, n, buf) < n) return 1;
   double sum = 0.0;
   for(int i = 0; i < n; i++) sum += buf[i];
   double avg = sum / n;
   if(avg <= 0.0) return 1;

   double r = atr / avg;
   ratioOut = r;
   if(r >= InpVolExtremeMult) return 3;
   if(r >= InpVolHighMult)    return 2;
   if(r <= 0.60)              return 0;
   return 1;
}

string VolRegimeName(int v)
{
   if(v == 0) return "Low";
   if(v == 2) return "High";
   if(v == 3) return "Extreme";
   return "Normal";
}

//==================================================================
// V2：BOS / CHoCH（规格 §8/§9）
//==================================================================
// ⚠️ 用的是**本文件给定的机械定义**,不是任何权威定义 —— 各家讲法互相矛盾,
//    不写死就没法回测。定义:
//      BOS(dir>0) = 最近一根已收盘K线的收盘价 > 最近一个**已确认**摆动高 + 缓冲
//      BOS(dir<0) = 收盘价 < 最近一个已确认摆动低 - 缓冲
//      CHoCH      = 该 BOS 的方向与当前 tf 的结构方向相反（性质改变）
//    "已确认"= 摆动点右侧已走出 InpSwingStrength 根K线（FindSwingHigh/Low 保证）。
bool StructureBreak(ENUM_TIMEFRAMES tf, int dir, double atr, bool &isChoch, string &note)
{
   isChoch = false; note = "";
   if(!InpUseBOS) return false;

   double sw; int at;
   double c1  = iClose(_Symbol, tf, 1);
   double buf = InpBosBufferATR * atr;

   if(dir > 0)
   {
      if(!FindSwingHigh(tf, 1, InpStructureLookback, InpSwingStrength, sw, at)) return false;
      if(c1 <= sw + buf) return false;
   }
   else if(dir < 0)
   {
      if(!FindSwingLow(tf, 1, InpStructureLookback, InpSwingStrength, sw, at)) return false;
      if(c1 >= sw - buf) return false;
   }
   else return false;

   int st = MarketStructure(tf);          // 当前结构方向
   isChoch = (st != 0 && st != dir);      // 与结构反向 = 性质改变
   note = StringFormat("%s %s %.2f", isChoch ? "CHoCH" : "BOS",
                       dir > 0 ? "上破" : "下破", sw);
   return true;
}

//==================================================================
// V2：10 分制评分与分级（规格 §28/§29）
//==================================================================
struct SetupScore
{
   int    trend;      // 0-2
   int    keyLevel;   // 0-2
   int    liquidity;  // 0-2
   int    structure;  // 0-2
   int    momentum;   // 0-1
   int    rr;         // 0-1
   int    total;      // 0-10
   string grade;      // A+ / A / B / C
   double riskCapPct; // 该等级允许的风险上限
   string detail;
};

string GradeOf(int total)
{
   if(total >= InpScoreMinAPlus) return "A+";
   if(total >= InpScoreMinA)     return "A";
   if(total >= InpScoreMinB)     return "B";
   return "C";
}

double RiskCapForGrade(string g)
{
   if(g == "A+") return InpRiskPctAPlus;
   if(g == "A")  return InpRiskPctA;
   if(g == "B")  return InpRiskPctB;
   return 0.0;                        // C 级不交易
}

// dir/atr 已定；sweptLevel!=0 表示本次触发来自扫损；rrVal 为实际风险回报
SetupScore ScoreSetupV2(int dir, double atr, bool fromSweep, bool nearKeyLevel,
                        double rrVal, double entry)
{
   SetupScore sc;
   sc.trend = 0; sc.keyLevel = 0; sc.liquidity = 0;
   sc.structure = 0; sc.momentum = 0; sc.rr = 0;

   // --- Trend 0-2：H1 均线方向 + H1 摆动结构（HH/HL 或 LH/LL）---
   int htf   = HtfTrend();
   int htfSt = MarketStructure(InpHTF);
   if(htf == dir)   sc.trend++;
   if(htfSt == dir) sc.trend++;

   // --- Key Level 0-2：入场是否贴着机构参考位 ---
   if(nearKeyLevel) sc.keyLevel++;
   double lv = 0.0; string nmA = "", nmB = "";
   // 前方还有明确目标位 = 有去处,不是撞墙
   if(dir > 0 ? KeyLevelAbove(entry, 0.0, lv, nmA) : KeyLevelBelow(entry, 0.0, lv, nmB))
      sc.keyLevel++;

   // --- Liquidity 0-2 ---
   // 只在"由扫损触发"时给分的话,非扫损路径这一维恒为 0,天花板掉到 8 分,
   // 大量合格 setup 会因此掉进 C 级被拒 —— 评分本身就成了新的一道墙。
   // 规格 §28 的 Liquidity 指的是"是否在流动性区域交易",扫损只是其中最强的一种。
   if(fromSweep)           sc.liquidity += 2;   // 实际发生了扫损 = 最强
   else if(nearKeyLevel)   sc.liquidity += 1;   // 在流动性池附近入场

   // --- Structure 0-2：M15 结构一致 + M5 出现 BOS/CHoCH ---
   if(MarketStructure(InpMTF) == dir) sc.structure++;
   bool choch = false; string bnote = "";
   if(StructureBreak(InpLTF, dir, atr, choch, bnote)) sc.structure++;

   // --- Momentum 0-1 ---
   if(Momentum() == dir) sc.momentum++;

   // --- RR 0-1 ---
   if(rrVal >= 1.5) sc.rr++;

   sc.total = sc.trend + sc.keyLevel + sc.liquidity + sc.structure + sc.momentum + sc.rr;
   sc.grade = GradeOf(sc.total);
   sc.riskCapPct = RiskCapForGrade(sc.grade);
   sc.detail = StringFormat("趋势%d/2 关键位%d/2 流动性%d/2 结构%d/2 动能%d/1 RR%d/1%s",
                            sc.trend, sc.keyLevel, sc.liquidity, sc.structure,
                            sc.momentum, sc.rr,
                            StringLen(bnote) > 0 ? " | " + bnote : "");
   return sc;
}

//==================================================================
// 入场 D：宽松顺势（采样用，质量最低的一条）
//==================================================================
// 条件只有三个:趋势方向已确定(调用处保证)、上一根收盘顺势、价格没有过度偏离快线。
// 最后一条是唯一的纪律 —— 没有它就变成"暴涨之后追多",那是规格 §12 明令禁止的 FOMO。
bool LooseEntry(int dir, double atr, string &note)
{
   if(!InpUseLooseEntry) return false;

   double c1 = iClose(_Symbol, g_entryTF, 1);
   double o1 = iOpen (_Symbol, g_entryTF, 1);
   double ema = Buf(hEmaFastL, 0, 1);
   if(ema <= 0.0 || atr <= 0.0) return false;

   if(dir > 0 && c1 <= o1) return false;          // 顺势收盘
   if(dir < 0 && c1 >= o1) return false;

   double dist = MathAbs(c1 - ema);
   if(dist > InpLooseMaxDistATR * atr)
   {
      note = StringFormat("宽松入场被拒：价格偏离快线 %.2f > %.2f×ATR（追高/追空）",
                          dist, InpLooseMaxDistATR);
      return false;
   }

   note = StringFormat("宽松顺势（偏离快线 %.2f = %.2fATR）", dist, dist / atr);
   return true;
}

//==================================================================
// 构建信号
//==================================================================
Signal BuildSignal(double atr, int minScore)
{
   Signal sg;
   sg.dir = 0; sg.score = 0; sg.entry = 0; sg.sl = 0; sg.tp1 = 0; sg.tp2 = 0; sg.rr = 0; sg.note = "";
   sg.grade = "C"; sg.riskCapPct = 0.0; sg.scoreDetail = "";

   int htf  = HtfTrend();
   int ltf  = LtfTrend();
   int strc = MarketStructure(InpLTF);
   int mom  = Momentum();
   double adx = Buf(hAdxL, 0, 1);

   // --- 方向判定 ---
   int dir = 0;
   if(InpDirectionMode == 1)
      dir = htf;                                   // H1 定方向，M5 交给评分
   else if(InpDirectionMode == 2)
      dir = (htf != 0) ? htf : ltf;                // H1 有方向听 H1，H1 中性才听 M5
   else if(InpDirectionMode == 3)
      dir = ltf;                                   // M5 定方向，H1 只进评分
   else if(InpDirectionMode == 4)
      dir = PriceActionDir(atr);                   // 纯K线：摆动结构 + 净推进
   else
   {
      if(htf > 0 && ltf > 0) dir =  1;             // 原行为：必须同向
      else if(htf < 0 && ltf < 0) dir = -1;
   }
   if(dir == 0)
   { NoTrade(StringFormat("趋势不一致 HTF=%d LTF=%d（模式%d）", htf, ltf, InpDirectionMode)); return sg; }
   if(dir > 0) g_dirBuy++; else g_dirSell++;

   // --- 逆势闸门：最近几根K线正在往我的反方向走，就不做 ---
   if(InpCounterMoveATR > 0.0 && atr > 0.0)
   {
      int nb = MathMax(2, InpCounterMoveBars);
      double cNow = iClose(_Symbol, InpLTF, 1);
      double cOld = iClose(_Symbol, InpLTF, nb);
      if(cNow > 0.0 && cOld > 0.0)
      {
         double against = (cOld - cNow) * dir;   // >0 = 这几根在往我的反方向走

         // 两级阈值。软的那级要配合"最新一根仍在继续"才否决 —— 否则会把
         // **趋势回调**一起毙掉（回调的定义就是最近几根在往反方向走，
         // 而入场 B 等的正是这一刻）。
         // 但只有软的一级不够：一波反弹里 K 线红绿交替，随便一根反向的
         // 就让它放行。所以再加一级硬阈值：逆向走得够远时，**不管最新一根
         // 是什么颜色一律否决** —— 一小时的反弹不会因为出现一根阴线就变成回调。
         double cPrev = iClose(_Symbol, InpLTF, 2);
         bool stillAgainst = (cPrev > 0.0) ? (((cNow - cPrev) * dir) < 0.0) : true;

         bool hardBlock = (InpCounterMoveHardATR > 0.0 &&
                           against > InpCounterMoveHardATR * atr);
         bool softBlock = (against > InpCounterMoveATR * atr && stillAgainst);

         if(hardBlock || softBlock)
         {
            NoTrade(StringFormat("最近 %d 根%s逆向走了 $%.2f（%.2f×ATR，%s），不做%s",
                    nb, EnumToString(InpLTF), against, against / atr,
                    hardBlock ? "超硬阈值" : "仍在继续", dir > 0 ? "多" : "空"));
            return sg;
         }
      }
   }

   // --- 冲突：否决 还是 只记录 ---
   // 回调行情里结构与动量必然与大方向冲突。把它们当否决条件,等于永远做不了回调。
   // 关掉否决后冲突不消失,只是改为记录 —— 事后能按"有无冲突"分组比期望值。
   string conflicts = "";
   if(strc != 0 && strc != dir) conflicts += "结构冲突 ";
   if(mom  != 0 && mom  != dir) conflicts += "动量冲突 ";
   if(ltf  != 0 && ltf  != dir) conflicts += "M5反向 ";
   if(InpConflictAsVeto && StringLen(conflicts) > 0)
   { NoTrade(StringFormat("与方向冲突：%s", conflicts)); return sg; }

   if(adx < InpAdxMin)          { NoTrade(StringFormat("ADX %.1f < %.1f，横盘", adx, InpAdxMin)); return sg; }

   // 评分（满分 7）
   int score = 0;
   if(htf == dir)  score++;                       // 1 高周期趋势
   if(ltf == dir)  score++;                       // 2 当前周期趋势
   if(strc == dir) score++;                       // 3 市场结构
   if(mom == dir)  score++;                       // 4 动量
   if(adx >= InpAdxMin + 6.0) score++;            // 5 趋势强度
   double refLevel = 0.0; string trigNote = "";
   bool trig = EntryTrigger(dir, atr, refLevel, trigNote);
   // 入场 C：突破回踩/趋势回调都没触发时，再看有没有关键位被扫损后收回。
   // 放在最后是因为它是**补充**路径，不该抢掉前两条的判定。
   bool fromSweep = false;
   if(!trig) { trig = SweepEntry(dir, atr, refLevel, trigNote); fromSweep = trig; }
   // 路径 D 放在最后:只有前三条形态都没出现时才用它兜底
   if(!trig) trig = LooseEntry(dir, atr, trigNote);
   if(trig) score += 2;                           // 6-7 触发（突破回踩 / 回调确认 / 扫损反手）

   if(!trig)
   {
      NoTrade(StringLen(trigNote) > 0 ? trigNote : "无有效突破/回踩触发");
      return sg;
   }
   if(score < minScore)
   {
      NoTrade(StringFormat("确认分不足 %d/%d", score, minScore));
      return sg;
   }

   // --- 入场价 / 止损 ---
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double entry = (dir > 0) ? ask : bid;

   // 止损跟着**触发根**走 —— 触发在 M1 就用 M1 的结构，否则会出现
   // "M1 进场却背着 M5 的宽止损"这种前后不一致的仓位。
   double swH, swL; int sH, sL;
   bool okH = FindSwingHigh(g_entryTF, 1, InpStructureLookback, InpSwingStrength, swH, sH);
   bool okL = FindSwingLow (g_entryTF, 1, InpStructureLookback, InpSwingStrength, swL, sL);
   if(!okH || !okL) { NoTrade("找不到有效 swing 结构"); return sg; }

   double sl;
   if(dir > 0) sl = MathMin(swL, iLow(_Symbol, g_entryTF, 1)) - InpSlAtrMult * atr * 0.5;
   else        sl = MathMax(swH, iHigh(_Symbol, g_entryTF, 1)) + InpSlAtrMult * atr * 0.5;

   double slDist = MathAbs(entry - sl);
   // 结构止损过近 -> 用 ATR 兜底；过远 -> 放弃（不是缩止损，而是不做）
   if(slDist < MathMax(InpSlMinUSD, StopsLevelUSD() + SpreadUSD()))
   {
      slDist = MathMax(InpSlMinUSD, MathMax(StopsLevelUSD() + SpreadUSD(), InpSlAtrMult * atr));
      sl = (dir > 0) ? entry - slDist : entry + slDist;
   }
   double slMax = InpSlMaxUSD;
   if(InpSlMaxATRMult > 0.0) slMax = MathMax(slMax, atr * InpSlMaxATRMult);
   if(slDist > slMax)
   {
      if(InpClampWideStop)
      {
         // 把止损收到上限照做 —— 止损硬锁在 slMax，不再因为结构宽而拒单。
         // 代价：止损比结构位近，更容易被噪音扫到；换来的是高波动里也能入场。
         slDist = slMax;
         sl = (dir > 0) ? entry - slDist : entry + slDist;
      }
      else
      {
         NoTrade(StringFormat("结构止损过宽 %.2f > %.2f USD（ATR %.2f）", slDist, slMax, atr));
         return sg;
      }
   }

   // --- 目标：受前方最近的关键位限制 ---
   double tp1 = (dir > 0) ? entry + InpTP1_R * slDist : entry - InpTP1_R * slDist;
   double tp2 = (dir > 0) ? entry + InpTP2_R * slDist : entry - InpTP2_R * slDist;

   double buffer = 0.15 * atr;
   double lvl = 0.0;
   // 止盈的天花板取「M5 摆动点」与「机构参考位」中**更近**的那个 —— 更近的
   // 才是先撞上的墙。两者都要越过 ignore 距离,近于此的一律当噪音跳过。
   double ignore  = InpLevelIgnoreR * slDist;
   string lvlName = "";
   bool   gotLvl  = false;
   double kl = 0.0; string kn = "";

   if(dir > 0)
   {
      if(NearestResistance(entry, ignore, lvl)) { gotLvl = true; lvlName = "M5摆动高"; }
      if(InpUseKeyLevels && KeyLevelAbove(entry, ignore, kl, kn))
         if(!gotLvl || kl < lvl) { lvl = kl; lvlName = kn; gotLvl = true; }
      if(gotLvl && (lvl - buffer) < tp2) tp2 = lvl - buffer;
   }
   else
   {
      if(NearestSupport(entry, ignore, lvl)) { gotLvl = true; lvlName = "M5摆动低"; }
      if(InpUseKeyLevels && KeyLevelBelow(entry, ignore, kl, kn))
         if(!gotLvl || kl > lvl) { lvl = kl; lvlName = kn; gotLvl = true; }
      if(gotLvl && (lvl + buffer) > tp2) tp2 = lvl + buffer;
   }
   if(gotLvl) trigNote += StringFormat(" | 止盈受限于%s %.2f", lvlName, lvl);

   double rr = (tp2 - entry) * dir / MathMax(slDist, _Point);
   // 固定金额目标模式下不查 RR:止盈由金额决定,RR 只是它的**结果**,
   // 拿结果去否决前提会把所有信号挡光。风险由 InpRiskCapUSD 控,不靠 RR 门槛。
   // 出场若是固定金额（挂在目标价 或 净盈利到点就走），"到下一个关键位有多远"
   // 这个 RR 就不再是我们实际拿到的盈亏比了，拿它当门槛只会白挡信号。
   if(InpTargetProfitUSD <= 0.0 && InpQuickProfitUSD <= 0.0 && rr < InpMinRR)
   {
      NoTrade(StringFormat("风险回报不足 RR=%.2f < %.2f（前方关键位太近）", rr, InpMinRR));
      return sg;
   }

   // --- V2：10 分制评分与分级（规格 §28/§29）---
   // 必须放在 rr 算出来之后 —— RR 本身是评分的一个维度。
   if(InpUseV2Scoring)
   {
      // 入场是否贴着机构参考位（0.5×ATR 以内算"在关键位上"）
      double nearLv = 0.0; string nearNm = "";
      bool nearKey = (dir > 0)
                     ? KeyLevelBelow(entry, 0.0, nearLv, nearNm)
                     : KeyLevelAbove(entry, 0.0, nearLv, nearNm);
      if(nearKey) nearKey = (MathAbs(entry - nearLv) <= 0.5 * atr);

      SetupScore v2 = ScoreSetupV2(dir, atr, fromSweep, nearKey, rr, entry);
      sg.score       = v2.total;
      sg.grade       = v2.grade;
      sg.riskCapPct  = v2.riskCapPct;
      sg.scoreDetail = v2.detail;

      if(v2.grade == "C")
      {
         NoTrade(StringFormat("C 级 setup %d/10 不交易（%s）", v2.total, v2.detail));
         sg.dir = 0;
         return sg;
      }
      trigNote += StringFormat(" | %s级 %d/10", v2.grade, v2.total);
   }
   else
   {
      sg.grade      = "-";
      sg.riskCapPct = InpRiskPctMax;
   }

   // --- 信号倒转（诊断）---
   // 以入场价为轴镜像反射,R 距离原样保留,方向取反。
   if(InpInvertSignals)
   {
      double e = entry;
      sl  = 2.0 * e - sl;          // 原来在下方的止损,反射到上方(反之亦然)
      tp1 = 2.0 * e - tp1;
      tp2 = 2.0 * e - tp2;
      dir = -dir;
      trigNote += " | 【倒转】原方向 " + (dir > 0 ? "空" : "多");
      // 面板的「判多/判空」故意**不**跟着翻 —— 它统计的是方向闸门的判断，
      // 用来查闸门有没有卡死；倒转后实际做了哪边，看「开多/开空」那两个数。
   }

   sg.dir   = dir;
   if(!InpUseV2Scoring) sg.score = score;
   sg.entry = entry;
   sg.sl    = Px(sl);
   sg.tp1   = Px(tp1);
   sg.tp2   = Px(tp2);
   sg.rr    = rr;
   sg.note  = trigNote + (StringLen(conflicts) > 0 ? " | 冲突:" + conflicts : " | 无冲突");
   return sg;
}

//==================================================================
// 仓位计算（严格按风险金额倒推，永不满仓）
//==================================================================
double CalcLot(double slDistUSD, double riskMoney, string &why)
{
   double mppd = MoneyPerLotPerDollar();       // 每手每 $1 金价波动的美元盈亏
   if(mppd <= 0.0) { why = "无法获取合约规格"; return 0.0; }

   double lotMinF = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMaxF = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   // --- 固定手数：绕过风险反算，但保留手数与保证金的硬约束 ---
   if(InpFixedLot > 0.0)
   {
      double flot = FloorToStep(InpFixedLot);
      if(flot < lotMinF)
      { why = StringFormat("固定手数 %s 低于品种最小手 %s",
              DoubleToString(InpFixedLot, VolDigits()),
              DoubleToString(lotMinF, VolDigits())); return 0.0; }
      if(flot > lotMaxF) flot = lotMaxF;

      // 保证金检查（和下面风险路径同一套逻辑）
      double fmargin = 0.0;
      double fprice  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      if(!OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, flot, fprice, fmargin))
      { why = "保证金计算失败"; return 0.0; }
      double fcap = EffectiveFreeMargin() * InpMaxMarginPctPerPos / 100.0;
      if(fmargin > fcap)
      { why = StringFormat("固定手数 %s 需保证金 $%.2f > 上限 $%.2f",
              DoubleToString(flot, VolDigits()), fmargin, fcap); return 0.0; }
      return flot;
   }

   // 美元硬上限:和风险%取更小的那个。设了 $10 目标却按 $100 风险开仓,
   // 是这个功能最容易出的事故。
   if(InpRiskCapUSD > 0.0 && riskMoney > InpRiskCapUSD)
      riskMoney = InpRiskCapUSD;

   double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double lotMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   double raw = riskMoney / (slDistUSD * mppd);
   double lot = FloorToStep(raw);                        // 只往下取整，绝不放大

   if(lot < lotMin)
   {
      double minRisk = lotMin * slDistUSD * mppd;
      why = StringFormat("最小手数 %s 的风险为 $%.2f（止损 $%.2f），超过允许的 $%.2f -> NO TRADE",
                         DoubleToString(lotMin, VolDigits()), minRisk, slDistUSD, riskMoney);
      return 0.0;
   }
   if(lot > lotMax) lot = lotMax;

   // 复核实际风险
   double actualRisk = lot * slDistUSD * mppd;
   if(actualRisk > riskMoney * 1.02)
   {
      why = StringFormat("复核未通过：实际风险 $%.2f > 允许 $%.2f", actualRisk, riskMoney);
      return 0.0;
   }

   // 保证金检查：禁止满仓
   double margin = 0.0;
   double price  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(!OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lot, price, margin))
   { why = "保证金计算失败"; return 0.0; }

   double freeMargin = EffectiveFreeMargin();
   double cap = freeMargin * InpMaxMarginPctPerPos / 100.0;
   if(margin > cap)
   {
      why = StringFormat("保证金 $%.2f 超过上限 $%.2f（可用 $%.2f 的 %.0f%%）—— 杠杆/最小手数不允许该笔交易",
                         margin, cap, freeMargin, InpMaxMarginPctPerPos);
      return 0.0;
   }

   return lot;
}

//==================================================================
// 小账户救济：把风险上调到规格自己的上限，而不是缩止损
//==================================================================
// 这里处理的是**颗粒度**问题，不是风控松紧问题：
//   $200 账户的 1% = $2，而黄金 M5 的结构止损普遍 $3~$6（近期 M5 ATR ≈ $4）。
//   0.01 手 = 1 盎司，没有比这更小的档位去承接这个差额，于是 CalcLot 一路拒单。
//
// 两个方向可以让它开得出单：把止损缩到 $2，或者把风险抬到 2%。
// 前者是规格里明令禁止的（缩止损 = 让市场噪音替你决定出场），
// 后者只是用掉规格自己写明的 1%~2% 区间的上半段。所以选后者。
//
// 代价要讲清楚：单笔亏损从 $2 变成最多 $4，日内 -$15 熔断从能扛 7.5 笔
// 变成 3.75 笔 —— 但连亏 3 笔本来就停手（-$12），所以真正起作用的仍是连亏闸门。
//
// 只在「正常模式」下生效：保守 / 收紧 / 观察模式的降险优先级更高，
// 那几档的存在意义就是在盈利或连亏之后主动缩手，不能被这里抬回去。
double EscalateRiskForMinLot(double slDist, double riskPct, DayStats &ds, string &note)
{
   note = "";
   if(!InpSmallAccountEscalate) return riskPct;
   if(ConsecObserveOn(ds.consecLoss)) return riskPct;               // 观察模式：不加码
   if(ds.total >= ConservativeAtUSD())            return riskPct;   // 已进盈利保护档

   double mppd   = MoneyPerLotPerDollar();
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double bal    = EffectiveBalance();
   if(mppd <= 0.0 || lotMin <= 0.0 || bal <= 0.0 || slDist <= 0.0) return riskPct;

   double needMoney = lotMin * slDist * mppd;          // 最小手在这个止损下的风险
   double haveMoney = bal * riskPct / 100.0;
   if(needMoney <= haveMoney) return riskPct;          // 本来就开得了，不动

   if(needMoney > bal * InpRiskPctMax / 100.0)
      return riskPct;                                  // 抬到上限也不够 -> 让 CalcLot 拒单并说明原因

   // 留 0.1% 余量：CalcLot 里 FloorToStep 是向下取整，预算刚好等于 lotMin 的风险时
   // 浮点误差可能把手数抹到 lotMin 以下，反而拒单。
   // 但余量本身不能把结果顶出上限 —— 止损恰好等于 2% 额度时（$200 账户的 $4 止损就是
   // 这个临界点）必须仍然能开，所以这里夹回 InpRiskPctMax，而不是判定超限。
   double needPct = MathMin(InpRiskPctMax, (needMoney * 1.001) / bal * 100.0);

   note = StringFormat("最小手 %s 在 $%.2f 止损下需 %.2f%% 风险($%.2f)，自 %.2f%% 上调（上限 %.2f%%）",
                       DoubleToString(lotMin, VolDigits()), slDist, needPct, needMoney,
                       riskPct, InpRiskPctMax);
   return needPct;
}

//==================================================================
// 启动提示：有没有颗粒度更细的黄金品种
//==================================================================
// 小账户的根本出路不是调参数，是换一个最小手数更小的品种。
// 0.001 手 = 0.1 盎司，同样 $4 的止损只冒 $0.40 风险 —— 风控一点不用让步。
// 这里只读不写，扫一遍经纪商的品种表，把更合适的那个报出来。
void SuggestFinerGoldSymbol()
{
   double myMppd = MoneyPerLotPerDollar();
   double myLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(myMppd <= 0.0 || myLot <= 0.0) return;
   double myRiskPerDollar = myLot * myMppd;     // 每 $1 止损距离、最小手要冒的风险

   string best = "";
   double bestRisk = myRiskPerDollar;
   int    total = SymbolsTotal(false);          // false = 经纪商全部品种，不限于市场报价

   for(int i = 0; i < total; i++)
   {
      string s = SymbolName(i, false);
      if(s == _Symbol) continue;
      if(StringFind(s, "XAU") < 0 && StringFind(s, "GOLD") < 0 && StringFind(s, "Gold") < 0) continue;

      double lm = SymbolInfoDouble(s, SYMBOL_VOLUME_MIN);
      double tv = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_VALUE);
      double ts = SymbolInfoDouble(s, SYMBOL_TRADE_TICK_SIZE);
      if(lm <= 0.0 || tv <= 0.0 || ts <= 0.0) continue;

      double risk = lm * (tv / ts);             // 每手每$1价值 = tickValue / tickSize
      if(risk < bestRisk * 0.999) { bestRisk = risk; best = s; }
   }

   if(StringLen(best) > 0)
      LogLine("HINT", StringFormat(
         "发现颗粒度更细的品种：%s —— 每 $1 止损距离，最小手风险 $%.2f，而当前 %s 是 $%.2f（细 %.0f 倍）。"
         "小账户把 EA 挂到 %s 的 M5 图表上，同样的止损只冒 1/%.0f 的风险，风控无需让步。",
         best, bestRisk, _Symbol, myRiskPerDollar,
         myRiskPerDollar / bestRisk, best, myRiskPerDollar / bestRisk));
}

//==================================================================
// 开仓
//==================================================================
void OpenTrade(Signal &sg, double riskPct, DayStats &ds)
{
   // 先查两道开关。不查的话每个信号都会走完全部计算再被 10027 打回,
   // 日志里只剩一行看不出所以然的"下单失败",真正的原因(哪个开关关着)看不见。
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
   {
      NoTrade(StringFormat("算法交易未开启：终端开关=%s，本EA开关=%s —— 开仓会以 10027 失败",
              TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "开" : "**关**",
              MQLInfoInteger(MQL_TRADE_ALLOWED)          ? "开" : "**关**"));
      return;
   }

   double balance   = EffectiveBalance();
   double riskMoney = balance * riskPct / 100.0;
   double slDist    = MathAbs(sg.entry - sg.sl);

   string why = "";
   double lot = CalcLot(slDist, riskMoney, why);
   if(lot <= 0.0) { NoTrade(why); return; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints((int)MathMax(10.0, SpreadUSD() / _Point));
   trade.SetTypeFillingBySymbol(_Symbol);

   // --- 固定金额止盈:按**实际手数**反算需要走多少美元金价 ---
   // 必须放在 lot 算出来之后:手数是向下取整的,用理论手数反算会有偏差。
   string targetNote = "";
   if(InpTargetProfitUSD > 0.0)
   {
      double perDollar = lot * MoneyPerLotPerDollar();   // 这个手数下,金价每动$1的盈亏
      if(perDollar > 0.0)
      {
         double tpDist = InpTargetProfitUSD / perDollar;
         double minDist = StopsLevelUSD() + SpreadUSD();
         if(tpDist < minDist)
         {
            // 目标太小,近到券商不接受挂单 —— 抬到最小距离并说明,不静默放行
            LogLine("TARGET", StringFormat(
               "目标 $%.2f 只需金价走 $%.2f，小于券商最小挂单距离 $%.2f，已抬至该距离（实际到手约 $%.2f）",
               InpTargetProfitUSD, tpDist, minDist, minDist * perDollar));
            tpDist = minDist;
         }
         sg.tp2 = Px((sg.dir > 0) ? sg.entry + tpDist : sg.entry - tpDist);
         targetNote = StringFormat(" | 目标$%.2f=金价走$%.2f(每$1盈亏$%.2f)",
                                   InpTargetProfitUSD, tpDist, perDollar);
      }
   }

   bool ok;
   // 订单备注只用 ASCII（部分经纪商会截断/乱码中文），中文原因写进日志
   string comment = StringFormat("SG s%d rr%.1f", sg.score, sg.rr);
   if(sg.dir > 0) ok = trade.Buy (lot, _Symbol, 0.0, sg.sl, sg.tp2, comment);
   else           ok = trade.Sell(lot, _Symbol, 0.0, sg.sl, sg.tp2, comment);

   if(!ok)
   {
      uint rc = trade.ResultRetcode();
      string hint = "";
      if(rc == 10027) hint = " —— 算法交易开关被关闭。工具栏 Algo Trading(Ctrl+E) 与"
                             " 图表右键->智能交易系统->属性->常用->允许算法交易，两处都要开。";
      else if(rc == 10014) hint = StringFormat(" —— 手数非法。本次 %.3f，品种最小 %.3f 步长 %.3f。",
                                  lot, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
                                  SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP));
      else if(rc == 10016) hint = " —— 止损/止盈距离不合法(太贴近现价)。";
      else if(rc == 10019) hint = " —— 保证金不足。";
      LogLine("ERROR", StringFormat("下单失败 %d %s%s", rc, trade.ResultRetcodeDescription(), hint));
      return;
   }

   if(sg.dir > 0) g_opnBuy++; else g_opnSell++;

   ulong openTicket = trade.ResultOrder();   // 对冲账户下,开仓订单号即持仓号
   LogLine("OPEN", StringFormat("#%I64u %s %s 手 @ %.2f | SL %.2f (%.2f USD) | TP %.2f | RR %.2f | 分数 %d | 风险 $%.2f (%.1f%%) | %s | 当日 %d/%d 笔，盈亏 $%.2f",
           openTicket, sg.dir > 0 ? "BUY" : "SELL", DoubleToString(lot, VolDigits()), sg.entry, sg.sl, slDist, sg.tp2, sg.rr, sg.score,
           lot * slDist * MoneyPerLotPerDollar(), riskPct, sg.note,
           ds.trades + 1, InpMaxTradesPerDay, ds.total) + targetNote);
   LogLine("QUALITY", StringFormat("#%I64u 开仓时行情质量：%s", openTicket, g_quality));

   Push(StringFormat("开仓 %s %s手 @%.2f | SL %.2f | TP %.2f | 风险 $%.2f (%.2f%%) | 分数 %d | %s",
        sg.dir > 0 ? "BUY" : "SELL", DoubleToString(lot, VolDigits()), sg.entry, sg.sl, sg.tp2,
        lot * slDist * MoneyPerLotPerDollar(), riskPct, sg.score, sg.note));

   // 强制校验：无止损绝不允许留仓
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;
      if(pos.StopLoss() == 0.0)
      {
         // 先补一次止损；补不上就平掉，绝不留裸单
         if(!trade.PositionModify(pos.Ticket(), sg.sl, sg.tp2))
         {
            LogLine("CRITICAL", StringFormat("#%I64u 无法设置止损，立即平仓（规则：禁止无止损交易）", pos.Ticket()));
            trade.PositionClose(pos.Ticket());
         }
         else
            LogLine("MANAGE", StringFormat("#%I64u 开仓后补设止损 %.2f", pos.Ticket(), sg.sl));
      }
   }
}

//------------------------------------------------------------------
// 持仓状态标记（用终端全局变量记录，EA 重启 / 断线也不丢）
//   SG_P_<ticket> = 已做过部分止盈
//   SG_R_<ticket> = 开仓时的初始 1R 距离（止损移动后仍以此为基准）
//------------------------------------------------------------------
string PartialKey(ulong ticket){ return StringFormat("SG_P_%I64u", ticket); }
string RKey      (ulong ticket){ return StringFormat("SG_R_%I64u", ticket); }
string MKey      (ulong ticket){ return StringFormat("SG_M_%I64u", ticket); }
string FKey      (ulong ticket){ return StringFormat("SG_F_%I64u", ticket); }  // 利润地板已武装

// 该仓位见过的最高盈利(R)。只增不减 —— 回吐上限要守的就是这个数。
double PeakR(ulong ticket, double curR)
{
   string k = MKey(ticket);
   double best = GlobalVariableCheck(k) ? GlobalVariableGet(k) : 0.0;
   if(curR > best) { best = curR; GlobalVariableSet(k, best); }
   return best;
}

bool PartialDone(ulong ticket){ return GlobalVariableCheck(PartialKey(ticket)); }
void MarkPartialDone(ulong ticket){ GlobalVariableSet(PartialKey(ticket), 1.0); }

// 初始 R：第一次见到该仓位时写入，之后一律读取，绝不因止损移动而改变
double InitialR(ulong ticket, double fallback)
{
   string k = RKey(ticket);
   if(GlobalVariableCheck(k))
   {
      double v = GlobalVariableGet(k);
      if(v > 0.0) return v;
   }
   if(fallback > 0.0) GlobalVariableSet(k, fallback);
   return fallback;
}

// 测试器专用:抹掉上一次回测残留的 SG_ 全局变量。
// 全局变量是**终端级**的,不随回测结束而消失;而每次回测的订单号都从 1 重新开始。
// 于是上一轮的 SG_R_1(初始止损距离)会被这一轮的 1 号单读到 —— R 倍数算错、
// 保本/追踪/部分止盈全部踩偏,而且只在回测里发生,实盘查不出来。
void PurgeFlags()
{
   int n = GlobalVariablesTotal();
   for(int i = n - 1; i >= 0; i--)
   {
      string nm = GlobalVariableName(i);
      if(StringFind(nm, "SG_P_") == 0 || StringFind(nm, "SG_R_") == 0 ||
         StringFind(nm, "SG_M_") == 0 || StringFind(nm, "SG_F_") == 0)
         GlobalVariableDel(nm);
   }
}

// 清理已平仓位留下的标记
void CleanFlags()
{
   int n = GlobalVariablesTotal();
   for(int i = n - 1; i >= 0; i--)
   {
      string nm = GlobalVariableName(i);
      bool isP = (StringFind(nm, "SG_P_") == 0);
      bool isR = (StringFind(nm, "SG_R_") == 0);
      bool isM = (StringFind(nm, "SG_M_") == 0);
      bool isF = (StringFind(nm, "SG_F_") == 0);
      if(!isP && !isR && !isM && !isF) continue;
      ulong tk = (ulong)StringToInteger(StringSubstr(nm, 5));
      if(!PositionSelectByTicket(tk)) GlobalVariableDel(nm);
   }
}

//==================================================================
// 停滞判定：最近 N 分钟价格是不是在一个很窄的区间里磨
//==================================================================
// 用 M1 数一根一分钟，和"分钟"这个口径一一对应，不受 InpLTF/InpEntryTF 影响。
// 拿不到完整数据时返回 false —— 数据不足时**不猜**，宁可不平仓。
bool PriceStalled(int dir, double atr, int minutes, double &rangeOut)
{
   rangeOut = 0.0;
   if(minutes <= 0 || atr <= 0.0) return false;

   double hi = -DBL_MAX, lo = DBL_MAX;
   int hiIdx = -1, loIdx = -1;
   for(int i = 1; i <= minutes; i++)
   {
      double h = iHigh(_Symbol, PERIOD_M1, i);
      double l = iLow (_Symbol, PERIOD_M1, i);
      if(h <= 0.0 || l <= 0.0) return false;
      if(h > hi) { hi = h; hiIdx = i; }
      if(l < lo) { lo = l; loIdx = i; }
   }
   rangeOut = hi - lo;
   if(rangeOut >= InpStallRangeATR * atr) return false;

   // 最新那根还在往我有利的方向创极值 = 还在走，别急着砍
   if(InpStallNeedNoNewExtreme)
   {
      if(dir > 0 && hiIdx == 1) return false;
      if(dir < 0 && loIdx == 1) return false;
   }
   return true;
}

//==================================================================
// 持仓的**净**盈亏（口径说明见 InpQuickProfitUSD 那段注释）
//==================================================================
// 调用前必须已经 pos.Select*() 选中该仓位。
double PositionNetUSD()
{
   double net = pos.Profit() + pos.Swap();

   // 手续费要翻历史,比读浮动盈亏贵得多。放在这里是因为调用点已经做了粗筛
   // （毛利没摸到目标就不会走到这一步），所以每 tick 的常态开销仍是两次读取。
   double comm = 0.0;
   if(HistorySelectByPosition((ulong)pos.Identifier()))
   {
      int nd = HistoryDealsTotal();
      for(int j = 0; j < nd; j++)
      {
         ulong dt = HistoryDealGetTicket(j);
         if(dt != 0) comm += HistoryDealGetDouble(dt, DEAL_COMMISSION);
      }
   }
   // comm 是负数。此刻历史里只有开仓那一笔,平仓那一笔还没发生 ——
   // 按往返对称估算,×2。点差型账户(commission=0)下这一项恒为 0,不影响。
   return net + comm * 2.0;
}

//==================================================================
// 持仓管理
//==================================================================
void ManagePositions(double atr)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;

      ulong  tk    = pos.Ticket();
      bool   isBuy = (pos.PositionType() == POSITION_TYPE_BUY);
      double open  = pos.PriceOpen();
      double sl    = pos.StopLoss();
      double tp    = pos.TakeProfit();
      double vol   = pos.Volume();
      double cur   = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);

      // 无止损 -> 立刻处理（绝不允许裸单）
      if(sl == 0.0)
      {
         LogLine("CRITICAL", StringFormat("#%I64u 检测到无止损，强制平仓", tk));
         Push(StringFormat("⚠️ #%I64u 检测到无止损持仓，已强制平仓", tk));
         trade.PositionClose(tk);
         continue;
      }

      // 初始 R 只在第一次记录，之后止损怎么移都不影响 R 的基准
      double R = InitialR(tk, MathAbs(open - sl));
      if(R <= 0.0) continue;
      double moved = isBuy ? (cur - open) : (open - cur);
      double rMult = moved / R;

      // --- 回吐上限：曾经赚到过，就不许全吐回去 ---
      // 守的是**曾经到过的最高点**，不是入场价 —— 保本管不到"从 +1.5R 退回 +0.1R"
      // 这种情况(全程都还在盈利)，回吐上限管得到。放最前面：它是最紧的一道。
      double peakR = PeakR(tk, rMult);
      if(InpGiveBackPct > 0.0 && peakR >= InpGiveBackMinR)
      {
         double keep = peakR * (1.0 - InpGiveBackPct / 100.0);
         if(rMult <= keep)
         {
            if(trade.PositionClose(tk))
            {
               LogLine("GIVEBACK", StringFormat(
                  "#%I64u 最高到过 %.2fR，现回落到 %.2fR（回吐 %.0f%% >= 上限 %.0f%%），落袋",
                  tk, peakR, rMult, peakR > 0.0 ? 100.0 * (peakR - rMult) / peakR : 0.0,
                  InpGiveBackPct));
               continue;
            }
            LogLine("ERROR", StringFormat("#%I64u 回吐离场失败 %d %s",
                    tk, trade.ResultRetcode(), trade.ResultRetcodeDescription()));
         }
      }

      // --- 利润地板：到过 $X 之后跌回它以下就落袋（不砍上限）---
      if(InpProfitFloorUSD > 0.0)
      {
         string fk = FKey(tk);
         bool armed = GlobalVariableCheck(fk);
         double grossQuick = pos.Profit() + pos.Swap();   // 先用毛利粗筛，别每 tick 翻手续费
         if(!armed && grossQuick >= InpProfitFloorUSD)
         {
            if(PositionNetUSD() >= InpProfitFloorUSD)      // 净额确认到过地板
            { GlobalVariableSet(fk, 1.0); armed = true; }
         }
         if(armed && PositionNetUSD() <= InpProfitFloorUSD)
         {
            if(trade.PositionClose(tk))
            {
               LogLine("FLOOR", StringFormat(
                  "#%I64u 净利到过 $%.2f 后回落到 $%.2f，触及利润地板，落袋（%.2fR）",
                  tk, InpProfitFloorUSD, PositionNetUSD(), rMult));
               continue;
            }
            LogLine("ERROR", StringFormat("#%I64u 利润地板离场失败 %d %s",
                    tk, trade.ResultRetcode(), trade.ResultRetcodeDescription()));
         }
      }

      // --- 固定金额快速离场：净赚到目标就立刻走 ---
      // 放在所有离场判断的最前面 —— 它的语义就是"到了就走",不该被保本、
      // 追踪、部分止盈这些先改一遍状态。
      // 先用毛利粗筛：没摸到目标就连手续费都不用去翻历史。
      if(InpQuickProfitUSD > 0.0 && (pos.Profit() + pos.Swap()) >= InpQuickProfitUSD)
      {
         double netUSD = PositionNetUSD();
         if(netUSD >= InpQuickProfitUSD)
         {
            if(trade.PositionClose(tk))
            {
               LogLine("QUICK", StringFormat(
                       "#%I64u 净盈利 $%.2f >= 目标 $%.2f，立刻平仓（%.2fR）",
                       tk, netUSD, InpQuickProfitUSD, rMult));
            }
            else
               LogLine("ERROR", StringFormat("#%I64u 快速离场失败 %d %s",
                       tk, trade.ResultRetcode(), trade.ResultRetcodeDescription()));
            continue;
         }
      }

      // --- 最长持仓时间（短线不拖单）---
      datetime openTime = (datetime)pos.Time();
      if(InpMaxHoldMinutes > 0 && (TimeCurrent() - openTime) > InpMaxHoldMinutes * 60)
      {
         LogLine("EXIT", StringFormat("#%I64u 超过最长持仓 %d 分钟，%.2fR 离场", tk, InpMaxHoldMinutes, rMult));
         trade.PositionClose(tk);
         continue;
      }

      // --- 收盘前清仓 ---
      MqlDateTime st; TimeToStruct(TimeCurrent(), st);
      if(st.hour >= InpFlatAllBeforeHour)
      {
         LogLine("EXIT", StringFormat("#%I64u 时段结束清仓，%.2fR", tk, rMult));
         trade.PositionClose(tk);
         continue;
      }

      // --- TP1：部分止盈 + 保本 ---
      bool partialDone = PartialDone(tk);
      double lotMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);

      // --- 保本：独立于 TP1，可以早得多 ---
      // 缓冲至少要盖住点差，否则"保本"出场仍然是净亏 —— 买单按 BID 结算，
      // 止损就摆在入场价的话，你还要再吐一个点差出去。
      double beR = (InpBreakEvenR > 0.0) ? InpBreakEvenR : InpTP1_R;
      // 金额触发：先用毛利粗筛，避免每 tick 去翻手续费历史
      bool beByUSD = (InpBreakEvenUSD > 0.0 &&
                      (pos.Profit() + pos.Swap()) >= InpBreakEvenUSD &&
                      PositionNetUSD() >= InpBreakEvenUSD);
      if(rMult >= beR || beByUSD)
      {
         double beBuf = MathMax(InpBreakevenBufferATR * atr, SpreadUSD());
         double be = isBuy ? open + beBuf : open - beBuf;
         bool needBE = isBuy ? (sl < be) : (sl > be);
         if(needBE && MathAbs(cur - be) > StopsLevelUSD() + _Point)
         {
            if(trade.PositionModify(tk, Px(be), tp))
            {
               sl = Px(be);        // 同步本地值，否则下面的追踪会拿旧止损比较，可能反而放宽
               LogLine("MANAGE", StringFormat("#%I64u %s，止损移至保本 %.2f（缓冲 $%.2f，含点差）",
                       tk, beByUSD ? StringFormat("净赚 $%.2f（%.2fR）", PositionNetUSD(), rMult)
                                   : StringFormat("达到 %.2fR", rMult),
                       be, beBuf));
            }
         }
      }

      if(rMult >= InpTP1_R)
      {
         // 部分止盈（手数够才做，不够就整体交给追踪止损）
         if(!partialDone)
         {
            double closeVol = FloorToStep(vol * InpPartialClosePct / 100.0);
            if(closeVol >= lotMin && (vol - closeVol) >= lotMin)
            {
               if(trade.PositionClosePartial(tk, closeVol))
               {
                  MarkPartialDone(tk);
                  LogLine("TP1", StringFormat("#%I64u 达到 %.2fR，部分止盈 %.2f 手，剩余 %.2f 手，止损保本",
                          tk, rMult, closeVol, vol - closeVol));
                  continue;   // 仓位状态已变，追踪交给下一 tick，避免用过期数据操作
               }
            }
            else
            {
               // 手数太小无法拆分：整笔交给保本 + 追踪止损
               MarkPartialDone(tk);
               LogLine("TP1", StringFormat("#%I64u 达到 %.2fR，但手数 %.2f 无法拆分，改为保本+追踪", tk, rMult, vol));
            }
         }
      }

      // --- TP1 之后 ATR 追踪（只收紧，绝不放大）---
      if(rMult >= InpTP1_R)
      {
         double trail = isBuy ? cur - InpTrailATRMult * atr : cur + InpTrailATRMult * atr;
         bool better = isBuy ? (trail > sl) : (trail < sl);
         if(better && MathAbs(cur - trail) > StopsLevelUSD() + _Point)
            if(trade.PositionModify(tk, Px(trail), tp))
               LogLine("TRAIL", StringFormat("#%I64u 追踪止损 -> %.2f (%.2fR)", tk, trail, rMult));
      }

      // --- 动量衰竭 / 反向信号 -> 提前锁利 ---
      if(InpExitOnMomentumFade && rMult >= InpFadeExitMinR)
      {
         int mom = Momentum();
         int ltf = LtfTrend();
         double c1 = iClose(_Symbol, InpLTF, 1);
         double o1 = iOpen (_Symbol, InpLTF, 1);
         bool against = isBuy ? (c1 < o1 && (o1 - c1) > 0.7 * atr) : (c1 > o1 && (c1 - o1) > 0.7 * atr);
         int myDir = isBuy ? 1 : -1;

         if((mom != 0 && mom != myDir) || (ltf != 0 && ltf != myDir) || against)
         {
            LogLine("EXIT", StringFormat("#%I64u 动量衰竭/反向信号，%.2fR 主动锁利", tk, rMult));
            trade.PositionClose(tk);
            continue;
         }
      }

      // --- 有利润但走不动了 -> 落袋 ---
      // 放在动量衰竭之后：那条管"掉头往回走"，这条管"根本不走了"，互补不重叠。
      if(InpExitOnStall)
      {
         bool   profitOk = false;
         double netUSD   = 0.0;
         if(InpStallMinUSD > 0.0)
         {
            netUSD   = PositionNetUSD();          // 点差/隔夜/手续费都已扣
            profitOk = (netUSD >= InpStallMinUSD);
         }
         else
            profitOk = (rMult >= InpStallMinR);

         double rng = 0.0;
         if(profitOk && PriceStalled(isBuy ? 1 : -1, atr, InpStallMinutes, rng))
         {
            if(trade.PositionClose(tk))
            {
               LogLine("STALL", StringFormat(
                  "#%I64u %d 分钟仅波动 $%.2f（< ATR %.2f × %.2f），%.2fR / 净 $%.2f 落袋",
                  tk, InpStallMinutes, rng, atr, InpStallRangeATR, rMult,
                  InpStallMinUSD > 0.0 ? netUSD : PositionNetUSD()));
               continue;
            }
            LogLine("ERROR", StringFormat("#%I64u 停滞离场失败 %d %s",
                    tk, trade.ResultRetcode(), trade.ResultRetcodeDescription()));
         }
      }

      // --- 逼近关键位且已有合理利润 -> 落袋 ---
      if(rMult >= InpLevelExitMinR)
      {
         double lv = 0.0;
         string kn = "";
         bool found;
         if(InpLevelExitKeyOnly)
            // 只认前日高低 / 亚洲区间 / 整数关口 —— 那些才是真会引发反应的位置
            found = isBuy ? KeyLevelAbove(cur, 0.0, lv, kn) : KeyLevelBelow(cur, 0.0, lv, kn);
         else
            found = isBuy ? NearestResistance(cur, 0.0, lv) : NearestSupport(cur, 0.0, lv);
         if(found)
         {
            bool near = isBuy ? ((lv - cur) < 0.20 * atr) : ((cur - lv) < 0.20 * atr);
            if(near)
            {
               LogLine("EXIT", StringFormat("#%I64u 逼近%s %.2f，%.2fR 提前平仓",
                       tk, StringLen(kn) > 0 ? kn : "关键位", lv, rMult));
               trade.PositionClose(tk);
            }
         }
      }
   }
}

//==================================================================
// 加仓闸门（规则十四：默认禁止，六项条件全满足才放行）
//==================================================================
// 当前所有持仓的在险金额（止损已到保本之外的按 0 计）
double OpenRiskUSD()
{
   double mppd = MoneyPerLotPerDollar();
   double risk = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;
      if(pos.StopLoss() == 0.0) return 1e9;      // 裸单视为无限风险
      bool isBuy = (pos.PositionType() == POSITION_TYPE_BUY);
      double d = isBuy ? (pos.PriceOpen() - pos.StopLoss()) : (pos.StopLoss() - pos.PriceOpen());
      if(d <= 0.0) continue;                     // 已保本/锁利
      risk += d * pos.Volume() * mppd;
   }
   return risk;
}

bool AddOnAllowed(int newDir, int newScore, DayStats &ds, double &allowedRiskPct, string &why)
{
   if(!InpAllowAddOn) { why = "加仓已禁用（默认）"; return false; }

   // 1) 原始交易必须已经盈利
   // 2) 方向必须一致
   bool anyPos = false;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;
      anyPos = true;
      int d = (pos.PositionType() == POSITION_TYPE_BUY) ? 1 : -1;
      if(d != newDir)               { why = "加仓被拒：方向与现有持仓相反"; return false; }
      if(pos.Profit() <= 0.0)       { why = "加仓被拒：原始交易尚未盈利（禁止亏损加仓）"; return false; }
      double R = MathAbs(pos.PriceOpen() - pos.StopLoss());
      double cur = (d > 0) ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double moved = (cur - pos.PriceOpen()) * d;
      if(R <= 0.0 || moved < 0.5 * R) { why = "加仓被拒：原始交易利润不足 0.5R"; return false; }
   }
   if(!anyPos) { why = ""; return true; }        // 没有持仓，不属于加仓

   // 5) 不属于追涨杀跌：只接受满分信号
   if(newScore < 7) { why = "加仓被拒：新信号非满分确认"; return false; }

   // 6) 不是为了追回亏损
   if(ds.total < 0.0) { why = "加仓被拒：当日处于亏损（禁止为追回亏损而加仓）"; return false; }

   // 4) 账户总风险仍不得超过 2%
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double budget = bal * InpRiskPctMax / 100.0 - OpenRiskUSD();
   if(budget <= 0.30) { why = "加仓被拒：账户总风险已用尽 2% 预算"; return false; }
   allowedRiskPct = MathMin(allowedRiskPct, budget / bal * 100.0);

   why = "";
   return true;                                   // 3) 新仓自带独立止损，由 OpenTrade 保证
}

//==================================================================
// V2：每 N 笔成交的统计（规格 §33）
//==================================================================
// 从成交历史按 position_id 聚合,和日内统计同源 —— 不依赖内存变量,
// EA 重启/重挂都不会丢,也就绕不过去。
long g_lastStatsAt = 0;

void ReportTradeStats(int everyN)
{
   // 这个函数每次都要 HistorySelect(0, ...) 拉**全部**历史再遍历。
   // 实盘每 30 秒扫几十笔没关系;回测里成交数会长到几千笔,而"每 30 秒"
   // 是模拟时间 —— 2 年就是 200 万次调用。必须在测试器里关掉。
   if(g_quiet) return;
   if(!HistorySelect(0, TimeCurrent() + 3600)) return;

   ulong  pid[]; double pnl[]; datetime tm[];
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
   {
      ulong tk = HistoryDealGetTicket(i);
      if(tk == 0) continue;
      if(HistoryDealGetInteger(tk, DEAL_MAGIC) != InpMagic)  continue;
      if(HistoryDealGetString(tk, DEAL_SYMBOL) != _Symbol)   continue;
      long en = HistoryDealGetInteger(tk, DEAL_ENTRY);
      if(en != DEAL_ENTRY_OUT && en != DEAL_ENTRY_OUT_BY && en != DEAL_ENTRY_INOUT) continue;

      double p = HistoryDealGetDouble(tk, DEAL_PROFIT)
               + HistoryDealGetDouble(tk, DEAL_SWAP)
               + HistoryDealGetDouble(tk, DEAL_COMMISSION);
      ulong    id = (ulong)HistoryDealGetInteger(tk, DEAL_POSITION_ID);
      datetime dt = (datetime)HistoryDealGetInteger(tk, DEAL_TIME);

      int idx = -1;
      for(int k = 0; k < ArraySize(pid); k++) if(pid[k] == id) { idx = k; break; }
      if(idx < 0)
      {
         idx = ArraySize(pid);
         ArrayResize(pid, idx + 1); ArrayResize(pnl, idx + 1); ArrayResize(tm, idx + 1);
         pid[idx] = id; pnl[idx] = 0.0; tm[idx] = 0;
      }
      pnl[idx] += p;
      if(dt > tm[idx]) tm[idx] = dt;
   }

   int n = ArraySize(pid);
   if(n <= 0 || n % everyN != 0) return;
   if(n == (int)g_lastStatsAt) return;          // 同一个笔数只报一次
   g_lastStatsAt = n;

   // 按时间排序,算最大回撤要按顺序累计
   for(int a = 0; a < n - 1; a++)
      for(int b = 0; b < n - 1 - a; b++)
         if(tm[b] > tm[b+1])
         {
            datetime tt = tm[b];  tm[b]  = tm[b+1];  tm[b+1]  = tt;
            double   pp = pnl[b]; pnl[b] = pnl[b+1]; pnl[b+1] = pp;
            ulong    ii = pid[b]; pid[b] = pid[b+1]; pid[b+1] = ii;
         }

   int    wins = 0, losses = 0;
   double gp = 0.0, gl = 0.0;
   double eq = 0.0, peak = 0.0, maxDD = 0.0;
   int    maxLossStreak = 0, curStreak = 0;
   for(int i = 0; i < n; i++)
   {
      if(pnl[i] > 0) { wins++;   gp += pnl[i]; curStreak = 0; }
      else           { losses++; gl += -pnl[i]; curStreak++;
                       if(curStreak > maxLossStreak) maxLossStreak = curStreak; }
      eq += pnl[i];
      if(eq > peak) peak = eq;
      if(peak - eq > maxDD) maxDD = peak - eq;
   }
   double winRate = 100.0 * wins / n;
   double pf      = (gl > 0.0) ? gp / gl : (gp > 0.0 ? 999.0 : 0.0);
   double avgWin  = (wins   > 0) ? gp / wins   : 0.0;
   double avgLoss = (losses > 0) ? gl / losses : 0.0;

   LogLine("STATS", StringFormat(
      "累计 %d 笔 | 胜 %d 负 %d 胜率 %.1f%% | 毛盈 $%.2f 毛亏 $%.2f 净 $%.2f | "
      "均盈 $%.2f 均亏 $%.2f | 盈亏比(PF) %.2f | 最大回撤 $%.2f | 最长连亏 %d 笔",
      n, wins, losses, winRate, gp, gl, gp - gl, avgWin, avgLoss, pf, maxDD, maxLossStreak));

   // 规格 §36：不能只说"市场不好",要指出可能的问题在哪
   if(pf < 1.0 && n >= everyN)
   {
      string hint = "";
      if(winRate >= 50.0 && avgLoss > avgWin * 1.5)
         hint = "胜率不低但均亏远大于均盈 -> 止盈太近或止损太宽,先看 TP/SL 比例";
      else if(winRate < 35.0)
         hint = "胜率偏低 -> 入场太早或 setup 质量不够,考虑提高 InpScoreMinB";
      else if(maxLossStreak >= 5)
         hint = "连亏偏长 -> 可能在震荡市反复被扫,检查是否该开回市场质量闸门";
      else
         hint = "盈亏比 <1,先按触发路径分组看是哪一类在亏(日志里的 [OPEN] 备注)";
      LogLine("STATS", StringFormat("⚠️ 当前为负期望。%s", hint));
   }
}

//==================================================================
// 面板
//==================================================================
void Panel(DayStats &ds, string status)
{
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   string mode = "正常";
   if(ds.total >= ReducedAtUSD())      mode = "收紧（只做最高质量）";
   else if(ds.total >= ConservativeAtUSD()) mode = "保守";
   if(ConsecObserveOn(ds.consecLoss)) mode += " + 观察模式";

   string txt = StringFormat(
      "===== XAUUSD ScalperGuard =====\n"
      "账户: %s  %s | 余额 $%.2f | 杠杆 1:%d\n"
      "当日盈亏: $%.2f (已实现 $%.2f / 浮动 $%.2f)\n"
      "目标 +$%.0f  |  上限 -$%.0f\n"
      "当日笔数: %d / %d   连亏: %d\n"
      "模式: %s\n"
      "点差: %.2f  ATR: %.2f\n"
      "算法交易: 终端%s / 本EA%s\n"
      "方向(挂载以来): 判多 %d / 判空 %d  |  开多 %d / 开空 %d\n"
      "状态: %s\n",
      AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : "REAL",
      _Symbol, bal, (int)AccountInfoInteger(ACCOUNT_LEVERAGE),
      ds.total, ds.realized, ds.floating,
      DailyTargetUSD(), DailyMaxLossUSD(),
      ds.trades, InpMaxTradesPerDay, ds.consecLoss,
      mode, SpreadUSD(), Buf(hAtrL, 0, 1),
      TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) ? "开" : "关!",
      MQLInfoInteger(MQL_TRADE_ALLOWED)          ? "开" : "关!",
      g_dirBuy, g_dirSell, g_opnBuy, g_opnSell,
      status);
   if(!g_optim) Comment(txt);      // 优化时没人看,Comment 每次都要刷图表
}

//==================================================================
// 监控：手机推送 + 状态快照
//==================================================================
// 推送只发**状态变化**（开仓/平仓/熔断/异常），不发心跳。
// 每次 NO-TRADE 都推一条的话，你会在半天内关掉通知 —— 那等于没有监控。
void Push(string msg)
{
   if(!InpPushNotify) return;
   if(MQLInfoInteger(MQL_TESTER)) return;        // 回测里不推送
   SendNotification(StringFormat("[%s] %s", _Symbol, msg));
}

string JsonEsc(string s)
{
   StringReplace(s, "\\", "\\\\");
   StringReplace(s, "\"", "\\\"");
   StringReplace(s, "\n", " ");
   StringReplace(s, "\r", " ");
   return s;
}

// MQL5 的 FILE_TXT|FILE_ANSI 会把中文写坏，FILE_UNICODE 写的是 UTF-16，
// JSON 解析器普遍不认。所以自己转 UTF-8 再按二进制写。
bool WriteUtf8(string fname, string content)
{
   uchar bytes[];
   int n = StringToCharArray(content, bytes, 0, -1, CP_UTF8);
   if(n <= 1) return false;
   n--;                                          // 去掉 StringToCharArray 补的结尾 0
   int h = FileOpen(fname, FILE_WRITE|FILE_BIN);
   if(h == INVALID_HANDLE) return false;
   FileWriteArray(h, bytes, 0, n);
   FileClose(h);
   return true;
}

// 状态快照。这个文件是**任何看板的数据源** —— 本地网页、VPS、或者以后
// 推到云端的接口，读的都是同一份结构，EA 这边不需要再改。
void PublishStatus(DayStats &ds, string status)
{
   if(!InpWriteStatusJson || g_quiet) return;

   string mode = "normal";
   if(ds.total >= ReducedAtUSD())           mode = "reduced";
   else if(ds.total >= ConservativeAtUSD()) mode = "conservative";
   bool observing = ConsecObserveOn(ds.consecLoss);
   bool halted    = (ds.total >= DailyTargetUSD()) ||
                    (ds.total <= -DailyMaxLossUSD()) ||
                    ConsecStopOn(ds.consecLoss) ||
                    (ds.trades >= InpMaxTradesPerDay);

   string posJson = "";
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!pos.SelectByIndex(i)) continue;
      if(pos.Magic() != InpMagic || pos.Symbol() != _Symbol) continue;

      bool   isBuy = (pos.PositionType() == POSITION_TYPE_BUY);
      double cur   = isBuy ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                           : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double moved = isBuy ? (cur - pos.PriceOpen()) : (pos.PriceOpen() - cur);
      // 用开仓时记下的初始 R，止损移到保本后仍以此为基准（和 ManagePositions 一致）
      double R     = InitialR(pos.Ticket(), MathAbs(pos.PriceOpen() - pos.StopLoss()));

      if(StringLen(posJson) > 0) posJson += ",";
      posJson += StringFormat(
         "{\"ticket\":%I64u,\"type\":\"%s\",\"volume\":%s,\"open\":%.2f,\"sl\":%.2f,\"tp\":%.2f,"
         "\"price\":%.2f,\"profit\":%.2f,\"r\":%.2f,\"opened\":\"%s\"}",
         pos.Ticket(), isBuy ? "buy" : "sell",
         DoubleToString(pos.Volume(), VolDigits()), pos.PriceOpen(), pos.StopLoss(),
         pos.TakeProfit(), cur, pos.Profit() + pos.Swap(),
         R > 0.0 ? moved / R : 0.0,
         TimeToString((datetime)pos.Time(), TIME_DATE|TIME_SECONDS));
   }

   string json = StringFormat(
      "{\n"
      "  \"schema\": 1,\n"
      "  \"ea\": \"XAUUSD_ScalperGuard\",\n"
      "  \"symbol\": \"%s\",\n"
      "  \"timeframe\": \"%s\",\n"
      "  \"server_time\": \"%s\",\n"
      "  \"account\": {\"mode\":\"%s\",\"login\":%I64d,\"balance\":%.2f,\"equity\":%.2f,"
      "\"leverage\":%d,\"currency\":\"%s\"},\n"
      "  \"day\": {\"realized\":%.2f,\"floating\":%.2f,\"total\":%.2f,\"trades\":%d,\"max_trades\":%d,"
      "\"consec_loss\":%d,\"target\":%.2f,\"max_loss\":%.2f,\"mode\":\"%s\",\"observing\":%s,\"halted\":%s},\n"
      "  \"market\": {\"spread\":%.2f,\"max_spread\":%.2f,\"atr\":%.2f,\"bid\":%.2f,\"ask\":%.2f,"
      "\"spread_avg_hour\":%.2f,\"spread_over_pct_hour\":%.0f},\n"
      "  \"status\": \"%s\",\n"
      "  \"last_quality\": \"%s\",\n"
      "  \"positions\": [%s]\n"
      "}\n",
      _Symbol, EnumToString(InpLTF),
      TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
      AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "demo" : "real",
      AccountInfoInteger(ACCOUNT_LOGIN),
      AccountInfoDouble(ACCOUNT_BALANCE), AccountInfoDouble(ACCOUNT_EQUITY),
      (int)AccountInfoInteger(ACCOUNT_LEVERAGE), AccountInfoString(ACCOUNT_CURRENCY),
      ds.realized, ds.floating, ds.total, ds.trades, InpMaxTradesPerDay, ds.consecLoss,
      DailyTargetUSD(), DailyMaxLossUSD(), mode,
      observing ? "true" : "false", halted ? "true" : "false",
      SpreadUSD(), InpMaxSpreadUSD, Buf(hAtrL, 0, 1),
      SymbolInfoDouble(_Symbol, SYMBOL_BID), SymbolInfoDouble(_Symbol, SYMBOL_ASK),
      SpreadAvgThisHour(), SpreadOverPctThisHour(),
      JsonEsc(status), JsonEsc(g_quality), posJson);

   WriteUtf8("XAUUSD_ScalperGuard_status.json", json);
}

//==================================================================
// 外部指令通道
//==================================================================
// 格式是每行 key=value 的纯文本 —— MQL5 没有 JSON 解析器，
// 自己手写一个解析器是给自己找 bug，而这个通道只有三个字段，不值得。
//
// 示例：
//     expires=2026.08.25 12:15:00
//     halt=0
//     block_dir=-1
//     note=正在反弹，暂停做空
string   g_cmdNote     = "";
bool     g_cmdHalt     = false;
int      g_cmdBlockDir = 0;        // -1 禁空 / 1 禁多 / 0 不限
datetime g_cmdSeenAt   = 0;

void ReadCommandFile()
{
   g_cmdHalt = false; g_cmdBlockDir = 0; g_cmdNote = "";
   if(!InpUseCommandFile) return;

   int h = FileOpen("XAUUSD_ScalperGuard_cmd.txt", FILE_READ|FILE_TXT|FILE_ANSI);
   if(h == INVALID_HANDLE) return;

   datetime expires = 0;
   bool     halt    = false;
   int      bdir    = 0;
   string   note    = "";

   while(!FileIsEnding(h))
   {
      string line = FileReadString(h);
      StringTrimLeft(line); StringTrimRight(line);
      if(StringLen(line) == 0 || StringGetCharacter(line, 0) == '#') continue;
      int eq = StringFind(line, "=");
      if(eq <= 0) continue;
      string k = StringSubstr(line, 0, eq);
      string v = StringSubstr(line, eq + 1);
      StringTrimRight(k); StringTrimLeft(v);
      if(k == "expires")        expires = StringToTime(v);
      else if(k == "halt")      halt    = (StringToInteger(v) != 0);
      else if(k == "block_dir") bdir    = (int)StringToInteger(v);
      else if(k == "note")      note    = v;
   }
   FileClose(h);

   // 过期判定：没写 expires 一律作废 —— 不允许"永久生效"的外部指令
   if(expires <= 0 || TimeCurrent() > expires) return;
   // 也不允许把有效期写得很远：外部程序挂掉之后，一条一年后过期的指令
   // 会一直生效而没人知道。超过 InpCommandMaxAgeMin 的一律不认。
   if(expires - TimeCurrent() > InpCommandMaxAgeMin * 60) return;

   // 钳位：block_dir 只认 -1/0/1，别的一律当 0
   if(bdir != -1 && bdir != 1) bdir = 0;

   g_cmdHalt = halt; g_cmdBlockDir = bdir; g_cmdNote = note;
   if(TimeCurrent() - g_cmdSeenAt > 60)
   {
      g_cmdSeenAt = TimeCurrent();
      if(halt || bdir != 0)
         LogLine("CMD", StringFormat("外部指令生效：%s%s%s（至 %s）",
                 halt ? "暂停开仓 " : "",
                 bdir == -1 ? "禁止做空 " : (bdir == 1 ? "禁止做多 " : ""),
                 StringLen(note) > 0 ? "| " + note : "",
                 TimeToString(expires, TIME_DATE|TIME_MINUTES)));
   }
}

//==================================================================
// OnInit
//==================================================================
int OnInit()
{
   // --- 运行环境 ---
   g_tester = (bool)MQLInfoInteger(MQL_TESTER);
   g_optim  = (bool)MQLInfoInteger(MQL_OPTIMIZATION);
   g_quiet  = (g_tester && InpTesterQuiet);
   g_entryTF = (InpEntryTF == PERIOD_CURRENT) ? InpLTF : InpEntryTF;

   // --- Demo 闸门 ---
   long tmode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   // 策略测试器一律放行:里面没有真钱,而某些经纪商的测试账户 ACCOUNT_TRADE_MODE
   // 并不报 DEMO,不放行就等于永远做不了回测。
   bool isDemo = (tmode == ACCOUNT_TRADE_MODE_DEMO ||
                  tmode == ACCOUNT_TRADE_MODE_CONTEST || g_tester);
   if(!isDemo && !InpAllowLiveAccount)
   {
      Alert("XAUUSD_ScalperGuard: 检测到真实账户。默认只允许 Demo 运行。"
            "确认要实盘请把 InpAllowLiveAccount 设为 true。");
      Print("拒绝启动：真实账户 + InpAllowLiveAccount=false");
      return INIT_FAILED;
   }

   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0 && StringFind(_Symbol, "Gold") < 0)
      Print("警告：当前图表 ", _Symbol, " 看起来不是黄金。本 EA 为 XAUUSD 设计。");

   // 上限从 2% 抬到 5%:V2 规格 §14/§29 明确要求 A+ setup 允许 5%。
   // 仍是**硬上限** —— 任何路径(评分分级、小账户救济、远程指令)都不得越过。
   if(InpRiskPctDefault > InpRiskPctMax || InpRiskPctMax > 5.0 ||
      InpRiskPctAPlus > 5.0 || InpRiskPctA > 5.0 || InpRiskPctB > 5.0)
   {
      Alert(StringFormat(
         "风险参数非法（v%s）：默认 %.2f%% / 上限 %.2f%% / A+ %.2f%% —— 上限不得超过 5%%。",
         SG_VERSION, InpRiskPctDefault, InpRiskPctMax, InpRiskPctAPlus));
      Print("拒绝启动：风险参数超限。若你刚更新过源码，请确认已在 MetaEditor 按 F7 重新编译 ——"
            " MT5 加载的是 .ex5，只换 .mq5 不重编译，跑的还是旧版本。");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
   {
      Alert("账户不允许 EA 自动交易。");
      return INIT_FAILED;
   }

   // MT5 有**两道**算法交易开关,任一关闭都会让每一次 OrderSend 以
   // 10027 (auto trading disabled by client) 失败 —— 而且是静默失败:
   // EA 照常运行、照常出信号,只是单子一张也发不出去。
   // 原来只查了账户级权限,查不到这两道,所以只能等下单时才发现。
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED))
      Alert("⚠️ 终端的【算法交易】按钮是关的（工具栏 Algo Trading / Ctrl+E）。"
            "现在开仓会全部以 10027 失败。");
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED))
      Alert("⚠️ 本 EA 的【允许算法交易】没有勾选（图表右键 -> 智能交易系统 -> 属性 -> 常用）。"
            "现在开仓会全部以 10027 失败。");

   hEmaFastH = iMA(_Symbol, InpHTF, InpEmaFastHTF, 0, MODE_EMA, PRICE_CLOSE);
   hEmaSlowH = iMA(_Symbol, InpHTF, InpEmaSlowHTF, 0, MODE_EMA, PRICE_CLOSE);
   hEmaFastL = iMA(_Symbol, InpLTF, InpEmaFastLTF, 0, MODE_EMA, PRICE_CLOSE);
   hEmaSlowL = iMA(_Symbol, InpLTF, InpEmaSlowLTF, 0, MODE_EMA, PRICE_CLOSE);
   hAtrL     = iATR(_Symbol, InpLTF, InpAtrPeriod);
   hRsiL     = iRSI(_Symbol, InpLTF, InpRsiPeriod, PRICE_CLOSE);
   hAdxL     = iADX(_Symbol, InpLTF, InpAdxPeriod);

   if(hEmaFastH == INVALID_HANDLE || hEmaSlowH == INVALID_HANDLE ||
      hEmaFastL == INVALID_HANDLE || hEmaSlowL == INVALID_HANDLE ||
      hAtrL == INVALID_HANDLE || hRsiL == INVALID_HANDLE || hAdxL == INVALID_HANDLE)
   {
      Print("指标句柄创建失败");
      return INIT_FAILED;
   }

   // 回测开始前清干净上一轮残留的标记(说明见 PurgeFlags)
   if(g_tester) PurgeFlags();

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetAsyncMode(false);

   for(int i = 0; i < 24; i++) ResetSpreadHour(i);

   // --- 启动自检：这个账户 / 杠杆 到底做不做得了 ---
   double bal    = AccountInfoDouble(ACCOUNT_BALANCE);
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double mppd   = MoneyPerLotPerDollar();
   double margin = 0.0;
   if(!OrderCalcMargin(ORDER_TYPE_BUY, _Symbol, lotMin, SymbolInfoDouble(_Symbol, SYMBOL_ASK), margin))
   {
      margin = 0.0;
      LogLine("WARN", "启动自检：保证金试算失败，下面那个保证金数字不作数。"
                      "真正的保证金闸门在 CalcLot() 里，每次开仓都会重算，不受影响。");
   }

   double risk1 = bal * InpRiskPctDefault / 100.0;
   double risk2 = bal * InpRiskPctMax     / 100.0;
   double slAtMinLot1 = (mppd > 0 && lotMin > 0) ? risk1 / (lotMin * mppd) : 0.0;
   double slAtMinLot2 = (mppd > 0 && lotMin > 0) ? risk2 / (lotMin * mppd) : 0.0;

   // 最小手数不能用 %.2f 打 —— 微型品种是 0.001，会显示成 0.00
   LogLine("VERSION", StringFormat("ScalperGuard v%s | 编译于 %s", SG_VERSION,
           TimeToString(SG_BUILD, TIME_DATE | TIME_MINUTES)));
   LogLine("INIT", StringFormat(
      "%s | 账户 %s | 余额 $%.2f | 杠杆 1:%d | 最小手数 %s | 每手每$1波动=$%.2f | 最小手保证金 $%.2f | "
      "1%%风险($%.2f)对应最大止损 $%.2f/盎司；2%%风险($%.2f)对应 $%.2f/盎司",
      _Symbol, isDemo ? "DEMO" : "REAL", bal, (int)AccountInfoInteger(ACCOUNT_LEVERAGE),
      DoubleToString(lotMin, VolDigits()), mppd, margin, risk1, slAtMinLot1, risk2, slAtMinLot2));

   // --- 日内上限 vs 账户规模的配错检查 ---
   // +$50/-$15 是按 $200 账户定的（+25% / -7.5%）。原样搬到一个 $10,000 的
   // 演示账户上，-$15 只有 0.15% —— 每一笔都会被「当日剩余亏损额度」闸门压到
   // 极小手数，而且**一笔亏损就结束当天**。EA 不会报错，只会安静地几乎不干活，
   // 所以这里必须开口说。
   if(DailyMaxLossUSD() < risk1)
      LogLine("WARN", StringFormat(
         "配置错配：当日亏损上限 $%.2f 小于单笔 %.1f%% 风险 $%.2f。"
         "后果是每笔都被压到 %.3f%% 风险，且一笔亏损就触发当日停止 —— 一天基本只做一笔。"
         "两个解法：把演示账户余额调成你真实计划的规模；或把日内上限按比例改成 "
         "目标 +$%.0f / 上限 -$%.0f（即当前余额的 +25%% / -7.5%%，与 $200 账户的 +$50/-$15 同口径）。",
         DailyMaxLossUSD(), InpRiskPctDefault, risk1,
         DailyMaxLossUSD() / bal * 100.0, bal * 0.25, bal * 0.075));

   if(margin > EffectiveBalance() * InpMaxMarginPctPerPos / 100.0)
      LogLine("WARN", StringFormat(
         "最小手数 %.2f 需要保证金 $%.2f，超过账户 %.0f%% 上限（余额 $%.2f）。"
         "以当前杠杆，这个账户几乎开不了合规仓位 —— EA 会持续 NO TRADE。"
         "请确认经纪商的黄金最小手数与杠杆。", lotMin, margin, InpMaxMarginPctPerPos, bal));

   if(slAtMinLot1 > 0 && slAtMinLot1 < InpSlMinUSD)
      LogLine("WARN", StringFormat(
         "按 1%% 风险，最小手数只允许 $%.2f 的止损，小于设定的最小止损 $%.2f。"
         "多数信号会因风险超限被拒。%s", slAtMinLot1, InpSlMinUSD,
         InpSmallAccountEscalate
            ? StringFormat("小账户救济已开启：需要时会把单笔风险上调至 %.1f%%（对应止损 $%.2f）。",
                           InpRiskPctMax, slAtMinLot2)
            : "小账户救济已关闭（InpSmallAccountEscalate=false）。"));

   // 抬到 2% 上限仍然接不住 M5 的结构止损 -> 这是账户规模问题，参数救不了
   if(slAtMinLot2 > 0 && slAtMinLot2 < 3.0)
      LogLine("WARN", StringFormat(
         "即使按上限 %.1f%% 风险，最小手数也只允许 $%.2f 的止损。黄金 M5 的结构止损通常在 $3~$6，"
         "本账户会持续拒单 —— 这是账户规模/最小手数问题，调参数解决不了。"
         "出路：换最小手数更小的黄金品种，或把余额加到约 $%.0f。",
         InpRiskPctMax, slAtMinLot2, 4.0 / (InpRiskPctMax / 100.0)));

   SuggestFinerGoldSymbol();

   if(InpInvertSignals)
      LogLine("INVERT", "信号倒转已开启 —— 所有方向取反，止损/止盈以入场价镜像反射。"
                        "这是诊断用途：成本在两个方向上都要付，毛期望为 0 时倒转照样亏。");

   // --- 触发周期 ---
   {
      int secLtf = PeriodSeconds(InpLTF), secEnt = PeriodSeconds(g_entryTF);
      LogLine("ENTRY", StringFormat(
         "触发周期 %s（趋势/结构/ATR 仍在 %s）—— 一个形态最长等 %d 秒被确认，"
         "相对 %s 快 %.1f 倍。",
         EnumToString(g_entryTF), EnumToString(InpLTF), secEnt,
         EnumToString(InpLTF), secEnt > 0 ? (double)secLtf / secEnt : 1.0));
      if(secEnt > secLtf)
         LogLine("WARN", StringFormat(
            "触发周期 %s **比** 交易周期 %s 还慢，进场只会更迟钝。"
            "想更快就把 InpEntryTF 设成比 %s 更小的周期。",
            EnumToString(g_entryTF), EnumToString(InpLTF), EnumToString(InpLTF)));
   }

   // --- 快速离场的自检:盈亏比、保本胜率、以及**日目标够不够得着** ---
   if(InpQuickProfitUSD > 0.0)
   {
      double effRisk = risk1;
      if(InpRiskCapUSD > 0.0) effRisk = MathMin(effRisk, InpRiskCapUSD);
      double rr = (effRisk > 0.0) ? InpQuickProfitUSD / effRisk : 0.0;
      double be = (rr > 0.0) ? 100.0 / (1.0 + rr) : 100.0;
      LogLine("QUICK", StringFormat(
         "净赚 $%.2f 立刻平仓 | 每笔实际风险 $%.2f | RR 1:%.2f | 保本胜率需 %.1f%%",
         InpQuickProfitUSD, effRisk, rr, be));

      if(rr < 0.8)
         LogLine("WARN", StringFormat(
            "赚 $%.2f / 亏 $%.2f = RR 1:%.2f —— 保本胜率要 %.1f%%。"
            "把 InpRiskCapUSD 设成 $%.2f 可得 RR 1:1。",
            InpQuickProfitUSD, effRisk, rr, be, InpQuickProfitUSD));

      // 这条是最容易被忽略、也最致命的一条:
      // 每笔只赚固定金额时,一天能赚到的**上限**就是 笔数 × 每笔金额。
      // 如果这个上限低于日目标,日目标永远触发不了 —— 于是每天唯一会生效的
      // 熔断就只剩"日亏上限"。小赢封顶、大亏照收,账户只会单向往下走。
      double maxDay = InpMaxTradesPerDay * InpQuickProfitUSD;
      double tgt    = DailyTargetUSD();
      if(tgt > 0.0 && maxDay < tgt)
         LogLine("WARN", StringFormat(
            "日目标 $%.2f 摸不到：每笔只赚 $%.2f × 每日上限 %d 笔 = 最多 $%.2f。"
            "日目标会永远失效，每天只有日亏上限 $%.2f 会触发 —— 小赢封顶、大亏照收。"
            "要么把 InpMaxTradesPerDay 提到 %d 以上，要么把日目标降到 $%.2f 以下。",
            tgt, InpQuickProfitUSD, InpMaxTradesPerDay, maxDay, DailyMaxLossUSD(),
            (int)MathCeil(tgt / InpQuickProfitUSD), maxDay));
   }

   // --- 固定金额目标的自检:把目标、风险、RR、保本胜率一次算清 ---
   if(InpTargetProfitUSD > 0.0)
   {
      double effRisk = risk1;                                  // 按默认风险% 算出的美元风险
      if(InpRiskCapUSD > 0.0) effRisk = MathMin(effRisk, InpRiskCapUSD);
      double rr   = (effRisk > 0.0) ? InpTargetProfitUSD / effRisk : 0.0;
      double be   = (rr > 0.0) ? 100.0 / (1.0 + rr) : 100.0;    // 不含成本的保本胜率
      LogLine("TARGET", StringFormat(
         "固定金额目标 $%.2f | 每笔实际风险 $%.2f | RR 1:%.2f | 保本胜率需 %.1f%%（未含点差）",
         InpTargetProfitUSD, effRisk, rr, be));

      if(rr < 0.5)
         LogLine("WARN", StringFormat(
            "目标/风险 = 1:%.2f —— 拿 $%.2f 去赚 $%.2f，保本胜率要 %.1f%%，"
            "扣掉点差只会更高。把 InpRiskCapUSD 设成 $%.2f 可得 RR 1:1，设成 $%.2f 可得 1:2。",
            rr, effRisk, InpTargetProfitUSD, be,
            InpTargetProfitUSD, InpTargetProfitUSD / 2.0));

      // 换算成"金价要走多少" —— 用最小手数举例,实际手数由每笔的止损距离决定
      double mppdMin = lotMin * mppd;
      if(mppdMin > 0.0)
         LogLine("TARGET", StringFormat(
            "参考:最小手 %s 时每 $1 金价波动盈亏 $%.2f，赚 $%.2f 需金价走 $%.2f。"
            "实际手数按每笔止损距离反推，日志会逐笔写明。",
            DoubleToString(lotMin, VolDigits()), mppdMin,
            InpTargetProfitUSD, InpTargetProfitUSD / mppdMin));
   }

   if(InpUseKeyLevels)
   {
      KeyLevels k0 = GetKeyLevels();
      LogLine("LEVELS", StringFormat(
         "机构参考位 | 前日高 %.2f  前日低 %.2f | 亚洲盘(服务器%02d:00-%02d:00) %s | 整数关口每 $%.0f",
         k0.pdh, k0.pdl, InpAsiaStartHour, InpAsiaEndHour,
         k0.asiaOk ? StringFormat("高 %.2f  低 %.2f", k0.asiaHi, k0.asiaLo) : "数据不足",
         InpRoundStep));
   }

   EventSetTimer(30);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   ReportSpreadHour(g_lastSpHour);      // 卸载前把当前这一小时的画像留下
   ReportReasons("卸载前合计");
   EventKillTimer();
   IndicatorRelease(hEmaFastH); IndicatorRelease(hEmaSlowH);
   IndicatorRelease(hEmaFastL); IndicatorRelease(hEmaSlowL);
   IndicatorRelease(hAtrL); IndicatorRelease(hRsiL); IndicatorRelease(hAdxL);
   Comment("");
}

void OnTimer()
{
   ReadCommandFile();
   CleanFlags();
   DayStats ds = GetDayStats();
   Panel(ds, g_lastNoTradeReason);
   PublishStatus(ds, g_lastNoTradeReason);
   ReportTradeStats(10);                 // 规格 §33：每 10 笔出一次统计
}

//==================================================================
// 主循环
//==================================================================
void OnTick()
{
   TrackSpread();                 // 点差画像:每 tick 记一笔,跨小时输出上一小时的统计

   double atr = Buf(hAtrL, 0, 1);
   if(atr <= 0.0) return;

   DayStats ds = GetDayStats();

   // 跨日重置提示
   static datetime lastDay = 0;
   if(g_dayStart != lastDay)
   {
      lastDay = g_dayStart;
      g_dayHaltLogged = false;
      ReportReasons("昨日合计");
      for(int r = 0; r < RB_N; r++) g_rbHit[r] = 0;
      LogLine("DAY", StringFormat("新交易日 %s，余额 $%.2f",
              TimeToString(g_dayStart, TIME_DATE), AccountInfoDouble(ACCOUNT_BALANCE)));
   }

   //--------------------------------------------------------------
   // 1) 硬性日内停止：先于一切逻辑
   //--------------------------------------------------------------
   if(ds.total >= DailyTargetUSD())
   {
      if(HasOpenPosition()) CloseAll(StringFormat("达到当日目标 +$%.2f", ds.total));
      if(!g_dayHaltLogged)
      {
         LogLine("HALT", StringFormat("当日盈利 $%.2f >= 目标 $%.2f —— 停止交易，今天结束。",
                 ds.total, DailyTargetUSD()));
         Push(StringFormat("达到当日目标 +$%.2f，已平仓并停止交易", ds.total));
         g_dayHaltLogged = true;
      }
      Panel(ds, "已达当日目标，停止交易");
      return;
   }

   if(ds.total <= -DailyMaxLossUSD())
   {
      if(HasOpenPosition()) CloseAll(StringFormat("触及当日最大亏损 $%.2f", ds.total));
      if(!g_dayHaltLogged)
      {
         LogLine("HALT", StringFormat("当日亏损 $%.2f <= -$%.2f —— 平仓并停止交易，今天结束。",
                 ds.total, DailyMaxLossUSD()));
         Push(StringFormat("触及当日亏损上限 $%.2f，已平仓并停止交易", ds.total));
         g_dayHaltLogged = true;
      }
      Panel(ds, "触及当日亏损上限，停止交易");
      return;
   }

   //--------------------------------------------------------------
   // 2) 持仓管理（每 tick）
   //--------------------------------------------------------------
   // --- 重大数据前清仓（规格 §26）---
   // 必须放在 ManagePositions **之前**、且不受 IsNewBar 限制:
   // 要赶在事件发生前离场,晚一根 M5 就没意义了。
   {
      string nwhy = "";
      if(NewsFlattenDue(nwhy) && HasOpenPosition())
      {
         CloseAll(StringFormat("重大数据前 %d 分钟清仓：%s", InpFlatBeforeNewsMin, nwhy));
         Push(StringFormat("⚠️ 重大数据临近（%s），已清仓离场", nwhy));
      }
   }

   ManagePositions(atr);

   //--------------------------------------------------------------
   // 3) 只在新 K 线上找入场
   //--------------------------------------------------------------
   if(!IsNewBar(g_entryTF)) return;

   // --- 多仓闸门（规格 §30）---
   // 加仓 = 往同一笔上追;多仓 = 各自独立的 setup + 各自独立的止损。
   // 后者不违反"禁止亏损加仓",前提是**总在险金额有上限**,那才是真正该守的东西。
   int nPos = CountMyPositions();
   if(nPos > 0)
   {
      if(!InpAllowMultiPosition && !InpAllowAddOn)
      {
         Panel(ds, "持仓中，等待管理（未开启多仓/加仓）");
         return;
      }
      if(InpAllowMultiPosition && nPos >= InpMaxPositions)
      {
         NoTrade(StringFormat("已达最大同时持仓数 %d", InpMaxPositions));
         Panel(ds, "持仓数上限");
         return;
      }
   }

   // 连亏保护
   if(ConsecStopOn(ds.consecLoss))
   {
      NoTrade(StringFormat("连亏 %d 笔 —— 当天停止交易", ds.consecLoss));
      Panel(ds, "连亏停止");
      return;
   }

   // 笔数上限
   if(ds.trades >= InpMaxTradesPerDay)
   {
      NoTrade(StringFormat("已达当日笔数上限 %d", InpMaxTradesPerDay));
      Panel(ds, "笔数上限");
      return;
   }

   // 外部指令：只能让它**少做**，不能让它多做
   if(g_cmdHalt)
   {
      NoTrade(StringFormat("外部指令：暂停开仓%s",
              StringLen(g_cmdNote) > 0 ? "（" + g_cmdNote + "）" : ""));
      Panel(ds, "外部指令暂停");
      return;
   }

   // 时段 / 点差 / 新闻
   string why = "";
   if(!SessionOk(why))      { NoTrade(why); Panel(ds, why); return; }
   if(!SpreadOk(atr, why))  { NoTrade(why); Panel(ds, why); return; }
   if(NewsBlocked(why))     { NoTrade(why); Panel(ds, why); return; }

   // 波动率
   if(atr < InpAtrMinUSD) { NoTrade(StringFormat("ATR %.2f 过低，波动不足", atr)); Panel(ds, "波动不足"); return; }
   if(atr > InpAtrMaxUSD) { NoTrade(StringFormat("ATR %.2f 过高，波动异常", atr)); Panel(ds, "波动异常"); return; }

   // 规格 §13：Extreme 波动等结构稳定，High 波动继续做但降仓（降仓在下面按乘数生效）
   double volRatio = 1.0;
   int    vol      = VolRegime(atr, volRatio);
   if(vol == 3)
   {
      NoTrade(StringFormat("波动 Extreme（ATR %.2f = 均值的 %.2f 倍），等结构稳定", atr, volRatio));
      Panel(ds, "波动 Extreme");
      return;
   }

   // 市场质量：横盘 / 高频假突破。
   // InpUseMarketQuality=false 时不否决交易，但结论照样算、照样跟着成交记录下来。
   string qWhy = "";
   bool   qOk  = MarketQualityOk(atr, qWhy);
   if(InpUseMarketQuality && !qOk) { NoTrade(qWhy); Panel(ds, qWhy); return; }
   g_quality = (qOk ? "OK|" : "BAD|") + qWhy;

   //--------------------------------------------------------------
   // 4) 模式：盈利保护 + 观察模式
   //--------------------------------------------------------------
   int    minScore = InpMinScore;
   double riskPct  = InpRiskPctDefault;
   double minRRreq = InpMinRR;

   if(ConsecObserveOn(ds.consecLoss)) { minScore += 1; riskPct = MathMin(riskPct, 1.0); }
   if(ds.total >= ConservativeAtUSD())            { minScore += 1; riskPct = MathMin(riskPct, 0.75); }
   if(ds.total >= ReducedAtUSD())                 { minScore  = 7; riskPct = MathMin(riskPct, 0.5); minRRreq = 2.0; }
   if(minScore > 7) minScore = 7;

   //--------------------------------------------------------------
   // 5) 信号
   //--------------------------------------------------------------
   Signal sg = BuildSignal(atr, minScore);
   if(sg.dir == 0) { Panel(ds, g_lastNoTradeReason); return; }

   if(g_cmdBlockDir != 0 && sg.dir == g_cmdBlockDir)
   {
      NoTrade(StringFormat("外部指令：禁止%s%s", sg.dir > 0 ? "做多" : "做空",
              StringLen(g_cmdNote) > 0 ? "（" + g_cmdNote + "）" : ""));
      Panel(ds, "外部指令禁止该方向");
      return;
   }
   // 同上:固定金额目标模式下 RR 是结果不是前提,保守/收紧档的 RR 要求不适用
   if(InpTargetProfitUSD <= 0.0 && InpQuickProfitUSD <= 0.0 && sg.rr < minRRreq)
   {
      NoTrade(StringFormat("当前模式要求 RR >= %.2f，实际 %.2f", minRRreq, sg.rr));
      Panel(ds, "RR 不达标");
      return;
   }

   // --- 风险由 setup 分级给出（规格 §14/§29），不由"想赚多少"给 ---
   if(InpUseV2Scoring && sg.riskCapPct > 0.0)
   {
      double capped = MathMin(sg.riskCapPct, InpRiskPctMax);   // 硬上限永远压得住分级
      // 连亏观察档 / 盈利保护档只降不升 —— 分级再高也不能把这两档顶回去
      if(ConsecObserveOn(ds.consecLoss)) capped = MathMin(capped, 1.0);
      if(ds.total >= ConservativeAtUSD())            capped = MathMin(capped, 0.75);
      if(ds.total >= ReducedAtUSD())                 capped = MathMin(capped, 0.5);
      riskPct = capped;
      LogLine("GRADE", StringFormat("%s级 %d/10 -> 风险 %.2f%% | %s",
              sg.grade, sg.score, riskPct, sg.scoreDetail));
   }
   else if(sg.score >= 7 && ds.consecLoss == 0 && ds.total < ConservativeAtUSD())
      riskPct = MathMin(InpRiskPctMax, 2.0);

   // 规格 §13：High 波动降仓
   if(vol == 2 && InpVolHighSizeMult > 0.0 && InpVolHighSizeMult < 1.0)
   {
      double before = riskPct;
      riskPct *= InpVolHighSizeMult;
      LogLine("RISK", StringFormat("波动 High（ATR %.2f = 均值 %.2f 倍），风险 %.2f%% -> %.2f%%",
              atr, volRatio, before, riskPct));
   }

   // 小账户救济：最小手数在当前预算下开不了，但抬到 2% 上限就能开 -> 抬。
   // 放在这里而不是更后面，是为了让下面两道**降险**闸门（加仓预算、当日剩余亏损额度）
   // 依然能把它压回去 —— 上调只是解锁开仓，不是绕过任何一条上限。
   string escNote = "";
   riskPct = EscalateRiskForMinLot(MathAbs(sg.entry - sg.sl), riskPct, ds, escNote);
   if(StringLen(escNote) > 0) LogLine("RISK", escNote);

   // --- 已有持仓时的两道闸门 ---
   if(nPos > 0)
   {
      if(InpAllowMultiPosition)
      {
         // 规格 §31：默认禁止对冲 —— 反向开仓是在掩盖错误，不是在管理风险
         int pd = MyPositionDir();
         if(!InpAllowHedge && pd != 0 && pd != sg.dir)
         {
            NoTrade(StringFormat("禁止对冲：已有%s仓，本信号为%s",
                    pd > 0 ? "多" : "空", sg.dir > 0 ? "多" : "空"));
            Panel(ds, "禁止对冲");
            return;
         }

         // 规格 §30：所有持仓的在险金额合计不得超过净值的 InpMaxCombinedRiskPct
         // OpenRiskUSD() 把已移到保本之外的仓位按 0 计 —— 那些确实不再有风险敞口。
         double eq        = EffectiveBalance();   // 组合风险上限同样按虚拟本金算
         double openRisk  = OpenRiskUSD();
         double budget    = eq * InpMaxCombinedRiskPct / 100.0 - openRisk;
         double thisRisk  = EffectiveBalance() * riskPct / 100.0;
         if(budget <= 0.0)
         {
            NoTrade(StringFormat("组合风险已用尽：在险 $%.2f 已达净值的 %.1f%%",
                    openRisk, InpMaxCombinedRiskPct));
            Panel(ds, "组合风险上限");
            return;
         }
         if(thisRisk > budget)
         {
            double before = riskPct;
            riskPct = budget / EffectiveBalance() * 100.0;
            LogLine("RISK", StringFormat(
               "组合风险剩余 $%.2f（已在险 $%.2f / 上限 %.1f%%），本笔风险 %.2f%% -> %.2f%%",
               budget, openRisk, InpMaxCombinedRiskPct, before, riskPct));
         }
      }
      else
      {
         // 未开多仓 = 走原来的严格加仓闸门（规格十四的六项条件）
         string addWhy = "";
         if(!AddOnAllowed(sg.dir, sg.score, ds, riskPct, addWhy))
         {
            NoTrade(addWhy);
            Panel(ds, addWhy);
            return;
         }
      }
   }

   // 单笔风险不得让当日亏损突破 -15：剩余亏损额度更小时，按额度缩仓
   double remainingLoss = DailyMaxLossUSD() + ds.total; // ds.total 为负时额度变小
   double riskMoney     = EffectiveBalance() * riskPct / 100.0;
   if(remainingLoss < riskMoney)
   {
      if(remainingLoss <= 0.30) { NoTrade("当日剩余亏损额度不足，不开新仓"); Panel(ds, "额度不足"); return; }
      riskPct = remainingLoss / EffectiveBalance() * 100.0;
      LogLine("RISK", StringFormat("剩余亏损额度 $%.2f，本笔风险下调至 %.2f%%", remainingLoss, riskPct));
   }

   // --- 规格 §38：开仓前输出完整决策块 ---
   {
      MqlDateTime st; TimeToStruct(TimeCurrent(), st);
      string sess = (st.hour >= InpAsiaStartHour && st.hour < InpAsiaEndHour) ? "Asia"
                  : (st.hour >= InpAsiaEndHour && st.hour < InpAsiaEndHour + 5) ? "London" : "New York";
      KeyLevels kk = GetKeyLevels();
      LogLine("DECISION", StringFormat(
         "XAUUSD %.2f | %s | H1=%d M15=%d M5=%d | 前日高%.2f 低%.2f 亚洲高%.2f 低%.2f | "
         "SWEEP=%s | MSS=%s | 动能=%s | ATR %.2f(%s) | ENTRY %.2f SL %.2f TP %.2f RR 1:%.2f | "
         "%s级 %d/10 -> 风险 %.2f%% | %s",
         sg.entry, sess, HtfTrend(), MarketStructure(InpMTF), MarketStructure(InpLTF),
         kk.pdh, kk.pdl, kk.asiaOk ? kk.asiaHi : 0.0, kk.asiaOk ? kk.asiaLo : 0.0,
         StringFind(sg.note, "扫损") >= 0 ? "YES" : "NO",
         StringFind(sg.scoreDetail, "BOS") >= 0 || StringFind(sg.scoreDetail, "CHoCH") >= 0 ? "YES" : "NO",
         Momentum() == sg.dir ? "Strong" : "Normal",
         atr, VolRegimeName(vol), sg.entry, sg.sl, sg.tp2, sg.rr,
         sg.grade, sg.score, riskPct, sg.note));
   }

   OpenTrade(sg, riskPct, ds);
}
//+------------------------------------------------------------------+
