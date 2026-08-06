# Crypto twin (24/7 BTC/altcoin paper trader)

This is a parallel **crypto** book that runs alongside the stock bot and never
touches its state. It reuses the same execution engine (`live_trader.py`) — the
crypto side is selected entirely through environment variables, so there's no
forked copy of the trading logic to keep in sync.

## Pieces

| File | Role | Stock counterpart |
|------|------|-------------------|
| `quotes_crypto.py` | Fetch BTC/ETH/SOL/... prices from Yahoo → `quotes_crypto.json` | `quotes.py` |
| `generate_signals_crypto.py` | 24/7 long-only momentum signals → `signals_crypto.json` | `generate_signals.py` |
| `broker_alpaca_crypto.py` | Alpaca **crypto** adapter (`BTC/USD`, GTC, long-only) | `broker_alpaca.py` |
| `live_trader.py` | **Shared** engine — env-driven | (same file) |
| `.github/workflows/trade_crypto.yml` | 24/7 GitHub Actions schedule | `trade.yml` |
| `live_trader_crypto_state.json` | Crypto ledger (committed) | `live_trader_state.json` |
| `reports/live_trader_crypto/` | Daily crypto reports | `reports/live_trader/` |

## How it differs from the stock book

- **24/7**: `MARKET_24_7=yes` skips the weekday + market-hours gate.
- **Regime = BTC**: `REGIME_SYMBOLS=BTC`. If BTC is down more than
  `regime_max_drop_pct` on the day, no new longs open (risk-off guard).
- **Long only**: Alpaca crypto has no shorting, so `ENABLE_SHORT=no` and the
  signal generator never emits shorts.
- **Cash only**: `LEVERAGE_CAP=1.0` (Alpaca crypto is non-marginable), so total
  exposure stays within the book.
- **Wider bands**: crypto is more volatile, so the default stop/T1/T2 are
  `3% / 4% / 8%` (vs `2.5% / 3% / 6%` for stocks).

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
