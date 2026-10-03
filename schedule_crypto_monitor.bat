@echo off
cd /d "%~dp0"
echo ============================================================
echo    Schedule the Crypto EA monitor to run every 30 minutes
echo ============================================================
echo.
schtasks /Create /TN "CryptoEA_Monitor" /TR "\"%~dp0_crypto_monitor_task.bat\"" /SC MINUTE /MO 30 /F
if errorlevel 1 (
  echo.
  echo [ERROR] Failed. Right-click this file, choose "Run as administrator", then retry.
) else (
  echo.
  echo [DONE] Scheduled. Runs every 30 min while the PC and MT5 are on.
  echo   Manage: search "Task Scheduler" in Start, find "CryptoEA_Monitor"
  echo   Remove: schtasks /Delete /TN "CryptoEA_Monitor" /F
)
echo.
pause
