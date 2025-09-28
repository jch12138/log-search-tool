"""
System Settings

Centralized application/runtime parameters with environment overrides and clear
parameter descriptions. Import and use `Settings` throughout the app.

Environment variables (override defaults):
- APP_HOST: Bind address for the HTTP server (default: 0.0.0.0)
- APP_PORT: Port for the HTTP server (default: 8000)
- APP_DEBUG: Enable debug mode ("1"/"true" to enable; default: "0")
- APP_LOG_LEVEL: Root log level (DEBUG/INFO/WARN/ERROR, default: INFO)
- APP_LOG_DIR: Directory for application logs (default: logs)
- APP_LOG_FILE: Log file name (default: app.log)
- APP_LOG_BACKUP: Number of daily log backups to keep (default: 7)
- TERMINAL_IDLE_TIMEOUT: Idle seconds before closing a terminal session (default: 1800)
- TERMINAL_IDLE_CHECK_INTERVAL: Seconds between idle checks (default: 30)
- MAX_SEARCH_RESULTS: Max lines returned by grep/tail on server side (default: 10000)
- SEARCH_TIMEOUT: Max seconds allowed for a single remote search command (default: 30)
- CACHE_TTL: In-memory cache TTL seconds for auxiliary data (default: 300)
- MAX_CONTENT_LENGTH: Max upload/request size in bytes (default: 16777216, 16MB)
 - CONFIG_FILE_PATH: Path to YAML log config file (default: ~/.log_search_app/config.yaml)
 - SECRET_KEY: Flask secret key (default: dev-secret-key-change-in-production)
 - API_PREFIX: REST API prefix (default: /api/v1)
 - SSH_TIMEOUT: SSH connection timeout seconds (default: 30)
 - SSH_RETRY_ATTEMPTS: SSH connection retry attempts (default: 3)

Notes:
- All values can be overridden via environment variables listed above.
- Keep this file as the single source of truth for system-level parameters.
"""

import os
from dataclasses import dataclass


def _get_bool(env_name: str, default: bool) -> bool:
    raw = os.getenv(env_name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


def _get_int(env_name: str, default: int) -> int:
    raw = os.getenv(env_name)
    try:
        return int(raw) if raw is not None and str(raw).strip() != "" else default
    except Exception:
        return default


@dataclass
class Settings:
    """System/runtime settings with env overrides.

    HOST: HTTP 绑定地址（默认 0.0.0.0）。环境变量：APP_HOST
    PORT: HTTP 端口（默认 8000）。环境变量：APP_PORT
    DEBUG: 是否开启调试模式（默认 False）。环境变量：APP_DEBUG（1/true 开启）
    LOG_LEVEL: 日志级别（DEBUG/INFO/WARNING/ERROR，默认 INFO）。环境变量：APP_LOG_LEVEL
    LOG_DIR: 应用日志目录（默认 logs）。环境变量：APP_LOG_DIR
    LOG_FILE_NAME: 应用日志文件名（默认 app.log）。环境变量：APP_LOG_FILE
    LOG_BACKUP_COUNT: 按天轮转保留的日志文件个数（默认 7）。环境变量：APP_LOG_BACKUP
    TERMINAL_IDLE_TIMEOUT: 终端空闲超时（秒，默认 1800）。环境变量：TERMINAL_IDLE_TIMEOUT
    TERMINAL_IDLE_CHECK_INTERVAL: 空闲检测频率（秒，默认 30）。环境变量：TERMINAL_IDLE_CHECK_INTERVAL
    MAX_SEARCH_RESULTS: 后端单次搜索返回的最大行数上限（默认 10000）。环境变量：MAX_SEARCH_RESULTS
    SEARCH_TIMEOUT: 单次远程搜索命令的超时时间（秒，默认 30）。环境变量：SEARCH_TIMEOUT
    CACHE_TTL: 缓存有效期（秒，默认 300）。环境变量：CACHE_TTL
    MAX_CONTENT_LENGTH: 请求体大小上限（字节，默认 16MB）。环境变量：MAX_CONTENT_LENGTH
    """

    HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    PORT: int = _get_int("APP_PORT", 8000)
    DEBUG: bool = _get_bool("APP_DEBUG", False)

    LOG_LEVEL: str = os.getenv("APP_LOG_LEVEL", "DEBUG")
    LOG_DIR: str = os.getenv("APP_LOG_DIR", "logs")
    LOG_FILE_NAME: str = os.getenv("APP_LOG_FILE", "app.log")
    LOG_BACKUP_COUNT: int = _get_int("APP_LOG_BACKUP", 7)

    TERMINAL_IDLE_TIMEOUT: int = _get_int("TERMINAL_IDLE_TIMEOUT", 1800)
    TERMINAL_IDLE_CHECK_INTERVAL: int = _get_int("TERMINAL_IDLE_CHECK_INTERVAL", 30)

    MAX_SEARCH_RESULTS: int = _get_int("MAX_SEARCH_RESULTS", 10000)
    SEARCH_TIMEOUT: int = _get_int("SEARCH_TIMEOUT", 30)

    CACHE_TTL: int = _get_int("CACHE_TTL", 300)
    MAX_CONTENT_LENGTH: int = _get_int("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)

    # Root-config (migrated)
    CONFIG_FILE_PATH: str = os.getenv("CONFIG_FILE_PATH", os.path.expanduser("./config.yaml"))
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    API_PREFIX: str = os.getenv("API_PREFIX", "/api/v1")
    SSH_TIMEOUT: int = _get_int("SSH_TIMEOUT", 30)
    SSH_RETRY_ATTEMPTS: int = _get_int("SSH_RETRY_ATTEMPTS", 3)

    def to_flask_config(self) -> dict:
        """Return a mapping suitable for Flask's app.config."""
        return {
            "DEBUG": self.DEBUG,
            "ENV": "development" if self.DEBUG else "production",
            "MAX_CONTENT_LENGTH": self.MAX_CONTENT_LENGTH,
            "SECRET_KEY": self.SECRET_KEY,
        }
