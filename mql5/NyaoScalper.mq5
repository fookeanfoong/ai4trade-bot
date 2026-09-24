//+------------------------------------------------------------------+
//|                                              NyaoScalper.mq5      |
//|   指标加权信号分剥头皮 EA(XAUUSD M1/M5) —— 自包含单文件            |
//|                                                                  |
//|  参照 Nyao Scalper v43.0 规格实现其**非马丁核心**:                 |
//|   0-10 加权信号分 = 趋势(3) + 动量(3) + 波动结构(4) - 价格行为惩罚 |
//|   死盘归零(ATR/均ATR < 阈值)、新K线才评估进场(不重绘)、            |
//|   跨K线信号平滑、点差/ATR/时段/新闻/日回撤/篮子止损全套风控、       |
//|   ATR 追踪 + 保本锁定 + R:R 止盈止损。                             |
//|                                                                  |
//|  ⚠️ 原规格的 Hedge Chain(对冲马丁)**故意不实现** —— 违反本项目红线 |
//|     「不加仓摊平、不马丁」。每单必带硬止损,止损只朝盈利方向移动。    |
//+------------------------------------------------------------------+
#property copyright "NyaoScalper - non-martingale core, open synthesis"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

//====================== 输入 ======================
input group "=== 基础 ==="
input double InpFixedLot        = 0.01;        // 固定手数
input long   InpMagic           = 20260927;    // 魔术号(独立)
input int    InpMaxPositions     = 3;          // 同时最多持仓

input group "=== 周期 ==="
input ENUM_TIMEFRAMES InpSignalTF = PERIOD_M1; // 信号周期(剥头皮:M1/M5)

input group "=== 指标 ==="
input int    InpEmaFast     = 12;              // 快 EMA
input int    InpEmaSlow     = 26;              // 慢 EMA
input int    InpSlopeLookback = 3;             // EMA 斜率回看K线数(减M1抖动)
input int    InpRsiPeriod   = 14;              // RSI 周期
input int    InpAtrPeriod   = 14;              // ATR 周期
input int    InpAvgAtrPeriod = 50;             // 均 ATR 周期(算波动比)
input int    InpBodyAvgBars = 10;              // 平均实体/范围回看
input int    InpPeakLookback = 5;              // 局部高低点回看(突破)

input group "=== 信号分门槛/平滑 ==="
input double InpMinSignalScore = 4.5;          // 进场门槛(0-10)
input int    InpSmoothCandles  = 1;            // 平滑:平均最近 N 根已收盘的分
input double InpMinVolRatio     = 0.65;        // 死盘闸:ATR/均ATR 低于此则信号归零
input bool   InpNewBarOnly      = true;        // 只在新K线收盘评估进场(不重绘)

input group "=== 权重(可调灵敏度) ==="
input double InpWTrendAlign   = 1.5;           // 趋势:EMA 排列
input double InpWTrendSlope   = 1.5;           // 趋势:EMA 斜率
input double InpWRsiSweet     = 1.0;           // 动量:RSI 甜点区
input double InpWRsiBreak     = 0.5;           // 动量:RSI 突破关键位
input double InpWBody         = 1.5;           // 动量:实体动量
input double InpWChopHigh     = 2.0;           // 结构:强趋势(高波动比)
input double InpWVolExpand    = 1.0;           // 结构:波动扩张
input double InpWPeakBreak    = 1.0;           // 结构:突破局部高低

input group "=== 波动率闸门 ==="
input double InpAtrMinUSD   = 0.60;            // ATR 下限($),太安静不做
input double InpAtrMaxUSD   = 20.0;            // ATR 上限($),太乱不做

input group "=== 行情自适应(最近N分钟识别趋势/震荡) ==="
input bool   InpUseRegime   = true;            // 开:按当前行情自动切进场打法
input int    InpRegimeBars  = 20;              // 回看K线数(M1=20分钟)
input double InpTrendER     = 0.45;            // 效率比>=此=趋势行情(只顺势做,禁逆势)
input double InpRangeER     = 0.28;            // 效率比<=此=震荡行情(只在区间边缘做)
input double InpRangeEdge   = 0.35;            // 震荡:多单只在下沿35%内/空单只在上沿35%内

input group "=== 黄金历史特征:防追高/贴关键位反转 ==="
input bool   InpUseSmartLevels = true;         // 开:冲高后不追 + 贴关键位不追
input int    InpSpikeBars      = 5;            // 近N根算冲刺幅度
input double InpMaxSpikeATR    = 2.5;          // 近N根同向已冲>此×ATR就不追(黄金冲后常回调)
input double InpKeyGuardATR    = 0.30;         // 距关键位<此×ATR不朝其方向追(阻力不追多/支撑不追空)
input double InpRoundStep      = 10.0;         // 整数关口步长($):黄金在整关常停/反转
input int    InpAsiaStartHour  = 3;            // 亚洲盘起(服务器时间,算亚洲区间高低)
input int    InpAsiaEndHour    = 10;           // 亚洲盘止

input group "=== 点差闸 ==="
input double InpMaxSpreadUSD     = 0.35;       // 点差上限($)
input double InpMaxSpreadATRRatio = 0.20;      // 点差/ATR 上限(0=关);两条都要过

input group "=== 出场:R:R(ATR) ==="
input double InpRRAtrMult   = 1.0;             // 止损 = N×ATR
input double InpRiskReward   = 1.5;            // 止盈 = 止损×该比

input group "=== 出场:追踪/保本 ==="
input bool   InpUseBreakeven = true;           // 到 1R 移保本
input double InpBeBufferATR  = 0.05;           // 保本缓冲(×ATR)
input bool   InpUseTrail    = true;            // ATR 追踪
input double InpTrailAtrMult = 1.2;            // 追踪跟价 N×ATR
input double InpTrailStartR  = 0.8;            // 盈利达 N×R 才启动追踪

input group "=== 时段(服务器时间,避开亚洲薄盘) ==="
input bool   InpUseSession  = true;            // 启用时段过滤
input int    InpSessStart   = 8;               // 开始小时(约伦敦盘)
input int    InpSessEnd     = 22;              // 结束小时(纽约盘尾)

input group "=== 重大数据黑窗(手动填,前后各停) ==="
input string InpNewsTimes   = "";              // 逗号分隔,如 2026.09.25 20:30 (服务器时间)
input int    InpNewsBeforeMin = 30;            // 数据前 N 分钟停
input int    InpNewsAfterMin  = 30;            // 数据后 N 分钟停

input group "=== 风控 ==="
input int    InpMaxTradesPerDay   = 100000;        // 每日最多开仓
input double InpDailyTargetUSD    = 100.0;     // 当日(相对开盘权益)赚到该值全平收工(0=关)
input double InpDailyMaxLossUSD   = 0.0;       // 当日(相对开盘权益)亏到该值停手(0=关)
input double InpMaxBasketLossPct  = 8.0;       // 组合浮亏超权益该% 全平并暂停(0=关)
input double InpMinEquityUSD      = 0.0;       // 权益跌破该值硬停(0=关)

input group "=== 手数增强(可选) ==="
input bool   InpConfidenceLot = false;         // 高分(>8)加大手数
input double InpConfidenceMult = 1.5;          // 高分手数倍数
input double InpMaxLot        = 0.05;          // 手数上限

input group "=== 监控 ==="
input bool   InpDashboard   = true;            // 图表面板
input bool   InpVerbose     = true;            // 详细日志

//====================== 全局 ======================
CTrade  trade;
int     hEmaF=INVALID_HANDLE, hEmaS=INVALID_HANDLE, hRsi=INVALID_HANDLE, hAtr=INVALID_HANDLE;
datetime g_lastBar=0;
int      g_dayIdx=-1, g_tradesToday=0;
double   g_dayStartEquity=0.0;
bool     g_dayHalted=false, g_basketPaused=false;
double   g_scoreHist[];       // 最近若干根的带符号信号分(+多/-空)
double   g_lastBuy=0, g_lastSell=0, g_lastSmoothed=0;   // 面板用
int      g_regime=0; double g_regER=0.0;               // 行情识别:1趋势/-1震荡/0过渡

//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(30);
   uint fill=(uint)SymbolInfoInteger(_Symbol,SYMBOL_FILLING_MODE);
   if((fill&SYMBOL_FILLING_FOK)!=0)      trade.SetTypeFilling(ORDER_FILLING_FOK);
   else if((fill&SYMBOL_FILLING_IOC)!=0) trade.SetTypeFilling(ORDER_FILLING_IOC);
   else                                  trade.SetTypeFilling(ORDER_FILLING_RETURN);

   hEmaF = iMA(_Symbol, InpSignalTF, InpEmaFast, 0, MODE_EMA, PRICE_CLOSE);
   hEmaS = iMA(_Symbol, InpSignalTF, InpEmaSlow, 0, MODE_EMA, PRICE_CLOSE);
   hRsi  = iRSI(_Symbol, InpSignalTF, InpRsiPeriod, PRICE_CLOSE);
   hAtr  = iATR(_Symbol, InpSignalTF, InpAtrPeriod);
   if(hEmaF==INVALID_HANDLE || hEmaS==INVALID_HANDLE || hRsi==INVALID_HANDLE || hAtr==INVALID_HANDLE)
   { Print("[NyaoScalper] 指标句柄创建失败"); return(INIT_FAILED); }

   ArrayResize(g_scoreHist, MathMax(1, InpSmoothCandles));
   ArrayInitialize(g_scoreHist, 0.0);
   g_dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   PrintFormat("[NyaoScalper] init | magic=%I64d lot=%.2f TF=%s minScore=%.1f",
               InpMagic, InpFixedLot, EnumToString(InpSignalTF), InpMinSignalScore);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(hEmaF!=INVALID_HANDLE) IndicatorRelease(hEmaF);
   if(hEmaS!=INVALID_HANDLE) IndicatorRelease(hEmaS);
   if(hRsi!=INVALID_HANDLE)  IndicatorRelease(hRsi);
   if(hAtr!=INVALID_HANDLE)  IndicatorRelease(hAtr);
   Comment("");
}

//+------------------------------------------------------------------+
double Buf(int h, int shift)
{
   double v[]; if(CopyBuffer(h,0,shift,1,v)!=1) return(0.0); return(v[0]);
}

int CountMyPositions()
{
   int n=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)==_Symbol && PositionGetInteger(POSITION_MAGIC)==InpMagic) n++;
   }
   return n;
}

double MyFloatingPL()
{
   double p=0.0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      p += PositionGetDouble(POSITION_PROFIT)+PositionGetDouble(POSITION_SWAP);
   }
   return p;
}

//+------------------------------------------------------------------+
//| 均 ATR                                                          |
//+------------------------------------------------------------------+
double AvgATR()
{
   double v[]; int n=MathMax(2,InpAvgAtrPeriod);
   if(CopyBuffer(hAtr,0,1,n,v)!=n) return(0.0);
   double s=0; for(int i=0;i<n;i++) s+=v[i];
   return s/n;
}

//+------------------------------------------------------------------+
//| 平均实体/范围(已收盘 K 线, shift 2..N+1)                        |
//+------------------------------------------------------------------+
void AvgBodyRange(double &avgBody, double &avgRange)
{
   int n=MathMax(2,InpBodyAvgBars); double sb=0, sr=0;
   for(int s=2; s<2+n; s++)
   {
      double o=iOpen(_Symbol,InpSignalTF,s), c=iClose(_Symbol,InpSignalTF,s);
      double h=iHigh(_Symbol,InpSignalTF,s), l=iLow(_Symbol,InpSignalTF,s);
      sb += MathAbs(c-o); sr += (h-l);
   }
   avgBody=sb/n; avgRange=sr/n;
}

//+------------------------------------------------------------------+
//| 核心:算多头分与空头分(0-10),用已收盘 K 线(shift=1),不重绘       |
//+------------------------------------------------------------------+
void RawScores(double atr, double &buyScore, double &sellScore)
{
   buyScore=0; sellScore=0;
   double emaF=Buf(hEmaF,1), emaS=Buf(hEmaS,1);
   double emaFprev=Buf(hEmaF,1+MathMax(1,InpSlopeLookback));
   double rsi=Buf(hRsi,1), rsiPrev=Buf(hRsi,2);
   if(emaF==0||emaS==0||emaFprev==0||rsi==0) return;

   double o1=iOpen(_Symbol,InpSignalTF,1), c1=iClose(_Symbol,InpSignalTF,1);
   double h1=iHigh(_Symbol,InpSignalTF,1), l1=iLow(_Symbol,InpSignalTF,1);
   double body=MathAbs(c1-o1);
   double upWick=h1-MathMax(o1,c1), dnWick=MathMin(o1,c1)-l1;

   double avgBody, avgRange; AvgBodyRange(avgBody,avgRange);
   double avgAtr=AvgATR();
   double atrRatio = (avgAtr>0)? atr/avgAtr : 1.0;

   // 死盘闸:太安静直接归零
   if(InpMinVolRatio>0 && atrRatio<InpMinVolRatio) return;

   // --- 趋势(max 3) ---
   double bTrend=0, sTrend=0;
   if(emaF>emaS) bTrend+=InpWTrendAlign; else if(emaF<emaS) sTrend+=InpWTrendAlign;
   if(emaF>emaFprev) bTrend+=InpWTrendSlope; else if(emaF<emaFprev) sTrend+=InpWTrendSlope;

   // --- 动量(max 3),含脉冲加成 ---
   double bMom=0, sMom=0;
   if(rsi>=50 && rsi<=80) bMom+=InpWRsiSweet;
   if(rsi>=20 && rsi<=50) sMom+=InpWRsiSweet;
   if(rsiPrev<=60 && rsi>60) bMom+=InpWRsiBreak;
   if(rsiPrev>=40 && rsi<40) sMom+=InpWRsiBreak;
   bool bigBody = (avgBody>0 && body>avgBody);
   if(bigBody && c1>o1) bMom+=InpWBody;
   if(bigBody && c1<o1) sMom+=InpWBody;
   // 脉冲:实体加速 + 范围扩张 + 连续同向
   double bodyAccel=(avgBody>0)? body/avgBody : 1.0;
   double rangeExp =(avgRange>0)? (h1-l1)/avgRange : 1.0;
   int consec=0; for(int s=1;s<6;s++){ double oo=iOpen(_Symbol,InpSignalTF,s),cc=iClose(_Symbol,InpSignalTF,s);
      if((c1>o1 && cc>oo)||(c1<o1 && cc<oo)) consec++; else break; }
   double impulse=(bodyAccel-1.0)*0.3+(rangeExp-1.0)*0.2+consec*0.08;
   impulse=MathMax(0.0, MathMin(1.0, impulse));
   bMom*=(1.0+impulse); sMom*=(1.0+impulse);
   bMom=MathMin(bMom,3.0*(1.0+1.0)); sMom=MathMin(sMom,3.0*(1.0+1.0));

   // --- 波动结构(max 4) ---
   double vs=0;
   if(atrRatio>=1.3) vs+=InpWChopHigh;          // 强趋势
   else if(atrRatio>=1.0) vs+=InpWChopHigh*0.5; // 中
   // 低波动(chop)不加分
   double bVS=vs, sVS=vs;
   if(atrRatio>1.2){ bVS+=InpWVolExpand; sVS+=InpWVolExpand; }
   // 突破局部高低
   double pkH=iHigh(_Symbol,InpSignalTF,iHighest(_Symbol,InpSignalTF,MODE_HIGH,InpPeakLookback,2));
   double pkL=iLow (_Symbol,InpSignalTF,iLowest (_Symbol,InpSignalTF,MODE_LOW ,InpPeakLookback,2));
   if(c1>pkH) bVS+=InpWPeakBreak;
   if(c1<pkL) sVS+=InpWPeakBreak;

   buyScore  = bTrend+bMom+bVS;
   sellScore = sTrend+sMom+sVS;

   // --- 价格行为惩罚:逆向长影 ---
   if(body>0)
   {
      buyScore  -= (upWick/body);   // 做多遇上影线拒绝
      sellScore -= (dnWick/body);   // 做空遇下影线拒绝
   }
   buyScore =MathMax(0.0, MathMin(10.0, buyScore));
   sellScore=MathMax(0.0, MathMin(10.0, sellScore));
}

//+------------------------------------------------------------------+
//| 平滑:把本根带符号分推入环形缓冲,返回平均;dir 带回              |
//+------------------------------------------------------------------+
double SmoothedScore(double atr, int &dir)
{
   double b=0,s=0; RawScores(atr,b,s);
   g_lastBuy=b; g_lastSell=s;
   double signed_ = (b>=s)? b : -s;   // 取强的一方,带方向符号
   // 推入环形
   int n=ArraySize(g_scoreHist);
   for(int i=n-1;i>0;i--) g_scoreHist[i]=g_scoreHist[i-1];
   g_scoreHist[0]=signed_;
   double sum=0; for(int i=0;i<n;i++) sum+=g_scoreHist[i];
   double avg=sum/n;
   dir=(avg>0)?1:((avg<0)?-1:0);
   g_lastSmoothed=avg;
   return MathAbs(avg);
}

//+------------------------------------------------------------------+
bool InSession()
{
   if(!InpUseSession) return true;
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   if(InpSessStart<=InpSessEnd) return (t.hour>=InpSessStart && t.hour<InpSessEnd);
   return (t.hour>=InpSessStart || t.hour<InpSessEnd);
}

bool InNewsBlackout()
{
   if(StringLen(InpNewsTimes)==0) return false;
   datetime now=TimeCurrent(); string p[];
   int n=StringSplit(InpNewsTimes,',',p);
   for(int i=0;i<n;i++){ string s=p[i]; StringTrimLeft(s); StringTrimRight(s);
      if(StringLen(s)==0) continue; datetime e=StringToTime(s); if(e<=0) continue;
      if(now>=e-InpNewsBeforeMin*60 && now<=e+InpNewsAfterMin*60) return true; }
   return false;
}

//+------------------------------------------------------------------+
//| 行情识别:效率比(Kaufman ER)分趋势/震荡 + 区间位置                 |
//|  返回 1=趋势 / -1=震荡 / 0=过渡; trendDir=近N根净方向; rangePos  |
//|  = 当前价在近N根高低区间的位置(0=底,1=顶)。这是"看当前",不预测。 |
//+------------------------------------------------------------------+
int RegimeDetect(int &trendDir, double &rangePos, double &erOut)
{
   int n=MathMax(5,InpRegimeBars);
   double c1=iClose(_Symbol,InpSignalTF,1);
   double cn=iClose(_Symbol,InpSignalTF,1+n);
   trendDir=0; rangePos=0.5; erOut=0.0;
   if(c1<=0||cn<=0) return 0;
   double net=MathAbs(c1-cn);
   double sum=0.0;
   for(int s=1;s<=n;s++){ double a=iClose(_Symbol,InpSignalTF,s), b=iClose(_Symbol,InpSignalTF,s+1);
      if(a>0&&b>0) sum+=MathAbs(a-b); }
   double er=(sum>0.0)? net/sum : 0.0;
   erOut=er;
   trendDir=(c1>cn)?1:((c1<cn)?-1:0);
   int hi=iHighest(_Symbol,InpSignalTF,MODE_HIGH,n,1);
   int lo=iLowest (_Symbol,InpSignalTF,MODE_LOW ,n,1);
   double h=iHigh(_Symbol,InpSignalTF,hi), l=iLow(_Symbol,InpSignalTF,lo);
   rangePos=(h>l)? (c1-l)/(h-l) : 0.5;
   if(er>=InpTrendER) return 1;    // 趋势
   if(er<=InpRangeER) return -1;   // 震荡
   return 0;                        // 过渡
}

//+------------------------------------------------------------------+
//| 关键位:前日高低 / 亚洲区间高低 / 整数关口                         |
//+------------------------------------------------------------------+
void AsiaHL(double &ah, double &al)
{
   ah=0; al=0;
   MqlDateTime now; TimeToStruct(TimeCurrent(),now);
   MqlDateTime d0=now; d0.hour=0; d0.min=0; d0.sec=0;
   datetime dayStart=StructToTime(d0);
   for(int s=1;s<1440;s++){
      datetime t=iTime(_Symbol,InpSignalTF,s); if(t==0||t<dayStart) break;
      MqlDateTime tt; TimeToStruct(t,tt);
      if(tt.hour>=InpAsiaStartHour && tt.hour<InpAsiaEndHour){
         double hh=iHigh(_Symbol,InpSignalTF,s), ll=iLow(_Symbol,InpSignalTF,s);
         if(ah==0||hh>ah) ah=hh;
         if(al==0||ll<al) al=ll;
      }
   }
}
double NearestResistance(double price)
{
   double pdh=iHigh(_Symbol,PERIOD_D1,1);
   double ah,al; AsiaHL(ah,al);
   double ru=MathCeil(price/InpRoundStep)*InpRoundStep; if(ru<=price) ru+=InpRoundStep;
   double cand[3]; cand[0]=pdh; cand[1]=ah; cand[2]=ru;
   double best=0;
   for(int i=0;i<3;i++){ double c=cand[i]; if(c>price && (best==0||c<best)) best=c; }
   return best;
}
double NearestSupport(double price)
{
   double pdl=iLow(_Symbol,PERIOD_D1,1);
   double ah,al; AsiaHL(ah,al);
   double rd=MathFloor(price/InpRoundStep)*InpRoundStep; if(rd>=price) rd-=InpRoundStep;
   double cand[3]; cand[0]=pdl; cand[1]=al; cand[2]=rd;
   double best=0;
   for(int i=0;i<3;i++){ double c=cand[i]; if(c>0 && c<price && (best==0||c>best)) best=c; }
   return best;
}

bool SpreadOK(double atr)
{
   double sp=SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID);
   if(sp>InpMaxSpreadUSD) return false;
   if(InpMaxSpreadATRRatio>0 && atr>0 && (sp/atr)>InpMaxSpreadATRRatio) return false;
   return true;
}

//+------------------------------------------------------------------+
void OpenTrade(int dir, double atr, double score)
{
   double lot=InpFixedLot;
   if(InpConfidenceLot && score>8.0) lot=MathMin(InpMaxLot, InpFixedLot*InpConfidenceMult);

   double ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK), bid=SymbolInfoDouble(_Symbol,SYMBOL_BID);
   double price=(dir>0)?ask:bid;
   double slDist=InpRRAtrMult*atr; if(slDist<=0) return;
   double tpDist=slDist*InpRiskReward;
   double sl=(dir>0)?price-slDist:price+slDist;
   double tp=(dir>0)?price+tpDist:price-tpDist;
   sl=NormalizeDouble(sl,_Digits); tp=NormalizeDouble(tp,_Digits);

   double stopLvl=(double)SymbolInfoInteger(_Symbol,SYMBOL_TRADE_STOPS_LEVEL)*_Point;
   if(stopLvl>0){
      if(dir>0 && (price-sl)<stopLvl) sl=NormalizeDouble(price-stopLvl,_Digits);
      if(dir<0 && (sl-price)<stopLvl) sl=NormalizeDouble(price+stopLvl,_Digits);
   }
   bool ok=(dir>0)?trade.Buy(lot,_Symbol,0.0,sl,tp,"NyaoScalper")
                  :trade.Sell(lot,_Symbol,0.0,sl,tp,"NyaoScalper");
   if(ok){ g_tradesToday++;
      PrintFormat("[OPEN] %s %.2f @%.3f SL=%.3f TP=%.3f | 分%.2f | 今日第%d笔",
                  dir>0?"BUY":"SELL", lot, price, sl, tp, score, g_tradesToday);
   } else PrintFormat("[NyaoScalper] 下单失败 %u %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
}

//+------------------------------------------------------------------+
void ManagePositions(double atr)
{
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      long type=PositionGetInteger(POSITION_TYPE);
      double open=PositionGetDouble(POSITION_PRICE_OPEN);
      double sl=PositionGetDouble(POSITION_SL), tp=PositionGetDouble(POSITION_TP);
      double bid=SymbolInfoDouble(_Symbol,SYMBOL_BID), ask=SymbolInfoDouble(_Symbol,SYMBOL_ASK);
      double rDist=InpRRAtrMult*atr; if(rDist<=0) continue;

      if(type==POSITION_TYPE_BUY){
         double prof=bid-open;
         if(InpUseBreakeven && prof>=rDist){ double be=NormalizeDouble(open+InpBeBufferATR*atr,_Digits); if(be>sl){trade.PositionModify(tk,be,tp); sl=be;} }
         if(InpUseTrail && prof>=InpTrailStartR*rDist){ double n=NormalizeDouble(bid-InpTrailAtrMult*atr,_Digits); if(n>sl) trade.PositionModify(tk,n,tp); }
      } else if(type==POSITION_TYPE_SELL){
         double prof=open-ask;
         if(InpUseBreakeven && prof>=rDist){ double be=NormalizeDouble(open-InpBeBufferATR*atr,_Digits); if(sl==0.0||be<sl){trade.PositionModify(tk,be,tp); sl=be;} }
         if(InpUseTrail && prof>=InpTrailStartR*rDist){ double n=NormalizeDouble(ask+InpTrailAtrMult*atr,_Digits); if(sl==0.0||n<sl) trade.PositionModify(tk,n,tp); }
      }
   }
}

void CloseAllMine()
{
   for(int i=PositionsTotal()-1;i>=0;i--){ ulong tk=PositionGetTicket(i); if(tk==0) continue;
      if(PositionGetString(POSITION_SYMBOL)!=_Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC)!=InpMagic) continue;
      trade.PositionClose(tk); }
}

//+------------------------------------------------------------------+
void UpdateDayState()
{
   MqlDateTime t; TimeToStruct(TimeCurrent(),t);
   int idx=t.year*1000+t.day_of_year;
   if(idx!=g_dayIdx){ g_dayIdx=idx; g_tradesToday=0; g_dayHalted=false; g_basketPaused=false;
      g_dayStartEquity=AccountInfoDouble(ACCOUNT_EQUITY); }
}

void ShowDashboard(double atr)
{
   if(!InpDashboard) return;
   double eq=AccountInfoDouble(ACCOUNT_EQUITY);
   string s="===== NyaoScalper =====\n";
   s+=StringFormat("多分 %.2f | 空分 %.2f | 平滑 %.2f (门槛%.1f)\n", g_lastBuy, g_lastSell, g_lastSmoothed, InpMinSignalScore);
   s+=StringFormat("ATR %.2f | 点差 %.2f\n", atr, SymbolInfoDouble(_Symbol,SYMBOL_ASK)-SymbolInfoDouble(_Symbol,SYMBOL_BID));
   if(InpUseRegime){ string rn=(g_regime==1?"趋势(只顺势)":(g_regime==-1?"震荡(高抛低吸)":"过渡")); s+=StringFormat("行情 %s ER%.2f\n", rn, g_regER); }
   s+=StringFormat("持仓 %d/%d | 今日 %d/%d 笔\n", CountMyPositions(), InpMaxPositions, g_tradesToday, InpMaxTradesPerDay);
   s+=StringFormat("权益 %.2f | 当日 %.2f | 浮动 %.2f\n", eq, eq-g_dayStartEquity, MyFloatingPL());
   s+=(g_dayHalted?"状态: 当日停手\n":(g_basketPaused?"状态: 篮子暂停\n":"状态: 运行中\n"));
   Comment(s);
}

//+------------------------------------------------------------------+
void OnTick()
{
   double atr=Buf(hAtr,1);
   ManagePositions(atr);
   UpdateDayState();
   ShowDashboard(atr);

   // 硬性权益停
   if(InpMinEquityUSD>0 && AccountInfoDouble(ACCOUNT_EQUITY)<InpMinEquityUSD){
      if(!g_dayHalted){ CloseAllMine(); g_dayHalted=true; if(InpVerbose) Print("[HALT] 权益跌破下限,全平停手"); }
      return;
   }
   // 篮子止损:组合浮亏超权益%
   if(InpMaxBasketLossPct>0){
      double eq=AccountInfoDouble(ACCOUNT_EQUITY);
      if(eq>0 && MyFloatingPL() <= -(InpMaxBasketLossPct/100.0)*eq){
         CloseAllMine(); g_basketPaused=true;
         if(InpVerbose) PrintFormat("[BASKET] 组合浮亏超 %.0f%% 权益,全平并暂停到明天", InpMaxBasketLossPct);
      }
   }
   if(g_basketPaused) return;

   // 日止盈:当日赚够目标,全平锁利收工到明天
   if(InpDailyTargetUSD>0 && !g_dayHalted &&
      (AccountInfoDouble(ACCOUNT_EQUITY)-g_dayStartEquity) >= InpDailyTargetUSD){
      CloseAllMine(); g_dayHalted=true;
      if(InpVerbose) PrintFormat("[TARGET] 当日止盈达标 +$%.2f,全平收工到明天", InpDailyTargetUSD);
      return;
   }

   // 只在新K线评估进场(不重绘)
   datetime bt=iTime(_Symbol,InpSignalTF,0);
   bool newBar=(bt!=g_lastBar);
   if(InpNewBarOnly && !newBar) return;
   if(newBar) g_lastBar=bt;

   if(g_dayHalted) return;
   if(InpDailyMaxLossUSD>0 && (AccountInfoDouble(ACCOUNT_EQUITY)-g_dayStartEquity) <= -InpDailyMaxLossUSD){
      g_dayHalted=true; if(InpVerbose) Print("[HALT] 当日亏损达上限,停手"); return; }
   if(g_tradesToday>=InpMaxTradesPerDay) return;
   if(CountMyPositions()>=InpMaxPositions) return;

   if(!InSession())        { return; }
   if(InNewsBlackout())    { if(InpVerbose) Print("[NO-TRADE] 重大数据黑窗"); return; }
   if(!SpreadOK(atr))      { if(InpVerbose) Print("[NO-TRADE] 点差过大"); return; }
   if(atr<InpAtrMinUSD || atr>InpAtrMaxUSD) return;

   int dir=0;
   double score=SmoothedScore(atr, dir);
   if(dir==0 || score<InpMinSignalScore){
      if(InpVerbose) PrintFormat("[NO-TRADE] 分%.2f<%.1f (多%.2f 空%.2f)", score, InpMinSignalScore, g_lastBuy, g_lastSell);
      return;
   }

   // --- 行情自适应:按当前是趋势还是震荡,限制进场 ---
   if(InpUseRegime)
   {
      int tdir; double rpos, er;
      int reg=RegimeDetect(tdir, rpos, er);
      g_regime=reg; g_regER=er;
      if(reg==1)   // 趋势行情:只顺近N根方向做,禁逆势(治"趋势里接刀")
      {
         if(tdir!=0 && dir!=tdir){
            if(InpVerbose) PrintFormat("[NO-TRADE] 趋势行情(ER%.2f)只顺%s,本信号逆势", er, tdir>0?"多":"空");
            return;
         }
      }
      else if(reg==-1)   // 震荡行情:高抛低吸,多单只在下沿/空单只在上沿
      {
         if(dir>0 && rpos>InpRangeEdge){
            if(InpVerbose) PrintFormat("[NO-TRADE] 震荡行情(ER%.2f)多单不在下沿(位置%.2f)", er, rpos);
            return;
         }
         if(dir<0 && rpos<(1.0-InpRangeEdge)){
            if(InpVerbose) PrintFormat("[NO-TRADE] 震荡行情(ER%.2f)空单不在上沿(位置%.2f)", er, rpos);
            return;
         }
      }
      // reg==0 过渡:正常放行
   }

   // --- 黄金历史特征:防追高 + 贴关键位不追 ---
   if(InpUseSmartLevels && atr>0)
   {
      double c1=iClose(_Symbol,InpSignalTF,1);
      double cS=iClose(_Symbol,InpSignalTF,1+MathMax(2,InpSpikeBars));
      // 1) 冲高/杀跌后不追:近N根同向已冲 > 阈值
      if(c1>0 && cS>0){
         double spike=c1-cS;
         if(MathAbs(spike) > InpMaxSpikeATR*atr && ((spike>0&&dir>0)||(spike<0&&dir<0))){
            if(InpVerbose) PrintFormat("[NO-TRADE] 近%d根已同向冲$%.2f(>%.1f×ATR),不追%s", InpSpikeBars, spike, InpMaxSpikeATR, dir>0?"多":"空");
            return;
         }
      }
      // 2) 贴关键位不朝其方向追(阻力不追多/支撑不追空)
      double px=(SymbolInfoDouble(_Symbol,SYMBOL_ASK)+SymbolInfoDouble(_Symbol,SYMBOL_BID))*0.5;
      if(dir>0){ double res=NearestResistance(px);
         if(res>0 && (res-px) < InpKeyGuardATR*atr){
            if(InpVerbose) PrintFormat("[NO-TRADE] 贴阻力%.2f(距%.2f)不追多", res, res-px); return; } }
      if(dir<0){ double sup=NearestSupport(px);
         if(sup>0 && (px-sup) < InpKeyGuardATR*atr){
            if(InpVerbose) PrintFormat("[NO-TRADE] 贴支撑%.2f(距%.2f)不追空", sup, px-sup); return; } }
   }

   OpenTrade(dir, atr, score);
}
//+------------------------------------------------------------------+
