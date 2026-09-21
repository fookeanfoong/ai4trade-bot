//+------------------------------------------------------------------+
//|                                                     GOLD_ORB.mq5  |
//|            Opening Range Breakout (XAUUSD H1) — 自包含单文件版      |
//|                                                                  |
//|  策略来源: GOLD_ORB by Ulysses O. Andulte (github GOLD_ORB)       |
//|  本文件把原多文件工程(依赖一堆自定义 include)重写成单文件,          |
//|  只用标准库 <Trade/Trade.mqh>,逻辑忠于原 ORB:                      |
//|   1) 每个交易日开盘首根 H1 K线的高/低 = 初始区间(阻力/支撑)         |
//|   2) 等至少 InpCandleComposition 根 K线在区间内盘整 -> 区间"定案"   |
//|   3) 定案后,某根收盘突破上沿(阳线)->买; 跌破下沿(阴线)->卖          |
//|   4) 每天最多 InpMaxTradePerDay 笔                                 |
//|                                                                  |
//|  注意: 点数(points)按你经纪商的小数位。3位小数金价 1美元=1000点。   |
//|  默认 SL=4000点($4) / TP=12000点($12) = 1:3,已按3位小数校准。      |
//+------------------------------------------------------------------+
#property copyright "GOLD_ORB single-file port"
#property version   "1.10"
#property strict

#include <Trade/Trade.mqh>

input group "=== 时段 ==="
input int    InpStartHour          = 1;       // 开盘时(服务器时间)——黄金约1点开盘
input group "=== ORB 参数 ==="
input int    InpCandleComposition  = 3;       // 区间定案需要盘整的K线数
input int    InpMaxTradePerDay     = 2;       // 每日最多开仓数
input bool   InpLong               = true;    // 允许做多
input bool   InpShort              = true;    // 允许做空
input group "=== 手数/止盈止损 ==="
input double InpFixedLot           = 0.02;    // 固定手数
input int    InpStopLossPoints     = 4000;    // 止损(点)——3位小数金价:4000点=$4
input int    InpTakeProfitPoints   = 12000;   // 止盈(点)——12000点=$12 (1:3)
input group "=== 追踪止损 ==="
input bool   InpEnableTrail        = true;    // 启用追踪
input int    InpTrailStartPoints   = 6000;    // 盈利达到该点数才启动追踪
input int    InpTrailDistPoints    = 4000;    // 追踪止损跟在价格后该点数
input group "=== 其他 ==="
input long   InpMagic              = 20260922;// 魔术号(独立)
input int    InpMaxSpreadPoints    = 500;     // 点差上限(点),超过不开仓

CTrade  trade;

// 当日区间状态
datetime g_dayStart      = 0;      // 当前交易日(0点)
bool     g_haveRange     = false;  // 是否已取到初始区间
double   g_rangeHigh     = 0.0;
double   g_rangeLow      = 0.0;
int      g_consol        = 0;      // 区间内盘整计数
bool     g_rangeFinal    = false;  // 区间是否定案
int      g_tradesToday   = 0;
bool     g_longDone      = false;
bool     g_shortDone     = false;
datetime g_lastBarTime   = 0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(50);
   uint fill=(uint)SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((fill&SYMBOL_FILLING_FOK)!=0)      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fill&SYMBOL_FILLING_IOC)!=0) trade.SetTypeFilling(ORDER_FILLING_IOC);
   else                                  trade.SetTypeFilling(ORDER_FILLING_RETURN);
   PrintFormat("[GOLD_ORB] init | magic=%I64d | SL=%d TP=%d pts | lot=%.2f",
               InpMagic, InpStopLossPoints, InpTakeProfitPoints, InpFixedLot);
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
int CountMyPositions()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol &&
         PositionGetInteger(POSITION_MAGIC)==InpMagic) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
void DayReset(datetime dayStart)
{
   g_dayStart    = dayStart;
   g_haveRange   = false;
   g_rangeHigh   = 0.0;
   g_rangeLow    = 0.0;
   g_consol      = 0;
   g_rangeFinal  = false;
   g_tradesToday = 0;
   g_longDone    = false;
   g_shortDone   = false;
}

//+------------------------------------------------------------------+
void ManageTrail()
{
   if(!InpEnableTrail) return;
   double pt=_Point;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      long   type =PositionGetInteger(POSITION_TYPE);
      double open =PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   =PositionGetDouble(POSITION_SL);
      double tp   =PositionGetDouble(POSITION_TP);
      double bid  =SymbolInfoDouble(_Symbol,SYMBOL_BID);
      double ask  =SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      if(type==POSITION_TYPE_BUY)
      {
         if(bid-open >= InpTrailStartPoints*pt)
         {
            double newSL=bid-InpTrailDistPoints*pt;
            if(newSL>sl) trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),tp);
         }
      }
      else if(type==POSITION_TYPE_SELL)
      {
         if(open-ask >= InpTrailStartPoints*pt)
         {
            double newSL=ask+InpTrailDistPoints*pt;
            if(sl==0.0 || newSL<sl) trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),tp);
         }
      }
   }
}

//+------------------------------------------------------------------+
void OpenTrade(bool isBuy)
{
   double pt=_Point;
   double price = isBuy ? SymbolInfoDouble(_Symbol,SYMBOL_ASK)
                        : SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double sl = isBuy ? price - InpStopLossPoints*pt   : price + InpStopLossPoints*pt;
   double tp = isBuy ? price + InpTakeProfitPoints*pt : price - InpTakeProfitPoints*pt;
   sl=NormalizeDouble(sl,_Digits); tp=NormalizeDouble(tp,_Digits);
   bool ok = isBuy ? trade.Buy(InpFixedLot,_Symbol,0.0,sl,tp,"GOLD_ORB")
                   : trade.Sell(InpFixedLot,_Symbol,0.0,sl,tp,"GOLD_ORB");
   if(ok)
   {
      g_tradesToday++;
      if(isBuy) g_longDone=true; else g_shortDone=true;
      PrintFormat("[GOLD_ORB] %s @%.3f SL=%.3f TP=%.3f (今日第%d笔)",
                  isBuy?"BUY":"SELL", price, sl, tp, g_tradesToday);
   }
   else PrintFormat("[GOLD_ORB] 下单失败 %u %s",
                    trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
void OnTick()
{
   ManageTrail();

   // 只在新的 H1 K线收盘时处理信号
   datetime bt=iTime(_Symbol,PERIOD_H1,0);
   if(bt==g_lastBarTime) return;
   g_lastBarTime=bt;

   MqlDateTime now; TimeToStruct(TimeCurrent(),now);
   MqlDateTime d0=now; d0.hour=0; d0.min=0; d0.sec=0;
   datetime todayStart=StructToTime(d0);
   if(todayStart!=g_dayStart) DayReset(todayStart);

   // 上一根已收盘 H1 K线
   double pHigh=iHigh(_Symbol,PERIOD_H1,1);
   double pLow =iLow (_Symbol,PERIOD_H1,1);
   double pOpen=iOpen(_Symbol,PERIOD_H1,1);
   double pClose=iClose(_Symbol,PERIOD_H1,1);
   MqlDateTime pt_; TimeToStruct(iTime(_Symbol,PERIOD_H1,1),pt_);

   // 1) 开盘首根 -> 初始区间
   if(!g_haveRange)
   {
      if(pt_.hour==InpStartHour)
      {
         g_rangeHigh=pHigh; g_rangeLow=pLow;
         g_haveRange=true; g_consol=0; g_rangeFinal=false;
         PrintFormat("[GOLD_ORB] 初始区间 高=%.3f 低=%.3f",g_rangeHigh,g_rangeLow);
      }
      return;
   }

   // 2) 区间未定案:盘整则计数,创新高/新低则扩区间并重置计数
   if(!g_rangeFinal)
   {
      if(pClose>g_rangeHigh || pClose<g_rangeLow)
      {
         if(pHigh>g_rangeHigh) g_rangeHigh=pHigh;
         if(pLow <g_rangeLow ) g_rangeLow =pLow;
         g_consol=0;
      }
      else
      {
         g_consol++;
         if(g_consol>=InpCandleComposition) g_rangeFinal=true;
      }
      return;
   }

   // 3) 区间已定案:突破/跌破 -> 信号
   if(g_tradesToday>=InpMaxTradePerDay) return;
   double spread=(SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;
   if(spread>InpMaxSpreadPoints) return;

   bool bull=(pClose>pOpen);
   bool bear=(pClose<pOpen);
   if(InpLong && !g_longDone && bull && pClose>g_rangeHigh)
      OpenTrade(true);
   else if(InpShort && !g_shortDone && bear && pClose<g_rangeLow)
      OpenTrade(false);
}
//+------------------------------------------------------------------+
