@echo off
cd /d "%~dp0"
echo ============================================================
echo    Gold EA Monitor  --  Install
echo ============================================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found.
  echo   Install Python 3.11+ from https://www.python.org
  echo   During install, TICK "Add Python to PATH", then run this again.
  echo.
  pause
  exit /b 1
)
for /f "delims=" %%v in ('python --version') do echo Found %%v
echo.
echo [1/2] Upgrading pip ...
python -m pip install --upgrade pip
echo.
echo [2/2] Installing MetaTrader5 library ...
python -m pip install -r requirements-mt5.txt
if errorlevel 1 (
  echo.
  echo [ERROR] Install failed. Screenshot the messages above and send to me.
  pause
  exit /b 1
)
echo.
echo ============================================================
echo    [DONE] Installed. Next:
echo      1. Open MT5, log in, attach the Gold EA to an XAUUSD chart
echo         (Tools - Options - Expert Advisors - Allow Algo Trading)
echo      2. Double-click  run_monitor.bat  to test
echo      3. To auto-schedule: right-click schedule_monitor.bat
echo         and choose "Run as administrator"
echo ============================================================
pause
