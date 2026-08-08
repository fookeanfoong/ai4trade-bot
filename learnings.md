# Learning journal

## 2026-07-06
- Trades: 0 (0W / 0L, WR 0%)
- Exits: 0 STOP, 0 TRAIL, 0 TP, 0 NEWS
- Avg win: $+0.00
- Realized today: $+0.00 | cumulative: $+0.00
- Consec losses now: 0
- Lessons:
  - net +0.00$, 0W/0L, WR 0% -> params held

## 2026-07-06
- Trades: 0 (0W / 0L, WR 0%)
- Exits: 0 STOP, 0 TRAIL, 0 TP, 0 NEWS
- Avg win: $+0.00
- Realized today: $+0.00 | cumulative: $+0.00
- Consec losses now: 0
- Lessons:
  - net +0.00$, 0W/0L, WR 0% -> params held

## 2026-07-07
- Trades: 2 (0W / 2L, WR 0%)
- Exits: 0 STOP, 0 TRAIL, 0 TP, 2 NEWS
- Avg win: $+0.00
- Realized today: $+0.00 | cumulative: $+0.00
- Consec losses now: 2
- Lessons:
  - net +0.00$, 0W/2L, WR 0% -> params held
  - 2 news-driven exits — keep monitoring headline signal

## 2026-07-09
- Trades: 3 (0W / 3L, WR 0%)
- Exits: 0 STOP, 0 TRAIL, 0 TP, 0 NEWS
- Avg win: $+0.00, avg loss: $-0.38, payoff 0.00x
- Realized today: $-1.14 | cumulative: $-2.33
- Consec losses now: 6
- Lessons:
  - net -1.14$, 0W/3L, WR 0% -> params held

## 2026-07-18 — Pre-open freshness + sudden-crash regime guard (encoded)
- Context: user's rule "资讯最好是根据开始前的为准", citing the day the Korean
  market suddenly crashed. Lesson: a decision made the night before can be wrong
  by the open. Two failure modes to defend against:
  1. Stale signal fires blindly the next morning even though the world changed.
  2. Buying into a broad risk-off / gap-down open (a Korea/DeepSeek-style crash).
- Encoded as CODE (not memory) in both live_trader.py and signal_sim.py:
  - **Signal expiry**: signals.json carries `valid_for`; once past, the signal
    is treated as expired and NEVER fires until refreshed pre-open. Safe default
    is "don't trade a stale signal."
  - **REGIME guard**: skip new longs if the broad market (SPY) is down more than
    `regime_max_drop_pct` (default 2%) on the day; symmetric for shorts on a rip.
    Uses live quotes.json refreshed premarket + every 10 min, so it reacts to the
    actual open, not yesterday's view.
  - **Premarket refresh routine**: a scheduled wake re-reads the latest news and
    rewrites signals.json before the open, so the trade uses pre-open info.
- Also: flagged bad data (VLO/MPC/PSX showed +27–29% single-day = implausible for
  large refiners) and refused to build signals on those names. Price sanity first.
- Market backdrop 7/17 close: rotation OUT of semis (SOX bear market, "DeepSeek
  moment", NFLX -11%) INTO energy (Hormuz truce collapsed, WTI ~$82 / Brent ~$88,
  oil +12% on the week). Candidate for 7/20: XOM long, conf 0.62, event-driven so
  requires_preopen_recheck=true (a ceasefire would reverse it violently).

## 2026-07-19 — Strategy review: why 0W/9L, and the fixes (see STRATEGY_REVIEW.md)
- Reviewed all 11 closed trades in state.json: 0W / 9L / 2 breakeven, net -$4.17.
  0% win rate is systematic, not variance. Root causes, all code-grounded:
  1. **Whipsaw**: 10-min cadence + momentum_lookback=2 (~20 min) + entry +0.3% /
     exit -0.4% => buy tiny blip, sell tiny dip. 4 of 11 exits were -0.14%..-0.31%
     TREND-BREAK noise.
  2. **No trend/regime filter on entry** — bought AMD/AVGO (semis) straight into a
     semis bear market the journal itself had flagged.
  3. **Correlated watchlist** (2 semis + 2 crypto-proxies + 1 high-beta) => all stop
     together on risk-off (AMD+AVGO same day 7/9 and 7/13).
  4. **Fast re-entry** (cooldown 3 runs ≈ 30 min) => AMD stopped 3x in a week.
  5. **Winners strangled**: trend-break exit cut positions before they could reach
     +6% TP.
- **BUG found & fixed**: reflect_and_learn() counted only reason=="STOP", but real
  stops are logged "GR-STOP" => the daily self-tuner never saw the losses and held
  bad params every day. Now counts both.
- Fixes (params.json + bot.py, hard -5% stop untouched): lookback 2->6, entry
  +0.3%->+0.8%, exit -0.4%->-1.2%, added SMA(12) uptrend filter on entry, trend-break
  now only fires when the position is losing (protect winners), and a stopped name is
  benched for the rest of the day (no falling-knife re-entry).
- HONEST: these remove self-harm, but do NOT guarantee profit. Must forward-test on
  the sim for 2-4 weeks before charging users or trading real money. If still shaky,
  pivot the product to "transparent research/learning tool", not "we make you money".

## 2026-07-20
- Trades: 2 (0W / 2L, WR 0%)
- Exits: 1 STOP, 0 TRAIL, 0 TP, 0 NEWS
- Avg win: $+0.00, avg loss: $-1.09, payoff 0.00x
- Realized today: $-2.18 | cumulative: $-6.34
- Consec losses now: 13
- Lessons:
  - net -2.18$, 0W/2L, WR 0% -> params held


## 2026-07-24 — Alpaca paper Week 1 review (real-execution) — 3W/0L, +$18.34 (+9.2% on $200 book)
- Closed exits: CVX +$6.37 (signal-invalidation into strength), OXY +$5.99 (T1 half) + $5.99 (trailing lock). All 3 green. NVDA still open (~flat).
- Win rate 100% (3/3), net realized +$18.34, account +$18 (+9.2% on the $200 logical book). Health: system clean — entries/exits fired every day via the open-kick, 0 broker/data errors, 0 failed orders, quotes errors {} across 28 runs.
- What worked:
  1. Disciplined EXITS: OXY T1 half-out + trailing lock captured +3% without round-tripping; CVX signal-invalidation booked the gain cleanly. Locking > hoping.
  2. NO-CHASE earned its keep: kept me out of AMD (+8–11%/3d) two days running; AMD then went ~flat on its Advancing-AI conference day ("sell the rumor"), so skipping it for OXY was the better P&L. Also dropped JPM's unexplained 4-day/+4.7% gap into a new-tariff Friday.
  3. CONVICTION-BASED COUNT worked: sized just 1 slice ($133) for a single-name NVDA day instead of padding to 3; sat mostly in cash on the murky AI-worry days.
- HONEST caveat: returns were FLATTERED by a strong trending week — energy ripped on the Iran/Hormuz oil spike and CVX/OXY rode it. The discipline was sound but +9%/week is NOT a repeatable baseline; it's regime-dependent. Sample is tiny (2–3 positions). Do NOT extrapolate.
- CHANGE: none. Results fine + sample far too small to tune; adjusting thresholds on a 3-win streak would overfit. Keep the discipline, accumulate trades. Still targeting 4 weeks / 20+ trades / net-positive / no data errors before any real-money talk. Paper only.

## 2026-07-26 — External-tools review (LEAN / quant-terminal demos): adopt ideas, not platforms
- ADOPTED (live in code since 21bb9f8): stock-split guard in live_trader.py reconcile() —
  confirms a split from the broker SHARE-COUNT change (a real crash never multiplies your
  share count) and rescales entry/stop/T1/T2, preventing a false catastrophic stop on a held
  name. The one corporate-action idea worth borrowing from heavyweight engines like LEAN.
- DEFERRED — MUST DO BEFORE ANY REAL-MONEY GO/NO-GO: haircut paper results by realistic
  slippage+fees (~0.1%/round trip) when judging whether the system is truly net-positive.
  Not added now: Alpaca paper fills are already non-ideal, layering a second haircut today
  would double-count. This line item exists so the weekly review does not forget it.
- REJECTED: migrating to LEAN (a $200 cloud bot on free GitHub Actions would be crushed by
  its ops complexity — simplicity IS the edge here) and cosmetic "quant terminal" dashboards
  (pretty numbers ≠ edge; EV = win%×odds −(1−win%) discipline is already encoded in our
  stops/targets/sizing). Built a clearly-labeled demo terminal for the user as a teaching
  toy; it is NOT part of the trading system.

## 2026-07-31 — Alpaca paper Week 2 review — net +$0.69 (1W/2L), discipline held through a chaotic tape
- HEALTH: system clean. 25 runs Mon–Fri, entries/exits fired every day via the open-kick, 0 broker/data errors, quotes errors {} all week, runs updating through Fri close. Nothing broken.
- Closed this week: NVDA -$2.04 (trail-lock, weekend gap on the Korea semis breakdown — a laggard cut, not a bad entry), JPM -$0.78 (deliberate flat before the FOMC, ~breakeven), CVX +$3.50 (Mideast/Hormuz oil supply-shock long, banked near T1 before the weekend). NET +$0.69.
- WHY the two losses — NOT a param failure: NVDA was a carried-over laggard cut on a genuine sector breakdown (Korea/China-DUV semis crash); JPM was a deliberate risk-management exit before a binary Fed. Neither was chop-between-stop-and-T1, wrong-regime, or a chased entry. The losers were tiny (-$2.04, -$0.78) and the winner (+$3.50) more than covered them — that's the payoff shape we want (small losses, bigger wins).
- WHAT WORKED (process, regime-dependent so don't extrapolate):
  1. Guards earned their keep in a two-crisis week: no-chase kept us out of AMD (which was down 9%→18%/3d); regime-awareness kept us defensive through the Korea semis crash; flat-into-Fed and flat-into-weekend avoided two un-manageable binary events.
  2. Energy long re-engaged ONLY when the catalyst flipped back (Mideast escalation, oil supply shock) AND 3d wasn't extended (CVX 3d ~flat, round-tripped Monday's crash) — symmetric with sitting out energy on Monday's oil crash. Consistent logic, not hindsight.
  3. Banking CVX before the weekend captured +$3.50 (rallied to ~T1 at the open) AND removed un-manageable weekend headline risk. Locking > hoping.
- HONEST cost of the discipline: skipping the AMD short (no-chase) missed a would-be winner (AMD fell another ~8%). Stand by the rule (protects against squeezes on average); one favorable instance is not a reason to loosen no-chase. Logged, no change.
- CHANGE: NONE. Only 3 closed trades this week (~6 since inception) = far too small to tune; the losses were deliberate/well-managed, not systematic; net positive. Adjusting generate_signals/live_trader thresholds on this would be overfitting. Keep the discipline, accumulate trades.
- GATE to any real-money talk: still 2 of 4 weeks, ~6 of 20+ trades, net-positive (+$19.0 cumulative), 0 data errors. Nowhere near ready — keep paper. Cumulative +$19.0 is still FLATTERED by Week 1's energy trend; Week 2 being ~flat in a Korea-crash + Fed + Mideast tape (survived with a small gain, no blowup) is the more honest read of the process.

## 2026-08-07 — Week 3 review + PIVOT: stock book PAUSED, crypto book is now the active trader
- OWNER CHANGE (not broken — intentional): the stock book's schedule + .trigger push are commented out in trade.yml ("PAUSED … the crypto book now trades the ai4trade.ai platform and is the only scheduled trader"; workflow_dispatch stays live for manual runs). So the market-open kick is now a no-op for stocks. Respect it — do not re-enable.
- STOCK book, final week (8/3-8/7): 1 trade — JPM +$1.50 (8/4, trail-lock). Sat out 8/3 (Mideast de-escalation reversed energy), 8/5 (record-high but RSI 74.5 overbought — validated, tech pulled back Wed), 8/6 (melt-up stalled), 8/7 (shock jobs report -23k vs +80k exp = binary/volatile). Net +$1.50. Cumulative +$20.53 over 7 legs, 0 broker/data errors all 3 weeks.
- HONEST verdict on the stock book's 3 weeks: +$20.53 (~+10% on the $200 logical book) is FLATTERED almost entirely by Week 1's energy trend (+$18.34 on the Iran/Hormuz oil spike). Weeks 2-3 were +$0.69 and +$1.50 — essentially flat. The disciplined read: the strategy AVOIDED losses well (no blow-ups; sat out Fed/overbought/jobs-shock correctly) but did NOT generate a repeatable edge beyond one lucky trending week. That's a fair reason the owner is exploring crypto. Sample still tiny; nothing proven either way.
- CRYPTO book (owner-built, now active on Alpaca crypto paper via ai4trade.ai): this week 24 legs, net +$3.23, 17/24 wins (71%). Churny (24 trades in days) — the owner already addressed the "fees eat tiny gains" problem (5 of the first 12 nets were < $0.10) by switching to fee-aware net-DOLLAR targets (only take a trade if, after both-side fees, $0.50-$1.00 lands), tightening stops to >=1:1 net RR, plus a PDT guard (hold overnight to dodge the <$25k 3-day-trade limit) and a run-winners trailing option. Sound fixes. Still new/tiny sample — do not extrapolate 71%.
- CHANGE by me: NONE. The owner is actively developing the crypto book; my conservative weekly-tuner role defers to that. Stock params untouched (book paused anyway). Documented the pivot here.
- STILL PAPER on both books. The real-money gate (4 weeks / 20+ trades / net-positive / no data errors) is not met on either as a standalone proven system — keep simulating.

## 2026-08-08 — 把「四步波段流程」从提示词编成代码 (SWING_PLAYBOOK.md)
- 起因:owner 给了一套常见的 4 步波段流程(system prompt → 选股 → 图表分析 → 出交易方案)。
  提示词的问题是每次都要重讲、结果不可复现、也无法回溯。所以落成代码:
  `swing_history.py`(runner 上抓 1 年日线)+ `swing_analysis.py`(筛选/评分/出方案)。
- 编码的规则(都能追溯到本仓库的旧教训,不是抄来的):
  1. **ADX 必须比 5 天前更高** —— 原流程只说「early signs of trend strength」,
     没给可执行阈值。ADX 在升 = 趋势刚起来;ADX 在降 = 趋势已经走完,这正是
     0胜9负那一批「买在动能末端」的翻版。
  2. **不追高闸门**:距 SMA20 超过 2.5×ATR 就出局 —— Week 1 的 no-chase 规则复用。
  3. **regime 读数**(SPY 对 50/200 日线)直接写进报告头部,risk-off 就写明空仓观望 ——
     对应「在半导体熊市里买漂亮的半导体图」那一课。
  4. **严格档不足 5 只时才放宽 ATR 带,并在报告里用 `*` 标记为二线** ——
     宁可少给,也不为了凑够 5 只而假装筛出来了。
- 仓位数学的诚实结果:$1,000 账户 + 2% 风险($20)+ 4-5% ATR 的票 => 通常只买得起
  1-3 股,单笔盈利是几十美元级别。这不是 bug,是「小账户就该有小仓位」。想要更大
  仓位得先有更大账户,而不是把止损放宽。
- 验证:`swing_analysis.py --selftest` 用合成 K 线核对指标数学(SMA/EMA/RSI/ATR/ADX/MACD
  都有可手算的期望值),另外用 13 只合成标的跑通了全流程 —— 下跌趋势、低流动性、
  过闷、过野的标的都按预期被筛掉了。
- 边界:这套东西**不下单、不碰券商**,只出 markdown 研究报告。也**没有**前向验证过。
  上真钱的门槛不变:4 周 / 20 笔以上 / 净盈利 / 零数据错误。
