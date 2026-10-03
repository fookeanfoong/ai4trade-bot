@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"
echo ============================================================
echo    Crypto EMA+MACD Scalper EA  --  Install into MT5
echo ============================================================
echo.
set "SRC=%~dp0mql5\CryptoEmaMacdScalper.mq5"
if not exist "%SRC%" (
  echo [ERROR] Cannot find mql5\CryptoEmaMacdScalper.mq5
  echo   Run this file from inside the ai4trade-bot folder.
  pause
  exit /b 1
)
set "ROOT=%APPDATA%\MetaQuotes\Terminal"
if not exist "%ROOT%" (
  echo [ERROR] No MT5 data folder at %ROOT%
  echo   Open MT5 once and log in, then run this again.
  echo   Portable install? Copy by hand: MT5 - File - Open Data Folder - MQL5\Experts
  pause
  exit /b 1
)

set /a FOUND=0
for /d %%T in ("%ROOT%\*") do (
  if exist "%%T\MQL5\Experts" (
    set /a FOUND+=1
    echo --- Terminal: %%~nxT
    copy /Y "%SRC%" "%%T\MQL5\Experts\" >nul
    echo     [1/3] EA copied to MQL5\Experts
    if not exist "%%T\MQL5\Presets" mkdir "%%T\MQL5\Presets"
    copy /Y "%~dp0presets\crypto\default.set"   "%%T\MQL5\Presets\CryptoEmaMacd_default.set" >nul
    copy /Y "%~dp0presets\crypto\defensive.set" "%%T\MQL5\Presets\CryptoEmaMacd_defensive.set" >nul
    echo     [2/3] Presets copied to MQL5\Presets
    set "ORIGIN="
    if exist "%%T\origin.txt" for /f "usebackq delims=" %%O in (`type "%%T\origin.txt"`) do set "ORIGIN=%%O"
    set "ME=!ORIGIN!\metaeditor64.exe"
    if exist "!ME!" (
      set "LOG=%%T\MQL5\Experts\CryptoEmaMacdScalper.log"
      set "EX5=%%T\MQL5\Experts\CryptoEmaMacdScalper.ex5"
      if exist "!EX5!" del /f /q "!EX5!"
      "!ME!" /compile:"%%T\MQL5\Experts\CryptoEmaMacdScalper.mq5" /log:"!LOG!"
      if not exist "!EX5!" (
        echo     [3/3] COMPILE FAILED. Log below - screenshot and send to me:
        type "!LOG!"
      ) else (
        echo     [3/3] Compiled OK
      )
    ) else (
      echo     [3/3] MetaEditor not found - open MetaEditor, open the EA, press F7
    )
  )
)
echo.
if !FOUND!==0 (
  echo [ERROR] Found the MetaQuotes folder but no MT5 terminal inside it.
  pause
  exit /b 1
)
echo ============================================================
echo    [DONE] Next:
echo      1. In MT5 Navigator, right-click Expert Advisors - Refresh
echo      2. Open a BTCUSD chart, set timeframe to M5
echo      3. Drag CryptoEmaMacdScalper onto the chart
echo         Inputs tab - Load - CryptoEmaMacd_default.set
echo      4. Toolbar: Algo Trading must be green
echo      5. Optional monitor: double-click run_crypto_monitor.bat
echo    Backtest + demo account first. Not investment advice.
echo ============================================================
pause
