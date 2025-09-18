# Build Scripts

This directory contains helper scripts for packaging the log-search-tool.

## Windows (onedir) build

Run from repository root in an elevated Developer Command Prompt or PowerShell:

```
build\package_win_onedir.bat
```
Steps performed:
1. Create artifacts & scripts directories if missing.
2. Collect extra start scripts (build/start_prod.bat, build/start_test.bat) if present.
3. Run PyInstaller in onedir mode including templates & static assets.
4. Move resulting folder to `artifacts/log-search-api-onedir`.
5. Add convenience `start.bat` if prod script exists.
6. Create compressed archive `log-search-api-onedir-windows.zip`.

Requirements:
- Python 3.11+
- Dependencies installed: `pip install -r requirements.txt`
- PyInstaller: `pip install pyinstaller==6.8.0`

Adjust hidden imports or data paths here if application structure changes.
