@echo off
REM Centralized start script (moved to build/scripts)
set FLASK_HOST=127.0.0.1
set FLASK_PORT=9000
set LOG_LEVEL=INFO
if not exist "log-search-api.exe" (
  echo Missing log-search-api.exe (run build first)
  pause
  exit /b 1
)
if not exist logs mkdir logs
start /b log-search-api.exe > logs\app_9000.log 2>&1
echo Started on http://127.0.0.1:9000  (logs/app_9000.log)
pause >nul
