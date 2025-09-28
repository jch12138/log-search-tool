# Build Assets

This directory centralizes all artifacts needed to build a standalone executable.

Structure:
- pyinstaller/app.spec              Main spec file (invoked from repo root)
- pyinstaller/hooks/                Custom hook files
- scripts/start.bat                 Windows start script for built exe
- scripts/stop.bat                  Windows stop script

Build (example):
  pyinstaller build/pyinstaller/app.spec -y --clean

Outputs go to `dist/log-search-api/` by default.
