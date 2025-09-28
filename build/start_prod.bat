@echo off
REM 启动生产环境 (端口 8000)
setlocal ENABLEDELAYEDEXPANSION
set APP_PORT=8000
set APP_DEBUG=0
set TERMINAL_IDLE_TIMEOUT=1800
REM 脚本所在目录
set SCRIPT_DIR=%~dp0
REM 优先使用同目录下已编译 exe
set EXE_NAME=log-search-api.exe
if not exist "%SCRIPT_DIR%!EXE_NAME!" (
	if exist "%SCRIPT_DIR%log-search-api-onefile-windows.exe" set EXE_NAME=log-search-api-onefile-windows.exe
)
if exist "%SCRIPT_DIR%!EXE_NAME!" (
	echo Launching %EXE_NAME% ...
	"%SCRIPT_DIR%!EXE_NAME!"
) else (
	echo Packaged exe not found, fallback to python source.
	if exist "%SCRIPT_DIR%..\run.py" (
		pushd "%SCRIPT_DIR%.."
		python run.py
		popd
	) else (
		echo run.py not found. Exiting.
		exit /b 1
	)
)
endlocal
