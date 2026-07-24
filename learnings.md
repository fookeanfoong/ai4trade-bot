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
