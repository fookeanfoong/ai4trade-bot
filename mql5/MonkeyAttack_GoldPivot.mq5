//+------------------------------------------------------------------+
//|                                   MonkeyAttack_GoldPivot.mq5      |
//|            MONKEY ATTACK GOLD PIVOT EA — MQL5 port                |
//|                                                                  |
//|  由原 MT4 版 (monkey_attack_visual_ea.mq4) 完整重写为 MQL5。       |
//|  策略照搬:日/周枢轴 + 分形动态支撑阻力 + RSI/MACD/MA 确认,          |
//|  近支撑买/近阻力卖 + 顺势入场,ATR 动态止损止盈(RR),追踪止损,        |
//|  交易质量评分(1-7),连亏降险,时段/波动率过滤。单仓。               |
//|  MT4->MT5 已转换:下单用 CTrade;指标改 handle+CopyBuffer;          |
//|  行情用 iHigh/iLow/iClose/SymbolInfo;时间用 MqlDateTime。         |
//+------------------------------------------------------------------+
#property copyright "MonkeyAttack MQL5 port"
#property version   "2.03"
#property strict

#include <Trade/Trade.mqh>

//--- 交易 / 风险
input double LotSize            = 0.01;   // 固定手数(UseAutoLotSizing=false 时用)
input bool   UseAutoLotSizing   = true;   // 按风险自动算手数
input double RiskPercent        = 1.5;    // 每笔风险(%)
input long   MagicNumber        = 99999;  // 魔术号
input string TradeComment       = "MonkeyAttack_Pivot";

//--- 动态区间 / 枢轴
input int    SR_Lookback_Period = 20;     // 支撑阻力回看根数
input int    ATR_Period         = 14;     // ATR 周期
input double ATR_Multiplier      = 2.0;   // 动态止损 ATR 倍数
input bool   Use_Daily_Pivots   = true;   // 用日枢轴
input bool   Use_Weekly_Pivots  = true;   // 用周枢轴
input int    Fractal_Period     = 10;     // 分形检测周期

//--- 技术指标
input int    RSI_Period         = 21;
input int    RSI_Overbought     = 65;
input int    RSI_Oversold       = 35;
input int    MACD_Fast          = 12;
input int    MACD_Slow          = 26;
input int    MACD_Signal        = 9;
input int    MA_Fast            = 20;
input int    MA_Slow            = 50;

//--- 波动率过滤
input bool   UseVolatilityFilter= true;
input double VolatilityThreshold= 1.3;
input int    VolatilityPeriod   = 20;

//--- 风险管理
input double MaxSpreadPts       = 700;    // 最大点差(点)。3位小数金价:700点=$0.70
input double MinStopLossPts     = 2500;   // 最小止损(点)。3位小数:2500点=$2.50
input double MaxStopLossPts     = 6000;   // 最大止损(点)。6000点=$6
input double RiskRewardRatio    = 2.5;    // 盈亏比
input bool   UseTrailingStop    = true;
input double TrailingMultiplier = 1.8;    // 追踪止损 ATR 倍数

//--- 增强策略
input int    MaxConsecutiveLosses= 3;
input double RiskReductionFactor = 0.5;
input int    MinTradeQuality     = 5;     // 最低质量分(1-7)
input bool   UseTradeQualityFilter= true;
input bool   UseVolatilityPositioning = true;

//--- 时段
input bool   UseTradingHours    = true;
input int    StartHour          = 8;      // 服务器时间
input int    EndHour            = 21;
input bool   UseSessionFilter   = true;
input bool   TradeLondonSession = true;
input bool   TradeNYSession     = true;
input bool   TradeAsianSession  = false;
input bool   TradeOverlapOnly   = false;

input bool   ShowPanel          = true;   // 图上显示状态面板(Comment)

//--- 全局
CTrade   trade;
int      hRSI=INVALID_HANDLE, hMACD=INVALID_HANDLE, hMAf=INVALID_HANDLE, hMAs=INVALID_HANDLE;
int      hATR=INVALID_HANDLE, hATRd=INVALID_HANDLE;
double   g_ATR;
double   SupportLevels[10], ResistanceLevels[10];
int      SupportCount=0, ResistanceCount=0;
double   DailyPivot,DailyR1,DailyR2,DailyR3,DailyS1,DailyS2,DailyS3;
double   WeeklyPivot,WeeklyR1,WeeklyR2,WeeklyS1,WeeklyS2;
datetime g_lastBar=0;
int      g_lastQuality=0;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(30);
   uint fill=(uint)SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((fill&SYMBOL_FILLING_FOK)!=0)      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fill&SYMBOL_FILLING_IOC)!=0) trade.SetTypeFilling(ORDER_FILLING_IOC);
   else                                  trade.SetTypeFilling(ORDER_FILLING_RETURN);

   hRSI = iRSI(_Symbol,PERIOD_CURRENT,RSI_Period,PRICE_CLOSE);
   hMACD= iMACD(_Symbol,PERIOD_CURRENT,MACD_Fast,MACD_Slow,MACD_Signal,PRICE_CLOSE);
   hMAf = iMA(_Symbol,PERIOD_CURRENT,MA_Fast,0,MODE_SMA,PRICE_CLOSE);
   hMAs = iMA(_Symbol,PERIOD_CURRENT,MA_Slow,0,MODE_SMA,PRICE_CLOSE);
   hATR = iATR(_Symbol,PERIOD_CURRENT,ATR_Period);
   hATRd= iATR(_Symbol,PERIOD_D1,20);
   if(hRSI==INVALID_HANDLE||hMACD==INVALID_HANDLE||hMAf==INVALID_HANDLE||
      hMAs==INVALID_HANDLE||hATR==INVALID_HANDLE||hATRd==INVALID_HANDLE)
   { Print("[Monkey] 指标 handle 创建失败"); return INIT_FAILED; }

   ArrayInitialize(SupportLevels,0); ArrayInitialize(ResistanceLevels,0);
   PrintFormat("[Monkey] init | magic=%I64d | RSI %d/%d | RR %.1f",
               MagicNumber,RSI_Overbought,RSI_Oversold,RiskRewardRatio);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason){ Comment(""); }

//--- 读指标某根K线的值
double IndVal(int handle,int buf,int shift)
{
   double a[]; ArraySetAsSeries(a,true);
   if(CopyBuffer(handle,buf,shift,1,a)<1) return 0.0;
   return a[0];
}

//+------------------------------------------------------------------+
void OnTick()
{
   // 追踪止损每 tick 管
   if(UseTrailingStop) TrailStop();
   if(ShowPanel) UpdatePanel();

   // 只在新 K线处理
   datetime bt=iTime(_Symbol,PERIOD_CURRENT,0);
   if(bt==g_lastBar) return;
   g_lastBar=bt;

   g_ATR=IndVal(hATR,0,1);
   CalculatePivotPoints();
   CalculateDynamicSR();

   if(!IsTradingAllowed()) return;
   if(CountMyPositions()>0) return;      // 单仓
   CheckEnhancedTradingSignals();
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
         PositionGetInteger(POSITION_MAGIC)==MagicNumber) n++;
   }
   return n;
}

//+------------------------------------------------------------------+
void CalculatePivotPoints()
{
   double ph=iHigh(_Symbol,PERIOD_D1,1), pl=iLow(_Symbol,PERIOD_D1,1), pc=iClose(_Symbol,PERIOD_D1,1);
   DailyPivot=(ph+pl+pc)/3.0;
   DailyR1=2*DailyPivot-pl; DailyR2=DailyPivot+(ph-pl); DailyR3=ph+2*(DailyPivot-pl);
   DailyS1=2*DailyPivot-ph; DailyS2=DailyPivot-(ph-pl); DailyS3=pl-2*(ph-DailyPivot);

   double wh=iHigh(_Symbol,PERIOD_W1,1), wl=iLow(_Symbol,PERIOD_W1,1), wc=iClose(_Symbol,PERIOD_W1,1);
   WeeklyPivot=(wh+wl+wc)/3.0;
   WeeklyR1=2*WeeklyPivot-wl; WeeklyR2=WeeklyPivot+(wh-wl);
   WeeklyS1=2*WeeklyPivot-wh; WeeklyS2=WeeklyPivot-(wh-wl);
}

//+------------------------------------------------------------------+
void CalculateDynamicSR()
{
   SupportCount=0; ResistanceCount=0;
   int bars=(int)iBars(_Symbol,PERIOD_CURRENT);
   for(int i=Fractal_Period; i<SR_Lookback_Period && i<bars-Fractal_Period; i++)
   {
      double hi=iHigh(_Symbol,PERIOD_CURRENT,i);
      bool swingHigh=true;
      for(int j=1;j<=Fractal_Period;j++)
         if(hi<=iHigh(_Symbol,PERIOD_CURRENT,i-j) || hi<=iHigh(_Symbol,PERIOD_CURRENT,i+j)){ swingHigh=false; break; }
      if(swingHigh && ResistanceCount<10){ ResistanceLevels[ResistanceCount]=hi; ResistanceCount++; }

      double lo=iLow(_Symbol,PERIOD_CURRENT,i);
      bool swingLow=true;
      for(int k=1;k<=Fractal_Period;k++)
         if(lo>=iLow(_Symbol,PERIOD_CURRENT,i-k) || lo>=iLow(_Symbol,PERIOD_CURRENT,i+k)){ swingLow=false; break; }
      if(swingLow && SupportCount<10){ SupportLevels[SupportCount]=lo; SupportCount++; }
   }
}

//+------------------------------------------------------------------+
double GetNearestSupport(double price)
{
   double nearest=0, minD=DBL_MAX;
   for(int i=0;i<SupportCount;i++)
      if(SupportLevels[i]>0 && SupportLevels[i]<price && price-SupportLevels[i]<minD){ minD=price-SupportLevels[i]; nearest=SupportLevels[i]; }
   if(Use_Daily_Pivots)
   {
      double lv[3]; lv[0]=DailyS1; lv[1]=DailyS2; lv[2]=DailyS3;
      for(int j=0;j<3;j++) if(lv[j]<price && price-lv[j]<minD){ minD=price-lv[j]; nearest=lv[j]; }
   }
   return nearest;
}
double GetNearestResistance(double price)
{
   double nearest=0, minD=DBL_MAX;
   for(int i=0;i<ResistanceCount;i++)
      if(ResistanceLevels[i]>0 && ResistanceLevels[i]>price && ResistanceLevels[i]-price<minD){ minD=ResistanceLevels[i]-price; nearest=ResistanceLevels[i]; }
   if(Use_Daily_Pivots)
   {
      double lv[3]; lv[0]=DailyR1; lv[1]=DailyR2; lv[2]=DailyR3;
      for(int j=0;j<3;j++) if(lv[j]>price && lv[j]-price<minD){ minD=lv[j]-price; nearest=lv[j]; }
   }
   return nearest;
}
bool IsNearLevel(double price,double level,double tol){ return (MathAbs(price-level)<=tol); }

//+------------------------------------------------------------------+
int ServerHour(){ MqlDateTime dt; TimeToStruct(TimeCurrent(),dt); return dt.hour; }

bool IsTradingAllowed()
{
   double spread=(SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;
   if(spread>MaxSpreadPts) return false;

   int h=ServerHour();
   if(UseTradingHours && (h<StartHour || h>=EndHour)) return false;

   if(UseSessionFilter)
   {
      bool inAsian=(h>=0 && h<8);
      bool inLondon=(h>=8 && h<16);
      bool inNY=(h>=13 && h<21);
      bool inOverlap=(h>=13 && h<16);
      if(TradeOverlapOnly && !inOverlap) return false;
      if(!TradeAsianSession && inAsian && !inLondon && !inNY) return false;
      if(!TradeLondonSession && inLondon && !inOverlap) return false;
      if(!TradeNYSession && inNY && !inOverlap) return false;
   }

   if(UseVolatilityFilter)
   {
      double avgRange=0;
      for(int i=1;i<=VolatilityPeriod;i++)
         avgRange += (iHigh(_Symbol,PERIOD_CURRENT,i)-iLow(_Symbol,PERIOD_CURRENT,i));
      avgRange/=VolatilityPeriod;
      if(avgRange>0 && g_ATR>avgRange*VolatilityThreshold) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
bool IsHighQualityPivotSignal(double price,double level)
{
   if(MathAbs(price-level) > g_ATR*0.3) return false;
   int h=ServerHour();
   if(h==15 || h==20) return false;      // 伦敦/纽约收尾质量差
   return true;
}
bool IsHighQualityTradingTime()
{
   int h=ServerHour();
   bool overlap=(h>=13 && h<=16), london=(h>=8 && h<=12), ny=(h>=16 && h<=20);
   if(overlap) return true;
   if(TradeOverlapOnly) return false;
   return (TradeLondonSession && london) || (TradeNYSession && ny);
}
int CalculateTradeQuality(double price,bool isBuy)
{
   int score=0;
   double ns=GetNearestSupport(price), nr=GetNearestResistance(price);
   if(isBuy && ns>0 && IsHighQualityPivotSignal(price,ns)) score+=3;
   else if(!isBuy && nr>0 && IsHighQualityPivotSignal(price,nr)) score+=3;
   if(IsHighQualityTradingTime()) score+=2;
   double rsi=IndVal(hRSI,0,1);
   if((isBuy && rsi<RSI_Oversold+10) || (!isBuy && rsi>RSI_Overbought-10)) score+=1;
   double dATR=IndVal(hATRd,0,1);
   if(dATR>0 && g_ATR<dATR*1.2) score+=1;
   return score;
}

//+------------------------------------------------------------------+
int ConsecutiveLosses()
{
   if(!HistorySelect(TimeCurrent()-30*24*3600,TimeCurrent())) return 0;
   int losses=0;
   for(int i=HistoryDealsTotal()-1;i>=0;i--)
   {
      ulong tk=HistoryDealGetTicket(i);
      if(tk==0) continue;
      if(HistoryDealGetInteger(tk,DEAL_MAGIC)!=MagicNumber) continue;
      if(HistoryDealGetString(tk,DEAL_SYMBOL)!=_Symbol) continue;
      if(HistoryDealGetInteger(tk,DEAL_ENTRY)!=DEAL_ENTRY_OUT) continue;
      double p=HistoryDealGetDouble(tk,DEAL_PROFIT)+HistoryDealGetDouble(tk,DEAL_SWAP)+HistoryDealGetDouble(tk,DEAL_COMMISSION);
      if(p<0) losses++;
      else break;
   }
   return losses;
}

//+------------------------------------------------------------------+
double StopDistance()
{
   double sd=g_ATR*ATR_Multiplier;
   double mn=MinStopLossPts*_Point, mx=MaxStopLossPts*_Point;
   return MathMax(mn,MathMin(mx,sd));
}

double CalcLot()
{
   double lot=LotSize;
   if(UseAutoLotSizing)
   {
      double eq=AccountInfoDouble(ACCOUNT_EQUITY);
      double riskAmt=eq*RiskPercent/100.0;
      double slPts=StopDistance()/_Point;
      double tickVal=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_VALUE);
      double tickSize=SymbolInfoDouble(_Symbol,SYMBOL_TRADE_TICK_SIZE);
      double perLot=(tickSize>0)? (StopDistance()/tickSize)*tickVal : slPts*tickVal;
      if(perLot>0) lot=riskAmt/perLot;
   }
   // 连亏降险
   if(ConsecutiveLosses()>=MaxConsecutiveLosses) lot*=RiskReductionFactor;
   // 波动率调仓
   if(UseVolatilityPositioning)
   {
      double dATR=IndVal(hATRd,0,1);
      if(dATR>0)
      {
         double r=g_ATR/dATR;
         if(r>1.3) lot*=0.7; else if(r<0.7) lot*=1.1;
      }
   }
   double step=SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_STEP);
   double mnL =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MIN);
   double mxL =SymbolInfoDouble(_Symbol,SYMBOL_VOLUME_MAX);
   if(step>0) lot=MathFloor(lot/step)*step;
   lot=MathMax(mnL,MathMin(mxL,lot));
   return NormalizeDouble(lot,2);
}

//+------------------------------------------------------------------+
void OpenOrder(bool isBuy)
{
   double lot=CalcLot();
   double sd=StopDistance();
   double price=isBuy? SymbolInfoDouble(_Symbol,SYMBOL_ASK):SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double sl=isBuy? price-sd : price+sd;
   double tp=isBuy? price+sd*RiskRewardRatio : price-sd*RiskRewardRatio;
   sl=NormalizeDouble(sl,_Digits); tp=NormalizeDouble(tp,_Digits);
   string cmt=TradeComment+(isBuy?" BUY Q":" SELL Q")+IntegerToString(g_lastQuality);
   bool ok=isBuy? trade.Buy(lot,_Symbol,0.0,sl,tp,cmt) : trade.Sell(lot,_Symbol,0.0,sl,tp,cmt);
   if(ok) PrintFormat("[Monkey] %s lot=%.2f @%.3f SL=%.3f TP=%.3f Q=%d",
                      isBuy?"BUY":"SELL",lot,price,sl,tp,g_lastQuality);
   else   PrintFormat("[Monkey] 下单失败 %u %s",trade.ResultRetcode(),trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
void CheckEnhancedTradingSignals()
{
   double rsi=IndVal(hRSI,0,1);
   double macdMain=IndVal(hMACD,0,1), macdSig=IndVal(hMACD,1,1);
   double maF=IndVal(hMAf,0,1), maS=IndVal(hMAs,0,1);
   double price=iClose(_Symbol,PERIOD_CURRENT,1);
   double ns=GetNearestSupport(price), nr=GetNearestResistance(price);
   double tol=g_ATR*0.5;

   bool buy=false, sell=false;

   // 近支撑买
   if(ns>0 && IsNearLevel(price,ns,tol))
      if(rsi<RSI_Oversold+10 && macdMain>macdSig && maF>maS && price>DailyPivot)
      {
         g_lastQuality=CalculateTradeQuality(price,true);
         if(!UseTradeQualityFilter || g_lastQuality>=MinTradeQuality) buy=true;
      }
   // 近阻力卖
   if(nr>0 && IsNearLevel(price,nr,tol))
      if(rsi>RSI_Overbought-10 && macdMain<macdSig && maF<maS && price<DailyPivot)
      {
         g_lastQuality=CalculateTradeQuality(price,false);
         if(!UseTradeQualityFilter || g_lastQuality>=MinTradeQuality) sell=true;
      }
   // 顺势
   if(!buy && !sell)
   {
      if(maF>maS && macdMain>macdSig && rsi>50 && price>DailyPivot){ g_lastQuality=CalculateTradeQuality(price,true);  if(!UseTradeQualityFilter||g_lastQuality>=MinTradeQuality) buy=true; }
      if(maF<maS && macdMain<macdSig && rsi<50 && price<DailyPivot){ g_lastQuality=CalculateTradeQuality(price,false); if(!UseTradeQualityFilter||g_lastQuality>=MinTradeQuality) sell=true; }
   }

   if(buy)  OpenOrder(true);
   else if(sell) OpenOrder(false);
}

//+------------------------------------------------------------------+
void TrailStop()
{
   double atr=IndVal(hATR,0,1);
   double dist=atr*TrailingMultiplier;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=MagicNumber) continue;
      long type=PositionGetInteger(POSITION_TYPE);
      double sl=PositionGetDouble(POSITION_SL), tp=PositionGetDouble(POSITION_TP);
      double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      if(type==POSITION_TYPE_BUY)
      {
         double newSL=bid-dist;
         if((sl==0.0 || newSL>sl) && newSL<bid-MinStopLossPts*_Point)
            trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),tp);
      }
      else if(type==POSITION_TYPE_SELL)
      {
         double newSL=ask+dist;
         if((sl==0.0 || newSL<sl) && newSL>ask+MinStopLossPts*_Point)
            trade.PositionModify(tk,NormalizeDouble(newSL,_Digits),tp);
      }
   }
}

//+------------------------------------------------------------------+
void UpdatePanel()
{
   double rsi=IndVal(hRSI,0,0);
   double price=iClose(_Symbol,PERIOD_CURRENT,0);
   double spread=(SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;
   string rz = rsi>=RSI_Overbought?"SELL区": (rsi<=RSI_Oversold?"BUY区":"中性");
   string st = IsTradingAllowed()?"READY":"WAITING";
   Comment(StringFormat("🐒 MonkeyAttack MQL5\n状态:%s  点差:%.0f\n价:%.3f  RSI:%.1f(%s)\n日枢轴:%.3f\n近支撑:%.3f 近阻力:%.3f\n连亏:%d",
           st,spread,price,rsi,rz,DailyPivot,GetNearestSupport(price),GetNearestResistance(price),ConsecutiveLosses()));
}
//+------------------------------------------------------------------+
