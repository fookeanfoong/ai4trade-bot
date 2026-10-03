@echo off
REM ============================================================
REM  Settings for the Crypto EA monitor. Reuses mt5_bridge.py / gold_health.py
REM  but points them at CryptoEmaMacdScalper (magic 20261003) and separate files.
REM  Telegram token / chat id are shared with the gold monitor: monitor_config.bat
REM ============================================================
call "%~dp0monitor_config.bat"
set GOLD_MAGIC=20261003
REM  * = any symbol traded by this EA's magic. Or list exact names: btcusd,ethusd
set GOLD_SYMBOLS=*
set GOLD_JOURNAL_FILE=crypto_journal.json
set GOLD_ALERT_FILE=reports\crypto_alert.txt
set GOLD_HEALTH_OUT=reports\crypto_health.md
REM  Fallback stop (price units) only used if an order's SL cannot be read
set NOMINAL_STOP_USD=300
