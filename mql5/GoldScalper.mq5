//+------------------------------------------------------------------+
//|                                                 GoldScalper.mq5  |
//|            XAUUSD 突破 + 回踩剥头皮 EA（MQL5 / MetaTrader 5）      |
//+------------------------------------------------------------------+
//
//  为什么是 MQL5 而不是 MQL4:你的账户是 OANDA_Global-Demo(MetaTrader 5)。
//  MQL4 编译出的 .ex4 在 MT5 上加载不了,两者下单 API 也完全不同。
//
//  ── 这个 EA 里**没有**什么 ────────────────────────────────────────
//  没有马丁格尔、没有网格、没有加仓摊平、没有无止损持仓。
//  这三样是「高胜率激进黄金 EA」的标准配方,也是账户归零的标准路径:
//  它们能把胜率做到 95%,代价是某一笔把前面 50 笔的利润连本金一起还回去。
//  每一笔单子进场时**必带止损**,而且止损跟单子一起提交给服务器 ——
//  EA 停了、终端关了、VPS 挂了,止损依然在券商那边活着。
//
//  ── $200 本金交易黄金的真实处境(必须先懂这个) ──────────────────
//  XAUUSD 合约 100 oz,最小 0.01 手 = 1 oz = 金价每动 $1 盈亏 $1。
//
//    止损    风险   占$200   点差$0.30占止损   1:1保本胜率
//     $2    $2.00   1.0%       15.0%           57.5%
//     $3    $3.00   1.5%       10.0%           55.0%
//     $5    $5.00   2.5%        6.0%           53.0%
//     $12   $12.00  6.0%        2.5%           51.3%
//
//  止损收窄到风险可控 -> 点差吃掉 10~15%;止损放宽到点差可忽略 -> 风险超标。
//  **没有一个止损距离能同时满足两边。** 所以本 EA 的默认参数偏保守,
//  并且带一个硬性的点差过滤器:点差超标就不交易,宁可整天不出手。
//  账户越小,这个过滤器越重要 —— 成本是小账户唯一确定会遇到的敌人。
//
//  ── 策略 ────────────────────────────────────────────────────────
//  1) 结构:用分型(fractal)找摆动高低点,聚类成支撑/阻力区
//  2) 趋势:EMA快/慢 排列决定只做多还是只做空(不逆势)
//  3) 入场 A(突破):收盘突破阻力 + RSI/MACD 同向 -> 回踩挂限价单
//     入场 B(回踩剥头皮):趋势中价格回到快线附近 + RSI 未超买 -> 顺势进
//  4) 止损:ATR 缩放,但有下限 = max(ATR倍数, N×点差, 券商最小止损距离)
//  5) 止盈:固定 R:R;可选保本移动 + ATR 追踪
//  6) 风控:每笔风险%、每日亏损上限、最大持仓数、点差过滤、时段过滤
//
//  免责:研究/学习用途,不构成投资建议。黄金杠杆交易可能损失全部本金。
//+------------------------------------------------------------------+
#property copyright "ai4trade-bot"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <Trade/SymbolInfo.mqh>

//--- 风险 ----------------------------------------------------------
input group "=== 风险管理 ==="
input double InpRiskPercent      = 1.0;    // 每笔风险占净值 %
input double InpMaxRiskPercent   = 2.0;    // 硬上限 %(超过会被夹回)
input double InpDailyLossPct     = 4.0;    // 当日亏损达净值 % 即停手
input int    InpMaxPositions     = 1;      // 最大同时持仓数
input double InpFixedLots        = 0.0;    // >0 则固定手数,忽略风险%计算

//--- 成本过滤 ------------------------------------------------------
input group "=== 成本过滤(小账户的生死线) ==="
input double InpMaxSpreadUSD     = 0.50;   // 点差超过这个金额就不交易($)
input double InpMinStopSpreadX   = 8.0;    // 止损至少是点差的几倍
input int    InpSlippagePoints   = 20;     // 允许滑点(point)

//--- 策略 ----------------------------------------------------------
input group "=== 策略 ==="
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M15;  // 工作周期
input int    InpFastEMA          = 20;     // 快 EMA
input int    InpSlowEMA          = 50;     // 慢 EMA
input int    InpTrendEMA         = 200;    // 趋势 EMA
input int    InpRSIPeriod        = 14;
input double InpRSIBuyMax        = 70.0;   // 做多时 RSI 上限(不追超买)
input double InpRSISellMin       = 30.0;   // 做空时 RSI 下限
input int    InpATRPeriod        = 14;
// ⬇ 默认值来自样本外验证,不是拍的。见 reports/gold_research.md:
//   M15 + 固定$3止损 + RR1:2 是唯一在「前半段选参数、后半段只跑一次」
//   之后仍然为正的配置(训练 41.4%/+0.098R,验证 40.5%/+0.091R)。
//   H1 的十组配置前后两半一致为负 —— $3 在 H1 上只有 0.16×ATR,必被噪音扫。
input double InpFixedStopUSD     = 3.0;    // >0 = 固定止损(金价美元距离);0 = 用ATR
input double InpATRStopMult      = 1.2;    // InpFixedStopUSD=0 时才用
input double InpRewardRisk       = 2.0;    // 止盈 = 止损 × 这个倍数
input int    InpSwingLookback    = 100;    // 找结构的回溯根数
input int    InpSwingWing        = 2;      // 分型左右各几根

//--- 出场管理 ------------------------------------------------------
input group "=== 出场 ==="
input bool   InpUseBreakeven     = true;   // 到 1R 移保本
input bool   InpUseTrailing      = true;   // 保本后 ATR 追踪
input double InpTrailATRMult     = 1.0;

//--- 时段 ----------------------------------------------------------
input group "=== 时段过滤(服务器时间) ==="
input bool   InpUseSession       = true;
input int    InpSessionStartHour = 7;      // 伦敦开盘前后
input int    InpSessionEndHour   = 20;     // 纽约午后收
input bool   InpFridayEarlyStop  = true;   // 周五晚不开新仓

//--- 其他 ----------------------------------------------------------
input group "=== 其他 ==="
input long   InpMagic            = 20260809;
input bool   InpAlerts           = true;   // 终端弹窗 + 推送

//--- 全局 ----------------------------------------------------------
CTrade        trade;
CSymbolInfo   sym;
int           hFast, hSlow, hTrend, hRSI, hMACD, hATR;
datetime      lastBarTime  = 0;
datetime      dayStamp     = 0;
double        dayStartEquity = 0.0;
bool          dayBlocked   = false;

//+------------------------------------------------------------------+
//| 初始化                                                            |
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

   // 指标句柄。MQL5 和 MQL4 最大的差别之一:指标返回句柄,取值要 CopyBuffer。
   hFast  = iMA(_Symbol, InpTimeframe, InpFastEMA,  0, MODE_EMA, PRICE_CLOSE);
   hSlow  = iMA(_Symbol, InpTimeframe, InpSlowEMA,  0, MODE_EMA, PRICE_CLOSE);
   hTrend = iMA(_Symbol, InpTimeframe, InpTrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   hRSI   = iRSI(_Symbol, InpTimeframe, InpRSIPeriod, PRICE_CLOSE);
   hMACD  = iMACD(_Symbol, InpTimeframe, 12, 26, 9, PRICE_CLOSE);
   hATR   = iATR(_Symbol, InpTimeframe, InpATRPeriod);

   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hTrend == INVALID_HANDLE ||
      hRSI  == INVALID_HANDLE || hMACD == INVALID_HANDLE || hATR  == INVALID_HANDLE)
   {
      Print("指标句柄创建失败");
      return(INIT_FAILED);
   }

   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   dayStamp       = TodayStamp();

   PrintFormat("GoldScalper 启动 | %s %s | 净值 %.2f | 合约 %.0f | 最小手 %.3f | 步长 %.3f | 点值 %.4f",
               _Symbol, EnumToString(InpTimeframe),
               AccountInfoDouble(ACCOUNT_EQUITY),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP),
               SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE));

   // 小账户 + 黄金的现实检查:如果最小手数下、按 ATR 算出的止损已经超过风险
   // 上限,那这个组合在数学上就做不了。与其让它带着超标风险开单,不如开口就说。
   WarnIfUntradeable();
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hFast);  IndicatorRelease(hSlow);  IndicatorRelease(hTrend);
   IndicatorRelease(hRSI);   IndicatorRelease(hMACD);  IndicatorRelease(hATR);
}

//+------------------------------------------------------------------+
//| 开口自检:最小手数下,典型止损要冒多少风险                          |
//+------------------------------------------------------------------+
void WarnIfUntradeable()
{
   double eq      = AccountInfoDouble(ACCOUNT_EQUITY);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double atr[];
   if(CopyBuffer(hATR, 0, 0, 2, atr) < 1) return;
   double stopDist = (InpFixedStopUSD > 0) ? InpFixedStopUSD : atr[0] * InpATRStopMult;
   double risk     = MoneyForDistance(minLot, stopDist);
   double pct      = (eq > 0) ? risk / eq * 100.0 : 0.0;

   PrintFormat("自检:最小手 %.3f × 止损 %.2f → 风险 $%.2f = 净值的 %.3f%%",
               minLot, stopDist, risk, pct);
   if(pct > InpMaxRiskPercent)
      PrintFormat("⚠️ 警告:最小手数下的单笔风险(%.2f%%)已超过上限 %.2f%% —— "
                  "本 EA 会拒绝开这些单。要么加大本金,要么换更小的合约品种。",
                  pct, InpMaxRiskPercent);
}

//+------------------------------------------------------------------+
//| 主循环                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!sym.RefreshRates()) return;

   ResetDailyIfNeeded();
   ManageOpenPositions();      // 持仓管理每个 tick 都跑(保本/追踪要及时)

   // 入场判断只在**新 K 线**上做一次。每个 tick 都判 = 用未收盘价做决策,
   // 那是未来函数的近亲:同一根 K 线里信号会反复闪烁,回测和实盘对不上。
   datetime t = iTime(_Symbol, InpTimeframe, 0);
   if(t == lastBarTime) return;
   lastBarTime = t;

   if(dayBlocked)              return;
   if(!SessionOK())            return;
   if(!SpreadOK())             return;
   if(CountPositions() >= InpMaxPositions) return;

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

   // 当日熔断。连亏之后最危险的不是下一笔的期望值变差(它没变),
   // 是人开始加码找回来。让规则替你停手。
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
bool SessionOK()
{
   if(!InpUseSession) return true;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(dt.day_of_week == 0 || dt.day_of_week == 6) return false;      // 周末
   if(InpFridayEarlyStop && dt.day_of_week == 5 && dt.hour >= 18) return false;
   return (dt.hour >= InpSessionStartHour && dt.hour < InpSessionEndHour);
}

// 点差过滤是这个 EA 里最重要的一个函数。黄金点差在亚洲盘和数据前后会
// 突然放大到平时的 3~5 倍,而剥头皮的止损很窄 —— 那种时候进场,
// 你付的成本可能就是整笔的预期利润。
bool SpreadOK()
{
   double spread = sym.Ask() - sym.Bid();
   if(spread > InpMaxSpreadUSD)
   {
      static datetime lastWarn = 0;
      if(TimeCurrent() - lastWarn > 300)
      {
         PrintFormat("点差 %.2f 超过上限 %.2f,跳过", spread, InpMaxSpreadUSD);
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

//+------------------------------------------------------------------+
//| 结构:分型摆动点 -> 支撑/阻力                                       |
//+------------------------------------------------------------------+
// 分型要求右侧也有 InpSwingWing 根确认 —— 一个高点在右边还没走出来之前
// 不算高点。事后看图每个顶都很明显,那是幸存者视角,不能拿来做实时决策。
bool FindStructure(double &resistance, double &support)
{
   int    need = InpSwingLookback + InpSwingWing * 2 + 2;
   double hi[], lo[];
   ArraySetAsSeries(hi, true);
   ArraySetAsSeries(lo, true);
   if(CopyHigh(_Symbol, InpTimeframe, 0, need, hi) < need) return false;
   if(CopyLow (_Symbol, InpTimeframe, 0, need, lo) < need) return false;

   resistance = 0.0;
   support    = 0.0;
   double bestHi = -DBL_MAX, bestLo = DBL_MAX;

   // i 从 wing+1 开始:跳过还没被右侧确认的最新几根
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
//| 取指标值(index 1 = 最近一根**已收盘** K 线)                        |
//+------------------------------------------------------------------+
bool GetIndicators(double &fast, double &slow, double &trend, double &rsi,
                   double &macdMain, double &macdPrev, double &atr)
{
   double b1[], b2[], b3[], b4[], b5[], b6[];
   if(CopyBuffer(hFast,  0, 1, 1, b1) < 1) return false;
   if(CopyBuffer(hSlow,  0, 1, 1, b2) < 1) return false;
   if(CopyBuffer(hTrend, 0, 1, 1, b3) < 1) return false;
   if(CopyBuffer(hRSI,   0, 1, 1, b4) < 1) return false;
   if(CopyBuffer(hMACD,  0, 1, 2, b5) < 2) return false;   // 0=MAIN
   if(CopyBuffer(hATR,   0, 1, 1, b6) < 1) return false;
   fast = b1[0]; slow = b2[0]; trend = b3[0]; rsi = b4[0];
   macdMain = b5[1];      // 较新那根
   macdPrev = b5[0];
   atr  = b6[0];
   return (atr > 0);
}

//+------------------------------------------------------------------+
//| 入场                                                              |
//+------------------------------------------------------------------+
void TryEntry()
{
   double fast, slow, trend, rsi, macdMain, macdPrev, atr;
   if(!GetIndicators(fast, slow, trend, rsi, macdMain, macdPrev, atr)) return;

   double res, sup;
   if(!FindStructure(res, sup)) return;

   double close1 = iClose(_Symbol, InpTimeframe, 1);
   double spread = sym.Ask() - sym.Bid();

   bool upTrend   = (fast > slow && slow > trend);
   bool downTrend = (fast < slow && slow < trend);
   if(!upTrend && !downTrend) return;      // 均线缠绕 = 无趋势,不做

   bool macdUp   = (macdMain > macdPrev && macdMain > 0);
   bool macdDown = (macdMain < macdPrev && macdMain < 0);

   // ---- 入场 A:突破 ----------------------------------------------
   // 突破要带缓冲,而且缓冲至少覆盖点差 —— 恰好擦到阻力的"突破"多半是插针。
   double buf = MathMax(atr * 0.15, spread * 2.0);
   bool breakUp   = upTrend   && close1 > res + buf;
   bool breakDown = downTrend && close1 < sup - buf;

   // ---- 入场 B:趋势中回踩快线(剥头皮) ------------------------------
   double pullbackZone = atr * 0.5;
   bool pullUp   = upTrend   && close1 <= fast + pullbackZone && close1 > slow;
   bool pullDown = downTrend && close1 >= fast - pullbackZone && close1 < slow;

   string reason = "";
   int    dir    = 0;

   if((breakUp || pullUp) && rsi < InpRSIBuyMax && macdUp)
   {
      dir    = 1;
      reason = breakUp ? "突破阻力" : "趋势回踩";
   }
   else if((breakDown || pullDown) && rsi > InpRSISellMin && macdDown)
   {
      dir    = -1;
      reason = breakDown ? "跌破支撑" : "趋势回踩";
   }
   if(dir == 0) return;

   OpenTrade(dir, atr, spread, reason);
}

//+------------------------------------------------------------------+
//| 手数:由「亏损金额固定」反推,不是拍脑袋                             |
//+------------------------------------------------------------------+
// 一手在价格变动 dist 时的盈亏 = dist / tickSize × tickValue
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

   double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
   double pct  = MathMin(InpRiskPercent, InpMaxRiskPercent);   // 硬上限,调高也夹回来
   double risk = eq * pct / 100.0;

   double perLot = MoneyForDistance(1.0, stopDistance);
   if(perLot <= 0) return 0.0;

   double lots = NormalizeLots(risk / perLot);
   if(lots <= 0) return 0.0;

   // 关键一步:向下取整到手数步长后,实际风险可能**高于**预算(因为最小手
   // 已经太大)。这时候不能"差不多就开" —— 超过硬上限就不开这一单。
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
   double minL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0) step = 0.01;
   lots = MathFloor(lots / step) * step;            // 向下取整:宁可少冒风险
   if(lots < minL) lots = minL;
   if(lots > maxL) lots = maxL;
   // 按步长的小数位归一,不能写死 2 位:XAUUSD.sml 步长 0.001,
   // 写死 2 位会把 0.006 手抹成 0.01,风险直接放大 66%。
   int digits = (step >= 1.0) ? 0 : (int)MathCeil(-MathLog10(step));
   return NormalizeDouble(lots, digits);
}

//+------------------------------------------------------------------+
//| 下单                                                              |
//+------------------------------------------------------------------+
void OpenTrade(int dir, double atr, double spread, string reason)
{
   double price = (dir > 0) ? sym.Ask() : sym.Bid();

   // 止损距离取三者最大:ATR 缩放 / 点差倍数 / 券商最小止损距离。
   // 只按 ATR 缩放的话,低波动时段会算出一个比点差还窄的止损 ——
   // 那不是止损,那是给点差和噪音送钱。
   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL)
                       * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   // 固定止损模式:止损大小由验证结果决定,不随波动缩放。
   // 但仍然不能低于点差倍数和券商最小止损距离 —— 那两个是硬成本,
   // 再"验证过"的参数也不能穿过它们。
   double base = (InpFixedStopUSD > 0) ? InpFixedStopUSD : atr * InpATRStopMult;
   double dist = MathMax(base, MathMax(spread * InpMinStopSpreadX, stopsLevel * 1.5));

   double riskUsed = 0.0;
   double lots     = CalculateLots(dist, riskUsed);
   if(lots <= 0) return;

   double sl = (dir > 0) ? price - dist : price + dist;
   double tp = (dir > 0) ? price + dist * InpRewardRisk
                         : price - dist * InpRewardRisk;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   sl = NormalizeDouble(sl, digits);
   tp = NormalizeDouble(tp, digits);

   bool ok = (dir > 0) ? trade.Buy (lots, _Symbol, 0.0, sl, tp, reason)
                       : trade.Sell(lots, _Symbol, 0.0, sl, tp, reason);

   if(ok)
      Notify(StringFormat("%s %s %.2f手 @%.2f SL=%.2f TP=%.2f 风险$%.2f 点差%.2f (%s)",
                          (dir > 0 ? "买入" : "卖出"), _Symbol, lots, price,
                          sl, tp, riskUsed, spread, reason));
   else
      PrintFormat("下单失败 retcode=%d %s", trade.ResultRetcode(),
                  trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
//| 持仓管理:保本 + ATR 追踪                                          |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   if(!InpUseBreakeven && !InpUseTrailing) return;

   double atrBuf[];
   if(CopyBuffer(hATR, 0, 1, 1, atrBuf) < 1) return;
   double atr = atrBuf[0];
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)   continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic)  continue;

      long   type  = PositionGetInteger(POSITION_TYPE);
      double open  = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double cur   = (type == POSITION_TYPE_BUY) ? sym.Bid() : sym.Ask();

      double r     = MathAbs(open - sl);      // 1R = 原始止损距离
      if(r <= 0) continue;
      double profitR = (type == POSITION_TYPE_BUY) ? (cur - open) / r
                                                   : (open - cur) / r;

      double newSL = sl;

      // 到 1R 移保本。注意要留一点缓冲盖住点差,否则"保本"出场其实是小亏。
      if(InpUseBreakeven && profitR >= 1.0)
      {
         double spread = sym.Ask() - sym.Bid();
         double be = (type == POSITION_TYPE_BUY) ? open + spread : open - spread;
         if((type == POSITION_TYPE_BUY  && be > newSL) ||
            (type == POSITION_TYPE_SELL && be < newSL))
            newSL = be;
      }

      // 保本之后才启动追踪 —— 一开始就追踪会在正常回抽里被扫掉。
      if(InpUseTrailing && profitR >= 1.0)
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
//| 通知                                                              |
//+------------------------------------------------------------------+
void Notify(string msg)
{
   Print(msg);
   if(!InpAlerts) return;
   if(!MQLInfoInteger(MQL_TESTER))     // 回测里不弹窗,否则跑不动
   {
      Alert(msg);
      SendNotification(msg);           // 需在 终端设置->通知 里填 MetaQuotes ID
   }
}
//+------------------------------------------------------------------+
