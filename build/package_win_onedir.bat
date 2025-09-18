@echo off
REM Windows packaging script for log-search-tool (onedir only)
REM Requires: Python 3.11+, pip install -r requirements.txt, pyinstaller

setlocal ENABLEDELAYEDEXPANSION

REM Detect project root (directory of this script)\..
set SCRIPT_DIR=%~dp0
pushd "%SCRIPT_DIR%.."

echo [1/5] Ensuring artifacts and temp folders...
if not exist artifacts mkdir artifacts
if not exist build\scripts mkdir build\scripts 2>nul

REM Extra data collection
set SEP=;
set EXTRA=
if exist build\start_prod.bat set EXTRA=%EXTRA% --add-data build/start_prod.bat%SEP%build
if exist build\start_test.bat set EXTRA=%EXTRA% --add-data build/start_test.bat%SEP%build

set SCRIPTS_ARG=
if exist build\scripts set SCRIPTS_ARG=--add-data build/scripts%SEP%build/scripts

echo [2/5] Cleaning previous dist/build folders...
if exist dist rmdir /S /Q dist
if exist build\__pycache__ rmdir /S /Q build\__pycache__

REM PyInstaller command
set CMD=pyinstaller --name log-search-api --onedir --noconfirm --clean ^
  --add-data "templates%SEP%templates" ^
  --add-data "static%SEP%static" ^
  --hidden-import engineio --hidden-import socketio ^
  --hidden-import engineio.async_drivers.threading ^
  --hidden-import socketio.async_drivers.threading ^
  --collect-all paramiko %SCRIPTS_ARG% %EXTRA% run.py

echo [3/5] Running PyInstaller...
%CMD%
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)

echo [4/5] Moving onedir folder to artifacts...
if exist artifacts\log-search-api-onedir rmdir /S /Q artifacts\log-search-api-onedir
move dist\log-search-api artifacts\log-search-api-onedir >nul

REM Add convenience start.bat if prod script exists
if exist build\start_prod.bat (
  copy /Y build\start_prod.bat artifacts\log-search-api-onedir\ >nul
  > artifacts\log-search-api-onedir\start.bat echo @echo off
  >> artifacts\log-search-api-onedir\start.bat echo call start_prod.bat
)

echo [5/5] Compressing zip...
pushd artifacts
if exist log-search-api-onedir-windows.zip del /F /Q log-search-api-onedir-windows.zip
powershell -command "Compress-Archive -Path 'log-search-api-onedir/*' -DestinationPath 'log-search-api-onedir-windows.zip'"
popd

echo Done. Artifact: artifacts\log-search-api-onedir-windows.zip
popd
endlocal
