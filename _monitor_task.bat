@echo off
REM 计划任务专用:静默运行(不弹窗、不 pause),日志写进 reports\monitor_task.log
REM 这个文件由 schedule_monitor.bat 注册的定时任务调用,一般不用手动双击。
cd /d "%~dp0"
call monitor_config.bat
if not exist reports mkdir reports
python mt5_bridge.py >> reports\monitor_task.log 2>&1
