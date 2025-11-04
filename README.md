Log Search Tool
================

Modular Flask + SocketIO application for multi-host log searching, SSH terminal sessions, and SFTP operations.

Directory Highlights:
- app/            Core application package (routes, services, models)
- static/,templates/  Front-end assets
- build/          All build & packaging assets (Dockerfile, requirements splits, Makefile)

Quick Start (local):
1. python -m venv .venv && source .venv/bin/activate
2. pip install -r build/requirements-dev.txt
3. python main.py

Docker:
  docker build -t log-search-tool:0.1.0 -f build/Dockerfile .
  docker run -p 8000:8000 log-search-tool:0.1.0

Build Assets (in build/):
- Dockerfile: multi-stage image using Python 3.13 slim
- requirements-runtime.txt / requirements-dev.txt: dependency split
- Makefile: helper targets (venv, build, docker, test, clean)

Tests:
  make test

Only UTF-8 + GB2312 decoding fallback is supported (simplified encoding strategy).

## Logging

By default, the app logs to both console and a daily-rotated file (e.g. `logs/app.log`) using Python's TimedRotatingFileHandler at midnight and keeps 7 backups.

Note about multi-process environments (e.g., Flask debug reloader or multiple workers):
- TimedRotatingFileHandler is not process-safe for rotation. After midnight, some processes may continue writing to the rotated file, making `app.log` look stale.
- To avoid this, you can opt into a multi-process–friendly handler and use external rotation:
  - Set `APP_USE_WATCHED_LOG=1` to use `WatchedFileHandler` (no internal rotation). Then rotate using system tools like `logrotate`/`newsyslog`.
- Alternatively, run the app as a single process (disable reloader: `APP_DEBUG=0`).

Env vars affecting logging:
- `APP_LOG_LEVEL` (default: DEBUG)
- `APP_LOG_DIR` (default: logs)
- `APP_LOG_FILE` (default: app.log)
- `APP_LOG_PATH` (optional) — full path; when set, overrides the combination of DIR+FILE
- `APP_LOG_BACKUP` (default: 7) — used only with the default TimedRotatingFileHandler
- `APP_USE_WATCHED_LOG` (default: 0) — when set, switches to WatchedFileHandler
