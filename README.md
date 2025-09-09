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
