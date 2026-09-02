@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo    设置"每 30 分钟自动跑一次监测器"
echo ============================================================
echo.
schtasks /Create /TN "GoldEA_Monitor" /TR "\"%~dp0_monitor_task.bat\"" /SC MINUTE /MO 30 /F
if errorlevel 1 (
  echo.
  echo [错误] 注册失败。请右键这个文件,选"以管理员身份运行"再试一次。
) else (
  echo.
  echo [完成] 已设置好。只要电脑和 MT5 开着,它每 30 分钟自动盯一次。
  echo   查看/管理:开始菜单搜"任务计划程序",找 "GoldEA_Monitor"
  echo   想取消:在这里运行  schtasks /Delete /TN "GoldEA_Monitor" /F
)
echo.
pause
