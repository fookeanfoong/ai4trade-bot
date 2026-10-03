# ============================================================
#  CryptoEmaMacdScalper - 一键安装到 MT5(单文件,无需 git / 下载仓库)
#  用法(PowerShell):
#    powershell -ExecutionPolicy Bypass -File install_crypto_ea.ps1
#  它会:找到所有 MT5 终端 -> 写入 EA + 2 个 preset -> 调 MetaEditor 编译
# ============================================================
$ErrorActionPreference = 'Stop'
$utf8bom = New-Object System.Text.UTF8Encoding $true

$EA = @'
//+------------------------------------------------------------------+
//|                                       CryptoEmaMacdScalper.mq5   |
//|        BTC/ETH/SOL 等 M5「EMA + MACD 动量剥头皮」EA(MQL5 / MT5)   |
//+------------------------------------------------------------------+
//
//  这个 EA 只做一件事:把下面这套规则逐字翻译成代码,不加任何系统外的指标。
//
//  ── 做多(4 条必须全部满足) ─────────────────────────────────────
//  L1 EMA20 上穿 EMA50(金叉发生在最近 N 根内),且当前 EMA20 仍在 EMA50 上方
//  L2 MACD(12,26,9) 线上穿信号线(最近 N 根内),柱状图(MACD-信号)> 0
//  L3 信号 K 线回踩 EMA20 或 EMA50 附近,并且是看涨吞没或锤子线
//  L4 信号 K 线成交量 >= 近期均量 × 倍数
//  做空完全对称(S1~S4),S4 额外要求信号 K 是阴线。
//
//  ── 进出场 ────────────────────────────────────────────────────────
//  入场:信号 K 线收盘后(新 K 线第一个 tick)市价进场
//  止损:做多 = 最近 N 根最低点下方;做空 = 最近 N 根最高点上方(加缓冲)
//  止盈:拆成两单,一单 1.5R、一单 2R(手数不够拆就单一目标)
//  移动止损:连续 N 根收在 EMA20 同侧 = 强趋势,止损跟随 EMA20
//  仓位:手数 = (净值 × 风险%) ÷ |入场 − 止损|,风险% 硬上限 2%
//
//  ── 不交易 ────────────────────────────────────────────────────────
//  任一条件不满足 / 高影响新闻前后 / EMA 反复交叉(缠绕)/ 低成交量 /
//  点差过大 / 同一次交叉已经交易过(禁止过度交易)/ 当日亏损熔断
//
//  没有马丁格尔、网格、加仓摊平。每一单进场时止损随单提交给服务器。
//  免责:研究/学习用途,不构成投资建议。加密货币杠杆交易可能损失全部本金。
//+------------------------------------------------------------------+
#property copyright "ai4trade-bot"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>
#include <Trade/SymbolInfo.mqh>

//--- 品种 / 周期 ----------------------------------------------------
input group "=== 品种 / 周期 ==="
input string InpWhitelist        = "BTC,ETH,SOL,XRP,BNB,DOGE,ADA,TRX,AVAX,LINK"; // 只做前10大高流动性币种
input ENUM_TIMEFRAMES InpTimeframe = PERIOD_M5;  // 系统规定 M5

//--- 风险 ----------------------------------------------------------
input group "=== 风险管理 ==="
input double InpRiskPercent      = 1.0;    // 每笔风险占净值 %
input double InpMaxRiskPercent   = 2.0;    // 硬上限 %(调高也会被夹回)
input double InpDailyLossPct     = 4.0;    // 当日亏损达净值 % 即停手
input double InpMaxStopPct       = 1.5;    // 止损距离 > 价格的 % 就放弃(摆动点太远)
input double InpMinStopSpreadX   = 3.0;    // 止损至少是点差的几倍
input double InpSLBufferPct      = 0.05;   // 止损放在摆动点外的缓冲(% 价格)
input int    InpSlippagePoints   = 50;     // 允许滑点(point)

//--- 系统参数 ------------------------------------------------------
input group "=== 系统参数 ==="
input int    InpFastEMA          = 20;     // EMA 快线
input int    InpSlowEMA          = 50;     // EMA 中线
input int    InpMacdFast         = 12;
input int    InpMacdSlow         = 26;
input int    InpMacdSignal       = 9;
input int    InpEmaCrossLookback = 12;     // L1/S1:金叉/死叉须在最近 N 根内
input int    InpMacdCrossLookback= 3;      // L2/S2:MACD 交叉须在最近 N 根内
input double InpTouchTolPct      = 0.10;   // L3/S3:「EMA 附近」容差(% 价格)
input double InpWickRatio        = 2.0;    // 锤子/射击之星:影线 >= 实体 × 此值
input int    InpVolAvgBars       = 20;     // L4/S4:均量窗口
input double InpVolMult          = 1.5;    // 信号 K 量 >= 均量 × 此值
input bool   InpUseRealVolume    = false;  // false = tick 成交量(多数 CFD 券商只有这个)
input int    InpSwingLookback    = 10;     // 摆动高低点回溯根数

//--- 出场 ----------------------------------------------------------
input group "=== 出场 ==="
input double InpTP1R             = 1.5;    // 目标 1(R)
input double InpTP2R             = 2.0;    // 目标 2(R)
input double InpSingleTPR        = 1.5;    // 手数不够拆两单时的单一目标(R)
input bool   InpTrailEMA20       = true;   // 强趋势时止损跟随 EMA20
input int    InpTrendBars        = 5;      // 连续 N 根收在 EMA20 同侧 = 强趋势

//--- 不交易过滤 ----------------------------------------------------
input group "=== 不交易过滤 ==="
input int    InpChopLookback     = 36;     // 缠绕检测窗口(根)
input int    InpMaxCrossesInChop = 1;      // 窗口内 EMA 交叉次数 > 此值 = 缠绕
input double InpMinAvgVolume     = 0;      // 均量低于此值 = 低成交量(0 = 关)
input double InpMaxSpreadPct     = 0.06;   // 点差 > 价格的 % 就不交易
input bool   InpUseCalendar      = true;   // 用 MT5 经济日历屏蔽高影响新闻
input string InpCalendarCurrencies = "USD";// 关注的货币(逗号分隔)
input int    InpNewsBeforeMin    = 30;     // 新闻前 N 分钟不开仓
input int    InpNewsAfterMin     = 30;     // 新闻后 N 分钟不开仓
input string InpManualNews       = "";     // 手动新闻(服务器时间),如 "2026.10.15 12:30;2026.10.29 18:00"
input bool   InpOneTradePerCross = true;   // 同一次 EMA 交叉只交易一次

//--- 其他 ----------------------------------------------------------
input group "=== 其他 ==="
input long   InpMagic            = 20261003;
input bool   InpAlerts           = true;   // 终端弹窗 + 推送
input bool   InpShowPanel        = true;   // 图表左上角显示条件检查表

//--- 全局 ----------------------------------------------------------
CTrade        trade;
CSymbolInfo   sym;
int           hFast, hSlow, hMACD;
datetime      lastBarTime    = 0;
datetime      dayStamp       = 0;
double        dayStartEquity = 0.0;
bool          dayBlocked     = false;
bool          isHedging      = true;

// 所有数组都是 series 方式:index 1 = 最近一根**已收盘** K 线
double   ema20[], ema50[], macdM[], macdS[];
double   op[], hi[], lo[], cl[];
long     vol[];
datetime tm[];

struct Check
{
   bool   c1, c2, c3, c4;
   string n1, n2, n3, n4;
   int    crossShift;      // L1/S1 所用那次 EMA 交叉在第几根
};

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
   // 系统规定只做前 10 大高流动性币种,其他一律不交易 —— 直接拒绝加载。
   if(!SymbolWhitelisted())
   {
      PrintFormat("%s 不在白名单(%s)内:系统规定其他币种一律不交易,EA 不加载。",
                  _Symbol, InpWhitelist);
      return(INIT_PARAMETERS_INCORRECT);
   }
   if(InpTimeframe != PERIOD_M5)
      PrintFormat("⚠️ 当前周期 %s,系统规定是 M5。", EnumToString(InpTimeframe));
   if(InpTP1R <= 0 || InpTP2R <= 0 || InpSwingLookback < 2 || InpVolAvgBars < 2)
      return(INIT_PARAMETERS_INCORRECT);

   sym.RefreshRates();
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);

   hFast = iMA(_Symbol, InpTimeframe, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, InpTimeframe, InpSlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   hMACD = iMACD(_Symbol, InpTimeframe, InpMacdFast, InpMacdSlow, InpMacdSignal, PRICE_CLOSE);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hMACD == INVALID_HANDLE)
   {
      Print("指标句柄创建失败");
      return(INIT_FAILED);
   }

   // 两个止盈目标靠「拆成两单」实现,这只在对冲账户里成立。
   // 净额账户同一品种只有一个持仓,所以改成:单一持仓挂 2R,到 1.5R 时 EA 平一半。
   isHedging = (AccountInfoInteger(ACCOUNT_MARGIN_MODE) == ACCOUNT_MARGIN_MODE_RETAIL_HEDGING);

   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   dayStamp       = TodayStamp();

   // 编译戳:确认跑的是刚编译的新版,不是旧 .ex5
   PrintFormat("[VERSION] CryptoEmaMacdScalper 编译于 %s", TimeToString(__DATETIME__, TIME_DATE | TIME_SECONDS));
   PrintFormat("CryptoEmaMacdScalper 启动 | %s %s | 净值 %.2f | %s 账户 | 最小手 %.3f | 步长 %.3f",
               _Symbol, EnumToString(InpTimeframe), AccountInfoDouble(ACCOUNT_EQUITY),
               (isHedging ? "对冲" : "净额"),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN),
               SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP));
   if(InpUseCalendar && MQLInfoInteger(MQL_TESTER))
      Print("提示:策略测试器里没有经济日历,新闻过滤只剩 InpManualNews 手动列表。");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hFast);
   IndicatorRelease(hSlow);
   IndicatorRelease(hMACD);
   Comment("");
}

//+------------------------------------------------------------------+
//| 主循环                                                            |
//+------------------------------------------------------------------+
void OnTick()
{
   if(!sym.RefreshRates()) return;

   ResetDailyIfNeeded();
   ManagePartialTP1();         // 净额账户的 1.5R 平半仓要逐 tick 检查

   // 所有判断只在新 K 线上做一次,只用已收盘 K 线 —— 「确认 K 线收盘时入场」。
   datetime t = iTime(_Symbol, InpTimeframe, 0);
   if(t == lastBarTime) return;
   if(!LoadData()) return;     // 数据没准备好就下一个 tick 再试,不标记本根已处理
   lastBarTime = t;

   ManageTrailing();
   TryEntry();
}

//+------------------------------------------------------------------+
//| 数据                                                              |
//+------------------------------------------------------------------+
int BarsNeeded()
{
   int n = MathMax(InpChopLookback, InpEmaCrossLookback);
   n = MathMax(n, InpVolAvgBars + 2);
   n = MathMax(n, InpSwingLookback);
   n = MathMax(n, InpTrendBars);
   n = MathMax(n, InpMacdCrossLookback);
   return n + 5;
}

bool LoadData()
{
   int need = BarsNeeded();
   ArraySetAsSeries(ema20, true); ArraySetAsSeries(ema50, true);
   ArraySetAsSeries(macdM, true); ArraySetAsSeries(macdS, true);
   ArraySetAsSeries(op, true);    ArraySetAsSeries(hi, true);
   ArraySetAsSeries(lo, true);    ArraySetAsSeries(cl, true);
   ArraySetAsSeries(vol, true);   ArraySetAsSeries(tm, true);

   if(CopyBuffer(hFast, 0, 0, need, ema20) < need) return false;
   if(CopyBuffer(hSlow, 0, 0, need, ema50) < need) return false;
   if(CopyBuffer(hMACD, 0, 0, need, macdM) < need) return false;   // 0 = MACD 线
   if(CopyBuffer(hMACD, 1, 0, need, macdS) < need) return false;   // 1 = 信号线
   if(CopyOpen (_Symbol, InpTimeframe, 0, need, op) < need) return false;
   if(CopyHigh (_Symbol, InpTimeframe, 0, need, hi) < need) return false;
   if(CopyLow  (_Symbol, InpTimeframe, 0, need, lo) < need) return false;
   if(CopyClose(_Symbol, InpTimeframe, 0, need, cl) < need) return false;
   if(CopyTime (_Symbol, InpTimeframe, 0, need, tm) < need) return false;
   int got = InpUseRealVolume ? CopyRealVolume(_Symbol, InpTimeframe, 0, need, vol)
                              : CopyTickVolume(_Symbol, InpTimeframe, 0, need, vol);
   return (got >= need);
}

//+------------------------------------------------------------------+
//| 交叉检测:+1 = 向上交叉(在第 i 根收盘时完成),-1 = 向下,0 = 无     |
//+------------------------------------------------------------------+
int EmaCrossDir(int i)
{
   bool nowAbove  = ema20[i]     > ema50[i];
   bool prevAbove = ema20[i + 1] > ema50[i + 1];
   if(nowAbove && !prevAbove) return  1;
   if(!nowAbove && prevAbove) return -1;
   return 0;
}

int MacdCrossDir(int i)
{
   bool nowAbove  = macdM[i]     > macdS[i];
   bool prevAbove = macdM[i + 1] > macdS[i + 1];
   if(nowAbove && !prevAbove) return  1;
   if(!nowAbove && prevAbove) return -1;
   return 0;
}

int CountEmaCrosses(int lookback)
{
   int n = 0;
   for(int i = 1; i <= lookback; i++)
      if(EmaCrossDir(i) != 0) n++;
   return n;
}

//+------------------------------------------------------------------+
//| K 线形态(只看已收盘的第 1、2 根)                                   |
//+------------------------------------------------------------------+
bool BullishEngulfing()
{
   return (cl[2] < op[2] && cl[1] > op[1] && op[1] <= cl[2] && cl[1] >= op[2]);
}

bool BearishEngulfing()
{
   return (cl[2] > op[2] && cl[1] < op[1] && op[1] >= cl[2] && cl[1] <= op[2]);
}

// 锤子线:下影线 >= 实体 × 倍数,上影线 <= 全长 25%
bool Hammer(int i)
{
   double rng = hi[i] - lo[i];
   if(rng <= 0) return false;
   double body  = MathAbs(cl[i] - op[i]);
   double lower = MathMin(op[i], cl[i]) - lo[i];
   double upper = hi[i] - MathMax(op[i], cl[i]);
   return (lower >= InpWickRatio * MathMax(body, rng * 0.05) && upper <= rng * 0.25);
}

// 射击之星:上影线 >= 实体 × 倍数,下影线 <= 全长 25%
bool ShootingStar(int i)
{
   double rng = hi[i] - lo[i];
   if(rng <= 0) return false;
   double body  = MathAbs(cl[i] - op[i]);
   double lower = MathMin(op[i], cl[i]) - lo[i];
   double upper = hi[i] - MathMax(op[i], cl[i]);
   return (upper >= InpWickRatio * MathMax(body, rng * 0.05) && lower <= rng * 0.25);
}

//+------------------------------------------------------------------+
//| 条件检查:dir = +1 做多(L1~L4),-1 做空(S1~S4)                     |
//+------------------------------------------------------------------+
void Evaluate(int dir, Check &ck)
{
   int d = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   string P = (dir > 0) ? "L" : "S";
   ck.crossShift = 0;

   // ---- 1:EMA 交叉 -----------------------------------------------
   int lastShift = 0, lastDir = 0;
   for(int i = 1; i <= InpChopLookback; i++)
   {
      int cd = EmaCrossDir(i);
      if(cd != 0) { lastShift = i; lastDir = cd; break; }
   }
   bool side = (dir > 0) ? (ema20[1] > ema50[1]) : (ema20[1] < ema50[1]);
   ck.c1 = side && lastDir == dir && lastShift >= 1 && lastShift <= InpEmaCrossLookback;
   if(ck.c1) ck.crossShift = lastShift;
   ck.n1 = StringFormat("%s1 EMA%s: EMA20=%s EMA50=%s, 最近交叉=%s(%d根前)",
                        P, (dir > 0 ? "金叉" : "死叉"),
                        DoubleToString(ema20[1], d), DoubleToString(ema50[1], d),
                        (lastDir > 0 ? "金叉" : lastDir < 0 ? "死叉" : "无"), lastShift);

   // ---- 2:MACD 交叉 + 柱状图颜色 -----------------------------------
   int mShift = 0;
   for(int i = 1; i <= InpMacdCrossLookback; i++)
      if(MacdCrossDir(i) == dir) { mShift = i; break; }
   double hist = macdM[1] - macdS[1];
   ck.c2 = (mShift > 0) && ((dir > 0) ? hist > 0 : hist < 0);
   ck.n2 = StringFormat("%s2 MACD: 线=%.5g 信号=%.5g 柱=%.5g(%s), %s交叉=%s",
                        P, macdM[1], macdS[1], hist, (hist > 0 ? "绿" : "红"),
                        (dir > 0 ? "上" : "下"),
                        (mShift > 0 ? IntegerToString(mShift) + "根前" : "近" +
                                      IntegerToString(InpMacdCrossLookback) + "根内无"));

   // ---- 3:回踩 EMA + 反转形态 --------------------------------------
   bool engulf = (dir > 0) ? BullishEngulfing() : BearishEngulfing();
   bool pin    = (dir > 0) ? Hammer(1)          : ShootingStar(1);
   double tol  = cl[1] * InpTouchTolPct / 100.0;
   double ext;
   bool near20, near50, structure;
   if(dir > 0)
   {
      ext       = engulf ? MathMin(lo[1], lo[2]) : lo[1];
      near20    = (ext <= ema20[1] + tol && cl[1] >= ema20[1] - tol);
      near50    = (ext <= ema50[1] + tol && cl[1] >= ema50[1] - tol);
      structure = (cl[1] > ema50[1]);      // 收盘没跌破 EMA50
   }
   else
   {
      ext       = engulf ? MathMax(hi[1], hi[2]) : hi[1];
      near20    = (ext >= ema20[1] - tol && cl[1] <= ema20[1] + tol);
      near50    = (ext >= ema50[1] - tol && cl[1] <= ema50[1] + tol);
      structure = (cl[1] < ema50[1]);      // 收盘没站上 EMA50
   }
   ck.c3 = (engulf || pin) && (near20 || near50) && structure;
   string patName = engulf ? (dir > 0 ? "看涨吞没" : "看跌吞没")
                  : pin    ? (dir > 0 ? "锤子线"   : "射击之星") : "无形态";
   ck.n3 = StringFormat("%s3 %s: 极值=%s 形态=%s 触及=%s 收盘%s EMA50",
                        P, (dir > 0 ? "回踩" : "反弹"), DoubleToString(ext, d), patName,
                        (near20 && near50 ? "EMA20+50" : near20 ? "EMA20" :
                         near50 ? "EMA50" : "未触及"),
                        (structure ? (dir > 0 ? "在上方" : "在下方") : "已穿越"));

   // ---- 4:成交量放大 ---------------------------------------------
   double avg = 0;
   for(int i = 2; i < 2 + InpVolAvgBars; i++) avg += (double)vol[i];
   avg /= InpVolAvgBars;
   bool bearBar = (cl[1] < op[1]);
   ck.c4 = (avg > 0 && (double)vol[1] >= avg * InpVolMult) && (dir > 0 || bearBar);
   ck.n4 = StringFormat("%s4 成交量: 信号K=%I64d 均量=%.0f (%.2fx, 需%.2fx)%s",
                        P, vol[1], avg, (avg > 0 ? vol[1] / avg : 0.0), InpVolMult,
                        (dir < 0 && !bearBar ? " 非阴线" : ""));
}

string Mark(bool ok) { return ok ? "[OK]" : "[X] "; }

//+------------------------------------------------------------------+
//| 不交易过滤:返回空串 = 放行,否则是拦截原因                          |
//+------------------------------------------------------------------+
string BlockReason()
{
   if(dayBlocked)            return "当日亏损熔断";
   if(CountPositions() > 0)  return "已有持仓";

   double spreadPct = (sym.Ask() - sym.Bid()) / sym.Bid() * 100.0;
   if(spreadPct > InpMaxSpreadPct)
      return StringFormat("点差 %.3f%% > %.3f%%", spreadPct, InpMaxSpreadPct);

   int crosses = CountEmaCrosses(InpChopLookback);
   if(crosses > InpMaxCrossesInChop)
      return StringFormat("横盘缠绕:最近 %d 根 EMA 交叉 %d 次", InpChopLookback, crosses);

   if(InpMinAvgVolume > 0)
   {
      double avg = 0;
      for(int i = 2; i < 2 + InpVolAvgBars; i++) avg += (double)vol[i];
      avg /= InpVolAvgBars;
      if(avg < InpMinAvgVolume)
         return StringFormat("低成交量:均量 %.0f < %.0f", avg, InpMinAvgVolume);
   }

   string news;
   if(NewsBlocked(news)) return "新闻窗口:" + news;
   return "";
}

bool NewsBlocked(string &what)
{
   datetime now = TimeCurrent();
   datetime lo_ = now - InpNewsAfterMin * 60;    // 刚发布过的
   datetime hi_ = now + InpNewsBeforeMin * 60;   // 即将发布的

   if(StringLen(InpManualNews) > 0)
   {
      string parts[];
      int n = StringSplit(InpManualNews, ';', parts);
      for(int k = 0; k < n; k++)
      {
         string s = parts[k];
         StringTrimLeft(s); StringTrimRight(s);
         if(s == "") continue;
         datetime t = StringToTime(s);
         if(t > 0 && t >= lo_ && t <= hi_) { what = "手动 " + s; return true; }
      }
   }

   if(InpUseCalendar && !MQLInfoInteger(MQL_TESTER))
   {
      string cur[];
      int nc = StringSplit(InpCalendarCurrencies, ',', cur);
      for(int c = 0; c < nc; c++)
      {
         string ccy = cur[c];
         StringTrimLeft(ccy); StringTrimRight(ccy);
         if(ccy == "") continue;
         MqlCalendarValue vals[];
         if(!CalendarValueHistory(vals, lo_, hi_, NULL, ccy)) continue;
         for(int j = 0; j < ArraySize(vals); j++)
         {
            MqlCalendarEvent ev;
            if(CalendarEventById(vals[j].event_id, ev) &&
               ev.importance == CALENDAR_IMPORTANCE_HIGH)
            {
               what = StringFormat("%s %s @%s", ccy, ev.name,
                                   TimeToString(vals[j].time, TIME_DATE | TIME_MINUTES));
               return true;
            }
         }
      }
   }
   return false;
}

//+------------------------------------------------------------------+
//| 入场                                                              |
//+------------------------------------------------------------------+
void TryEntry()
{
   Check L, S;
   Evaluate( 1, L);
   Evaluate(-1, S);
   string block = BlockReason();

   bool longOK  = L.c1 && L.c2 && L.c3 && L.c4;
   bool shortOK = S.c1 && S.c2 && S.c3 && S.c4;
   string verdict = longOK ? "做多" : shortOK ? "做空" : "不交易";
   if((longOK || shortOK) && block != "") verdict = "不交易(" + block + ")";

   if(InpShowPanel)
      Comment(StringFormat(
         "CryptoEmaMacdScalper  %s %s  @ %s\n结论: %s\n\n"
         "%s %s\n%s %s\n%s %s\n%s %s\n\n%s %s\n%s %s\n%s %s\n%s %s\n\n过滤: %s",
         _Symbol, EnumToString(InpTimeframe), TimeToString(tm[1], TIME_DATE | TIME_MINUTES),
         verdict,
         Mark(L.c1), L.n1, Mark(L.c2), L.n2, Mark(L.c3), L.n3, Mark(L.c4), L.n4,
         Mark(S.c1), S.n1, Mark(S.c2), S.n2, Mark(S.c3), S.n3, Mark(S.c4), S.n4,
         (block == "" ? "无" : block)));

   if(!longOK && !shortOK) return;
   if(block != "")
   {
      Print("信号成立但被过滤 —— ", block);
      return;
   }

   int dir = longOK ? 1 : -1;
   int crossShift   = longOK ? L.crossShift : S.crossShift;
   string checklist = longOK ? StringFormat("%s\n%s\n%s\n%s", L.n1, L.n2, L.n3, L.n4)
                             : StringFormat("%s\n%s\n%s\n%s", S.n1, S.n2, S.n3, S.n4);

   // 禁止过度交易:同一次 EMA 交叉只给一次机会。
   datetime crossTime = tm[crossShift];
   if(InpOneTradePerCross && (datetime)(long)GVGet("cross", 0) == crossTime)
   {
      PrintFormat("本次交叉(%s)已交易过,跳过", TimeToString(crossTime));
      return;
   }

   if(OpenTrade(dir, checklist))
      GVSet("cross", (double)(long)crossTime);
}

//+------------------------------------------------------------------+
//| 下单                                                              |
//+------------------------------------------------------------------+
bool OpenTrade(int dir, string checklist)
{
   sym.RefreshRates();
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double entry  = (dir > 0) ? sym.Ask() : sym.Bid();
   double spread = sym.Ask() - sym.Bid();
   double buf    = MathMax(spread, entry * InpSLBufferPct / 100.0);

   // 止损 = 最近摆动点外侧
   double swing = (dir > 0) ? lo[1] : hi[1];
   for(int i = 1; i <= InpSwingLookback; i++)
      swing = (dir > 0) ? MathMin(swing, lo[i]) : MathMax(swing, hi[i]);
   double sl   = NormalizeDouble((dir > 0) ? swing - buf : swing + buf, digits);
   double dist = (dir > 0) ? entry - sl : sl - entry;

   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   if(dist <= 0 || dist <= stopsLevel)
   {
      PrintFormat("放弃:止损距离 %.*f 无效(券商最小 %.*f)", digits, dist, digits, stopsLevel);
      return false;
   }
   if(dist < spread * InpMinStopSpreadX)
   {
      PrintFormat("放弃:止损 %.*f 不到点差 %.*f 的 %.1f 倍,成本占比过高",
                  digits, dist, digits, spread, InpMinStopSpreadX);
      return false;
   }
   if(dist / entry * 100.0 > InpMaxStopPct)
   {
      PrintFormat("放弃:摆动点太远,止损 %.2f%% > %.2f%%", dist / entry * 100.0, InpMaxStopPct);
      return false;
   }

   double riskUsed = 0.0;
   double lots = CalculateLots(dist, riskUsed);
   if(lots <= 0) return false;

   double tp1 = NormalizeDouble(entry + dir * dist * InpTP1R, digits);
   double tp2 = NormalizeDouble(entry + dir * dist * InpTP2R, digits);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double half = NormalizeLots(lots / 2.0);
   bool   split = (half >= minL && NormalizeLots(lots - half) >= minL);

   string side = (dir > 0) ? "买入" : "卖出";
   bool ok = false;
   string plan;

   if(split && isHedging)
   {
      double rest = NormalizeLots(lots - half);
      bool ok1 = Send(dir, half, sl, tp1, "EMACD TP1");
      bool ok2 = Send(dir, rest, sl, tp2, "EMACD TP2");
      ok   = ok1 || ok2;
      plan = StringFormat("%.3f手→TP1 %s / %.3f手→TP2 %s%s", half,
                          DoubleToString(tp1, digits), rest, DoubleToString(tp2, digits),
                          (ok1 && ok2) ? "" : "(有一单失败,见日志)");
   }
   else if(split)
   {
      // 净额账户:一个持仓挂 TP2,到 TP1 由 EA 平掉一半
      ok = Send(dir, lots, sl, tp2, "EMACD");
      if(ok)
      {
         GVSet("tp1",  tp1);
         GVSet("half", half);
         GVSet("dir",  dir);
      }
      plan = StringFormat("%.3f手 TP2 %s,到 TP1 %s 平 %.3f手", lots,
                          DoubleToString(tp2, digits), DoubleToString(tp1, digits), half);
   }
   else
   {
      double tp = NormalizeDouble(entry + dir * dist * InpSingleTPR, digits);
      ok   = Send(dir, lots, sl, tp, "EMACD");
      plan = StringFormat("%.3f手 单一目标 %.1fR=%s(手数不够拆两单)", lots, InpSingleTPR,
                          DoubleToString(tp, digits));
   }

   if(ok)
      Notify(StringFormat("%s %s @%s SL=%s 每单位风险=%s 总风险$%.2f | %s\n%s",
                          side, _Symbol, DoubleToString(entry, digits),
                          DoubleToString(sl, digits), DoubleToString(dist, digits),
                          riskUsed, plan, checklist));
   return ok;
}

bool Send(int dir, double lots, double sl, double tp, string comment)
{
   bool sent = (dir > 0) ? trade.Buy (lots, _Symbol, 0.0, sl, tp, comment)
                         : trade.Sell(lots, _Symbol, 0.0, sl, tp, comment);
   uint rc = trade.ResultRetcode();
   bool ok = sent && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED ||
                      rc == TRADE_RETCODE_DONE_PARTIAL);
   if(!ok)
      PrintFormat("下单失败 retcode=%u %s", rc, trade.ResultRetcodeDescription());
   return ok;
}

//+------------------------------------------------------------------+
//| 手数:由「亏损金额固定」反推                                       |
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
   double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
   double pct  = MathMin(InpRiskPercent, InpMaxRiskPercent);
   double risk = eq * pct / 100.0;

   double perLot = MoneyForDistance(1.0, stopDistance);
   if(perLot <= 0) return 0.0;

   double lots = NormalizeLots(risk / perLot);
   double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(lots < minL) lots = minL;

   // 最小手数的风险已经超过硬上限 = 这个账户做不了这一单,宁可错过。
   double actual = MoneyForDistance(lots, stopDistance);
   if(actual > eq * InpMaxRiskPercent / 100.0)
   {
      PrintFormat("拒绝开仓:%.3f 手风险 $%.2f 超过上限 %.2f%%(净值 $%.2f)",
                  lots, actual, InpMaxRiskPercent, eq);
      return 0.0;
   }
   riskUsedOut = actual;
   return lots;
}

// 向下取整到步长(宁可少冒风险);小于最小手返回原值,由调用方判断
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

//+------------------------------------------------------------------+
//| 持仓管理                                                          |
//+------------------------------------------------------------------+
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

// 强趋势(连续 N 根收在 EMA20 同侧)时,止损跟随 EMA20,只朝有利方向移动
void ManageTrailing()
{
   if(!InpTrailEMA20) return;

   bool strongUp = true, strongDn = true;
   for(int i = 1; i <= InpTrendBars; i++)
   {
      if(cl[i] <= ema20[i]) strongUp = false;
      if(cl[i] >= ema20[i]) strongDn = false;
   }
   if(!strongUp && !strongDn) return;

   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double stops  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
   double buf    = MathMax(sym.Ask() - sym.Bid(), cl[1] * InpSLBufferPct / 100.0);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      long   type = PositionGetInteger(POSITION_TYPE);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      double newSL;

      if(type == POSITION_TYPE_BUY && strongUp)
      {
         newSL = NormalizeDouble(ema20[1] - buf, digits);
         if(newSL <= sl + point || newSL >= sym.Bid() - stops) continue;
      }
      else if(type == POSITION_TYPE_SELL && strongDn)
      {
         newSL = NormalizeDouble(ema20[1] + buf, digits);
         if((sl > 0 && newSL >= sl - point) || newSL <= sym.Ask() + stops) continue;
      }
      else continue;

      if(trade.PositionModify(ticket, newSL, tp))
         PrintFormat("止损跟随 EMA20:ticket=%I64u %s → %s", ticket,
                     DoubleToString(sl, digits), DoubleToString(newSL, digits));
      else
         PrintFormat("移动止损失败 ticket=%I64u retcode=%u", ticket, trade.ResultRetcode());
   }
}

// 净额账户:价格到 TP1 时平掉一半
void ManagePartialTP1()
{
   if(isHedging) return;
   double tp1 = GVGet("tp1", 0);
   if(tp1 <= 0) return;

   if(CountPositions() == 0) { GVSet("tp1", 0); return; }   // 已出场,清掉

   int    dir  = (int)GVGet("dir", 0);
   double half = GVGet("half", 0);
   double px   = (dir > 0) ? sym.Bid() : sym.Ask();
   if(!((dir > 0 && px >= tp1) || (dir < 0 && px <= tp1))) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol)  continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(trade.PositionClosePartial(ticket, half))
      {
         Notify(StringFormat("%s 到达 TP1 %s,平仓 %.3f 手", _Symbol,
                             DoubleToString(tp1, (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS)),
                             half));
         GVSet("tp1", 0);
      }
      else
         PrintFormat("TP1 平半仓失败 retcode=%u", trade.ResultRetcode());
      break;
   }
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
   }
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
//| 工具                                                              |
//+------------------------------------------------------------------+
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

// 用终端全局变量保存少量状态,EA 重启/换周期后不丢
string GVName(string key)
{
   return "EMACD_" + _Symbol + "_" + IntegerToString(InpMagic) + "_" + key;
}
double GVGet(string key, double def)
{
   string n = GVName(key);
   return GlobalVariableCheck(n) ? GlobalVariableGet(n) : def;
}
void GVSet(string key, double v) { GlobalVariableSet(GVName(key), v); }

void Notify(string msg)
{
   Print(msg);
   if(!InpAlerts) return;
   if(!MQLInfoInteger(MQL_TESTER))
   {
      Alert(msg);
      SendNotification(StringSubstr(msg, 0, 255));   // 推送上限 255 字符
   }
}
//+------------------------------------------------------------------+

'@

$PRESET_DEFAULT = @'
; CryptoEmaMacdScalper —— 默认 preset(= EA 出厂参数,严格按系统规则)
; M5 · EMA20/50 · MACD(12,26,9) · 放量1.5x · 1.5R/2R · 每笔风险 1%
; 注意:尚未回测验证。先回测 + 模拟盘。
; 在 MT5:EA 属性 → 输入 → 加载 → 选本文件。
InpWhitelist=BTC,ETH,SOL,XRP,BNB,DOGE,ADA,TRX,AVAX,LINK
InpTimeframe=5
InpRiskPercent=1.0
InpMaxRiskPercent=2.0
InpDailyLossPct=4.0
InpMaxStopPct=1.5
InpMinStopSpreadX=3.0
InpSLBufferPct=0.05
InpSlippagePoints=50
InpFastEMA=20
InpSlowEMA=50
InpMacdFast=12
InpMacdSlow=26
InpMacdSignal=9
InpEmaCrossLookback=12
InpMacdCrossLookback=3
InpTouchTolPct=0.10
InpWickRatio=2.0
InpVolAvgBars=20
InpVolMult=1.5
InpUseRealVolume=false
InpSwingLookback=10
InpTP1R=1.5
InpTP2R=2.0
InpSingleTPR=1.5
InpTrailEMA20=true
InpTrendBars=5
InpChopLookback=36
InpMaxCrossesInChop=1
InpMinAvgVolume=0
InpMaxSpreadPct=0.06
InpUseCalendar=true
InpCalendarCurrencies=USD
InpNewsBeforeMin=30
InpNewsAfterMin=30
InpManualNews=
InpOneTradePerCross=true
InpMagic=20261003
InpAlerts=true
InpShowPanel=true

'@

$PRESET_DEFENSIVE = @'
; CryptoEmaMacdScalper —— 防守 preset
; 风险 0.5% · 当日熔断 2% · 放量要求 2x · 点差/止损过滤更严 · 新闻前后各 60 分钟
; 用在:模拟盘刚起步、监测器报 RETHINK、或行情剧烈(大新闻周)时。
; 在 MT5:EA 属性 → 输入 → 加载 → 选本文件。
InpWhitelist=BTC,ETH,SOL,XRP,BNB,DOGE,ADA,TRX,AVAX,LINK
InpTimeframe=5
InpRiskPercent=0.5
InpMaxRiskPercent=2.0
InpDailyLossPct=2.0
InpMaxStopPct=1.0
InpMinStopSpreadX=5.0
InpSLBufferPct=0.05
InpSlippagePoints=50
InpFastEMA=20
InpSlowEMA=50
InpMacdFast=12
InpMacdSlow=26
InpMacdSignal=9
InpEmaCrossLookback=12
InpMacdCrossLookback=3
InpTouchTolPct=0.10
InpWickRatio=2.0
InpVolAvgBars=20
InpVolMult=2.0
InpUseRealVolume=false
InpSwingLookback=10
InpTP1R=1.5
InpTP2R=2.0
InpSingleTPR=1.5
InpTrailEMA20=true
InpTrendBars=5
InpChopLookback=36
InpMaxCrossesInChop=1
InpMinAvgVolume=0
InpMaxSpreadPct=0.04
InpUseCalendar=true
InpCalendarCurrencies=USD
InpNewsBeforeMin=60
InpNewsAfterMin=60
InpManualNews=
InpOneTradePerCross=true
InpMagic=20261003
InpAlerts=true
InpShowPanel=true

'@

Write-Host '============================================================'
Write-Host '   Crypto EMA+MACD Scalper EA  --  Install into MT5'
Write-Host '============================================================'

$root = Join-Path $env:APPDATA 'MetaQuotes\Terminal'
$terms = @()
if (Test-Path $root) {
  $terms = Get-ChildItem $root -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'MQL5\Experts') }
}
if ($terms.Count -eq 0) {
  $out = Join-Path (Get-Location) 'CryptoEmaMacdScalper'
  New-Item -ItemType Directory -Force $out | Out-Null
  [IO.File]::WriteAllText((Join-Path $out 'CryptoEmaMacdScalper.mq5'), $EA, $utf8bom)
  [IO.File]::WriteAllText((Join-Path $out 'CryptoEmaMacd_default.set'), $PRESET_DEFAULT, $utf8bom)
  [IO.File]::WriteAllText((Join-Path $out 'CryptoEmaMacd_defensive.set'), $PRESET_DEFENSIVE, $utf8bom)
  Write-Host "[!] 没找到 MT5 数据文件夹(先打开 MT5 登录一次)。文件已写到: $out"
  Write-Host '    手动复制: MT5 -> 文件 -> 打开数据文件夹 -> MQL5\Experts'
  Read-Host '按回车退出'; exit 1
}

foreach ($t in $terms) {
  Write-Host "--- 终端: $($t.Name)"
  $experts = Join-Path $t.FullName 'MQL5\Experts'
  $presets = Join-Path $t.FullName 'MQL5\Presets'
  New-Item -ItemType Directory -Force $presets | Out-Null
  $mq5 = Join-Path $experts 'CryptoEmaMacdScalper.mq5'
  $ex5 = Join-Path $experts 'CryptoEmaMacdScalper.ex5'
  [IO.File]::WriteAllText($mq5, $EA, $utf8bom)
  [IO.File]::WriteAllText((Join-Path $presets 'CryptoEmaMacd_default.set'), $PRESET_DEFAULT, $utf8bom)
  [IO.File]::WriteAllText((Join-Path $presets 'CryptoEmaMacd_defensive.set'), $PRESET_DEFENSIVE, $utf8bom)
  Write-Host '    [1/2] EA + preset 已写入'

  $origin = Join-Path $t.FullName 'origin.txt'
  $me = $null
  if (Test-Path $origin) { $me = Join-Path ((Get-Content $origin -Raw).Trim()) 'metaeditor64.exe' }
  if ($me -and (Test-Path $me)) {
    if (Test-Path $ex5) { Remove-Item $ex5 -Force }
    $log = Join-Path $experts 'CryptoEmaMacdScalper.log'
    Start-Process -FilePath $me -ArgumentList "/compile:`"$mq5`"", "/log:`"$log`"" -Wait -NoNewWindow
    if (Test-Path $ex5) { Write-Host '    [2/2] 编译成功' -ForegroundColor Green }
    else {
      Write-Host '    [2/2] 编译失败,日志如下(截图发给我):' -ForegroundColor Red
      if (Test-Path $log) { Get-Content $log }
    }
  } else {
    Write-Host '    [2/2] 没找到 MetaEditor:打开 MetaEditor -> 打开该 EA -> 按 F7'
  }
}

Write-Host '============================================================'
Write-Host '  [完成] 下一步:'
Write-Host '   1. MT5 导航器 -> 右键「EA交易」-> 刷新'
Write-Host '   2. 打开 BTCUSD 图表,周期切到 M5,把 CryptoEmaMacdScalper 拖上去'
Write-Host '   3. 输入 -> 加载 -> CryptoEmaMacd_default.set'
Write-Host '   4. 工具栏「算法交易」要是绿色'
Write-Host '  先回测 + 模拟盘。不构成投资建议。'
Write-Host '============================================================'
Read-Host '按回车退出'
