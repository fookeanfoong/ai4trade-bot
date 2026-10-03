//+------------------------------------------------------------------+
//|                                          Crypto3EmaStochRsi.mq5  |
//|     BTC/ETH/SOL H1「3EMA + StochRSI」顺势回调 EA(MQL5 / MT5)        |
//+------------------------------------------------------------------+
//
//  ── 这个策略是怎么选出来的 ──────────────────────────────────────
//  crypto_scalp_lab.py 把网上 6 个公开剥头皮策略 + 原 EMA+MACD EA,在
//  M5 / M15 / H1 三个周期上用币安真实数据做「样本内选参 → 样本外只跑一次」。
//  21 个组合里只有这一个在样本内和样本外都为正(reports/crypto_scalp_lab_1h.md):
//
//    H1 · 2024-10 ~ 2026-01 样本内:467 笔,胜率 59%,+0.061R/笔
//    H1 · 2026-01 ~ 2026-08 样本外:233 笔,胜率 60%,+0.084R/笔
//                                  95% 区间 [-0.01, +0.18] —— **还不显著**
//    点差 0.02% / 0.04% / 0.08% → +0.086 / +0.084 / +0.065R(对成本不敏感)
//    分品种:BTC +0.07R · ETH -0.04R · SOL +0.24R
//
//  21 选 1 本身就有运气成分。这是「值得上模拟盘继续验证」,不是「确认赚钱」。
//
//  ── 规则(与 crypto_scalp_lab.py 的 build_ema3_srsi 逐条一致) ────────
//  做多:EMA8 > EMA14 > EMA50,且 StochRSI 的 K 上穿 D、穿越前 K < 20(超卖区),
//        且信号 K 收盘在 EMA8 上方
//  做空:完全对称(EMA8 < EMA14 < EMA50,K 在 > 80 区域下穿 D,收盘在 EMA8 下方)
//  入场:信号 K 收盘后,下一根第一个 tick 市价进
//  止损:3 × ATR(14);止盈:2 × ATR(14)(即 0.67R —— 高胜率、小盈亏比)
//  时间止损:持仓满 24 根 K 线还没出场就平掉
//  仓位:手数 = 净值 × 风险% ÷ 止损距离,硬上限 2%
//
//  没有马丁格尔、网格、加仓。止损随单提交给服务器。
//  免责:研究/学习用途,不构成投资建议。加密货币杠杆交易可能损失全部本金。
//+------------------------------------------------------------------+
#property copyright "ai4trade-bot"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <Trade/SymbolInfo.mqh>

input group "=== 品种 / 周期 ==="
input string InpWhitelist        = "BTC,ETH,SOL,XRP,BNB,DOGE,ADA,TRX,AVAX,LINK"; // 只做前10大高流动性币种
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_H1;   // 验证过的是 H1(M5/M15 样本外都为负)

input group "=== 风险管理 ==="
input double InpRiskPercent      = 1.0;    // 每笔风险占净值 %
input double InpMaxRiskPercent   = 2.0;    // 硬上限 %
input double InpDailyLossPct     = 4.0;    // 当日亏损达净值 % 即停手
input double InpMaxStopPct       = 5.0;    // 止损距离 > 价格的 % 就放弃
input double InpMinStopSpreadX   = 3.0;    // 止损至少是点差的几倍
input double InpMaxSpreadPct     = 0.08;   // 点差 > 价格的 % 就不交易
input int    InpSlippagePoints   = 100;

input group "=== 策略参数(验证值,别乱改) ==="
input int    InpEma1             = 8;
input int    InpEma2             = 14;
input int    InpEma3             = 50;
input int    InpRsiPeriod        = 14;     // StochRSI:RSI 周期
input int    InpStochPeriod      = 14;     // StochRSI:随机周期
input int    InpKSmooth          = 3;
input int    InpDSmooth          = 3;
input double InpOversold         = 20.0;   // 做多:穿越前 K 须低于此值
input double InpOverbought       = 80.0;   // 做空:穿越前 K 须高于此值
input int    InpAtrPeriod        = 14;
input double InpSlAtr            = 3.0;    // 止损 = ATR × 此值
input double InpTpAtr            = 2.0;    // 止盈 = ATR × 此值
input int    InpMaxBars          = 24;     // 时间止损(根)

input group "=== 新闻过滤 ==="
input bool   InpUseCalendar      = true;   // 用 MT5 经济日历屏蔽高影响新闻(回测里没有这一条)
input string InpCalendarCurrencies = "USD";
input int    InpNewsBeforeMin    = 30;
input int    InpNewsAfterMin     = 30;

input group "=== 其他 ==="
input long   InpMagic            = 20261004;
input bool   InpAlerts           = true;
input bool   InpShowPanel        = true;

CTrade        trade;
CSymbolInfo   sym;
int           hE1, hE2, hE3, hRSI;
datetime      lastBarTime    = 0;
datetime      dayStamp       = 0;
double        dayStartEquity = 0.0;
bool          dayBlocked     = false;

//+------------------------------------------------------------------+
int OnInit()
{
   if(!sym.Name(_Symbol)) return(INIT_FAILED);
   if(!SymbolWhitelisted())
   {
      PrintFormat("%s 不在白名单(%s)内,EA 不加载。", _Symbol, InpWhitelist);
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpTimeframe != PERIOD_H1)
      PrintFormat("⚠️ 当前周期 %s。验证过的只有 H1,M5/M15 样本外都是负的。", EnumToString(InpTimeframe));

   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   hE1  = iMA(_Symbol, InpTimeframe, InpEma1, 0, MODE_EMA, PRICE_CLOSE);
   hE2  = iMA(_Symbol, InpTimeframe, InpEma2, 0, MODE_EMA, PRICE_CLOSE);
   hE3  = iMA(_Symbol, InpTimeframe, InpEma3, 0, MODE_EMA, PRICE_CLOSE);
   hRSI = iRSI(_Symbol, InpTimeframe, InpRsiPeriod, PRICE_CLOSE);
   if(hE1 == INVALID_HANDLE || hE2 == INVALID_HANDLE || hE3 == INVALID_HANDLE || hRSI == INVALID_HANDLE)
      return(INIT_FAILED);

   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   dayStamp       = TodayStamp();
   PrintFormat("[VERSION] Crypto3EmaStochRsi 编译于 %s", TimeToString(__DATETIME__, TIME_DATE | TIME_SECONDS));
   PrintFormat("Crypto3EmaStochRsi 启动 | %s %s | 净值 %.2f", _Symbol, EnumToString(InpTimeframe),
               AccountInfoDouble(ACCOUNT_EQUITY));
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hE1); IndicatorRelease(hE2); IndicatorRelease(hE3); IndicatorRelease(hRSI);
   Comment("");
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(!sym.RefreshRates()) return;
   ResetDailyIfNeeded();

   datetime t = iTime(_Symbol, InpTimeframe, 0);
   if(t == lastBarTime) return;

   double e1[], e2[], e3[], k[], d[], atr[];
   if(!LoadIndicators(e1, e2, e3, k, d, atr)) return;
   lastBarTime = t;

   ManageTimeStop();
   Evaluate(e1, e2, e3, k, d, atr);
}

//+------------------------------------------------------------------+
//| 指标:index 1 = 最近一根已收盘 K 线(series 方式)                     |
//+------------------------------------------------------------------+
bool LoadIndicators(double &e1[], double &e2[], double &e3[], double &k[], double &d[], double &atr[])
{
   ArraySetAsSeries(e1, true); ArraySetAsSeries(e2, true); ArraySetAsSeries(e3, true);
   if(CopyBuffer(hE1, 0, 0, 3, e1) < 3) return false;
   if(CopyBuffer(hE2, 0, 0, 3, e2) < 3) return false;
   if(CopyBuffer(hE3, 0, 0, 3, e3) < 3) return false;

   // StochRSI:raw = (RSI - 最近N根最低RSI) / (最高 - 最低) × 100;K = SMA(raw,3);D = SMA(K,3)
   // 需要 K 的第 1、2 根,D 的第 1、2 根 → raw 要第 1..(2+K+D-2) 根 → RSI 要再多 Stoch-1 根
   int nRaw = 2 + InpKSmooth + InpDSmooth - 2;
   int nRsi = nRaw + InpStochPeriod;
   double r[];
   ArraySetAsSeries(r, true);
   if(CopyBuffer(hRSI, 0, 0, nRsi + 2, r) < nRsi + 2) return false;

   double raw[];
   ArrayResize(raw, nRaw + 1);
   for(int s = 1; s <= nRaw; s++)
   {
      double hi = -DBL_MAX, lo = DBL_MAX;
      for(int j = s; j < s + InpStochPeriod; j++) { hi = MathMax(hi, r[j]); lo = MathMin(lo, r[j]); }
      raw[s] = (hi > lo) ? (r[s] - lo) / (hi - lo) * 100.0 : 50.0;
   }
   int nK = 2 + InpDSmooth - 1;
   ArrayResize(k, nK + 1);
   for(int s = 1; s <= nK; s++)
   {
      double sum = 0;
      for(int j = s; j < s + InpKSmooth; j++) sum += raw[j];
      k[s] = sum / InpKSmooth;
   }
   ArrayResize(d, 3);
   for(int s = 1; s <= 2; s++)
   {
      double sum = 0;
      for(int j = s; j < s + InpDSmooth; j++) sum += k[j];
      d[s] = sum / InpDSmooth;
   }

   // ATR 用 Wilder 平滑(和回测一致;MT5 内置 iATR 是简单平均,数值会略有不同)
   int need = InpAtrPeriod * 15;
   double hh[], ll[], cc[];
   ArraySetAsSeries(hh, true); ArraySetAsSeries(ll, true); ArraySetAsSeries(cc, true);
   if(CopyHigh (_Symbol, InpTimeframe, 0, need + 2, hh) < need + 2) return false;
   if(CopyLow  (_Symbol, InpTimeframe, 0, need + 2, ll) < need + 2) return false;
   if(CopyClose(_Symbol, InpTimeframe, 0, need + 2, cc) < need + 2) return false;
   double a = 0;
   for(int s = need; s >= 1; s--)
   {
      double tr = MathMax(hh[s] - ll[s], MathMax(MathAbs(hh[s] - cc[s + 1]), MathAbs(ll[s] - cc[s + 1])));
      a = (s == need) ? tr : (a * (InpAtrPeriod - 1) + tr) / InpAtrPeriod;
   }
   ArrayResize(atr, 2);
   atr[1] = a;
   return (a > 0);
}

//+------------------------------------------------------------------+
void Evaluate(const double &e1[], const double &e2[], const double &e3[],
              const double &k[], const double &d[], const double &atr[])
{
   double c1 = iClose(_Symbol, InpTimeframe, 1);
   int    dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   bool upTrend = (e1[1] > e2[1] && e2[1] > e3[1]);
   bool dnTrend = (e1[1] < e2[1] && e2[1] < e3[1]);
   bool kxUp    = (k[1] > d[1] && k[2] <= d[2] && k[2] < InpOversold);
   bool kxDn    = (k[1] < d[1] && k[2] >= d[2] && k[2] > InpOverbought);
   bool longOK  = upTrend && kxUp && c1 > e1[1];
   bool shortOK = dnTrend && kxDn && c1 < e1[1];

   string block = BlockReason();
   if(InpShowPanel)
      Comment(StringFormat(
         "Crypto3EmaStochRsi  %s %s  @ %s\n"
         "EMA8=%s EMA14=%s EMA50=%s  趋势: %s\n"
         "StochRSI K=%.1f(前 %.1f) D=%.1f(前 %.1f)\n"
         "ATR=%s  止损=%s  止盈=%s\n"
         "做多: %s %s %s\n做空: %s %s %s\n结论: %s%s",
         _Symbol, EnumToString(InpTimeframe), TimeToString(iTime(_Symbol, InpTimeframe, 1)),
         DoubleToString(e1[1], dg), DoubleToString(e2[1], dg), DoubleToString(e3[1], dg),
         (upTrend ? "多头排列" : dnTrend ? "空头排列" : "无排列"),
         k[1], k[2], d[1], d[2],
         DoubleToString(atr[1], dg), DoubleToString(atr[1] * InpSlAtr, dg), DoubleToString(atr[1] * InpTpAtr, dg),
         (upTrend ? "[OK]排列" : "[X]排列"), (kxUp ? "[OK]超卖金叉" : "[X]超卖金叉"), (c1 > e1[1] ? "[OK]收>EMA8" : "[X]收>EMA8"),
         (dnTrend ? "[OK]排列" : "[X]排列"), (kxDn ? "[OK]超买死叉" : "[X]超买死叉"), (c1 < e1[1] ? "[OK]收<EMA8" : "[X]收<EMA8"),
         (longOK ? "做多" : shortOK ? "做空" : "不交易"),
         (block != "" && (longOK || shortOK) ? "(被过滤: " + block + ")" : "")));

   if(!longOK && !shortOK) return;
   if(block != "") { Print("信号成立但被过滤 —— ", block); return; }
   OpenTrade(longOK ? 1 : -1, atr[1]);
}

string BlockReason()
{
   if(dayBlocked)           return "当日亏损熔断";
   if(CountPositions() > 0) return "已有持仓";
   double spreadPct = (sym.Ask() - sym.Bid()) / sym.Bid() * 100.0;
   if(spreadPct > InpMaxSpreadPct) return StringFormat("点差 %.3f%%", spreadPct);
   string news;
   if(NewsBlocked(news)) return "新闻窗口:" + news;
   return "";
}

//+------------------------------------------------------------------+
void OpenTrade(int dir, double atrVal)
{
   sym.RefreshRates();
   int    dg     = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double entry  = (dir > 0) ? sym.Ask() : sym.Bid();
   double spread = sym.Ask() - sym.Bid();
   double dist   = atrVal * InpSlAtr;
   double stops  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(dist <= stops || dist < spread * InpMinStopSpreadX || dist / entry * 100.0 > InpMaxStopPct)
   {
      PrintFormat("放弃:止损距离 %s 不合格(点差 %s,上限 %.1f%%)", DoubleToString(dist, dg),
                  DoubleToString(spread, dg), InpMaxStopPct);
      return;
   }
   double riskUsed = 0;
   double lots = CalculateLots(dist, riskUsed);
   if(lots <= 0) return;

   double sl = NormalizeDouble(entry - dir * dist, dg);
   double tp = NormalizeDouble(entry + dir * atrVal * InpTpAtr, dg);
   bool sent = (dir > 0) ? trade.Buy (lots, _Symbol, 0.0, sl, tp, "3EMA-SRSI")
                         : trade.Sell(lots, _Symbol, 0.0, sl, tp, "3EMA-SRSI");
   uint rc = trade.ResultRetcode();
   if(sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED || rc == TRADE_RETCODE_DONE_PARTIAL))
      Notify(StringFormat("%s %s %.3f手 @%s SL=%s TP=%s 风险$%.2f", (dir > 0 ? "买入" : "卖出"), _Symbol,
                          lots, DoubleToString(entry, dg), DoubleToString(sl, dg), DoubleToString(tp, dg), riskUsed));
   else
      PrintFormat("下单失败 retcode=%u %s", rc, trade.ResultRetcodeDescription());
}

// 时间止损:持仓满 InpMaxBars 根 K 线就在新 K 线开盘平掉(回测按第 N 根收盘价,几乎相同)
void ManageTimeStop()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      datetime opened = (datetime)PositionGetInteger(POSITION_TIME);
      int bars = iBarShift(_Symbol, InpTimeframe, opened);   // 入场那根现在是第几根 = 已持有根数
      if(bars >= InpMaxBars)
      {
         if(trade.PositionClose(ticket))
            Notify(StringFormat("%s 持仓满 %d 根,时间止损平仓", _Symbol, bars));
         else
            PrintFormat("时间止损平仓失败 retcode=%u", trade.ResultRetcode());
      }
   }
}

//+------------------------------------------------------------------+
//| 以下工具函数与 CryptoEmaMacdScalper 相同                           |
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
   double eq     = AccountInfoDouble(ACCOUNT_EQUITY);
   double risk   = eq * MathMin(InpRiskPercent, InpMaxRiskPercent) / 100.0;
   double perLot = MoneyForDistance(1.0, stopDistance);
   if(perLot <= 0) return 0.0;
   double lots = NormalizeLots(risk / perLot);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(lots < minL) lots = minL;
   double actual = MoneyForDistance(lots, stopDistance);
   if(actual > eq * InpMaxRiskPercent / 100.0)
   {
      PrintFormat("拒绝开仓:%.3f 手风险 $%.2f 超过上限 %.2f%%(净值 $%.2f)", lots, actual, InpMaxRiskPercent, eq);
      return 0.0;
   }
   riskUsedOut = actual;
   return lots;
}

double NormalizeLots(double lots)
{
   double maxL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step <= 0) step = 0.01;
   lots = MathFloor(lots / step + 1e-9) * step;
   if(lots > maxL) lots = maxL;
   int digits = (step >= 1.0) ? 0 : (int)MathCeil(-MathLog10(step) - 1e-9);
   return NormalizeDouble(lots, digits);
}

int CountPositions()
{
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic) n++;
   }
   return n;
}

bool NewsBlocked(string &what)
{
   if(!InpUseCalendar || MQLInfoInteger(MQL_TESTER)) return false;
   datetime now = TimeCurrent();
   string cur[];
   int nc = StringSplit(InpCalendarCurrencies, ',', cur);
   for(int c = 0; c < nc; c++)
   {
      string ccy = cur[c];
      StringTrimLeft(ccy); StringTrimRight(ccy);
      if(ccy == "") continue;
      MqlCalendarValue vals[];
      if(!CalendarValueHistory(vals, now - InpNewsAfterMin * 60, now + InpNewsBeforeMin * 60, NULL, ccy)) continue;
      for(int j = 0; j < ArraySize(vals); j++)
      {
         MqlCalendarEvent ev;
         if(CalendarEventById(vals[j].event_id, ev) && ev.importance == CALENDAR_IMPORTANCE_HIGH)
         {
            what = StringFormat("%s %s @%s", ccy, ev.name, TimeToString(vals[j].time, TIME_DATE | TIME_MINUTES));
            return true;
         }
      }
   }
   return false;
}

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
      dayStamp = today;
      dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      dayBlocked = false;
   }
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
   if(!dayBlocked && dayStartEquity > 0 && (dayStartEquity - eq) / dayStartEquity * 100.0 >= InpDailyLossPct)
   {
      dayBlocked = true;
      Notify(StringFormat("当日亏损达到 %.2f%%,今日停止开新仓", InpDailyLossPct));
   }
}

bool SymbolWhitelisted()
{
   string s = _Symbol;
   StringToUpper(s);
   string list[];
   int n = StringSplit(InpWhitelist, ',', list);
   for(int i = 0; i < n; i++)
   {
      string w = list[i];
      StringTrimLeft(w); StringTrimRight(w); StringToUpper(w);
      if(w != "" && StringFind(s, w) >= 0) return true;
   }
   return false;
}

void Notify(string msg)
{
   Print(msg);
   if(!InpAlerts || MQLInfoInteger(MQL_TESTER)) return;
   Alert(msg);
   SendNotification(StringSubstr(msg, 0, 255));
}
//+------------------------------------------------------------------+
