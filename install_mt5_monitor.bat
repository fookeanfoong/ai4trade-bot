@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo    黄金 EA 监测器  --  一键安装
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
  echo [错误] 没找到 Python。
  echo   请先到 https://www.python.org 下载并安装 Python 3.11 或更新版本,
  echo   安装时务必勾选 "Add Python to PATH"。装完后重新双击这个文件。
  echo.
  pause
  exit /b 1
)
for /f "delims=" %%v in ('python --version') do echo 找到 %%v
echo.

echo [1/2] 升级 pip ...
python -m pip install --upgrade pip
echo.

echo [2/2] 安装 MetaTrader5 库 ...
python -m pip install -r requirements-mt5.txt
if errorlevel 1 (
  echo.
  echo [错误] 安装失败。把上面的报错截图发我看看。
  pause
  exit /b 1
)

echo.
echo ============================================================
echo    [完成] 装好了!接下来:
echo      1. 打开 MT5,登录账户,把黄金 EA 挂在 XAUUSD 图表上
echo         (工具-选项-EA交易 里勾"允许算法交易")
echo      2. 双击  run_monitor.bat  试跑一次
echo      3. 想让它自动定时跑:右键 schedule_monitor.bat
echo         选"以管理员身份运行"
echo ============================================================
pause
