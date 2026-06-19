@echo off
REM ============================================================
REM JOM Sync Runtime - Scheduler Wrapper
REM ============================================================
REM Runs sync_runtime.py and propagates Python's exit code
REM back to Task Scheduler.
REM ============================================================

chcp 65001 >nul

set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

set PROJECT_ROOT=C:\Users\Luke_C\Desktop\JiraObservationMonitor
set LOG_DIR=%PROJECT_ROOT%\docs\control\logs
set LOG_FILE=%LOG_DIR%\scheduled_sync.log

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%PROJECT_ROOT%"

>> "%LOG_FILE%" echo.
>> "%LOG_FILE%" echo ============================================================
>> "%LOG_FILE%" echo Sync run started: %date% %time%
>> "%LOG_FILE%" echo ============================================================

python scripts\sync_runtime.py >> "%LOG_FILE%" 2>&1
set PYTHON_EXIT=%errorlevel%

>> "%LOG_FILE%" echo Sync run finished: %date% %time% (exit code: %PYTHON_EXIT%)
>> "%LOG_FILE%" echo.

exit /b %PYTHON_EXIT%