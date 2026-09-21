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
#property version   "1.20"
#property strict

#include <Trade/Trade.mqh>

input group "=== 时段 ==="
input int    InpStartHour          = 1;       // 开盘时(服务器时间)——黄金约1点开盘
input group "=== ORB 参数 ==="
input int    InpCandleComposition  = 2;       // 区间定案需要盘整的K线数(降到2=更早能进场)
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
// 从历史 H1 K线重建"今天"的区间状态(高/低/是否定案)。
// 这样不管 EA 几点挂上去,都能回看当天开盘K线,当天就能工作。
void BuildTodayRange()
{
   g_haveRange=false; g_rangeFinal=false; g_consol=0;

   // 找今天开盘 K线(hour==InpStartHour)在已收盘K线里的位移
   int openShift=-1;
   for(int s=1; s<72; s++)
   {
      datetime t=iTime(_Symbol,PERIOD_H1,s);
      if(t==0) break;
      MqlDateTime dt; TimeToStruct(t,dt);
      MqlDateTime m=dt; m.hour=0; m.min=0; m.sec=0;
      if(StructToTime(m)<g_dayStart) break;   // 已经到昨天,今天没这根就退出
      if(dt.hour==InpStartHour){ openShift=s; break; }
   }
   if(openShift<0) return;                      // 今天的开盘K线还没出现

   g_rangeHigh=iHigh(_Symbol,PERIOD_H1,openShift);
   g_rangeLow =iLow (_Symbol,PERIOD_H1,openShift);
   g_haveRange=true;

   // 从开盘K线的下一根按时间顺序重放到最近一根已收盘K线
   for(int s=openShift-1; s>=1; s--)
   {
      double c=iClose(_Symbol,PERIOD_H1,s);
      double h=iHigh (_Symbol,PERIOD_H1,s);
      double l=iLow  (_Symbol,PERIOD_H1,s);
      if(g_rangeFinal) continue;               // 定案后不再动区间(突破留给下面判信号)
      if(c>g_rangeHigh || c<g_rangeLow)
      {
         if(h>g_rangeHigh) g_rangeHigh=h;
         if(l<g_rangeLow ) g_rangeLow =l;
         g_consol=0;
      }
      else
      {
         g_consol++;
         if(g_consol>=InpCandleComposition) g_rangeFinal=true;
      }
   }
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

   // 每根新 H1 K线从历史重建当天区间(幂等,挂晚了也能补上)
   BuildTodayRange();
   if(!g_haveRange || !g_rangeFinal) return;

   // 区间已定案:看最近一根已收盘 K线是否突破/跌破 -> 信号
   if(g_tradesToday>=InpMaxTradePerDay) return;
   double spread=(SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;
   if(spread>InpMaxSpreadPoints) return;

   double pOpen =iOpen (_Symbol,PERIOD_H1,1);
   double pClose=iClose(_Symbol,PERIOD_H1,1);
   bool bull=(pClose>pOpen);
   bool bear=(pClose<pOpen);
   if(InpLong && !g_longDone && bull && pClose>g_rangeHigh)
      OpenTrade(true);
   else if(InpShort && !g_shortDone && bear && pClose<g_rangeLow)
      OpenTrade(false);
}
//+------------------------------------------------------------------+
