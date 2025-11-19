"""应用配置 - 统一的配置参数管理"""
import os
import configparser
from dataclasses import dataclass
from pathlib import Path


def _get_config_file() -> str:
    """获取配置文件路径（环境变量 > 可执行文件目录 > 当前目录）"""
    import sys
    import logging
    
    logger = logging.getLogger(__name__)
    
    if env_config := os.getenv("SETTINGS_FILE"):
        logger.info(f"[config] Using config from env: {env_config}")
        return env_config
    
    # PyInstaller 打包后，sys._MEIPASS 指向临时解压目录
    # 配置文件应该在可执行文件同目录，不在 _internal 里
    if getattr(sys, 'frozen', False):
        # 打包后：配置文件在可执行文件同目录
        # 使用 os.path.dirname 而不是 Path().parent 以兼容所有 Windows 环境
        exe_path = sys.executable
        exe_dir = os.path.dirname(os.path.abspath(exe_path))
        exe_config = os.path.join(exe_dir, "settings.ini")
        
        logger.info(f"[config] Running in frozen mode")
        logger.info(f"[config] sys.executable: {exe_path}")
        logger.info(f"[config] exe_dir: {exe_dir}")
        logger.info(f"[config] Looking for config at: {exe_config}")
        logger.info(f"[config] Config exists: {os.path.exists(exe_config)}")
        
        if os.path.exists(exe_config):
            logger.info(f"[config] Using config from exe dir: {exe_config}")
            return exe_config
        else:
            logger.warning(f"[config] Config file not found in exe dir: {exe_config}")
            # 尝试当前工作目录作为备选
            cwd = os.getcwd()
            cwd_config = os.path.join(cwd, "settings.ini")
            if os.path.exists(cwd_config):
                logger.info(f"[config] Fallback: using config from cwd: {cwd_config}")
                return cwd_config
    
    # 开发模式：当前工作目录
    cwd_config = Path.cwd() / "settings.ini"
    logger.info(f"[config] Current working directory: {Path.cwd()}")
    logger.info(f"[config] Looking for config in cwd: {cwd_config}")
    
    if cwd_config.exists():
        logger.info(f"[config] Using config from cwd: {cwd_config}")
        return str(cwd_config)
    
    # 开发模式：项目根目录（兜底）
    root_config = Path(__file__).parent.parent.parent / "settings.ini"
    if root_config.exists():
        logger.info(f"[config] Using config from root: {root_config}")
        return str(root_config)
    
    # 默认路径（返回当前目录，文件不存在时使用默认值）
    logger.warning(f"[config] No config file found, using defaults. Would use: {cwd_config}")
    return str(cwd_config)


def _load_config() -> configparser.ConfigParser:
    """加载外部配置文件"""
    import logging
    logger = logging.getLogger(__name__)
    
    config = configparser.ConfigParser()
    config_file = _get_config_file()
    
    logger.info(f"[config] Attempting to load config from: {config_file}")
    logger.info(f"[config] File exists: {os.path.exists(config_file)}")
    
    if os.path.exists(config_file):
        try:
            # 尝试多种编码
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'cp1252', 'latin-1']
            loaded = False
            
            for encoding in encodings:
                try:
                    config.read(config_file, encoding=encoding)
                    if config.sections():
                        logger.info(f"[config] Successfully loaded config file with encoding: {encoding}")
                        logger.info(f"[config] Config sections: {config.sections()}")
                        loaded = True
                        break
                except Exception as e:
                    logger.debug(f"[config] Failed to read with encoding {encoding}: {e}")
                    continue
            
            if not loaded:
                logger.error(f"[config] Failed to read config file with any encoding")
        except Exception as e:
            logger.error(f"[config] Failed to read config file: {e}")
    else:
        logger.warning(f"[config] Config file does not exist, using defaults")
    
    return config


def _get_bool(env_name: str, default: bool, config_section: str = None, config_key: str = None) -> bool:
    """解析布尔值：环境变量 > 配置文件 > 默认值"""
    # 优先环境变量
    if raw := os.getenv(env_name):
        return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}
    
    # 其次配置文件
    if config_section and config_key:
        _config = _load_config()
        if _config.has_option(config_section, config_key):
            try:
                return _config.getboolean(config_section, config_key)
            except Exception:
                pass
    
    return default


def _get_int(env_name: str, default: int, config_section: str = None, config_key: str = None) -> int:
    """解析整数：环境变量 > 配置文件 > 默认值"""
    # 优先环境变量
    if raw := os.getenv(env_name):
        try:
            return int(raw) if raw.strip() else default
        except Exception:
            pass
    
    # 其次配置文件
    if config_section and config_key:
        _config = _load_config()
        if _config.has_option(config_section, config_key):
            try:
                return _config.getint(config_section, config_key)
            except Exception:
                pass
    
    return default


def _get_str(env_name: str, default: str, config_section: str = None, config_key: str = None) -> str:
    """解析字符串：环境变量 > 配置文件 > 默认值"""
    # 优先环境变量
    if raw := os.getenv(env_name):
        return raw
    
    # 其次配置文件
    if config_section and config_key:
        _config = _load_config()
        if _config.has_option(config_section, config_key):
            try:
                return _config.get(config_section, config_key)
            except Exception:
                pass
    
    return default


@dataclass
class Settings:
    """应用配置类 - 优先级：环境变量 > settings.ini > 默认值"""
    
    # ===== 服务器配置 =====
    HOST: str = _get_str("APP_HOST", "0.0.0.0", "server", "host")
    PORT: int = _get_int("APP_PORT", 8000, "server", "port")
    DEBUG: bool = _get_bool("APP_DEBUG", True, "server", "debug")
    
    # ===== API 配置 =====
    API_PREFIX: str = _get_str("API_PREFIX", "/api/v1", "api", "api_prefix")
    MAX_CONTENT_LENGTH: int = _get_int("MAX_CONTENT_LENGTH", 16 * 1024 * 1024, "api", "max_content_length")
    
    # ===== 日志配置 =====
    LOG_LEVEL: str = _get_str("APP_LOG_LEVEL", "INFO", "log", "log_level")
    LOG_DIR: str = _get_str("APP_LOG_DIR", "logs", "log", "log_dir")
    LOG_FILE_NAME: str = _get_str("APP_LOG_FILE", "app.log", "log", "log_file")
    LOG_BACKUP_COUNT: int = _get_int("APP_LOG_BACKUP", 7, "log", "log_backup_count")
    USE_WATCHED_LOG: bool = _get_bool("APP_USE_WATCHED_LOG", False, "log", "use_watched_log")
    
    # ===== 业务日志配置文件 =====
    CONFIG_FILE_PATH: str = _get_str("CONFIG_FILE_PATH", "./config.yaml", "business", "config_file_path")
    WORKSPACE_SITES_FILE: str = _get_str("WORKSPACE_SITES_FILE", "./workspace_sites.json", "business", "workspace_sites_file")
    
    # ===== SSH 配置 =====
    SSH_TIMEOUT: int = _get_int("SSH_TIMEOUT", 30, "ssh", "ssh_timeout")
    SSH_RETRY_ATTEMPTS: int = _get_int("SSH_RETRY_ATTEMPTS", 3, "ssh", "ssh_retry_attempts")
    
    # ===== 搜索配置 =====
    MAX_SEARCH_RESULTS: int = _get_int("MAX_SEARCH_RESULTS", 10000, "search", "max_search_results")
    SEARCH_TIMEOUT: int = _get_int("SEARCH_TIMEOUT", 30, "search", "search_timeout")
    
    # ===== 终端配置 =====
    TERMINAL_IDLE_TIMEOUT: int = _get_int("TERMINAL_IDLE_TIMEOUT", 1800, "terminal", "terminal_idle_timeout")
    TERMINAL_IDLE_CHECK_INTERVAL: int = _get_int("TERMINAL_IDLE_CHECK_INTERVAL", 30, "terminal", "terminal_idle_check_interval")
    
    # ===== 缓存配置 =====
    CACHE_TTL: int = _get_int("CACHE_TTL", 300, "cache", "cache_ttl")
    
    # ===== 方法 =====
    def to_flask_config(self) -> dict:
        """转换为 Flask 配置格式"""
        return {
            "DEBUG": self.DEBUG,
            "ENV": "development" if self.DEBUG else "production",
            "MAX_CONTENT_LENGTH": self.MAX_CONTENT_LENGTH,
        }
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置并创建必要的目录"""
        settings = cls()
        
        # 创建日志配置文件目录
        config_dir = os.path.dirname(settings.CONFIG_FILE_PATH)
        if config_dir and not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except Exception:
                return False
        
        # 创建应用日志目录
        if settings.LOG_DIR and not os.path.exists(settings.LOG_DIR):
            try:
                os.makedirs(settings.LOG_DIR, exist_ok=True)
            except Exception:
                return False
        
        return True


# 向后兼容别名
Config = Settings
