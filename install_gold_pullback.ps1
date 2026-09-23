# GoldPullback 一键安装(Windows PowerShell)
# 做的事:
#   1) 找到本机所有 MT5 数据目录(%APPDATA%\MetaQuotes\Terminal\*)
#   2) 写入 MQL5\Experts\GoldPullback.mq5 和 MQL5\Presets\GoldPullback_all_0.02.set
#   3) 用 MetaEditor 编译,打印编译结果
# 用法:双击同目录的 install_gold_pullback.bat
#   或:powershell -ExecutionPolicy Bypass -File install_gold_pullback.ps1
# 由 make_gold_installer.py 生成,别手改。

$ErrorActionPreference = "Stop"

$ea = @'
//+------------------------------------------------------------------+
//|                                                GoldPullback.mq5  |
//|        XAUUSD 顺势回调K线 EA（MQL5 / MetaTrader 5）               |
//+------------------------------------------------------------------+
//
//  思路(老交易员的做法:少出手,只做看得懂的那一种):
//    1) 先看大周期定方向,逆势单一律不做
//    2) 等价格回调到均线价值区(EMA20~EMA50),不追高、不杀跌
//    3) 回调末端出现"拒绝K线"(长下影 pin bar / 吞没)才算确认
//    4) 在确认K线的高点上方挂突破单:价格自己走回原方向才成交,不对就不进
//    5) 止损放在回调低点下方(结构失效位),止盈按 RR,到 1R 移保本
//    6) 大周期均线缠在一起(横盘)不做;超过 12 小时没走完就平掉
//    (每日笔数上限 / 亏一笔收工 / 交易时段 都做成了可选,默认关 —— 研究显示它们砍掉的多是好单)
//
//  规则与 gold_pullback_research.py 一一对应,改一边就要改另一边。
//
//  ── 研究结果(reports/gold_pullback.md,GC=F H1 两年,实话) ─────────
//  带纪律的两轮 40 组参数,训练期(2024-11~2025-12)没有一组是正期望。
//  去掉纪律(不限笔数 / 不因亏损收工 / 24 小时)后,再做第 3 轮 range 稳健性:
//  每个参数在附近试几档,只用训练期、选"高原中间"的值(不选孤立尖峰),加横盘过滤。默认这组:
//    只做多 · 突破确认K线高点进场 · 结构外 0.5ATR 止损 · RR 2.5 · 0.75R 保本 · 12 小时平
//    训练 65 笔 +0.35R/笔 · 验证 31 笔 +0.10R/笔 · 最长连亏 4 笔 —— 两边为正,
//    训练的提升大多是调参本身带来的,验证只从 +0.08 到 +0.10。先模拟盘跑满 30 笔。
//  0.02 手下止损中位数约 $24 金价 = 风险约 $48/笔;InpMaxRiskUSD 会跳过超过上限的单
//  (回测没有这条上限,设 0 = 与回测一致)。
//
//  每笔单子进场时止损止盈都跟单一起提交给服务器 ——
//  EA 停了、终端关了,止损依然在券商那边。无马丁、无网格、无加仓。
//
//  免责:研究/学习用途,不构成投资建议。黄金杠杆交易可能损失全部本金。
//+------------------------------------------------------------------+
#property copyright "ai4trade-bot"
#property version   "1.00"
#property description "XAUUSD 顺势回调K线:大周期定方向,回调到EMA区出现pin bar/吞没后挂突破单,结构止损,1R保本"

#include <Trade/Trade.mqh>

//--- 参数 ----------------------------------------------------------
input group "=== 仓位 ==="
input double InpLots             = 0.02;   // 固定手数
input double InpMaxRiskUSD       = 60.0;   // 单笔最大亏损($),止损算出来超过就不做(0=不限)

input group "=== 周期 ==="
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_H1;   // 执行周期(找回调K线)
input ENUM_TIMEFRAMES InpTrendTF   = PERIOD_H4;   // 方向周期(比执行周期大)

input group "=== 方向(大周期) ==="
input bool   InpAllowBuy         = true;   // 允许做多
input bool   InpAllowSell        = false;  // 允许做空(研究里空单样本太少,默认关)
input int    InpHTFFastEMA       = 50;
input int    InpHTFSlowEMA       = 200;
input double InpRangeFilterATR   = 0.5;    // 横盘过滤:大周期 EMA50 与 EMA200 至少分开 N×大周期ATR(0=关)

input group "=== 回调K线 ==="
input int    InpFastEMA          = 20;     // 价值区上沿
input int    InpMidEMA           = 50;     // 价值区下沿(结构)
input int    InpATRPeriod        = 14;
input double InpPullbackDepthATR = 1.0;    // 回调深度至少几个 ATR(过滤横盘)
input int    InpSwingLookback    = 12;     // 在前几根里找波段高/低点
input int    InpPullbackBars     = 3;      // 回调低点取最近几根
input double InpTouchBufATR      = 0.25;   // 回调要碰到 EMA20 ± 这么多 ATR
input double InpZoneBelowATR     = 0.3;    // 不能跌破 EMA50 超过这么多 ATR
input int    InpMinCounterBars   = 2;      // 前 N 根里至少几根是逆向K线(真回调)
input int    InpCounterLook      = 4;
input double InpClosePos         = 0.6;    // 确认K线收在全长的 60% 以上位置
input double InpWickMin          = 0.4;    // pin bar 影线至少占全长 40%
input double InpMaxRangeATR      = 2.5;    // 确认K线太大(新闻K)不追

input group "=== 进场与出场 ==="
input bool   InpUseStopEntry     = true;   // true=高点上方挂突破单 false=确认K线收盘后市价进
input double InpTrigBufATR       = 0.05;   // 突破单离确认K线高/低点的距离(ATR)
input int    InpPendingBars      = 2;      // 挂单几根K线内不成交就撤
input double InpSLBufATR         = 0.5;    // 止损放在回调低点外这么多 ATR
input double InpMinStopATR       = 1.0;    // 止损最小距离(ATR)
input double InpMaxStopATR       = 2.5;    // 止损超过这么多 ATR 就放弃这笔
input double InpRewardRisk       = 2.5;    // 止盈 = 止损距离 × RR
input double InpBreakevenR       = 0.75;   // 浮盈到几 R 移保本(0=关闭)
input double InpBELockR          = 0.1;    // 保本时多锁几 R(覆盖点差)
input int    InpMaxHoldHours     = 12;     // 持仓超过几小时就平(0=关闭)

input group "=== 纪律 ==="
input int    InpMaxTradesPerDay  = 0;      // 每天最多几笔(0=不限)
input int    InpMaxLossesPerDay  = 0;      // 当天亏几笔就收工(0=不限)
input double InpMaxSpreadUSD     = 0.50;   // 点差超过就不下单($)
input bool   InpUseSession       = false;  // false=24小时都可以开单
input int    InpSessionStartUTC  = 7;      // 只在 UTC 这个时段内开新单(伦敦+纽约上午)
input int    InpSessionEndUTC    = 17;
input int    InpTesterGMTOffset  = 3;      // 仅策略测试器用:服务器时区(OANDA 夏令=3,冬令=2)
input int    InpSlippagePoints   = 30;

input group "=== 其他 ==="
input long   InpMagic            = 20260924;
input bool   InpAlerts           = true;

//--- 全局 ----------------------------------------------------------
CTrade   trade;
int      hFast = INVALID_HANDLE, hMid = INVALID_HANDLE, hATR = INVALID_HANDLE;
int      hHTFFast = INVALID_HANDLE, hHTFSlow = INVALID_HANDLE, hHTFATR = INVALID_HANDLE;
datetime g_lastBar = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   if(PeriodSeconds(InpTrendTF) <= PeriodSeconds(InpTimeframe))
     {
      Print("参数错误:方向周期必须比执行周期大(例如 H1 执行 + H4 定方向)");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpLots <= 0 || InpRewardRisk <= 0 || InpMinStopATR <= 0 || InpMaxStopATR <= InpMinStopATR)
     {
      Print("参数错误:检查手数 / RR / 止损范围");
      return(INIT_PARAMETERS_INCORRECT);
     }

   hFast    = iMA(_Symbol, InpTimeframe, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   hMid     = iMA(_Symbol, InpTimeframe, InpMidEMA,  0, MODE_EMA, PRICE_CLOSE);
   hATR     = iATR(_Symbol, InpTimeframe, InpATRPeriod);
   hHTFFast = iMA(_Symbol, InpTrendTF, InpHTFFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   hHTFSlow = iMA(_Symbol, InpTrendTF, InpHTFSlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   hHTFATR  = iATR(_Symbol, InpTrendTF, InpATRPeriod);
   if(hFast == INVALID_HANDLE || hMid == INVALID_HANDLE || hATR == INVALID_HANDLE ||
      hHTFFast == INVALID_HANDLE || hHTFSlow == INVALID_HANDLE || hHTFATR == INVALID_HANDLE)
     {
      Print("指标句柄创建失败");
      return(INIT_FAILED);
     }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   PrintFormat("GoldPullback 启动 | %s 执行=%s 方向=%s | %.3f手 | RR 1:%.1f | 服务器时区 UTC%+d",
               _Symbol, EnumToString(InpTimeframe), EnumToString(InpTrendTF),
               InpLots, InpRewardRisk, ServerGMTOffset());
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(hFast    != INVALID_HANDLE) IndicatorRelease(hFast);
   if(hMid     != INVALID_HANDLE) IndicatorRelease(hMid);
   if(hATR     != INVALID_HANDLE) IndicatorRelease(hATR);
   if(hHTFFast != INVALID_HANDLE) IndicatorRelease(hHTFFast);
   if(hHTFSlow != INVALID_HANDLE) IndicatorRelease(hHTFSlow);
   if(hHTFATR  != INVALID_HANDLE) IndicatorRelease(hHTFATR);
   Comment("");
  }

//+------------------------------------------------------------------+
//| 工具                                                              |
//+------------------------------------------------------------------+
int ServerGMTOffset()
  {
   if(MQLInfoInteger(MQL_TESTER))
      return(InpTesterGMTOffset);
   return((int)MathRound((double)(TimeTradeServer() - TimeGMT()) / 3600.0));
  }

int UTCHour()
  {
   MqlDateTime dt;
   TimeToStruct(TimeCurrent() - ServerGMTOffset() * 3600, dt);
   return(dt.hour);
  }

bool InSession()
  {
   if(!InpUseSession)
      return(true);
   int h = UTCHour();
   if(InpSessionStartUTC <= InpSessionEndUTC)
      return(h >= InpSessionStartUTC && h < InpSessionEndUTC);
   return(h >= InpSessionStartUTC || h < InpSessionEndUTC);
  }

double Buf1(const int handle, const int shift)
  {
   double v[];
   if(CopyBuffer(handle, 0, shift, 1, v) != 1)
      return(EMPTY_VALUE);
   return(v[0]);
  }

double MoneyForDistance(const double dist)
  {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tv <= 0 || ts <= 0)
      return(0.0);
   return(dist / ts * tv * InpLots);
  }

string Alert2(const string msg)
  {
   Print(msg);
   if(InpAlerts && !MQLInfoInteger(MQL_TESTER))
     {
      Alert(msg);
      SendNotification(msg);
     }
   return(msg);
  }

// 大周期方向:+1 多 / -1 空 / 0 不明或横盘(只用已收盘K线)
int TrendDir()
  {
   double f[], s[];
   ArraySetAsSeries(f, true);
   ArraySetAsSeries(s, true);
   if(CopyBuffer(hHTFFast, 0, 1, 4, f) != 4 || CopyBuffer(hHTFSlow, 0, 1, 1, s) != 1)
      return(0);
   if(InpRangeFilterATR > 0)
     {
      double a = Buf1(hHTFATR, 1);
      if(a == EMPTY_VALUE || a <= 0 || MathAbs(f[0] - s[0]) < InpRangeFilterATR * a)
         return(0);   // 两条均线缠在一起 = 横盘,不做
     }
   if(f[0] > s[0] && f[0] > f[3])
      return(1);
   if(f[0] < s[0] && f[0] < f[3])
      return(-1);
   return(0);
  }

//+------------------------------------------------------------------+
//| 本 EA 的持仓 / 挂单                                                |
//+------------------------------------------------------------------+
bool MyPosition(ulong &ticket)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionSelectByTicket(t) &&
         PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
        { ticket = t; return(true); }
     }
   return(false);
  }

bool MyPending(ulong &ticket)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t > 0 && OrderSelect(t) &&
         OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic)
        { ticket = t; return(true); }
     }
   return(false);
  }

// 今天(服务器日)开了几笔、亏了几笔、盈亏多少
void TodayStats(int &opened, int &losses, double &pnl)
  {
   opened = 0; losses = 0; pnl = 0.0;
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   if(!HistorySelect(StructToTime(dt), TimeCurrent() + 60))
      return;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol ||
         HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)
         continue;
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e == DEAL_ENTRY_IN)
         opened++;
      else if(e == DEAL_ENTRY_OUT)
        {
         double p = HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_SWAP) +
                    HistoryDealGetDouble(d, DEAL_COMMISSION);
         pnl += p;
         if(p < 0)
            losses++;
        }
     }
  }

//+------------------------------------------------------------------+
//| 每个 tick:保本 / 挂单失效                                         |
//+------------------------------------------------------------------+
void ManageBreakeven(const ulong ticket)
  {
   if(InpBreakevenR <= 0 || !PositionSelectByTicket(ticket))
      return;
   long   type = PositionGetInteger(POSITION_TYPE);
   double open = PositionGetDouble(POSITION_PRICE_OPEN);
   double sl   = PositionGetDouble(POSITION_SL);
   double tp   = PositionGetDouble(POSITION_TP);
   if(tp <= 0 || sl <= 0)
      return;
   double dist = MathAbs(tp - open) / InpRewardRisk;   // 原始 1R
   if(dist <= 0)
      return;

   if(type == POSITION_TYPE_BUY)
     {
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double be  = NormalizeDouble(open + InpBELockR * dist, _Digits);
      if(sl < be && bid - open >= InpBreakevenR * dist && be < bid)
         if(trade.PositionModify(ticket, be, tp))
            PrintFormat("[保本] #%I64u 浮盈 %.1fR,止损移到 %.2f", ticket, (bid - open) / dist, be);
     }
   else
     {
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double be  = NormalizeDouble(open - InpBELockR * dist, _Digits);
      if(sl > be && open - ask >= InpBreakevenR * dist && be > ask)
         if(trade.PositionModify(ticket, be, tp))
            PrintFormat("[保本] #%I64u 浮盈 %.1fR,止损移到 %.2f", ticket, (open - ask) / dist, be);
     }
  }

void ManagePending(const ulong ticket, const bool newBar)
  {
   if(!OrderSelect(ticket))
      return;
   long   type = OrderGetInteger(ORDER_TYPE);
   double sl   = OrderGetDouble(ORDER_SL);
   bool   kill = false;
   string why  = "";
   // 还没成交价格就已经打到止损位 -> 回调结构坏了,撤
   if(type == ORDER_TYPE_BUY_STOP && SymbolInfoDouble(_Symbol, SYMBOL_BID) <= sl)
     { kill = true; why = "价格先跌破止损位,结构失效"; }
   if(type == ORDER_TYPE_SELL_STOP && SymbolInfoDouble(_Symbol, SYMBOL_ASK) >= sl)
     { kill = true; why = "价格先涨破止损位,结构失效"; }
   if(!kill && newBar)
     {
      datetime setup = (datetime)OrderGetInteger(ORDER_TIME_SETUP);
      if(iBarShift(_Symbol, InpTimeframe, setup, false) >= InpPendingBars)
        { kill = true; why = StringFormat("%d 根K线内没突破", InpPendingBars); }
     }
   if(kill && trade.OrderDelete(ticket))
      PrintFormat("[撤单] #%I64u %s", ticket, why);
  }

//+------------------------------------------------------------------+
//| 回调K线信号(bar 1 = 刚收盘的确认K线)                              |
//| 返回 +1/-1/0;sl = 结构止损价;ext = 确认K线高点(多)/低点(空)       |
//+------------------------------------------------------------------+
int Signal(double &sl, double &ext, double &atr, string &desc)
  {
   int dir = TrendDir();
   if(dir == 0 || (dir > 0 && !InpAllowBuy) || (dir < 0 && !InpAllowSell))
      return(0);

   int need = MathMax(InpSwingLookback, InpCounterLook) + 2;
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, InpTimeframe, 1, need, r) != need)
      return(0);
   double ef = Buf1(hFast, 1), em = Buf1(hMid, 1);
   atr = Buf1(hATR, 1);
   if(ef == EMPTY_VALUE || em == EMPTY_VALUE || atr == EMPTY_VALUE || atr <= 0)
      return(0);

   double rng = r[0].high - r[0].low;
   if(rng <= 0 || rng > InpMaxRangeATR * atr)
      return(0);

   // r[0]=确认K线, r[1..]=更早
   double lo = r[0].low, hi = r[0].high;
   for(int k = 1; k < InpPullbackBars; k++)
     { lo = MathMin(lo, r[k].low); hi = MathMax(hi, r[k].high); }
   double swingHi = r[1].high, swingLo = r[1].low;
   for(int k = 1; k <= InpSwingLookback; k++)
     { swingHi = MathMax(swingHi, r[k].high); swingLo = MathMin(swingLo, r[k].low); }
   int bear = 0, bull = 0;
   for(int k = 1; k <= InpCounterLook; k++)
     {
      if(r[k].close < r[k].open) bear++;
      if(r[k].close > r[k].open) bull++;
     }

   if(dir > 0)
     {
      if(!(ef > em)) return(0);
      if(swingHi - lo < InpPullbackDepthATR * atr) return(0);
      if(!(lo <= ef + InpTouchBufATR * atr && lo >= em - InpZoneBelowATR * atr)) return(0);
      if(bear < InpMinCounterBars) return(0);
      if(!(r[0].close > r[0].open && r[0].close > ef && (r[0].close - r[0].low) / rng >= InpClosePos)) return(0);
      bool pin    = (MathMin(r[0].open, r[0].close) - r[0].low) / rng >= InpWickMin;
      bool engulf = r[1].close < r[1].open && r[0].close >= r[1].open && r[0].open <= r[1].close;
      if(!(pin || engulf)) return(0);
      sl  = lo - InpSLBufATR * atr;
      ext = r[0].high;
      desc = StringFormat("多 | 回调 %.1fATR 到EMA%d | %s", (swingHi - lo) / atr, InpFastEMA,
                          pin ? "下影pin bar" : "看涨吞没");
      return(1);
     }
   else
     {
      if(!(ef < em)) return(0);
      if(hi - swingLo < InpPullbackDepthATR * atr) return(0);
      if(!(hi >= ef - InpTouchBufATR * atr && hi <= em + InpZoneBelowATR * atr)) return(0);
      if(bull < InpMinCounterBars) return(0);
      if(!(r[0].close < r[0].open && r[0].close < ef && (r[0].high - r[0].close) / rng >= InpClosePos)) return(0);
      bool pin    = (r[0].high - MathMax(r[0].open, r[0].close)) / rng >= InpWickMin;
      bool engulf = r[1].close > r[1].open && r[0].close <= r[1].open && r[0].open >= r[1].close;
      if(!(pin || engulf)) return(0);
      sl  = hi + InpSLBufATR * atr;
      ext = r[0].low;
      desc = StringFormat("空 | 反弹 %.1fATR 到EMA%d | %s", (hi - swingLo) / atr, InpFastEMA,
                          pin ? "上影pin bar" : "看跌吞没");
      return(-1);
     }
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   ulong pos = 0, pend = 0;
   bool  hasPos  = MyPosition(pos);
   bool  hasPend = MyPending(pend);

   datetime bar    = iTime(_Symbol, InpTimeframe, 0);
   bool     newBar = (bar != 0 && bar != g_lastBar);

   if(hasPos)
      ManageBreakeven(pos);
   if(hasPend)
      ManagePending(pend, newBar);
   if(!newBar)
      return;
   if(Bars(_Symbol, InpTrendTF) < InpHTFSlowEMA + 10 || Bars(_Symbol, InpTimeframe) < InpMidEMA + 20)
      return;
   g_lastBar = bar;

   //--- 超时平仓
   if(hasPos && InpMaxHoldHours > 0 && PositionSelectByTicket(pos))
     {
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      if(TimeCurrent() - opened >= InpMaxHoldHours * 3600)
        {
         if(trade.PositionClose(pos))
           {
            Alert2(StringFormat("GoldPullback [平仓] #%I64u 持仓超过 %d 小时", pos, InpMaxHoldHours));
            hasPos = false;
           }
        }
     }
   hasPend = MyPending(pend);

   //--- 状态
   int    opened, losses;
   double pnl;
   TodayStats(opened, losses, pnl);
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int    tdir   = TrendDir();
   bool   sess   = InSession();
   Comment(StringFormat("GoldPullback %s  执行%s / 方向%s\n大周期方向: %s\n时段(UTC %02d-%02d): %s  点差 $%.2f\n今日 %d 笔 / 亏 %d 笔 / 盈亏 %.2f\n%s",
                        _Symbol, EnumToString(InpTimeframe), EnumToString(InpTrendTF),
                        tdir > 0 ? "多头 ↑" : (tdir < 0 ? "空头 ↓" : "不明/横盘,不做"),
                        InpSessionStartUTC, InpSessionEndUTC, sess ? "开" : "关", spread,
                        opened, losses, pnl,
                        hasPos ? "持仓中" : (hasPend ? "挂单等突破" : "等回调K线")));

   //--- 开新单的条件
   if(hasPos || hasPend)
      return;
   if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
      return;
   if(!sess)
      return;
   if(InpMaxTradesPerDay > 0 && opened >= InpMaxTradesPerDay)
      return;
   if(InpMaxLossesPerDay > 0 && losses >= InpMaxLossesPerDay)
      return;

   double sl, ext, atr;
   string desc;
   int dir = Signal(sl, ext, atr, desc);
   if(dir == 0)
      return;

   if(spread > InpMaxSpreadUSD)
     {
      PrintFormat("[跳过] %s,但点差 $%.2f > $%.2f", desc, spread, InpMaxSpreadUSD);
      return;
     }

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ref = InpUseStopEntry ? ext + InpTrigBufATR * atr * dir : (dir > 0 ? ask : bid);
   double dist = MathAbs(ref - sl);
   if(dist < InpMinStopATR * atr)
     {
      dist = InpMinStopATR * atr;
      sl   = ref - dist * dir;
     }
   if(dist > InpMaxStopATR * atr)
     {
      PrintFormat("[跳过] %s,止损 $%.2f 超过 %.1fATR", desc, dist, InpMaxStopATR);
      return;
     }
   double risk = MoneyForDistance(dist);
   if(InpMaxRiskUSD > 0 && risk > InpMaxRiskUSD)
     {
      PrintFormat("[跳过] %s,止损 $%.2f → 风险 $%.2f 超过上限 $%.2f", desc, dist, risk, InpMaxRiskUSD);
      return;
     }

   ref = NormalizeDouble(ref, _Digits);
   sl  = NormalizeDouble(sl, _Digits);
   double tp = NormalizeDouble(ref + dist * InpRewardRisk * dir, _Digits);
   double minGap = (SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) + 1) * _Point;
   bool ok = false;

   if(InpUseStopEntry)
     {
      // 价格已经越过突破位:不追,等下一个
      if((dir > 0 && ref <= ask + minGap) || (dir < 0 && ref >= bid - minGap))
        {
         PrintFormat("[跳过] %s,价格已越过突破位 %.2f,不追", desc, ref);
         return;
        }
      ok = (dir > 0) ? trade.BuyStop(InpLots, ref, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "GoldPullback")
                     : trade.SellStop(InpLots, ref, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "GoldPullback");
     }
   else
     {
      ok = (dir > 0) ? trade.Buy(InpLots, _Symbol, ask, sl, tp, "GoldPullback")
                     : trade.Sell(InpLots, _Symbol, bid, sl, tp, "GoldPullback");
     }

   string msg = StringFormat("GoldPullback [%s] %s | %s %.3f手 @%.2f SL %.2f TP %.2f | 风险 $%.2f | RR 1:%.1f",
                             ok ? (InpUseStopEntry ? "挂单" : "进场") : "下单失败",
                             desc, dir > 0 ? "BUY" : "SELL", InpLots, ref, sl, tp, risk, InpRewardRisk);
   if(!ok)
      msg += StringFormat(" | retcode=%d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
   Alert2(msg);
  }
//+------------------------------------------------------------------+
'@

$preset = @'
; GoldPullback —— 合成版 · 0.02 手 · 去掉纪律 · range 设定稳健版(第 3 轮)
; H1 找回调K线 + H4 定方向 · 只做多 · 大周期均线缠在一起(横盘)不做
; 在确认K线高点上方挂突破单 · 止损在回调低点外 0.5ATR · RR1:2.5 · 0.75R 移保本 · 12 小时平
; 每个 range 参数都在附近几档里选"高原中间"(只看训练期),不选孤立尖峰
; 回测(reports/gold_pullback.md,GC=F H1 两年):训练 65 笔 +0.35R/笔,验证 31 笔 +0.10R/笔,最长连亏 4 笔
;   训练的提升大多来自调参本身,验证只从 +0.08 到 +0.10 —— 先模拟盘跑满 30 笔再谈实盘
; 保留的保护:止损止盈随单提交、点差 > $0.50 不下单、单笔风险 > $60 跳过(设 0 = 与回测一致)
InpLots=0.02
InpMaxRiskUSD=60.0
InpTimeframe=16385
InpTrendTF=16388
InpAllowBuy=true
InpAllowSell=false
InpHTFFastEMA=50
InpHTFSlowEMA=200
InpRangeFilterATR=0.5
InpFastEMA=20
InpMidEMA=50
InpATRPeriod=14
InpPullbackDepthATR=1.0
InpSwingLookback=12
InpPullbackBars=3
InpTouchBufATR=0.25
InpZoneBelowATR=0.3
InpMinCounterBars=2
InpCounterLook=4
InpClosePos=0.6
InpWickMin=0.4
InpMaxRangeATR=2.5
InpUseStopEntry=true
InpTrigBufATR=0.05
InpPendingBars=2
InpSLBufATR=0.5
InpMinStopATR=1.0
InpMaxStopATR=2.5
InpRewardRisk=2.5
InpBreakevenR=0.75
InpBELockR=0.1
InpMaxHoldHours=12
InpMaxTradesPerDay=0
InpMaxLossesPerDay=0
InpMaxSpreadUSD=0.50
InpUseSession=false
InpSessionStartUTC=7
InpSessionEndUTC=17
InpTesterGMTOffset=3
InpSlippagePoints=30
InpMagic=20260924
InpAlerts=true
'@

$root = Join-Path $env:APPDATA "MetaQuotes\Terminal"
if (-not (Test-Path $root)) {
    Write-Host "没找到 MT5 数据目录:$root" -ForegroundColor Red
    Write-Host "请先在 MT5 里点 文件 -> 打开数据文件夹,确认 MT5 已安装并运行过一次。"
    exit 1
}

$utf8bom = New-Object System.Text.UTF8Encoding $true
$n = 0
Get-ChildItem $root -Directory | ForEach-Object {
    $mql = Join-Path $_.FullName "MQL5"
    if (-not (Test-Path $mql)) { return }
    $n++
    $experts = Join-Path $mql "Experts"
    $presets = Join-Path $mql "Presets"
    New-Item -ItemType Directory -Force -Path $experts, $presets | Out-Null

    $eaPath = Join-Path $experts "GoldPullback.mq5"
    $setPath = Join-Path $presets "GoldPullback_all_0.02.set"
    [System.IO.File]::WriteAllText($eaPath, $ea, $utf8bom)
    [System.IO.File]::WriteAllText($setPath, $preset, [System.Text.Encoding]::Unicode)

    $origin = Join-Path $_.FullName "origin.txt"
    $install = if (Test-Path $origin) { (Get-Content $origin -Raw).Trim() } else { "" }
    Write-Host ""
    Write-Host "== $install" -ForegroundColor Cyan
    Write-Host "   EA     -> $eaPath"
    Write-Host "   preset -> $setPath"

    $me = if ($install) { Join-Path $install "metaeditor64.exe" } else { "" }
    if ($me -and (Test-Path $me)) {
        $log = Join-Path $experts "GoldPullback.compile.log"
        & $me /compile:"$eaPath" /log:"$log" | Out-Null
        Start-Sleep -Seconds 2
        $ex5 = [System.IO.Path]::ChangeExtension($eaPath, ".ex5")
        if (Test-Path $ex5) {
            Write-Host "   编译成功 -> $ex5" -ForegroundColor Green
        } else {
            Write-Host "   编译失败,日志如下(截图发给 Claude):" -ForegroundColor Red
            if (Test-Path $log) { Get-Content $log | Select-String -Pattern "error|warning|result" }
        }
    } else {
        Write-Host "   没找到 metaeditor64.exe,请在 MetaEditor 里打开 GoldPullback.mq5 按 F7 编译" -ForegroundColor Yellow
    }
}

if ($n -eq 0) {
    Write-Host "Terminal 目录下没有 MQL5 文件夹,MT5 可能还没运行过。" -ForegroundColor Red
    exit 1
}
Write-Host ""
Write-Host "装好了。接下来在 MT5:" -ForegroundColor Green
Write-Host "  1) 导航器(Ctrl+N)-> EA交易 -> 右键 刷新"
Write-Host "  2) 把 GoldPullback 拖到 XAUUSD 图表(任意周期都行,EA 自己用 H1/H4)"
Write-Host "  3) 输入 -> 加载 -> 选 GoldPullback_all_0.02.set -> 勾允许算法交易 -> 确定"
