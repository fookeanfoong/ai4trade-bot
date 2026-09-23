//+------------------------------------------------------------------+
//|                                           EURUSD_QuickScalp.mq5  |
//|            EURUSD 快进快出 EA（MQL5 / MetaTrader 5）               |
//+------------------------------------------------------------------+
//
//  由 EMAcrossEUROUSDH1 改写而来。原版的问题:
//    1) CopyBuffer 默认 [0]=最旧、[1]=最新,原代码当成反的 -> 死叉时买入
//    2) 用还没收盘的 bar 0 判断交叉 -> 一根K线里反复穿越,假信号多
//    3) H1 上 EMA50/200 交叉几周才一次,谈不上"快进快出"
//
//  ── 策略 ────────────────────────────────────────────────────────
//  周期:默认 M5(由参数决定,跟图表周期无关)
//  入场(只看已收盘K线,每根K线最多判断一次):
//    做多:EMA9 上穿 EMA21 + 收盘价在 EMA200 上方 + RSI 在 50~70
//    做空:EMA9 下穿 EMA21 + 收盘价在 EMA200 下方 + RSI 在 30~50
//  出场(哪个先到就走哪个):
//    - 止盈 = ATR × 1.0,止损 = ATR × 1.2(跟单一起提交给服务器)
//    - 浮盈到止盈距离的 50% -> 止损移到保本
//    - 持仓满 N 根K线还没走 -> 市价平掉(快出)
//    - 出现反向交叉 -> 市价平掉
//  风控:点差过滤、交易时段、每日最多笔数、每日亏损上限
//
//  注意:快进快出 = 交易次数多 = 点差成本占比高。
//  EURUSD 点差 1 点(pip),止盈才 5 点的话,点差就吃掉 20%。
//  所以有点差过滤,点差大时宁可不做。先在策略测试器和模拟账户验证。
//
//  免责:研究/学习用途,不构成投资建议。杠杆交易可能损失全部本金。
//+------------------------------------------------------------------+
#property copyright "ai4trade-bot"
#property version   "1.00"
#property description "EURUSD 快进快出:EMA9/21 交叉 + EMA200 趋势 + RSI,ATR 止损止盈,超时平仓"

#include <Trade/Trade.mqh>

//--- 参数 ----------------------------------------------------------
input group "=== 周期与信号 ==="
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M5;  // 工作周期(与图表周期无关)
input int    InpFastEMA          = 9;      // 快 EMA
input int    InpSlowEMA          = 21;     // 慢 EMA
input int    InpTrendEMA         = 200;    // 趋势 EMA(只顺势做)
input int    InpRSIPeriod        = 14;
input double InpRSIBuyMin        = 50.0;   // 做多 RSI 下限
input double InpRSIBuyMax        = 70.0;   // 做多 RSI 上限(不追超买)
input double InpRSISellMin       = 30.0;   // 做空 RSI 下限(不追超卖)
input double InpRSISellMax       = 50.0;   // 做空 RSI 上限
input int    InpATRPeriod        = 14;
input bool   InpAllowBuy         = true;   // 允许做多
input bool   InpAllowSell        = true;   // 允许做空

input group "=== 止损止盈(快进快出) ==="
input double InpSL_ATR           = 1.2;    // 止损 = ATR × 这个倍数
input double InpTP_ATR           = 1.0;    // 止盈 = ATR × 这个倍数
input double InpBEAtTPPct        = 50.0;   // 浮盈到止盈距离的 % 就移保本(0=关闭)
input int    InpBEOffsetPoints   = 5;      // 保本时多锁的 point 数
input int    InpMaxHoldBars      = 6;      // 最多持仓几根K线,到了就平(0=关闭)
input bool   InpExitOnReverse    = true;   // 出现反向交叉就平仓

input group "=== 仓位与风控 ==="
input double InpFixedLots        = 0.01;   // 固定手数(InpRiskPercent=0 时使用)
input double InpRiskPercent      = 0.0;    // >0 = 按每笔风险占净值 % 算手数
input int    InpMaxTradesPerDay  = 10;     // 每天最多开几笔
input double InpDailyLossPct     = 3.0;    // 当日亏损达净值 % 就停手(0=关闭)

input group "=== 成本过滤 ==="
input int    InpMaxSpreadPoints  = 15;     // 点差超过就不开仓(point;5位报价 10 point = 1 pip)
input int    InpSlippagePoints   = 10;     // 允许滑点(point)

input group "=== 时段过滤(服务器时间) ==="
input bool   InpUseSession       = true;
input int    InpSessionStartHour = 9;      // 开始(含)
input int    InpSessionEndHour   = 21;     // 结束(不含)

input group "=== 其他 ==="
input long   InpMagic            = 20260923;

//--- 全局 ----------------------------------------------------------
CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hTrend = INVALID_HANDLE;
int      hRSI  = INVALID_HANDLE, hATR  = INVALID_HANDLE;
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpFastEMA <= 0 || InpFastEMA >= InpSlowEMA || InpSL_ATR <= 0 || InpTP_ATR <= 0)
     {
      Print("参数错误:需要 0 < 快EMA < 慢EMA,且止损/止盈倍数 > 0");
      return(INIT_PARAMETERS_INCORRECT);
     }

   hFast  = iMA(_Symbol, InpTimeframe, InpFastEMA,  0, MODE_EMA, PRICE_CLOSE);
   hSlow  = iMA(_Symbol, InpTimeframe, InpSlowEMA,  0, MODE_EMA, PRICE_CLOSE);
   hTrend = iMA(_Symbol, InpTimeframe, InpTrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   hRSI   = iRSI(_Symbol, InpTimeframe, InpRSIPeriod, PRICE_CLOSE);
   hATR   = iATR(_Symbol, InpTimeframe, InpATRPeriod);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hTrend == INVALID_HANDLE ||
      hRSI == INVALID_HANDLE || hATR == INVALID_HANDLE)
     {
      Print("OnInit: 指标句柄创建失败");
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   PrintFormat("QuickScalp 启动:%s 周期=%s EMA%d/%d 趋势EMA%d 止损%.1fATR 止盈%.1fATR 最多持仓%d根",
               _Symbol, EnumToString(InpTimeframe), InpFastEMA, InpSlowEMA, InpTrendEMA,
               InpSL_ATR, InpTP_ATR, InpMaxHoldBars);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hFast  != INVALID_HANDLE) IndicatorRelease(hFast);
   if(hSlow  != INVALID_HANDLE) IndicatorRelease(hSlow);
   if(hTrend != INVALID_HANDLE) IndicatorRelease(hTrend);
   if(hRSI   != INVALID_HANDLE) IndicatorRelease(hRSI);
   if(hATR   != INVALID_HANDLE) IndicatorRelease(hATR);
   Comment("");
  }

//+------------------------------------------------------------------+
//| 取已收盘K线的指标值:out[0]=bar1(最近收盘), out[1]=bar2           |
//+------------------------------------------------------------------+
bool GetClosed(const int handle, double &out[])
  {
   ArraySetAsSeries(out, true);
   return(CopyBuffer(handle, 0, 1, 2, out) == 2);
  }

//+------------------------------------------------------------------+
//| 找本 EA 在本品种上的持仓                                         |
//+------------------------------------------------------------------+
bool FindMyPosition(ulong &ticket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !PositionSelectByTicket(t))
         continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol &&
         PositionGetInteger(POSITION_MAGIC) == InpMagic)
        {
         ticket = t;
         return(true);
        }
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| 今天本 EA 的开仓笔数和已实现盈亏                                   |
//+------------------------------------------------------------------+
void TodayStats(int &trades, double &pnl)
  {
   trades = 0;
   pnl    = 0.0;
   datetime dayStart = iTime(_Symbol, PERIOD_D1, 0);
   if(dayStart == 0 || !HistorySelect(dayStart, TimeCurrent() + 60))
      return;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)
         continue;
      long entry = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(entry == DEAL_ENTRY_IN)
         trades++;
      else
         pnl += HistoryDealGetDouble(d, DEAL_PROFIT) +
                HistoryDealGetDouble(d, DEAL_SWAP) +
                HistoryDealGetDouble(d, DEAL_COMMISSION);
     }
  }

//+------------------------------------------------------------------+
bool InSession()
  {
   if(!InpUseSession)
      return(true);
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   if(InpSessionStartHour <= InpSessionEndHour)
      return(dt.hour >= InpSessionStartHour && dt.hour < InpSessionEndHour);
   return(dt.hour >= InpSessionStartHour || dt.hour < InpSessionEndHour); // 跨午夜
  }

//+------------------------------------------------------------------+
double CalcLots(const double slDist)
  {
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(minLot <= 0.0 || lotStep <= 0.0)
      return(0.0);

   double lots = InpFixedLots;
   if(InpRiskPercent > 0.0)
     {
      double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
      double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
      if(tickValue <= 0.0 || tickSize <= 0.0)
         return(0.0);
      double riskMoney  = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0;
      double lossPerLot = slDist / tickSize * tickValue;
      lots = riskMoney / lossPerLot;
     }

   lots = MathFloor(lots / lotStep + 1e-9) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));
   int volDigits = (int)MathMax(0, MathCeil(-MathLog10(lotStep)));
   return(NormalizeDouble(lots, volDigits));
  }

//+------------------------------------------------------------------+
//| 每个 tick:浮盈够了就把止损挪到保本                               |
//+------------------------------------------------------------------+
void ManageBreakeven(const ulong ticket)
  {
   if(InpBEAtTPPct <= 0.0 || !PositionSelectByTicket(ticket))
      return;
   long   type = PositionGetInteger(POSITION_TYPE);
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl   = PositionGetDouble(POSITION_SL);
   double tp   = PositionGetDouble(POSITION_TP);
   if(tp <= 0.0)
      return;
   double trigger = MathAbs(tp - open) * InpBEAtTPPct / 100.0;
   double offset  = InpBEOffsetPoints * _Point;

   if(type == POSITION_TYPE_BUY)
     {
      double bid   = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double newSL = NormalizeDouble(open + offset, _Digits);
      if(bid - open >= trigger && (sl < newSL || sl == 0.0) && newSL < bid)
         if(trade.PositionModify(ticket, newSL, tp))
            PrintFormat("[保本] #%I64u 止损移到 %.5f", ticket, newSL);
     }
   else
     {
      double ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double newSL = NormalizeDouble(open - offset, _Digits);
      if(open - ask >= trigger && (sl > newSL || sl == 0.0) && newSL > ask)
         if(trade.PositionModify(ticket, newSL, tp))
            PrintFormat("[保本] #%I64u 止损移到 %.5f", ticket, newSL);
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   ulong ticket = 0;
   bool  hasPos = FindMyPosition(ticket);
   if(hasPos)
      ManageBreakeven(ticket);

   // 以下只在新K线收盘后跑一次
   datetime bar = iTime(_Symbol, InpTimeframe, 0);
   if(bar == 0 || bar == g_lastBar)
      return;
   if(Bars(_Symbol, InpTimeframe) < InpTrendEMA + 5)
      return;

   double fast[], slow[], trend[], rsi[], atr[];
   if(!GetClosed(hFast, fast) || !GetClosed(hSlow, slow) || !GetClosed(hTrend, trend) ||
      !GetClosed(hRSI, rsi) || !GetClosed(hATR, atr))
      return;   // 数据还没准备好,下个 tick 再试(不更新 g_lastBar)
   g_lastBar = bar;

   double close1   = iClose(_Symbol, InpTimeframe, 1);
   bool   crossUp  = (fast[1] <= slow[1]) && (fast[0] > slow[0]);
   bool   crossDn  = (fast[1] >= slow[1]) && (fast[0] < slow[0]);

   //--- 出场:超时 / 反向交叉
   if(hasPos && PositionSelectByTicket(ticket))
     {
      long     type     = PositionGetInteger(POSITION_TYPE);
      datetime openTime = (datetime)PositionGetInteger(POSITION_TIME);
      int      held     = iBarShift(_Symbol, InpTimeframe, openTime, false);
      string   why      = "";
      if(InpMaxHoldBars > 0 && held >= InpMaxHoldBars)
         why = StringFormat("持仓 %d 根K线超时", held);
      else if(InpExitOnReverse && ((type == POSITION_TYPE_BUY && crossDn) ||
                                   (type == POSITION_TYPE_SELL && crossUp)))
         why = "反向交叉";
      if(why != "")
        {
         if(trade.PositionClose(ticket))
           {
            PrintFormat("[平仓] #%I64u %s", ticket, why);
            hasPos = false;
           }
         else
            PrintFormat("[平仓失败] #%I64u %s retcode=%d %s", ticket, why,
                        trade.ResultRetcode(), trade.ResultRetcodeDescription());
        }
     }

   //--- 状态显示
   int    todayTrades;
   double todayPnl;
   TodayStats(todayTrades, todayPnl);
   long   spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool   session = InSession();
   Comment(StringFormat("QuickScalp %s %s\n点差 %d / 上限 %d point\n时段内: %s\n今日 %d 笔, 盈亏 %.2f\nATR %.5f  RSI %.1f",
                        _Symbol, EnumToString(InpTimeframe), spread, InpMaxSpreadPoints,
                        session ? "是" : "否", todayTrades, todayPnl, atr[0], rsi[0]));

   //--- 入场过滤
   if(hasPos)
      return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
      return;
   if(!session)
      return;
   if(todayTrades >= InpMaxTradesPerDay)
      return;
   if(InpDailyLossPct > 0.0 &&
      todayPnl <= -AccountInfoDouble(ACCOUNT_BALANCE) * InpDailyLossPct / 100.0)
      return;

   bool buySig  = InpAllowBuy  && crossUp && close1 > trend[0] && fast[0] > trend[0] &&
                  rsi[0] >= InpRSIBuyMin && rsi[0] <= InpRSIBuyMax;
   bool sellSig = InpAllowSell && crossDn && close1 < trend[0] && fast[0] < trend[0] &&
                  rsi[0] >= InpRSISellMin && rsi[0] <= InpRSISellMax;
   if(!buySig && !sellSig)
      return;

   if(spread > InpMaxSpreadPoints)
     {
      PrintFormat("[跳过] 有信号但点差 %d > 上限 %d", spread, InpMaxSpreadPoints);
      return;
     }

   //--- 止损止盈距离(不小于券商最小止损距离)
   double minDist = (SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) + spread + 2) * _Point;
   double slDist  = MathMax(atr[0] * InpSL_ATR, minDist);
   double tpDist  = MathMax(atr[0] * InpTP_ATR, minDist);

   double lots = CalcLots(slDist);
   if(lots <= 0.0)
     {
      Print("[跳过] 手数计算失败");
      return;
     }

   bool ok;
   if(buySig)
     {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl  = NormalizeDouble(ask - slDist, _Digits);
      double tp  = NormalizeDouble(ask + tpDist, _Digits);
      ok = trade.Buy(lots, _Symbol, ask, sl, tp, "QuickScalp Buy");
      PrintFormat("[开多] %s %.2f手 @%.5f SL=%.5f TP=%.5f RSI=%.1f -> %s",
                  _Symbol, lots, ask, sl, tp, rsi[0], ok ? "成功" : trade.ResultRetcodeDescription());
     }
   else
     {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl  = NormalizeDouble(bid + slDist, _Digits);
      double tp  = NormalizeDouble(bid - tpDist, _Digits);
      ok = trade.Sell(lots, _Symbol, bid, sl, tp, "QuickScalp Sell");
      PrintFormat("[开空] %s %.2f手 @%.5f SL=%.5f TP=%.5f RSI=%.1f -> %s",
                  _Symbol, lots, bid, sl, tp, rsi[0], ok ? "成功" : trade.ResultRetcodeDescription());
     }
  }
//+------------------------------------------------------------------+
