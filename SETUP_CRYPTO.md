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
- **Net-return target** (`NET_PROFIT_MODE=yes`): one exit, priced at a
  **return after fees**, not a raw percentage. See below.
- **Crash circuit breaker**: a fast-drop guard on top of the per-name stops.

## Net-dollar target (why raw percentage targets failed)

The first 12 crypto trades averaged **$0.14** each — five of them netted under
$0.10. A +0.6% target is +0.6% *gross*, and Alpaca's ~0.25% per-side taker fee
takes ~0.5% of the round trip. Most of those "wins" were losses after costs.

So the exit is stated as the number that actually matters: **how many dollars
land in the account after both sides' fees**. For a position of notional `V`
and fee rate `f` per side, the gross move `g` that nets `N` dollars is:

```
net = V*g - V*f*(2+g)     =>     g = (N + 2*f*V) / (V * (1-f))
```

### Each coin picks its own point in the band

The target is a **range**, `NET_TARGET_MIN_USD`..`NET_TARGET_MAX_USD`
($0.50–$1.00), not one fixed number. Each coin's place in it comes from its own
Bollinger width as a fraction of price — a quiet coin takes the floor and banks
it, a volatile one holds out for more:

| BB width | Net target | Meaning |
|---|---|---|
| ≤ `VOL_SPAN_LO` (1.5%) | $0.50 | dead tape — take the floor |
| between | linear | |
| ≥ `VOL_SPAN_HI` (5%) | $1.00 | volatile — ask for more |

Worked example at `f=0.25%`, ~$50 a name:

| Coin | BB width | Net target | Gross needed | Stop | Realized net |
|---|---|---|---|---|---|
| BTC | 1.2% | $0.50 | +1.50% | 1.50% | **+$0.5000** |
| ETH | 2.5% | $0.64 | +1.79% | 1.79% | **+$0.6430** |
| XRP | 3.5% | $0.79 | +2.08% | 2.08% | **+$0.7862** |
| DOGE | 6.0% | $1.00 | +2.51% | 2.51% | **+$1.0004** |

### Position size sets the difficulty

Unlike a percentage target, a dollar target gets **harder as the book splits
thinner** — the same $0.50 is a bigger fraction of a smaller position:

| Names | Notional each | Move for $0.50 | Move for $1.00 |
|---|---|---|---|
| 1 | $200 | 0.75% | 1.00% |
| 2 | $100 | 1.00% | 1.50% |
| 3 | $67 | 1.25% | 2.00% |
| **4** | **$50** | **1.50%** | **2.51%** |
| 5 | $40 | 1.75% | 3.01% |

`MAX_POSITIONS=4` is chosen here: at 5 names the $1.00 target needs a 3.0% move
inside a 5-minute bar, which mostly means sitting in trades that never finish.

### Price precision

Target prices are rounded **up** to the coin's tick (`ceil_price`), never
nearest. Rounding a target down silently shaves the net below the promised
floor, and the coins where that bites are the many-decimal ones: at $1.03, XRP
would lose ~0.01% of the round trip to a downward round. Rounding up can only
overshoot, never undershoot.

### Consequences

- **One target, full exit.** Positions carry `single_exit`, so the T1 half-sell
  is skipped — the whole position closes at the target rather than leaving half
  exposed above it. Each trade ends at target or at stop.
- **The stop tightens to match the target** (`MIN_RR_NET=1.0`). This matters:
  the signal layer computes R:R against its *technical* target (often +3%), but
  the engine now exits at 1.5%–2.5%. Capping stop distance at target distance
  keeps every trade at least 1:1. The trade-off is a tighter stop, so expect
  more stop-outs.
- **The trailing stop arms at the target**, not at the default +0.4%. That
  0.4% arm was what closed positions below fee cost.
- **Trades needing more than `MAX_TARGET_MOVE_PCT` (3.5%) are skipped** as
  unreachable rather than opened and left hanging.

## Crash circuit breaker

Crypto drops without warning (the BTC-to-$30k kind). Day-change alone finds out
too late — mid-flush the day figure can still be green. So the guard reads three
faster signals off BTC, any one of which halts new entries:

| Trigger | Threshold | Action |
|---------|-----------|--------|
| BTC off its 4h high | ≥ 3% | `risk_off` — no new entries |
| BTC 1-hour drop | ≥ 2.5% | `risk_off` — no new entries |
| BTC day drop | ≥ 4% | `risk_off` — no new entries |
| BTC off 4h high **or** day drop | ≥ 7% | `panic_flatten` — **close everything** |

A single coin that has fallen ≥6% off its own 4h high is skipped individually
(no catching that knife) even when BTC looks fine. Panic-flatten runs *before*
position management, dumps every open name at market, and benches them all for
the rest of the day.

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
