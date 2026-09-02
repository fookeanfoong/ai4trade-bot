@echo off
chcp 65001 >nul
cd /d "%~dp0"
call monitor_config.bat
echo 正在读取 MT5 黄金 EA 的成交,判断策略健康 ...
echo (确保 MT5 已打开并登录,否则会提示连不上)
echo.
python mt5_bridge.py
echo.
echo ------------------------------------------------------------
echo  详细报告: reports\gold_health.md
echo  需要动作时的提醒: reports\gold_alert.txt
echo ------------------------------------------------------------
pause
