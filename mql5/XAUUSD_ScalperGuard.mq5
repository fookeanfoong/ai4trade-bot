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
#property version   "1.00"
#property strict

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
input double   InpRiskPctDefault     = 1.0;     // 默认单笔风险 %（账户余额）
input double   InpRiskPctMax         = 2.0;     // 单笔风险上限 %（仅最高质量信号）
input double   InpDailyProfitTarget  = 50.0;    // 每日盈利目标 USD -> 停止交易
input double   InpDailyMaxLoss       = 15.0;    // 每日最大亏损 USD -> 停止交易
input double   InpConservativeAt     = 20.0;    // 当日盈利达到该值 -> 保守模式
input double   InpReducedAt          = 30.0;    // 当日盈利达到该值 -> 进一步收紧
input int      InpMaxTradesPerDay    = 10;      // 每日最大交易笔数
input int      InpStopAfterConsecLoss= 3;       // 连亏 N 笔 -> 当天停止
input int      InpObserveAfterConsecLoss = 2;   // 连亏 N 笔 -> 观察模式
input double   InpMaxMarginPctPerPos = 35.0;    // 单仓占用保证金上限（占可用保证金 %）
input bool     InpUseFloatingInLimits= true;    // 日盈亏统计是否包含浮动盈亏
input bool     InpSmallAccountEscalate = true;  // 小账户救济：最小手开不了时，把风险上调至 InpRiskPctMax

input group "=== 交易时段 / 点差 / 流动性 ==="
input int      InpSessionStartHour   = 8;       // 交易时段开始（服务器时间，小时）
input int      InpSessionEndHour     = 21;      // 交易时段结束（服务器时间，小时）
input int      InpFlatAllBeforeHour  = 22;      // 该小时后强制清仓（服务器时间）
input double   InpMaxSpreadUSD       = 0.35;    // 最大允许点差（美元，黄金）
input double   InpSpreadVsATRMax     = 0.12;    // 点差 / ATR 上限（点差异常过滤）

input group "=== 信号 / 结构 ==="
input ENUM_TIMEFRAMES InpHTF         = PERIOD_H1;  // 高时间周期（趋势）
input ENUM_TIMEFRAMES InpLTF         = PERIOD_M5;  // 交易时间周期
input int      InpEmaFastHTF         = 50;      // HTF 快线 EMA
input int      InpEmaSlowHTF         = 200;     // HTF 慢线 EMA
input int      InpEmaFastLTF         = 20;      // LTF 快线 EMA
input int      InpEmaSlowLTF         = 50;      // LTF 慢线 EMA
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

input group "=== 止损 / 止盈 ==="
input double   InpSlAtrMult          = 1.2;     // 止损 = swing 之外 + ATR * 该系数
input double   InpSlMinUSD           = 1.20;    // 最小止损距离（美元）
input double   InpSlMaxUSD           = 6.00;    // 最大止损距离（美元）
input double   InpMinRR              = 1.5;     // 最低风险回报比（到下一个关键位）
input double   InpTP1_R              = 1.0;     // TP1 = 1R
input double   InpTP2_R              = 1.8;     // TP2 = 1.8R
input double   InpPartialClosePct    = 50.0;    // TP1 平仓比例 %
input double   InpBreakevenBufferATR = 0.05;    // 保本止损缓冲（ATR 倍数）
input double   InpTrailATRMult       = 1.0;     // TP1 后 ATR 追踪止损系数
input int      InpMaxHoldMinutes     = 120;     // 单笔最长持仓分钟数（短线）
input bool     InpExitOnMomentumFade = true;    // 动量衰竭提前离场

input group "=== 新闻过滤 ==="
input bool     InpUseNewsFilter      = true;    // 启用经济日历过滤
input int      InpNewsBeforeMin      = 30;      // 数据公布前 N 分钟禁止开仓
input int      InpNewsAfterMin       = 20;      // 数据公布后 N 分钟禁止开仓
input bool     InpNewsHighOnly       = true;    // 仅过滤高重要性事件
input string   InpManualNewsTimes    = "";      // 手动黑名单时间 "HH:MM,HH:MM"（服务器时间）

input group "=== 加仓（默认关闭）==="
input bool     InpAllowAddOn         = false;   // 允许加仓（必须满足全部条件）

//==================================================================
// 全局
//==================================================================
CTrade        trade;
CPositionInfo pos;

int hEmaFastH, hEmaSlowH;      // HTF EMA
int hEmaFastL, hEmaSlowL;      // LTF EMA
int hAtrL, hRsiL, hAdxL;       // LTF 指标

datetime g_lastBarTime   = 0;
datetime g_dayStart      = 0;
string   g_lastNoTradeReason = "";
datetime g_lastReasonLog = 0;
string   g_logFile       = "XAUUSD_ScalperGuard_log.csv";
bool     g_dayHaltLogged = false;

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
   int      score;       // 确认分
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

datetime DayStart(datetime t)
{
   MqlDateTime st; TimeToStruct(t, st);
   st.hour = 0; st.min = 0; st.sec = 0;
   return StructToTime(st);
}

void LogLine(string tag, string msg)
{
   if(InpVerboseLog)
   {
      int h = FileOpen(g_logFile, FILE_READ|FILE_WRITE|FILE_CSV|FILE_ANSI, ',');
      if(h != INVALID_HANDLE)
      {
         FileSeek(h, 0, SEEK_END);
         FileWrite(h, TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), tag, msg);
         FileClose(h);
      }
   }
   Print("[", tag, "] ", msg);
}

// NO-TRADE 原因去重，避免刷屏
void NoTrade(string reason)
{
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
      if(trade.PositionClose(tk))
         LogLine("CLOSE", StringFormat("#%I64u 平仓：%s", tk, reason));
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

bool SpreadOk(double atr, string &why)
{
   double sp = SpreadUSD();
   if(sp > InpMaxSpreadUSD)
   { why = StringFormat("点差过大 %.2f > %.2f", sp, InpMaxSpreadUSD); return false; }
   if(atr > 0.0 && sp / atr > InpSpreadVsATRMax)
   { why = StringFormat("点差/ATR 异常 %.3f", sp / atr); return false; }
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

bool NewsBlocked(string &why)
{
   if(!InpUseNewsFilter) return false;

   if(ManualNewsBlocked()) { why = "手动新闻黑名单时间窗口内"; return true; }

   // 经济日历在策略测试器中不可用
   if(MQLInfoInteger(MQL_TESTER)) return false;

   datetime from = TimeCurrent() - InpNewsAfterMin  * 60;
   datetime to   = TimeCurrent() + InpNewsBeforeMin * 60;

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
         why = StringFormat("重大数据窗口：%s (%s) @ %s", ev.name, curr[c],
                            TimeToString(vals[i].time, TIME_MINUTES));
         return true;
      }
   }
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
   if(range < 2.5 * atr)
   {
      why = StringFormat("横盘：%d 根 K 线区间仅 %.2f (< 2.5×ATR)", lookback, range);
      return false;
   }
   if(smallBody > lookback * 0.7)
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
   if(fakes >= 5)
   {
      why = StringFormat("高频假突破：近 25 根内出现 %d 次失败突破", fakes);
      return false;
   }

   return true;
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
bool NearestResistance(double price, double &lvl)
{
   bool found = false; double best = 0.0;
   int str = InpSwingStrength + 1;
   int maxShift = InpStructureLookback * 2;
   for(int i = 1 + str; i < maxShift; i++)
   {
      double h = iHigh(_Symbol, InpLTF, i);
      if(h <= price + _Point) continue;
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
bool NearestSupport(double price, double &lvl)
{
   bool found = false; double best = 0.0;
   int str = InpSwingStrength + 1;
   int maxShift = InpStructureLookback * 2;
   for(int i = 1 + str; i < maxShift; i++)
   {
      double l = iLow(_Symbol, InpLTF, i);
      if(l >= price - _Point) continue;
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
int HtfTrend()
{
   double f = Buf(hEmaFastH, 0, 1);
   double s = Buf(hEmaSlowH, 0, 1);
   double fPrev = Buf(hEmaFastH, 0, 4);
   double c = iClose(_Symbol, InpHTF, 1);
   if(f <= 0.0 || s <= 0.0) return 0;
   if(f > s && c > f && f > fPrev) return  1;
   if(f < s && c < f && f < fPrev) return -1;
   return 0;
}

// LTF 趋势
int LtfTrend()
{
   double f = Buf(hEmaFastL, 0, 1);
   double s = Buf(hEmaSlowL, 0, 1);
   double c = iClose(_Symbol, InpLTF, 1);
   if(f <= 0.0 || s <= 0.0) return 0;
   if(f > s && c > s) return  1;
   if(f < s && c < s) return -1;
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
      double h = iHigh(_Symbol, InpLTF, i);
      double l = iLow (_Symbol, InpLTF, i);
      double c = iClose(_Symbol, InpLTF, i);
      if(dir > 0 && h > level && c < level) return true;   // 上破失败
      if(dir < 0 && l < level && c > level) return true;   // 下破失败
   }
   return false;
}

// 长影线拒绝（做多时上影线过长 = 抛压）
bool WickRejection(int dir, int shift)
{
   double o = iOpen (_Symbol, InpLTF, shift);
   double h = iHigh (_Symbol, InpLTF, shift);
   double l = iLow  (_Symbol, InpLTF, shift);
   double c = iClose(_Symbol, InpLTF, shift);
   double rng = h - l;
   if(rng <= 0.0) return false;
   if(dir > 0) return ((h - MathMax(o, c)) / rng) > 0.55;
   else        return ((MathMin(o, c) - l) / rng) > 0.55;
}

// 触发条件：突破回踩 或 趋势回调确认
// 返回 true 并给出 note
bool EntryTrigger(int dir, double atr, double &refLevel, string &note)
{
   double swH, swL; int sH, sL;
   bool okH = FindSwingHigh(InpLTF, 1, InpStructureLookback, InpSwingStrength, swH, sH);
   bool okL = FindSwingLow (InpLTF, 1, InpStructureLookback, InpSwingStrength, swL, sL);

   double c1 = iClose(_Symbol, InpLTF, 1);
   double o1 = iOpen (_Symbol, InpLTF, 1);
   double h1 = iHigh (_Symbol, InpLTF, 1);
   double l1 = iLow  (_Symbol, InpLTF, 1);
   double ema20 = Buf(hEmaFastL, 0, 1);
   double tol   = 0.35 * atr;

   if(dir > 0)
   {
      if(!okH) return false;
      refLevel = swH;

      // A) 有效突破 + 回踩确认
      bool broke = false;
      for(int i = 1; i <= InpBreakoutLookback; i++)
         if(iClose(_Symbol, InpLTF, i) > swH + 0.10 * atr) { broke = true; break; }
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
         bool bull   = (c1 > o1) && ((c1 - l1) / MathMax(h1 - l1, _Point) > 0.55);
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
         if(iClose(_Symbol, InpLTF, i) < swL - 0.10 * atr) { broke = true; break; }
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
         bool bear   = (c1 < o1) && ((h1 - c1) / MathMax(h1 - l1, _Point) > 0.55);
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
// 构建信号
//==================================================================
Signal BuildSignal(double atr, int minScore)
{
   Signal sg;
   sg.dir = 0; sg.score = 0; sg.entry = 0; sg.sl = 0; sg.tp1 = 0; sg.tp2 = 0; sg.rr = 0; sg.note = "";

   int htf  = HtfTrend();
   int ltf  = LtfTrend();
   int strc = MarketStructure(InpLTF);
   int mom  = Momentum();
   double adx = Buf(hAdxL, 0, 1);

   // 多空信号冲突 -> NO TRADE
   int dir = 0;
   if(htf > 0 && ltf > 0) dir =  1;
   else if(htf < 0 && ltf < 0) dir = -1;
   else { NoTrade(StringFormat("趋势不一致 HTF=%d LTF=%d", htf, ltf)); return sg; }

   if(strc != 0 && strc != dir) { NoTrade("市场结构与趋势冲突"); return sg; }
   if(mom  != 0 && mom  != dir) { NoTrade("动量与趋势冲突");     return sg; }
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
   if(trig) score += 2;                           // 6-7 触发（突破回踩 / 回调确认）

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

   double swH, swL; int sH, sL;
   bool okH = FindSwingHigh(InpLTF, 1, InpStructureLookback, InpSwingStrength, swH, sH);
   bool okL = FindSwingLow (InpLTF, 1, InpStructureLookback, InpSwingStrength, swL, sL);
   if(!okH || !okL) { NoTrade("找不到有效 swing 结构"); return sg; }

   double sl;
   if(dir > 0) sl = MathMin(swL, iLow(_Symbol, InpLTF, 1)) - InpSlAtrMult * atr * 0.5;
   else        sl = MathMax(swH, iHigh(_Symbol, InpLTF, 1)) + InpSlAtrMult * atr * 0.5;

   double slDist = MathAbs(entry - sl);
   // 结构止损过近 -> 用 ATR 兜底；过远 -> 放弃（不是缩止损，而是不做）
   if(slDist < MathMax(InpSlMinUSD, StopsLevelUSD() + SpreadUSD()))
   {
      slDist = MathMax(InpSlMinUSD, MathMax(StopsLevelUSD() + SpreadUSD(), InpSlAtrMult * atr));
      sl = (dir > 0) ? entry - slDist : entry + slDist;
   }
   if(slDist > InpSlMaxUSD)
   {
      NoTrade(StringFormat("结构止损过宽 %.2f > %.2f USD", slDist, InpSlMaxUSD));
      return sg;
   }

   // --- 目标：受前方最近的关键位限制 ---
   double tp1 = (dir > 0) ? entry + InpTP1_R * slDist : entry - InpTP1_R * slDist;
   double tp2 = (dir > 0) ? entry + InpTP2_R * slDist : entry - InpTP2_R * slDist;

   double buffer = 0.15 * atr;
   double lvl = 0.0;
   if(dir > 0 && NearestResistance(entry, lvl) && (lvl - buffer) < tp2) tp2 = lvl - buffer;
   if(dir < 0 && NearestSupport   (entry, lvl) && (lvl + buffer) > tp2) tp2 = lvl + buffer;

   double rr = (tp2 - entry) * dir / MathMax(slDist, _Point);
   if(rr < InpMinRR)
   {
      NoTrade(StringFormat("风险回报不足 RR=%.2f < %.2f（前方关键位太近）", rr, InpMinRR));
      return sg;
   }

   sg.dir   = dir;
   sg.score = score;
   sg.entry = entry;
   sg.sl    = Px(sl);
   sg.tp1   = Px(tp1);
   sg.tp2   = Px(tp2);
   sg.rr    = rr;
   sg.note  = trigNote;
   return sg;
}

//==================================================================
// 仓位计算（严格按风险金额倒推，永不满仓）
//==================================================================
double CalcLot(double slDistUSD, double riskMoney, string &why)
{
   double mppd = MoneyPerLotPerDollar();       // 每手每 $1 金价波动的美元盈亏
   if(mppd <= 0.0) { why = "无法获取合约规格"; return 0.0; }

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

   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
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
   if(ds.consecLoss >= InpObserveAfterConsecLoss) return riskPct;   // 观察模式：不加码
   if(ds.total >= InpConservativeAt)              return riskPct;   // 已进盈利保护档

   double mppd   = MoneyPerLotPerDollar();
   double lotMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double bal    = AccountInfoDouble(ACCOUNT_BALANCE);
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
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * riskPct / 100.0;
   double slDist    = MathAbs(sg.entry - sg.sl);

   string why = "";
   double lot = CalcLot(slDist, riskMoney, why);
   if(lot <= 0.0) { NoTrade(why); return; }

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints((int)MathMax(10.0, SpreadUSD() / _Point));
   trade.SetTypeFillingBySymbol(_Symbol);

   bool ok;
   // 订单备注只用 ASCII（部分经纪商会截断/乱码中文），中文原因写进日志
   string comment = StringFormat("SG s%d rr%.1f", sg.score, sg.rr);
   if(sg.dir > 0) ok = trade.Buy (lot, _Symbol, 0.0, sg.sl, sg.tp2, comment);
   else           ok = trade.Sell(lot, _Symbol, 0.0, sg.sl, sg.tp2, comment);

   if(!ok)
   {
      LogLine("ERROR", StringFormat("下单失败 %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription()));
      return;
   }

   LogLine("OPEN", StringFormat("%s %.2f 手 @ %.2f | SL %.2f (%.2f USD) | TP %.2f | RR %.2f | 分数 %d | 风险 $%.2f (%.1f%%) | %s | 当日 %d/%d 笔，盈亏 $%.2f",
           sg.dir > 0 ? "BUY" : "SELL", lot, sg.entry, sg.sl, slDist, sg.tp2, sg.rr, sg.score,
           lot * slDist * MoneyPerLotPerDollar(), riskPct, sg.note,
           ds.trades + 1, InpMaxTradesPerDay, ds.total));

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

// 清理已平仓位留下的标记
void CleanFlags()
{
   int n = GlobalVariablesTotal();
   for(int i = n - 1; i >= 0; i--)
   {
      string nm = GlobalVariableName(i);
      bool isP = (StringFind(nm, "SG_P_") == 0);
      bool isR = (StringFind(nm, "SG_R_") == 0);
      if(!isP && !isR) continue;
      ulong tk = (ulong)StringToInteger(StringSubstr(nm, 5));
      if(!PositionSelectByTicket(tk)) GlobalVariableDel(nm);
   }
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
         trade.PositionClose(tk);
         continue;
      }

      // 初始 R 只在第一次记录，之后止损怎么移都不影响 R 的基准
      double R = InitialR(tk, MathAbs(open - sl));
      if(R <= 0.0) continue;
      double moved = isBuy ? (cur - open) : (open - cur);
      double rMult = moved / R;

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

      if(rMult >= InpTP1_R)
      {
         // 先保本（只往盈利方向移动）
         double be = isBuy ? open + InpBreakevenBufferATR * atr : open - InpBreakevenBufferATR * atr;
         bool needBE = isBuy ? (sl < be) : (sl > be);
         if(needBE && MathAbs(cur - be) > StopsLevelUSD() + _Point)
         {
            if(trade.PositionModify(tk, Px(be), tp))
            {
               sl = Px(be);        // 同步本地值，否则下面的追踪会拿旧止损比较，可能反而放宽
               LogLine("MANAGE", StringFormat("#%I64u 达到 %.2fR，止损移至保本 %.2f", tk, rMult, be));
            }
         }

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
      if(InpExitOnMomentumFade && rMult >= 0.45)
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

      // --- 逼近关键位且已有合理利润 -> 落袋 ---
      if(rMult >= 0.7)
      {
         double lv = 0.0;
         bool found = isBuy ? NearestResistance(cur, lv) : NearestSupport(cur, lv);
         if(found)
         {
            bool near = isBuy ? ((lv - cur) < 0.20 * atr) : ((cur - lv) < 0.20 * atr);
            if(near)
            {
               LogLine("EXIT", StringFormat("#%I64u 逼近关键位 %.2f，%.2fR 提前平仓", tk, lv, rMult));
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
// 面板
//==================================================================
void Panel(DayStats &ds, string status)
{
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   string mode = "正常";
   if(ds.total >= InpReducedAt)      mode = "收紧（只做最高质量）";
   else if(ds.total >= InpConservativeAt) mode = "保守";
   if(ds.consecLoss >= InpObserveAfterConsecLoss) mode += " + 观察模式";

   string txt = StringFormat(
      "===== XAUUSD ScalperGuard =====\n"
      "账户: %s  %s | 余额 $%.2f | 杠杆 1:%d\n"
      "当日盈亏: $%.2f (已实现 $%.2f / 浮动 $%.2f)\n"
      "目标 +$%.0f  |  上限 -$%.0f\n"
      "当日笔数: %d / %d   连亏: %d\n"
      "模式: %s\n"
      "点差: %.2f  ATR: %.2f\n"
      "状态: %s\n",
      AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : "REAL",
      _Symbol, bal, (int)AccountInfoInteger(ACCOUNT_LEVERAGE),
      ds.total, ds.realized, ds.floating,
      InpDailyProfitTarget, InpDailyMaxLoss,
      ds.trades, InpMaxTradesPerDay, ds.consecLoss,
      mode, SpreadUSD(), Buf(hAtrL, 0, 1), status);
   Comment(txt);
}

//==================================================================
// OnInit
//==================================================================
int OnInit()
{
   // --- Demo 闸门 ---
   long tmode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   bool isDemo = (tmode == ACCOUNT_TRADE_MODE_DEMO || tmode == ACCOUNT_TRADE_MODE_CONTEST);
   if(!isDemo && !InpAllowLiveAccount)
   {
      Alert("XAUUSD_ScalperGuard: 检测到真实账户。默认只允许 Demo 运行。"
            "确认要实盘请把 InpAllowLiveAccount 设为 true。");
      Print("拒绝启动：真实账户 + InpAllowLiveAccount=false");
      return INIT_FAILED;
   }

   if(StringFind(_Symbol, "XAU") < 0 && StringFind(_Symbol, "GOLD") < 0 && StringFind(_Symbol, "Gold") < 0)
      Print("警告：当前图表 ", _Symbol, " 看起来不是黄金。本 EA 为 XAUUSD 设计。");

   if(InpRiskPctDefault > InpRiskPctMax || InpRiskPctMax > 2.0)
   {
      Alert("风险参数非法：单笔风险上限不得超过 2%。");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(!AccountInfoInteger(ACCOUNT_TRADE_EXPERT))
   {
      Alert("账户不允许 EA 自动交易。");
      return INIT_FAILED;
   }

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

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetAsyncMode(false);

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
   if(InpDailyMaxLoss < risk1)
      LogLine("WARN", StringFormat(
         "配置错配：当日亏损上限 $%.2f 小于单笔 %.1f%% 风险 $%.2f。"
         "后果是每笔都被压到 %.3f%% 风险，且一笔亏损就触发当日停止 —— 一天基本只做一笔。"
         "两个解法：把演示账户余额调成你真实计划的规模；或把日内上限按比例改成 "
         "目标 +$%.0f / 上限 -$%.0f（即当前余额的 +25%% / -7.5%%，与 $200 账户的 +$50/-$15 同口径）。",
         InpDailyMaxLoss, InpRiskPctDefault, risk1,
         InpDailyMaxLoss / bal * 100.0, bal * 0.25, bal * 0.075));

   if(margin > bal * InpMaxMarginPctPerPos / 100.0)
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

   EventSetTimer(30);
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   IndicatorRelease(hEmaFastH); IndicatorRelease(hEmaSlowH);
   IndicatorRelease(hEmaFastL); IndicatorRelease(hEmaSlowL);
   IndicatorRelease(hAtrL); IndicatorRelease(hRsiL); IndicatorRelease(hAdxL);
   Comment("");
}

void OnTimer()
{
   CleanFlags();
   DayStats ds = GetDayStats();
   Panel(ds, g_lastNoTradeReason);
}

//==================================================================
// 主循环
//==================================================================
void OnTick()
{
   double atr = Buf(hAtrL, 0, 1);
   if(atr <= 0.0) return;

   DayStats ds = GetDayStats();

   // 跨日重置提示
   static datetime lastDay = 0;
   if(g_dayStart != lastDay)
   {
      lastDay = g_dayStart;
      g_dayHaltLogged = false;
      LogLine("DAY", StringFormat("新交易日 %s，余额 $%.2f",
              TimeToString(g_dayStart, TIME_DATE), AccountInfoDouble(ACCOUNT_BALANCE)));
   }

   //--------------------------------------------------------------
   // 1) 硬性日内停止：先于一切逻辑
   //--------------------------------------------------------------
   if(ds.total >= InpDailyProfitTarget)
   {
      if(HasOpenPosition()) CloseAll(StringFormat("达到当日目标 +$%.2f", ds.total));
      if(!g_dayHaltLogged)
      {
         LogLine("HALT", StringFormat("当日盈利 $%.2f >= 目标 $%.2f —— 停止交易，今天结束。",
                 ds.total, InpDailyProfitTarget));
         g_dayHaltLogged = true;
      }
      Panel(ds, "已达当日目标，停止交易");
      return;
   }

   if(ds.total <= -InpDailyMaxLoss)
   {
      if(HasOpenPosition()) CloseAll(StringFormat("触及当日最大亏损 $%.2f", ds.total));
      if(!g_dayHaltLogged)
      {
         LogLine("HALT", StringFormat("当日亏损 $%.2f <= -$%.2f —— 平仓并停止交易，今天结束。",
                 ds.total, InpDailyMaxLoss));
         g_dayHaltLogged = true;
      }
      Panel(ds, "触及当日亏损上限，停止交易");
      return;
   }

   //--------------------------------------------------------------
   // 2) 持仓管理（每 tick）
   //--------------------------------------------------------------
   ManagePositions(atr);

   //--------------------------------------------------------------
   // 3) 只在新 K 线上找入场
   //--------------------------------------------------------------
   if(!IsNewBar(InpLTF)) return;

   if(HasOpenPosition() && !InpAllowAddOn)
   {
      Panel(ds, "持仓中，等待管理（默认禁止加仓）");
      return;
   }

   // 连亏保护
   if(ds.consecLoss >= InpStopAfterConsecLoss)
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

   // 时段 / 点差 / 新闻
   string why = "";
   if(!SessionOk(why))      { NoTrade(why); Panel(ds, why); return; }
   if(!SpreadOk(atr, why))  { NoTrade(why); Panel(ds, why); return; }
   if(NewsBlocked(why))     { NoTrade(why); Panel(ds, why); return; }

   // 波动率
   if(atr < InpAtrMinUSD) { NoTrade(StringFormat("ATR %.2f 过低，波动不足", atr)); Panel(ds, "波动不足"); return; }
   if(atr > InpAtrMaxUSD) { NoTrade(StringFormat("ATR %.2f 过高，波动异常", atr)); Panel(ds, "波动异常"); return; }

   // 市场质量：横盘 / 高频假突破
   if(!MarketQualityOk(atr, why)) { NoTrade(why); Panel(ds, why); return; }

   //--------------------------------------------------------------
   // 4) 模式：盈利保护 + 观察模式
   //--------------------------------------------------------------
   int    minScore = InpMinScore;
   double riskPct  = InpRiskPctDefault;
   double minRRreq = InpMinRR;

   if(ds.consecLoss >= InpObserveAfterConsecLoss) { minScore += 1; riskPct = MathMin(riskPct, 1.0); }
   if(ds.total >= InpConservativeAt)              { minScore += 1; riskPct = MathMin(riskPct, 0.75); }
   if(ds.total >= InpReducedAt)                   { minScore  = 7; riskPct = MathMin(riskPct, 0.5); minRRreq = 2.0; }
   if(minScore > 7) minScore = 7;

   //--------------------------------------------------------------
   // 5) 信号
   //--------------------------------------------------------------
   Signal sg = BuildSignal(atr, minScore);
   if(sg.dir == 0) { Panel(ds, g_lastNoTradeReason); return; }
   if(sg.rr < minRRreq)
   {
      NoTrade(StringFormat("当前模式要求 RR >= %.2f，实际 %.2f", minRRreq, sg.rr));
      Panel(ds, "RR 不达标");
      return;
   }

   // 只有满分信号 + 正常模式，才允许提高到 2%
   if(sg.score >= 7 && ds.consecLoss == 0 && ds.total < InpConservativeAt)
      riskPct = MathMin(InpRiskPctMax, 2.0);

   // 小账户救济：最小手数在当前预算下开不了，但抬到 2% 上限就能开 -> 抬。
   // 放在这里而不是更后面，是为了让下面两道**降险**闸门（加仓预算、当日剩余亏损额度）
   // 依然能把它压回去 —— 上调只是解锁开仓，不是绕过任何一条上限。
   string escNote = "";
   riskPct = EscalateRiskForMinLot(MathAbs(sg.entry - sg.sl), riskPct, ds, escNote);
   if(StringLen(escNote) > 0) LogLine("RISK", escNote);

   // 加仓闸门：有持仓时必须通过规则十四的全部条件
   if(HasOpenPosition())
   {
      string addWhy = "";
      if(!AddOnAllowed(sg.dir, sg.score, ds, riskPct, addWhy))
      {
         NoTrade(addWhy);
         Panel(ds, addWhy);
         return;
      }
   }

   // 单笔风险不得让当日亏损突破 -15：剩余亏损额度更小时，按额度缩仓
   double remainingLoss = InpDailyMaxLoss + ds.total;   // ds.total 为负时额度变小
   double riskMoney     = AccountInfoDouble(ACCOUNT_BALANCE) * riskPct / 100.0;
   if(remainingLoss < riskMoney)
   {
      if(remainingLoss <= 0.30) { NoTrade("当日剩余亏损额度不足，不开新仓"); Panel(ds, "额度不足"); return; }
      riskPct = remainingLoss / AccountInfoDouble(ACCOUNT_BALANCE) * 100.0;
      LogLine("RISK", StringFormat("剩余亏损额度 $%.2f，本笔风险下调至 %.2f%%", remainingLoss, riskPct));
   }

   OpenTrade(sg, riskPct, ds);
}
//+------------------------------------------------------------------+
