//+------------------------------------------------------------------+
//|                                                  BTCScalper.mq5  |
//|        BTCUSD 快进快出剥头皮 EA（MQL5 / MetaTrader 5 · XM BTCUSD#）  |
//+------------------------------------------------------------------+
//
//  骨架来自 GoldScalper.mq5(风险定量、点差过滤、当日熔断、分型结构、
//  保本+ATR追踪、服务器端止损),入场和过滤换成适合 BTC 的版本,
//  并整合了网上常见的 BTC 剥头皮做法和 NyaoScalper 的几个风控思路。
//  对应的 Python 复刻 + 样本外验证:btc_research.py → reports/btc_research.md
//
//  ── 和 GoldScalper 一样,这里**没有**什么 ───────────────────────────
//  没有马丁格尔、没有网格、没有加仓摊平、没有对冲链恢复。
//  NyaoScalper 的 Hedge Chain Recovery 作者自己都标注是马丁格尔 —— 不抄。
//  每一笔进场必带止损,止损跟单子一起提交给服务器。
//
//  ── BTC 和黄金不一样的地方 ─────────────────────────────────────────
//  1) 24/7 交易(XM 周末也开,但会有短暂维护,流动性差、点差大)。
//     所以不再按周末一刀切,而是:周末可选降风险 + 点差过滤兜底。
//  2) XM BTCUSD# 合约 = 1 BTC/手,最小 0.01 手 → 价格每动 $1 盈亏 $0.01。
//     止损 $300 × 0.01 手 = $3 风险。小账户做得了,但点差是 $ 级别的硬成本。
//  3) 点差相对波动更大、会突然放大 → 除了绝对点差上限,再加「点差占 ATR 比例」上限。
//  4) 加密 CFD 的隔夜利息很贵 → 时间止损:持有超过 N 根 K 线直接平,真正的快进快出。
//  5) 会无预警跳水/拉升 → 崩盘保护(来自 ai4trade 加密版的 crash circuit breaker)。
//
//  ── 策略 ────────────────────────────────────────────────────────
//  趋势:EMA 快>慢 且收盘在趋势 EMA 同侧(做空镜像)
//  VWAP:只在当日 VWAP 上方做多、下方做空(EMA9/21 + VWAP 是网上最常见的 BTC 5m 组合)
//  入场 A 回踩:收盘回到快线 ±0.5ATR 内、收在慢线同侧、收出顺势 K 线、RSI 在甜区
//  入场 B 突破:收盘突破分型阻力/支撑 + 缓冲(GoldScalper 入场 A)
//  入场 C 反转(默认关):布林带外 + RSI 极值 + 反向 K 线 —— 你加密版回测里这类是亏的
//  过滤:死市(ATR/均ATR)、点差/ATR、反向长影线、崩盘/暴涨、时段、冷却、日内笔数
//  出场:固定 RR 止盈;到 1R 保本 + ATR 追踪;时间止损
//
//  免责:研究/学习用途,不构成投资建议。加密货币杠杆交易可能损失全部本金。
//+------------------------------------------------------------------+
#property copyright "ai4trade-bot"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <Trade/SymbolInfo.mqh>

//--- 风险 ----------------------------------------------------------
input group "=== 风险管理 ==="
input double InpRiskPercent      = 1.0;    // 每笔风险占净值 %
input double InpMaxRiskPercent   = 2.0;    // 硬上限 %(超过会被夹回;最小手超过它就不开)
input double InpDailyLossPct     = 4.0;    // 当日亏损达净值 % 即停手
input int    InpMaxPositions     = 1;      // 最大同时持仓数
input int    InpMaxTradesPerDay  = 20;     // 每天最多开几笔(剥头皮最怕越亏越频繁)
input int    InpCooldownBars     = 3;      // 亏损平仓后冷却几根 K 线再开
input double InpFixedLots        = 0.0;    // >0 则固定手数,忽略风险%计算

//--- 成本过滤 ------------------------------------------------------
input group "=== 成本过滤 ==="
input double InpMaxSpreadUSD     = 40.0;   // 点差超过这个金额($)就不交易 —— 按你账户实际点差调
input double InpMaxSpreadATRPct  = 25.0;   // 点差超过 ATR 的这个 % 就不交易
input double InpMinStopSpreadX   = 4.0;    // 止损至少是点差的几倍
input int    InpSlippagePoints   = 500;    // 允许滑点(point)

//--- 策略 ----------------------------------------------------------
input group "=== 策略 ==="
// ⬇ 默认值来自样本外验证(reports/btc_research.md):48 组里只有
//   H1 + 趋势回踩 + 时段过滤 两边为正(验证 122 笔 / 50% / +0.078R)。
//   M5/M15 的真·快进快出全部为负 —— M5 上 $30 点差 ≈ ATR 的 40%。
//   要跑 M5 请加载 presets/btc/m5_fast.set,但那套没有通过验证。
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_H1;  // 工作周期
input bool   InpUsePullback      = true;   // 入场 A:趋势回踩
input bool   InpUseBreakout      = false;  // 入场 B:结构突破(回测各周期均为负,默认关)
input bool   InpUseMeanRev       = false;  // 入场 C:布林带反转(默认关)
input int    InpFastEMA          = 9;
input int    InpSlowEMA          = 21;
input int    InpTrendEMA         = 100;
input bool   InpUseVWAP          = true;   // 只在当日 VWAP 同侧开仓
input int    InpRSIPeriod        = 14;
input double InpRSILongMin       = 40.0;   // 做多 RSI 甜区
input double InpRSILongMax       = 70.0;
input double InpRSIShortMin      = 30.0;   // 做空 RSI 甜区
input double InpRSIShortMax      = 60.0;
input int    InpBBPeriod         = 20;     // 反转模块用
input double InpBBDev            = 2.0;
input int    InpATRPeriod        = 14;
input double InpATRStopMult      = 1.5;    // 止损 = ATR × 这个倍数
input double InpRewardRisk       = 1.5;    // 止盈 = 止损 × 这个倍数
input int    InpSwingLookback    = 100;
input int    InpSwingWing        = 2;

//--- 过滤器 --------------------------------------------------------
input group "=== 过滤器 ==="
input double InpDeadMarketRatio  = 0.7;    // ATR / 50根平均ATR 低于它 = 死市,不做
input double InpWickBodyMax      = 1.5;    // 反向影线 > 实体 × 这个倍数 就不做(0=关)
input double InpCrashPct         = 3.0;    // 距 4h 高点跌超 %:不开多;距低点涨超 %:不开空

//--- 出场管理 ------------------------------------------------------
input group "=== 出场 ==="
input bool   InpUseBreakeven     = true;   // 到 1R 移保本
input bool   InpUseTrailing      = true;   // 保本后 ATR 追踪
input double InpTrailATRMult     = 1.0;
input int    InpMaxHoldBars      = 12;     // 时间止损:持有超过几根 K 线就平(0=关)

//--- 时段 ----------------------------------------------------------
input group "=== 时段(服务器时间;XM 服务器 = GMT+2 冬令 / GMT+3 夏令) ==="
input bool   InpUseSession       = true;
input int    InpSessionStartHour = 9;      // ≈ 伦敦开盘(夏令 06:00 UTC)
input int    InpSessionEndHour   = 23;     // ≈ 纽约午后(夏令 20:00 UTC)
input bool   InpTradeWeekend     = true;   // BTC 周末也开;流动性差,见下一项
input double InpWeekendRiskMult  = 0.5;    // 周末风险打几折

//--- 其他 ----------------------------------------------------------
input group "=== 其他 ==="
input long   InpMagic            = 20260930;
input bool   InpAlerts           = true;

//--- 全局 ----------------------------------------------------------
CTrade        trade;
CSymbolInfo   sym;
int           hFast, hSlow, hTrend, hRSI, hATR, hBB;
datetime      lastBarTime    = 0;
datetime      dayStamp       = 0;
double        dayStartEquity = 0.0;
bool          dayBlocked     = false;

//+------------------------------------------------------------------+
int OnInit()
{
   if(!sym.Name(_Symbol))
   {
      Print("无法初始化交易品种 ", _Symbol);
      return(INIT_FAILED);
   }
   sym.RefreshRates();

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   hFast  = iMA(_Symbol, InpTimeframe, InpFastEMA,  0, MODE_EMA, PRICE_CLOSE);
   hSlow  = iMA(_Symbol, InpTimeframe, InpSlowEMA,  0, MODE_EMA, PRICE_CLOSE);
   hTrend = iMA(_Symbol, InpTimeframe, InpTrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   hRSI   = iRSI(_Symbol, InpTimeframe, InpRSIPeriod, PRICE_CLOSE);
   hATR   = iATR(_Symbol, InpTimeframe, InpATRPeriod);
   hBB    = iBands(_Symbol, InpTimeframe, InpBBPeriod, 0, InpBBDev, PRICE_CLOSE);

   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hTrend == INVALID_HANDLE ||
      hRSI  == INVALID_HANDLE || hATR  == INVALID_HANDLE || hBB    == INVALID_HANDLE)
   {
      Print("指标句柄创建失败");
      return(INIT_FAILED);
   }

   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   dayStamp       = TodayStamp();

   PrintFormat("BTCScalper 启动 | %s %s | 净值 %.2f | 合约 %.2f | 最小手 %.3f | 步长 %.3f | 点差 %.2f",
               _Symbol, EnumToString(InpTimeframe),
               AccountInfoDouble(ACCOUNT_EQUITY),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
               sym.Ask() - sym.Bid());
   WarnIfUntradeable();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hFast);  IndicatorRelease(hSlow);  IndicatorRelease(hTrend);
   IndicatorRelease(hRSI);   IndicatorRelease(hATR);   IndicatorRelease(hBB);
}

// 开口自检:最小手数下、按当前 ATR 止损要冒多少风险
void WarnIfUntradeable()
{
   double eq     = AccountInfoDouble(ACCOUNT_EQUITY);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double atr[];
   if(CopyBuffer(hATR, 0, 1, 1, atr) < 1) return;
   double dist = atr[0] * InpATRStopMult;
   double risk = MoneyForDistance(minLot, dist);
   double pct  = (eq > 0) ? risk / eq * 100.0 : 0.0;
   PrintFormat("自检:最小手 %.3f × 止损 $%.2f → 风险 $%.2f = 净值的 %.2f%%",
               minLot, dist, risk, pct);
   if(pct > InpMaxRiskPercent)
      PrintFormat("⚠️ 最小手数下的单笔风险(%.2f%%)超过上限 %.2f%% —— 这些单会被拒绝。"
                  "要么加本金,要么换更低周期(ATR 更小),要么调高上限(不建议)。",
                  pct, InpMaxRiskPercent);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!sym.RefreshRates()) return;

   ResetDailyIfNeeded();
   ManageOpenPositions();      // 保本/追踪/时间止损每个 tick 都跑

   // 入场只在新 K 线上判断一次(用已收盘的 K 线,避免信号在 K 线内闪烁)
   datetime t = iTime(_Symbol, InpTimeframe, 0);
   if(t == lastBarTime) return;
   lastBarTime = t;

   if(dayBlocked)                             return;
   if(!SessionOK())                           return;
   if(!SpreadOK())                            return;
   if(CountPositions() >= InpMaxPositions)    return;
   if(TradesToday() >= InpMaxTradesPerDay)    return;
   if(InCooldown())                           return;

   TryEntry();
}

//+------------------------------------------------------------------+
//| 每日重置 + 当日亏损熔断                                            |
//+------------------------------------------------------------------+
datetime TodayStamp()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
}

void ResetDailyIfNeeded()
{
   datetime today = TodayStamp();
   if(today != dayStamp)
   {
      dayStamp       = today;
      dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      dayBlocked     = false;
      Print("新交易日,净值基准重置为 ", DoubleToString(dayStartEquity, 2));
   }
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(!dayBlocked && dayStartEquity > 0)
   {
      double ddPct = (dayStartEquity - eq) / dayStartEquity * 100.0;
      if(ddPct >= InpDailyLossPct)
      {
         dayBlocked = true;
         Notify(StringFormat("当日亏损 %.2f%% 达到上限 %.2f%%,今日停止开新仓",
                             ddPct, InpDailyLossPct));
      }
   }
}

//+------------------------------------------------------------------+
//| 过滤器                                                            |
//+------------------------------------------------------------------+
bool IsWeekend()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   return (dt.day_of_week == 0 || dt.day_of_week == 6);
}

bool SessionOK()
{
   if(IsWeekend() && !InpTradeWeekend) return false;
   if(!InpUseSession) return true;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(InpSessionStartHour <= InpSessionEndHour)
      return (dt.hour >= InpSessionStartHour && dt.hour < InpSessionEndHour);
   // 跨午夜的时段,例如 22 → 6
   return (dt.hour >= InpSessionStartHour || dt.hour < InpSessionEndHour);
}

bool SpreadOK()
{
   double spread = sym.Ask() - sym.Bid();
   double atr[];
   double atrNow = (CopyBuffer(hATR, 0, 1, 1, atr) == 1) ? atr[0] : 0.0;
   bool   tooWide  = spread > InpMaxSpreadUSD;
   bool   tooRatio = (atrNow > 0 && spread > atrNow * InpMaxSpreadATRPct / 100.0);
   if(tooWide || tooRatio)
   {
      static datetime lastWarn = 0;
      if(TimeCurrent() - lastWarn > 300)
      {
         PrintFormat("点差 $%.2f(ATR $%.2f 的 %.0f%%)超过上限,跳过",
                     spread, atrNow, atrNow > 0 ? spread / atrNow * 100.0 : 0.0);
         lastWarn = TimeCurrent();
      }
      return false;
   }
   return true;
}

int CountPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
         n++;
   }
   return n;
}

// 今天(服务器日)已经开了几笔
int TradesToday()
{
   if(!HistorySelect(dayStamp, TimeCurrent() + 60)) return 0;
   int n = 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)      continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)     continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN) n++;
   }
   return n;
}

// 最近一笔平仓如果是亏损,冷却 N 根 K 线 —— 连续在同一段噪音里反复被扫是剥头皮最常见的死法
bool InCooldown()
{
   if(InpCooldownBars <= 0) return false;
   int secs = InpCooldownBars * PeriodSeconds(InpTimeframe);
   if(!HistorySelect(TimeCurrent() - secs, TimeCurrent() + 60)) return false;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
   {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0) continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)          continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)         continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) != DEAL_ENTRY_OUT)   continue;
      double pnl = HistoryDealGetDouble(d, DEAL_PROFIT)
                 + HistoryDealGetDouble(d, DEAL_SWAP)
                 + HistoryDealGetDouble(d, DEAL_COMMISSION);
      return (pnl < 0);      // 只看最近一笔
   }
   return false;
}

//+------------------------------------------------------------------+
//| 结构:分型摆动点 -> 支撑/阻力(同 GoldScalper)                      |
//+------------------------------------------------------------------+
bool FindStructure(double &resistance, double &support)
{
   int    need = InpSwingLookback + InpSwingWing * 2 + 2;
   double hi[], lo[];
   ArraySetAsSeries(hi, true);
   ArraySetAsSeries(lo, true);
   if(CopyHigh(_Symbol, InpTimeframe, 0, need, hi) < need) return false;
   if(CopyLow (_Symbol, InpTimeframe, 0, need, lo) < need) return false;

   double bestHi = -DBL_MAX, bestLo = DBL_MAX;
   for(int i = InpSwingWing + 1; i <= InpSwingLookback; i++)
   {
      bool isHigh = true, isLow = true;
      for(int k = 1; k <= InpSwingWing; k++)
      {
         if(hi[i] < hi[i - k] || hi[i] < hi[i + k]) isHigh = false;
         if(lo[i] > lo[i - k] || lo[i] > lo[i + k]) isLow  = false;
      }
      if(isHigh && hi[i] > bestHi) bestHi = hi[i];
      if(isLow  && lo[i] < bestLo) bestLo = lo[i];
   }
   if(bestHi == -DBL_MAX || bestLo == DBL_MAX) return false;
   resistance = bestHi;
   support    = bestLo;
   return true;
}

//+------------------------------------------------------------------+
//| 当日 VWAP(用 tick volume;CFD 没有真实成交量)                     |
//+------------------------------------------------------------------+
double DailyVWAP()
{
   int shift = iBarShift(_Symbol, InpTimeframe, dayStamp, false);
   if(shift < 1) shift = 1;                 // 今天刚开盘:至少用上一根
   MqlRates r[];
   ArraySetAsSeries(r, true);
   int got = CopyRates(_Symbol, InpTimeframe, 1, shift, r);   // 只用已收盘 K 线
   if(got < 1) return 0.0;
   double pv = 0.0, vv = 0.0;
   for(int i = 0; i < got; i++)
   {
      double v = (r[i].tick_volume > 0) ? (double)r[i].tick_volume : 1.0;
      pv += (r[i].high + r[i].low + r[i].close) / 3.0 * v;
      vv += v;
   }
   return (vv > 0) ? pv / vv : 0.0;
}

//+------------------------------------------------------------------+
//| 取指标值(index 1 = 最近一根已收盘 K 线)                            |
//+------------------------------------------------------------------+
bool Get1(int handle, int buffer, double &val)
{
   double b[];
   if(CopyBuffer(handle, buffer, 1, 1, b) < 1) return false;
   val = b[0];
   return true;
}

double AvgATR(int n)
{
   double b[];
   int got = CopyBuffer(hATR, 0, 1, n, b);
   if(got < 1) return 0.0;
   double s = 0.0;
   for(int i = 0; i < got; i++) s += b[i];
   return s / got;
}

//+------------------------------------------------------------------+
//| 入场                                                              |
//+------------------------------------------------------------------+
void TryEntry()
{
   double fast, slow, trend, rsi, atr, bbUp, bbLo;
   if(!Get1(hFast, 0, fast) || !Get1(hSlow, 0, slow) || !Get1(hTrend, 0, trend) ||
      !Get1(hRSI, 0, rsi)   || !Get1(hATR, 0, atr)   ||
      !Get1(hBB, 1, bbUp)   || !Get1(hBB, 2, bbLo))
      return;
   if(atr <= 0) return;

   // 死市过滤(NyaoScalper):波动塌下去的时候,剥头皮赚不回点差
   double avgAtr = AvgATR(50);
   if(avgAtr > 0 && atr / avgAtr < InpDeadMarketRatio) return;

   double o1 = iOpen (_Symbol, InpTimeframe, 1);
   double h1 = iHigh (_Symbol, InpTimeframe, 1);
   double l1 = iLow  (_Symbol, InpTimeframe, 1);
   double c1 = iClose(_Symbol, InpTimeframe, 1);
   double spread = sym.Ask() - sym.Bid();

   bool upTrend   = (fast > slow && c1 > trend);
   bool downTrend = (fast < slow && c1 < trend);

   // 崩盘 / 暴涨保护:最近 4 小时
   int n4h = MathMax(2, 4 * 3600 / PeriodSeconds(InpTimeframe));
   int iHi = iHighest(_Symbol, InpTimeframe, MODE_HIGH, n4h, 1);
   int iLo = iLowest (_Symbol, InpTimeframe, MODE_LOW,  n4h, 1);
   if(iHi < 0 || iLo < 0) return;
   double hi4 = iHigh(_Symbol, InpTimeframe, iHi);
   double lo4 = iLow (_Symbol, InpTimeframe, iLo);
   bool noLong  = (hi4 > 0 && (hi4 - c1) / hi4 * 100.0 > InpCrashPct);
   bool noShort = (lo4 > 0 && (c1 - lo4) / lo4 * 100.0 > InpCrashPct);

   bool longOK  = !noLong;
   bool shortOK = !noShort;
   if(InpUseVWAP)
   {
      double vwap = DailyVWAP();
      if(vwap <= 0) return;
      longOK  = longOK  && c1 > vwap;
      shortOK = shortOK && c1 < vwap;
   }

   // 影线惩罚(NyaoScalper):信号 K 线顶着长上影做多 = 上方有人在卖
   if(InpWickBodyMax > 0)
   {
      double body  = MathAbs(c1 - o1);
      double upper = h1 - MathMax(c1, o1);
      double lower = MathMin(c1, o1) - l1;
      if(body <= 0) { longOK = false; shortOK = false; }
      else
      {
         if(upper > body * InpWickBodyMax) longOK  = false;
         if(lower > body * InpWickBodyMax) shortOK = false;
      }
   }

   int    dir    = 0;
   string reason = "";

   // ---- 入场 A:趋势回踩 ----------------------------------------------
   if(InpUsePullback)
   {
      double zone = atr * 0.5;
      if(upTrend && longOK && c1 <= fast + zone && c1 > slow && c1 > o1 &&
         rsi >= InpRSILongMin && rsi <= InpRSILongMax)
      { dir = 1;  reason = "趋势回踩"; }
      else if(downTrend && shortOK && c1 >= fast - zone && c1 < slow && c1 < o1 &&
              rsi >= InpRSIShortMin && rsi <= InpRSIShortMax)
      { dir = -1; reason = "趋势回踩"; }
   }

   // ---- 入场 B:结构突破 ----------------------------------------------
   if(dir == 0 && InpUseBreakout)
   {
      double res, sup;
      if(FindStructure(res, sup))
      {
         double buf = MathMax(atr * 0.15, spread * 2.0);
         if(upTrend && longOK && c1 > res + buf && rsi < InpRSILongMax)
         { dir = 1;  reason = "突破阻力"; }
         else if(downTrend && shortOK && c1 < sup - buf && rsi > InpRSIShortMin)
         { dir = -1; reason = "跌破支撑"; }
      }
   }

   // ---- 入场 C:布林带反转(逆势,不看 VWAP/趋势,但受崩盘保护) --------
   if(dir == 0 && InpUseMeanRev)
   {
      if(!noLong && rsi < 30.0 && l1 <= bbLo && c1 > o1)
      { dir = 1;  reason = "超卖反弹"; }
      else if(!noShort && rsi > 70.0 && h1 >= bbUp && c1 < o1)
      { dir = -1; reason = "超买回落"; }
   }

   if(dir == 0) return;
   OpenTrade(dir, atr, spread, reason);
}

//+------------------------------------------------------------------+
//| 手数(同 GoldScalper:由固定亏损金额反推)                          |
//+------------------------------------------------------------------+
double MoneyForDistance(double lots, double dist)
{
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickSize <= 0 || tickVal <= 0) return 0.0;
   return lots * (dist / tickSize) * tickVal;
}

double CalculateLots(double stopDistance, double &riskUsedOut)
{
   riskUsedOut = 0.0;
   if(stopDistance <= 0) return 0.0;

   if(InpFixedLots > 0)
   {
      riskUsedOut = MoneyForDistance(InpFixedLots, stopDistance);
      return NormalizeLots(InpFixedLots);
   }

   double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
   double pct = MathMin(InpRiskPercent, InpMaxRiskPercent);
   if(IsWeekend()) pct *= InpWeekendRiskMult;
   double risk = eq * pct / 100.0;

   double perLot = MoneyForDistance(1.0, stopDistance);
   if(perLot <= 0) return 0.0;

   double lots = NormalizeLots(risk / perLot);
   if(lots <= 0) return 0.0;

   // 向下取整到最小手后,实际风险可能高于预算 —— 超过硬上限就不开
   double actual = MoneyForDistance(lots, stopDistance);
   if(actual > eq * InpMaxRiskPercent / 100.0)
   {
      PrintFormat("拒绝开仓:最小可下手数 %.2f 的风险 $%.2f 超过上限 %.2f%%(净值 $%.2f)",
                  lots, actual, InpMaxRiskPercent, eq);
      return 0.0;
   }
   riskUsedOut = actual;
   return lots;
}

double NormalizeLots(double lots)
{
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0) step = 0.01;
   lots = MathFloor(lots / step) * step;
   if(lots < minL) lots = minL;
   if(lots > maxL) lots = maxL;
   int digits = (step >= 1.0) ? 0 : (int)MathCeil(-MathLog10(step));
   return NormalizeDouble(lots, digits);
}

//+------------------------------------------------------------------+
//| 下单                                                              |
//+------------------------------------------------------------------+
void OpenTrade(int dir, double atr, double spread, string reason)
{
   double price = (dir > 0) ? sym.Ask() : sym.Bid();

   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)
                       * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double dist = MathMax(atr * InpATRStopMult,
                         MathMax(spread * InpMinStopSpreadX, stopsLevel * 1.5));

   double riskUsed = 0.0;
   double lots     = CalculateLots(dist, riskUsed);
   if(lots <= 0) return;

   double sl = (dir > 0) ? price - dist : price + dist;
   double tp = (dir > 0) ? price + dist * InpRewardRisk
                         : price - dist * InpRewardRisk;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   bool ok = (dir > 0) ? trade.Buy (lots, _Symbol, 0.0, sl, tp, "BTCScalper " + reason)
                       : trade.Sell(lots, _Symbol, 0.0, sl, tp, "BTCScalper " + reason);
   if(ok)
      Notify(StringFormat("%s %s %.2f手 @%.2f SL=%.2f TP=%.2f 风险$%.2f 点差$%.2f (%s)",
                          (dir > 0 ? "买入" : "卖出"), _Symbol, lots, price,
                          sl, tp, riskUsed, spread, reason));
   else
      PrintFormat("下单失败 retcode=%d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
//| 持仓管理:时间止损 + 保本 + ATR 追踪                                |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   double atrBuf[];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1) return;
   double atr    = atrBuf[0];
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   int    maxAge = InpMaxHoldBars * PeriodSeconds(InpTimeframe);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)   continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic)  continue;

      // 时间止损:快进快出。一笔剥头皮单在 N 根 K 线里没走出来,
      // 说明判断的动能没兑现 —— 不等它变成隔夜仓去付加密 CFD 的高额隔夜利息。
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(InpMaxHoldBars > 0 && TimeCurrent() - opened >= maxAge)
      {
         if(trade.PositionClose(ticket))
            Notify(StringFormat("时间止损:持仓超过 %d 根 K 线,平仓 ticket=%I64u",
                                InpMaxHoldBars, ticket));
         else
            PrintFormat("时间止损平仓失败 ticket=%I64u retcode=%d", ticket,
                        trade.ResultRetcode());
         continue;
      }

      if(!InpUseBreakeven && !InpUseTrailing) continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double cur  = (type == POSITION_TYPE_BUY) ? sym.Bid() : sym.Ask();

      // 1R 用开仓时的止损距离:止损一旦被移动,|open-sl| 就不再是 1R 了,
      // 所以用 TP 反推(TP 从不移动,= open ± R×RR)
      double r = (InpRewardRisk > 0) ? MathAbs(tp - open) / InpRewardRisk
                                     : MathAbs(open - sl);
      if(r <= 0) continue;
      double profitR = (type == POSITION_TYPE_BUY) ? (cur - open) / r
                                                   : (open - cur) / r;
      if(profitR < 1.0) continue;

      double newSL  = sl;
      double spread = sym.Ask() - sym.Bid();
      if(InpUseBreakeven)
      {
         double be = (type == POSITION_TYPE_BUY) ? open + spread : open - spread;
         if((type == POSITION_TYPE_BUY  && be > newSL) ||
            (type == POSITION_TYPE_SELL && (newSL == 0 || be < newSL)))
            newSL = be;
      }
      if(InpUseTrailing)
      {
         double trail = (type == POSITION_TYPE_BUY) ? cur - atr * InpTrailATRMult
                                                    : cur + atr * InpTrailATRMult;
         if((type == POSITION_TYPE_BUY  && trail > newSL) ||
            (type == POSITION_TYPE_SELL && trail < newSL))
            newSL = trail;
      }

      newSL = NormalizeDouble(newSL, digits);
      if(MathAbs(newSL - sl) > SymbolInfoDouble(_Symbol, SYMBOL_POINT))
      {
         if(!trade.PositionModify(ticket, newSL, tp))
            PrintFormat("移动止损失败 ticket=%I64u retcode=%d", ticket,
                        trade.ResultRetcode());
      }
   }
}

//+------------------------------------------------------------------+
void Notify(string msg)
{
   Print(msg);
   if(!InpAlerts) return;
   if(!MQLInfoInteger(MQL_TESTER))
   {
      Alert(msg);
      SendNotification(msg);
   }
}
//+------------------------------------------------------------------+
