@echo off
REM 打包版本专用启动脚本 - 端口9000

echo 在端口9000启动Log Search Tool (打包版本)...

REM 设置自定义配置
set FLASK_HOST=127.0.0.1
set FLASK_PORT=9000
set LOG_LEVEL=INFO

REM 检查可执行文件
if not exist "log-search-api.exe" (
    echo 错误: 未找到 log-search-api.exe
    echo 请确保此脚本在打包后的程序目录中运行
    pause
    exit /b 1
)

REM 创建logs目录
if not exist logs mkdir logs

REM 后台启动
echo 启动命令: log-search-api.exe
start /b log-search-api.exe > logs\app_9000.log 2>&1

echo ✅ 应用已在端口9000后台启动
echo 🌐 访问地址: http://127.0.0.1:9000
echo 📝 日志文件: logs\app_9000.log
echo.
echo 💡 使用 stop.bat 停止应用
echo 按任意键关闭此窗口...
pause >nul
