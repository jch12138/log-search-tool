@echo off
tasklist /fi "imagename eq log-search-api.exe" /fo csv | find /i "log-search-api.exe" >nul
if not errorlevel 1 (
  taskkill /f /im log-search-api.exe >nul 2>&1
  echo Stopped log-search-api.exe
) else (
  echo Process not running
)
pause >nul
