@echo off
REM 启动测试环境 (端口 6000)
setlocal ENABLEDELAYEDEXPANSION
set APP_PORT=6000
set APP_DEBUG=1
set TERMINAL_IDLE_TIMEOUT=600
set SCRIPT_DIR=%~dp0
set EXE_NAME=log-search-api.exe
if not exist "%SCRIPT_DIR%!EXE_NAME!" (
	if exist "%SCRIPT_DIR%log-search-api-onefile-windows.exe" set EXE_NAME=log-search-api-onefile-windows.exe
)
if exist "%SCRIPT_DIR%!EXE_NAME!" (
	echo Launching %EXE_NAME% (test)...
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
