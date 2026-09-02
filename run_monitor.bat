@echo off
cd /d "%~dp0"
call monitor_config.bat
echo Reading MT5 Gold EA trades and checking strategy health ...
echo (Make sure MT5 is open and logged in.)
echo.
python mt5_bridge.py
echo.
echo ------------------------------------------------------------
echo  Report : reports\gold_health.md
echo  Alert  : reports\gold_alert.txt
echo ------------------------------------------------------------
pause
