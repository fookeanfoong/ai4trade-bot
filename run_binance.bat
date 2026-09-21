@echo off
cd /d "%~dp0"

REM --- Load your Binance API keys -------------------------------------------
REM Copy binance_keys.example.bat to binance_keys.bat and put your key inside.
if exist binance_keys.bat (
    call binance_keys.bat
) else (
    echo.
    echo  [!] binance_keys.bat not found.
    echo      Copy binance_keys.example.bat to binance_keys.bat, put your
    echo      Binance TESTNET API key inside, then double-click this again.
    echo.
    pause
    exit /b 1
)

REM --- Install deps on first run (safe to re-run) ---------------------------
python -m pip install --quiet -r requirements-binance.txt

echo.
echo  Binance local runner. KEEP THIS WINDOW OPEN to keep trading.
echo  Close it (or press Ctrl+C) to STOP. Nothing trades while it is closed.
echo.
python run_binance_local.py %*

echo.
echo ------------------------------------------------------------
echo  Runner stopped. If a position is still OPEN, flatten it:
echo     python run_binance_local.py --flatten --once
echo ------------------------------------------------------------
pause
