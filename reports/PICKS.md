# Week of 2026-07-06 — Picks & Thesis

**Mandate:** $100 sim capital, US NASDAQ, aggressive, up to 5 names, hard −5% stop-loss.
**Author:** research pass 2026-07-04 (Sat, market closed) — Claude, working as head of options research.

## Macro backdrop

- ai4trade macro verdict: **bullish** (3/5 signals risk-on, as of 2026-06-22).
- BTC ETF flow: leaning **outflow** (headwind for MSTR/COIN).
- Q2 earnings season starts week of Jul 14 (banks first, mega-cap tech Jul 22–30).
- **None of my 5 picks report during the target week (Jul 6–10)** — so no binary earnings-print risk. Moves come from momentum, macro, and stock-specific catalyst continuation.

## The picks

### 1. AMD — strongest technical + fundamental combo
- **ai4trade signal:** `buy`, score 3.5, trend **bullish** (as of 2026-06-18).
- Above 20-day MA ($501.86) **and** 60-day MA ($377.98). +10.02% / 5d, +20.06% / 20d.
- Catalyst: Meta committed up to **6 GW of Instinct GPUs** — real hyperscale validation of MI300.
- Risk: near resistance $547.26 — a reject here is our stop trigger.

### 2. PLTR — freshest catalyst momentum
- +7.77% on Jul 1, closed $125.73.
- Two live catalysts in one week: **U.S. Army NGC2** picked Foundry as core data layer; **NVIDIA sovereign-AI partnership** (Nemotron on secure gov infra).
- Q1 revenue +85% YoY, ~84% gross margin. Growth acceleration story intact.
- Risk: crowded, high-beta on any AI-narrative wobble.

### 3. MSTR — leveraged BTC + capital-plan re-rating
- +11.81% on Jul 1 after **new Digital Credit Capital Framework**: $1B common buyback + $1B DCS buyback + selective BTC monetization.
- Citi reiterated **Buy, $260 target**.
- Holdings: 847,363 BTC (~$64.1B cost basis).
- Risk: BTC ETF flows negative in ai4trade macro snapshot — this is the highest-vol name in the basket. −5% stop will trigger easily here; that's intended.

### 4. AVGO — constructive ballast
- ai4trade `hold`, score 1.0, **constructive** trend.
- Above 60-day MA, +6.69% / 5d, resistance far ($481.57 vs price $411.35).
- Function in basket: AI-infra exposure with lower single-stock vol; damps portfolio drawdown when the beta names correct.

### 5. COIN — crypto beta w/o MSTR concentration
- Directly correlated to BTC/ETH but with equity-market discovery.
- Hedges the "BTC up but MSTR premium compresses" scenario.
- Same downside vector as MSTR — if BTC breaks, both stop out together. Sized $20 accepts this.

## What I deliberately skipped

- **NVDA** — ai4trade `watch` (score 0), below 20-day MA, next earnings **Aug 26** (no near catalyst). Consolidating $180–210.
- **TSLA** — `watch`, −7.5% on Jul 3 despite Q2 delivery **beat** by 74k units = classic sell-the-news. Earnings Jul 22 outside window. Wait for post-print direction.
- **SMCI, MARA** — too small, too correlated to existing exposure, and MARA is another BTC-miner overlap.

## How the bot will play these

1. **Monday open (~09:35 ET):** first market-open run seeds **equal-weight $20** into all 5. No momentum filter on day 1 — real desks get exposure then trade around it.
2. **Every subsequent run (~4x/day):** manage.
   - Hard −5% stop → sell + 3-run cooldown.
   - +6% take-profit → lock.
   - Negative-momentum trend break → exit.
3. **Near close (~15:50 ET):** write daily report + `learnings.md` reflection + nudge `params.json`.
4. **stop_loss = −5% is a user rule, never auto-loosened.** Everything else is fair game for the learning loop.

## Honest expectations

- Target of $400/week on $100 = ~400%/wk. Not realistic.
- Realistic aggressive-basket weekly return band: roughly **−8% to +8%**, i.e. **−$8 to +$8** on $100. Any bigger positive number would be luck.
- If the whole basket stops out, worst case ≈ **−$25** (5 × $20 × 5% stop, ignoring slippage).

## Sources

- [NVDA (Yahoo)](https://finance.yahoo.com/quote/NVDA/)
- [TSLA sell-the-news (Motley Fool)](https://www.fool.com/investing/2026/07/03/tesla-beat-delivery-estimates-by-74000-vehicles-an/)
- [Q2 2026 earnings calendar (Plus500)](https://us.plus500.com/en/newsandmarketinsights/q2-2026-earnings-season)
- [MSTR capital plan (StocksToTrade)](https://stockstotrade.com/news/strategy-inc-mstr-news-2026_07_02-2/)
- [PLTR Army NGC2 + NVIDIA deal (Yahoo)](https://finance.yahoo.com/technology/ai/articles/palantir-technologies-pltr-nvidia-sovereign-211703928.html)
- [AMD H1 recap (TheStreet)](https://www.thestreet.com/investing/stocks/amd-advanced-micro-devices-stock-price-target-5-star-wells-fargo-analyst-aaron-rakers-june-2026)
- ai4trade `/api/market-intel/stocks/featured` (server-side signals)
