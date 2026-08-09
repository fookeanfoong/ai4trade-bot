# ai4trade-bot

Autonomous NASDAQ **simulated** trading bot for [ai4trade.ai](https://ai4trade.ai).
Runs on **GitHub Actions** — GitHub's servers, on a cron schedule. **Your PC can be
off and this app closed.** It trades only during real US market hours (the platform
enforces this server-side too).

## What it does each run

1. Skips if the US market is closed.
2. Reads its ledger (`state.json`) and appends live prices (`price_history.json`).
3. Manages open positions:
   - **hard −5% stop-loss** (your rule),
   - +6% take-profit,
   - trend-break exit on negative momentum.
4. Opens up to **5** positions from an aggressive watchlist (NVDA, TSLA, AMD, MSTR,
   COIN, PLTR, SMCI, MARA) on positive momentum. Total budget **$100** (~$20/name).
5. Writes a daily report in `reports/YYYY-MM-DD.md`.
6. Near close, writes a "lesson learned" in `learnings.md` and **nudges its own
   strategy parameters** (`params.json`) based on the day's wins/losses.

State is committed back to the repo each run, so it persists across the stateless runner.

> Reality check: the $400/week target on $100 is ~400% weekly — not achievable. This
> aims for the best aggressive return it can and logs honestly when it loses.

## Crypto twin (24/7)

There's a parallel **crypto scalping** book (BTC/ETH/SOL/...) that runs 24/7 on
the 5-minute timeframe (RSI / Bollinger Bands / volume / support-resistance),
alongside this stock bot. It shares the same execution engine and Alpaca account
without touching the stock state. See **[SETUP_CRYPTO.md](SETUP_CRYPTO.md)**.

## Forex module (EUR/USD, signals only)

A third, fully separate book: **OANDA + EUR/USD H4**, sized for a **$200** account.
It codifies two setups — trend-following breakout-retest long, and counter-trend
double-top short — and emits a signal only when a trigger **and** at least two
confirmations line up. Everything else is `wait`.

It **generates signals, it does not place orders.** Run it on a practice account
for 20+ signals before wiring execution. Why OANDA and not any MT5 broker: OANDA
sizes in *units* (1 minimum), so a 1% risk on $200 is actually expressible — at a
0.01-lot minimum it is not. See **[SETUP_FOREX.md](SETUP_FOREX.md)**.

## One-time deploy (~5 min)

1. Create a **new GitHub repo** (private is fine), e.g. `ai4trade-bot`.
2. Upload every file in this folder (keep the `.github/workflows/` path intact).
   - CLI version:
     ```bash
     cd ai4trade-bot
     git init && git add -A && git commit -m "init"
     git branch -M main
     git remote add origin https://github.com/<you>/ai4trade-bot.git
     git push -u origin main
     ```
3. In the repo: **Settings -> Secrets and variables -> Actions -> New repository secret**
   - Name: `AI4TRADE_TOKEN`
   - Value: your ai4trade token (in `ai4trade-credentials.txt` — **do NOT commit that file**)
4. **Actions** tab -> enable workflows if prompted -> open **ai4trade-bot** ->
   **Run workflow** once to test (it will skip if the market is closed).

Done. It now runs automatically on US trading days.

## Watch it / stop it

- Reports + journal appear in the repo (`reports/`, `learnings.md`) after each run.
- Live positions: also visible on ai4trade under your account.
- **Stop:** Actions tab -> ai4trade-bot -> `...` -> Disable workflow.

## Notes

- Cron times in `trade.yml` are UTC, mapped for **EDT (summer)**. In winter (EST),
  add 1 hour to each — or just leave it; the bot gates on real market hours anyway.
- GitHub disables scheduled workflows after 60 days of no repo activity (irrelevant
  for a 1-week test).
- Change budget: edit `BUDGET_USD` in `.github/workflows/trade.yml`.
