//+------------------------------------------------------------------+
//|                                            GoldAIScalper.mq5      |
//|   XAUUSD 日内剥头皮 —— 多因子「AI」共识打分策略（自包含单文件）    |
//|                                                                  |
//|  策略来源：综合网上主流黄金日内剥头皮共识（EMA 交叉 + RSI 动量 +   |
//|  VWAP + ATR 波动 + 高周期趋势），把「AI EA」常见的 BUY/SELL/WAIT   |
//|  信号层落地成**透明的加权共识分(0-100)**，不依赖任何外部 API。      |
//|                                                                  |
//|  打分维度（各因子只加分，方向一致才计）：                          |
//|    1) 信号周期趋势   EMA9 vs EMA21        权重 25                   |
//|    2) 高周期趋势     H1 EMA50 斜率/价位   权重 20                   |
//|    3) RSI 动量区     多头 50-70/空头 30-50 权重 20                  |
//|    4) VWAP 同侧      价在 VWAP 哪一边      权重 15                   |
//|    5) 动量推进       最近K线净推进方向     权重 20                   |
//|  多空各自算分，取高的一方；>= InpMinScore 且过滤全过才开仓。        |
//|                                                                  |
//|  红线（写死，不留开关）：每单必带硬止损；止损只朝盈利方向移动。     |
//+------------------------------------------------------------------+
#property copyright "GoldAIScalper - open synthesis"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//====================== 输入参数 ======================
input group "=== 基础 ==="
input double InpFixedLot        = 0.01;        // 固定手数
input long   InpMagic           = 20260926;    // 魔术号(独立)
input int    InpMaxSpreadPoints  = 500;        // 点差上限(点),超过不开仓

input group "=== 周期 ==="
input ENUM_TIMEFRAMES InpSignalTF = PERIOD_M5; // 信号周期(剥头皮主周期)
input ENUM_TIMEFRAMES InpTrendTF  = PERIOD_H1; // 高周期趋势参考

input group "=== 指标参数 ==="
input int    InpEmaFast     = 9;               // 快 EMA(信号周期)
input int    InpEmaSlow     = 21;              // 慢 EMA(信号周期)
input int    InpEmaTrend    = 50;              // 趋势 EMA(高周期)
input int    InpRsiPeriod   = 14;              // RSI 周期
input double InpRsiBuyLo    = 50.0;            // 多头 RSI 下界
input double InpRsiBuyHi    = 72.0;            // 多头 RSI 上界(不追极值)
input double InpRsiSellHi   = 50.0;            // 空头 RSI 上界
input double InpRsiSellLo   = 28.0;            // 空头 RSI 下界
input int    InpAtrPeriod   = 14;              // ATR 周期

input group "=== 共识分门槛 ==="
input double InpMinScore    = 65.0;            // 共识分门槛(0-100),越高越少越准
input int    InpMomBars     = 3;               // 动量推进回看K线数

input group "=== 波动率闸门(避开死盘/暴动) ==="
input double InpAtrMinUSD   = 0.80;            // ATR 下限($),太安静不做
input double InpAtrMaxUSD   = 20.0;            // ATR 上限($),太乱不做

input group "=== 出场 ==="
input double InpSlAtrMult   = 1.2;             // 止损 = N×ATR
input double InpTpRR        = 1.8;             // 止盈 = RR×止损距离
input bool   InpUseBreakeven = true;           // 到 1R 移保本
input double InpBeAtBuffer  = 0.05;            // 保本缓冲(×ATR)
input bool   InpUseTrail    = true;            // ATR 追踪止损
input double InpTrailAtrMult = 1.5;            // 追踪跟在价格后 N×ATR
input double InpTrailStartR  = 1.0;            // 盈利达 N×R 才启动追踪

input group "=== 时段(服务器时间) ==="
input bool   InpUseSession  = true;            // 启用时段过滤
input int    InpSessStart   = 8;               // 开始小时(服务器时间,约伦敦盘)
input int    InpSessEnd     = 22;              // 结束小时(纽约盘尾)

input group "=== 风控 ==="
input int    InpMaxPositions      = 1;         // 同时最多持仓
input int    InpMaxTradesPerDay   = 12;        // 每日最多开仓
input int    InpStopAfterConsecLoss = 3;       // 连亏 N 笔当日停手
input double InpDailyMaxLossUSD   = 40.0;      // 当日浮亏+已实现亏到该值停手(0=关)

input group "=== 监控 ==="
input bool   InpVerbose     = true;            // 详细日志

//====================== 全局 ======================
CTrade  trade;
int     hEmaFast=INVALID_HANDLE, hEmaSlow=INVALID_HANDLE, hEmaTrend=INVALID_HANDLE;
int     hRsi=INVALID_HANDLE, hAtr=INVALID_HANDLE;
datetime g_lastBar=0;
int      g_dayIdx=-1;
int      g_tradesToday=0;
int      g_consecLoss=0;
double   g_dayStartEquity=0.0;
bool     g_dayHalted=false;

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   uint fill=(uint)SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((fill&SYMBOL_FILLING_FOK)!=0)      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fill&SYMBOL_FILLING_IOC)!=0) trade.SetTypeFilling(ORDER_FILLING_IOC);
   else                                  trade.SetTypeFilling(ORDER_FILLING_RETURN);

   hEmaFast  = iMA(_Symbol, InpSignalTF, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hEmaSlow  = iMA(_Symbol, InpSignalTF, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hEmaTrend = iMA(_Symbol, InpTrendTF,  InpEmaTrend,0, MODE_EMA, PRICE_CLOSE);
   hRsi      = iRSI(_Symbol, InpSignalTF, InpRsiPeriod, PRICE_CLOSE);
   hAtr      = iATR(_Symbol, InpSignalTF, InpAtrPeriod);

   if(hEmaFast==INVALID_HANDLE || hEmaSlow==INVALID_HANDLE || hEmaTrend==INVALID_HANDLE ||
      hRsi==INVALID_HANDLE || hAtr==INVALID_HANDLE)
   {
      Print("[GoldAIScalper] 指标句柄创建失败");
      return(INIT_FAILED);
   }

   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   PrintFormat("[GoldAIScalper] init | magic=%I64d | lot=%.2f | signalTF=%s | minScore=%.0f",
               InpMagic, InpFixedLot, EnumToString(InpSignalTF), InpMinScore);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(hEmaFast!=INVALID_HANDLE) IndicatorRelease(hEmaFast);
   if(hEmaSlow!=INVALID_HANDLE) IndicatorRelease(hEmaSlow);
   if(hEmaTrend!=INVALID_HANDLE) IndicatorRelease(hEmaTrend);
   if(hRsi!=INVALID_HANDLE) IndicatorRelease(hRsi);
   if(hAtr!=INVALID_HANDLE) IndicatorRelease(hAtr);
}

//+------------------------------------------------------------------+
double Buf(int handle, int shift)
{
   double v[];
   if(CopyBuffer(handle, 0, shift, 1, v) != 1) return(0.0);
   return(v[0]);
}

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
//| 当日 VWAP：从服务器日 0 点起 typical price × tick volume 加权     |
//+------------------------------------------------------------------+
double SessionVWAP()
{
   MqlDateTime now; TimeToStruct(TimeCurrent(), now);
   MqlDateTime d0=now; d0.hour=0; d0.min=0; d0.sec=0;
   datetime dayStart=StructToTime(d0);

   double pv=0.0, vv=0.0;
   for(int s=0; s<1440; s++)   // 最多回看一天的信号周期K线
   {
      datetime t=iTime(_Symbol, InpSignalTF, s);
      if(t==0 || t<dayStart) break;
      double h=iHigh(_Symbol, InpSignalTF, s);
      double l=iLow(_Symbol, InpSignalTF, s);
      double c=iClose(_Symbol, InpSignalTF, s);
      long   vol=iTickVolume(_Symbol, InpSignalTF, s);
      double tp=(h+l+c)/3.0;
      pv += tp*(double)vol;
      vv += (double)vol;
   }
   if(vv<=0.0) return(iClose(_Symbol, InpSignalTF, 0));
   return(pv/vv);
}

//+------------------------------------------------------------------+
//| 多因子共识分：返回方向(+1多/-1空/0无)，score 通过引用带回         |
//+------------------------------------------------------------------+
int ConsensusScore(double atr, double &scoreOut, string &detail)
{
   // 用已收盘K线(shift=1)取值，杜绝重绘
   double emaF = Buf(hEmaFast, 1);
   double emaS = Buf(hEmaSlow, 1);
   double emaT = Buf(hEmaTrend,1);
   double rsi  = Buf(hRsi, 1);
   double c1   = iClose(_Symbol, InpSignalTF, 1);
   double vwap = SessionVWAP();

   if(emaF==0 || emaS==0 || emaT==0 || rsi==0 || c1==0) { scoreOut=0; detail="数据不足"; return 0; }

   // 高周期趋势斜率
   double emaTPrev = Buf(hEmaTrend, 3);
   int htf = 0;
   if(emaT>emaTPrev && c1>emaT) htf=1;
   else if(emaT<emaTPrev && c1<emaT) htf=-1;

   // --- 多头分 ---
   double bs=0.0;
   if(emaF>emaS) bs += 25.0;                                  // 1 信号周期趋势
   if(htf>0)     bs += 20.0;                                  // 2 高周期趋势
   if(rsi>=InpRsiBuyLo && rsi<=InpRsiBuyHi) bs += 20.0;       // 3 RSI 动量区
   if(c1>vwap)   bs += 15.0;                                  // 4 VWAP 同侧
   double mom = c1 - iClose(_Symbol, InpSignalTF, 1+MathMax(1,InpMomBars));
   if(mom>0)     bs += 20.0;                                  // 5 动量推进

   // --- 空头分 ---
   double ss=0.0;
   if(emaF<emaS) ss += 25.0;
   if(htf<0)     ss += 20.0;
   if(rsi<=InpRsiSellHi && rsi>=InpRsiSellLo) ss += 20.0;
   if(c1<vwap)   ss += 15.0;
   if(mom<0)     ss += 20.0;

   if(bs>=ss && bs>0)
   {
      scoreOut=bs;
      detail=StringFormat("多 %.0f (EMA%s RSI%.1f VWAP%s HTF%d mom%.2f)",
             bs, emaF>emaS?"↑":"↓", rsi, c1>vwap?"上":"下", htf, mom);
      return 1;
   }
   else
   {
      scoreOut=ss;
      detail=StringFormat("空 %.0f (EMA%s RSI%.1f VWAP%s HTF%d mom%.2f)",
             ss, emaF<emaS?"↓":"↑", rsi, c1<vwap?"下":"上", htf, mom);
      return -1;
   }
}

//+------------------------------------------------------------------+
bool InSession()
{
   if(!InpUseSession) return true;
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   if(InpSessStart<=InpSessEnd) return (t.hour>=InpSessStart && t.hour<InpSessEnd);
   return (t.hour>=InpSessStart || t.hour<InpSessEnd); // 跨零点
}

bool SpreadOK()
{
   double sp=(SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID))/_Point;
   return (sp<=InpMaxSpreadPoints);
}

//+------------------------------------------------------------------+
void OpenTrade(int dir, double atr, double score, string detail)
{
   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
   double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double price = (dir>0)? ask : bid;
   double slDist = InpSlAtrMult*atr;
   if(slDist<=0) return;
   double sl = (dir>0)? price-slDist : price+slDist;
   double tp = (dir>0)? price+InpTpRR*slDist : price-InpTpRR*slDist;
   sl=NormalizeDouble(sl,_Digits); tp=NormalizeDouble(tp,_Digits);

   // 券商最小止损距离
   double stopLvl=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*_Point;
   if(stopLvl>0)
   {
      if(dir>0 && (price-sl)<stopLvl) sl=NormalizeDouble(price-stopLvl,_Digits);
      if(dir<0 && (sl-price)<stopLvl) sl=NormalizeDouble(price+stopLvl,_Digits);
   }

   bool ok = (dir>0)? trade.Buy(InpFixedLot,_Symbol,0.0,sl,tp,"GoldAIScalper")
                    : trade.Sell(InpFixedLot,_Symbol,0.0,sl,tp,"GoldAIScalper");
   if(ok)
   {
      g_tradesToday++;
      PrintFormat("[OPEN] %s @%.3f SL=%.3f TP=%.3f | 分%.0f | %s | 今日第%d笔",
                  dir>0?"BUY":"SELL", price, sl, tp, score, detail, g_tradesToday);
   }
   else PrintFormat("[GoldAIScalper] 下单失败 %u %s",
                    trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
//| 持仓管理：到 1R 移保本 -> ATR 追踪(止损只朝盈利方向)              |
//+------------------------------------------------------------------+
void ManagePositions(double atr)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i);
      if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;

      long   type=PositionGetInteger(POSITION_TYPE);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl  =PositionGetDouble(POSITION_SL);
      double tp  =PositionGetDouble(POSITION_TP);
      double bid =SymbolInfoDouble(_Symbol,SYMBOL_BID);
      double ask =SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      double rDist=InpSlAtrMult*atr;
      if(rDist<=0) continue;

      if(type==POSITION_TYPE_BUY)
      {
         double prof=bid-open;
         // 保本
         if(InpUseBreakeven && prof>=rDist)
         {
            double be=NormalizeDouble(open+InpBeAtBuffer*atr,_Digits);
            if(be>sl) { trade.PositionModify(tk,be,tp); sl=be; }
         }
         // 追踪
         if(InpUseTrail && prof>=InpTrailStartR*rDist)
         {
            double nsl=NormalizeDouble(bid-InpTrailAtrMult*atr,_Digits);
            if(nsl>sl) trade.PositionModify(tk,nsl,tp);
         }
      }
      else if(type==POSITION_TYPE_SELL)
      {
         double prof=open-ask;
         if(InpUseBreakeven && prof>=rDist)
         {
            double be=NormalizeDouble(open-InpBeAtBuffer*atr,_Digits);
            if(sl==0.0 || be<sl) { trade.PositionModify(tk,be,tp); sl=be; }
         }
         if(InpUseTrail && prof>=InpTrailStartR*rDist)
         {
            double nsl=NormalizeDouble(ask+InpTrailAtrMult*atr,_Digits);
            if(sl==0.0 || nsl<sl) trade.PositionModify(tk,nsl,tp);
         }
      }
   }
}

//+------------------------------------------------------------------+
//| 当日风控：换日重置；连亏/日亏/笔数达标当日停手                    |
//+------------------------------------------------------------------+
void UpdateDayState()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   int idx=t.year*1000+t.day_of_year;
   if(idx!=g_dayIdx)
   {
      g_dayIdx=idx;
      g_tradesToday=0;
      g_consecLoss=0;
      g_dayHalted=false;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY);
   }
}

// 统计本 EA 当日已实现盈亏(粗略:用 equity-balance 浮动 + 当日 equity 变化)
double DayFloatingAndRealized()
{
   // 当日相对开盘 equity 的变化(含浮动)。足够做"当日亏到X停手"的闸。
   return AccountInfoDouble(ACCOUNT_EQUITY) - g_dayStartEquity;
}

//+------------------------------------------------------------------+
void OnTick()
{
   double atr = Buf(hAtr, 1);
   ManagePositions(atr);

   UpdateDayState();

   // 只在信号周期新K线收盘时判断入场
   datetime bt=iTime(_Symbol, InpSignalTF, 0);
   if(bt==g_lastBar) return;
   g_lastBar=bt;

   if(g_dayHalted) return;

   // 当日亏损闸
   if(InpDailyMaxLossUSD>0 && DayFloatingAndRealized() <= -InpDailyMaxLossUSD)
   {
      if(!g_dayHalted && InpVerbose) Print("[HALT] 当日亏损达上限,停手到明天");
      g_dayHalted=true;
      return;
   }
   if(InpStopAfterConsecLoss>0 && g_consecLoss>=InpStopAfterConsecLoss)
   {
      if(!g_dayHalted && InpVerbose) PrintFormat("[HALT] 连亏 %d 笔,当日停手", g_consecLoss);
      g_dayHalted=true;
      return;
   }
   if(g_tradesToday>=InpMaxTradesPerDay) return;
   if(CountMyPositions()>=InpMaxPositions) return;

   // 过滤
   if(!InSession())  return;
   if(!SpreadOK())   return;
   if(atr<InpAtrMinUSD || atr>InpAtrMaxUSD) return;

   // 共识分
   double score=0.0; string detail="";
   int dir=ConsensusScore(atr, score, detail);
   if(dir==0 || score<InpMinScore)
   {
      if(InpVerbose) PrintFormat("[NO-TRADE] %s (门槛%.0f)", detail, InpMinScore);
      return;
   }

   OpenTrade(dir, atr, score, detail);
}

//+------------------------------------------------------------------+
//| 成交结果跟踪：平仓亏损累计连亏,盈利清零                           |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
{
   if(trans.type!=TRADE_TRANSACTION_DEAL_ADD) return;
   ulong deal=trans.deal;
   if(deal==0) return;
   if(!HistoryDealSelect(deal)) return;
   if(HistoryDealGetInteger(deal,DEAL_MAGIC)!=InpMagic) return;
   if(HistoryDealGetString(deal,DEAL_SYMBOL)!=_Symbol) return;
   if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(deal,DEAL_ENTRY)!=DEAL_ENTRY_OUT) return;

   double profit=HistoryDealGetDouble(deal,DEAL_PROFIT)
                +HistoryDealGetDouble(deal,DEAL_SWAP)
                +HistoryDealGetDouble(deal,DEAL_COMMISSION);
   if(profit<0) g_consecLoss++;
   else if(profit>0) g_consecLoss=0;
}
//+------------------------------------------------------------------+
