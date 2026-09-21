@echo off
REM ============================================================
REM  Copy this file to  binance_keys.bat  and fill in your keys.
REM  binance_keys.bat is gitignored -- it never gets committed.
REM
REM  DEMO (default): use a Binance SPOT TESTNET key from
REM  https://testnet.binance.vision  (fake money, no risk).
REM ============================================================
set BINANCE_API_KEY=PUT_YOUR_TESTNET_API_KEY_HERE
set BINANCE_API_SECRET=PUT_YOUR_TESTNET_API_SECRET_HERE
set BINANCE_PAPER=true

REM --- Optional: what to trade and how fast (remove REM to turn on) ---------
REM  Trade BTC instead of ETH (BTC also stays the market-regime reference):
REM set CRYPTO_SYMBOLS=BTC
REM  "kuai jin kuai chu" fast-scalp preset: 5-min bars, 5-min cycle, quick exits:
REM set SCALP_MODE=fast

REM ------------------------------------------------------------
REM  GOING LIVE (real money) -- ONLY after the testnet demo works.
REM  Use a REAL binance.com key, then set both lines below:
REM     set BINANCE_PAPER=false
REM     set BINANCE_I_UNDERSTAND_REAL_MONEY=yes
REM ------------------------------------------------------------
