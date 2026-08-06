# Crypto twin (24/7 BTC/altcoin scalper)

This is a parallel **crypto scalping** book that runs alongside the stock bot and
never touches its state. It reuses the same execution engine (`live_trader.py`) —
the crypto side is selected entirely through environment variables, so there's no
forked copy of the trading logic to keep in sync.

## The method (automated BTC scalping)

It automates the Xynth/ChatGPT "BTC scalper" flow — but with **pulled data
instead of chart screenshots**, and **real risk-sizing instead of "deploy the
entire capital"**:

1. **Data** — `quotes_crypto.py` pulls the **5-minute** BTCUSD (and alt) series
   for the last few hours and computes the indicators a scalper reads off the
   chart: **RSI(14)**, **Bollinger Bands(20,2)** + %B, **EMA9 vs EMA21** trend,
   **volume ratio**, and recent **support / resistance**.
2. **Setups** — `generate_signals_crypto.py` turns those technicals into clean
   **long-only** scalp setups:
   - **Oversold bounce**: RSI oversold + price at/below the lower band, hugging
     support, with volume → bounce toward mid/upper band.
   - **Trend pullback**: EMA9 > EMA21 uptrend + pullback to the mid band, not
     overbought → continuation toward the upper band / resistance.
   - **No-chase**: RSI ≥ 68 or %B ≥ 0.85 → never open a new long at the top.
   - **R:R filter**: setups whose reward(to T2):risk is below 1.2 are dropped.
   - **Say-so**: if nothing qualifies, it writes zero signals and stands aside.
   Each setup carries its own `stop_pct` (just below support), `t1_pct`, `t2_pct`
   and R:R — the shared engine executes them and manages stop / T1(half) / T2 /
   trailing per position.

## Pieces

| File | Role | Stock counterpart |
|------|------|-------------------|
| `quotes_crypto.py` | 5m BTC/ETH/SOL/... technicals from Yahoo → `quotes_crypto.json` (+`.md`) | `quotes.py` |
| `generate_signals_crypto.py` | 5m long-only scalp setups → `signals_crypto.json` | `generate_signals.py` |
| `broker_alpaca_crypto.py` | Alpaca **crypto** adapter (`BTC/USD`, GTC, long-only) | `broker_alpaca.py` |
| `live_trader.py` | **Shared** engine — env-driven | (same file) |
| `.github/workflows/trade_crypto.yml` | 24/7 GitHub Actions schedule (every 5 min) | `trade.yml` |
| `live_trader_crypto_state.json` | Crypto ledger (committed) | `live_trader_state.json` |
| `reports/live_trader_crypto/` | Daily crypto reports | `reports/live_trader/` |

## How it differs from the stock book

- **24/7 / 5-minute**: `MARKET_24_7=yes` skips the weekday + market-hours gate;
  the workflow runs every 5 min to match the 5m analysis timeframe.
- **Regime = BTC**: `REGIME_SYMBOLS=BTC`. If BTC is down more than
  `regime_max_drop_pct` on the day, no new longs open (risk-off guard).
- **Long only**: Alpaca crypto has no shorting, so `ENABLE_SHORT=no` and the
  generator never emits shorts.
- **Cash only**: `LEVERAGE_CAP=1.0` (Alpaca crypto is non-marginable), so total
  exposure stays within the book.
- **Dynamic scalp stops**: the stop is placed just below the setup's support
  (clamped to 0.4%–3%), not a fixed percentage — tight, chart-based risk.

> **Not "all-in".** The referenced prompt says to *deploy the entire capital* and
> *never refuse* — this book ignores both. Every scalp is risk-sized with a real
> stop, and it says "no trade" when the tape is bad. That's the difference between
> scalping and donating.

## Run it

It uses the **same** `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY` secrets as the
stock bot (same Alpaca account, paper by default). No new secret needed. Once the
key is set:

1. **Actions** tab → **ai4trade-bot-crypto** → **Run workflow** to test.
2. It then runs every 15 minutes, 24/7.

### Try it locally (dry-run, no orders, no keys needed)

```bash
python quotes_crypto.py
python generate_signals_crypto.py
MARKET_24_7=yes REGIME_SYMBOLS=BTC \
  SIGNALS_FILE=signals_crypto.json QUOTES_FILE=quotes_crypto.json \
  STATE_FILE=live_trader_crypto_state.json REPORTS_SUBDIR=live_trader_crypto \
  LEVERAGE_CAP=1.0 ENABLE_SHORT=no \
  python live_trader.py --dry-run
```

## Going live (real money)

Same double-lock as the stock bot: set `ALPACA_PAPER=false` **and**
`ALPACA_I_UNDERSTAND_REAL_MONEY=yes`, with **live** Alpaca keys. Prove it on the
paper book first. These are algorithmic heuristic signals, not analyst calls, and
crypto is more volatile than stocks — this is not investment advice.
