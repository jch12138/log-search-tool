@echo off
chcp 65001 >nul
REM 停止Log Search Tool应用

echo 正在停止Log Search Tool...

REM 停止log-search-api.exe进程
tasklist /fi "imagename eq log-search-api.exe" /fo csv | find /i "log-search-api.exe" >nul
if not errorlevel 1 (
    echo 找到log-search-api.exe进程，正在停止...
    taskkill /f /im log-search-api.exe >nul 2>&1
    echo 应用已停止
) else (
    echo 未找到运行中的log-search-api.exe进程
)

echo.
echo 按任意键关闭此窗口...
pause >nul
