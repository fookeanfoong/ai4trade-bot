@echo off
REM Scheduled-task runner: silent, no pause. Called by schedule_monitor.bat.
REM Not meant to be double-clicked by hand.
cd /d "%~dp0"
call monitor_config.bat
if not exist reports mkdir reports
python mt5_bridge.py >> reports\monitor_task.log 2>&1
