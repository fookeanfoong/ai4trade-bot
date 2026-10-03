@echo off
cd /d "%~dp0"
call crypto_monitor_config.bat
echo Reading MT5 Crypto EA trades and checking strategy health ...
echo (Make sure MT5 is open and logged in.)
echo.
if not exist reports mkdir reports
python mt5_bridge.py
echo.
echo ------------------------------------------------------------
echo  Report : reports\crypto_health.md
echo  Alert  : reports\crypto_alert.txt
echo  Presets: presets\crypto\  - default.set / defensive.set
echo ------------------------------------------------------------
pause
