import os
from dataclasses import dataclass

@dataclass
class Settings:
    HOST: str = os.getenv('APP_HOST', '0.0.0.0')
    PORT: int = int(os.getenv('APP_PORT', '8000'))
    DEBUG: bool = os.getenv('APP_DEBUG', '0') == '0'
    LOG_LEVEL: str = os.getenv('APP_LOG_LEVEL', 'INFO')
    LOG_DIR: str = os.getenv('APP_LOG_DIR', 'logs')
    LOG_FILE_NAME: str = os.getenv('APP_LOG_FILE', 'app.log')
    LOG_BACKUP_COUNT: int = int(os.getenv('APP_LOG_BACKUP', '7'))
    TERMINAL_IDLE_TIMEOUT: int = int(os.getenv('TERMINAL_IDLE_TIMEOUT', '1800'))  # 秒，默认30分钟
    TERMINAL_IDLE_CHECK_INTERVAL: int = int(os.getenv('TERMINAL_IDLE_CHECK_INTERVAL', '30'))  # 秒

    def to_flask_config(self) -> dict:
        return {
            'DEBUG': self.DEBUG,
            'ENV': 'development' if self.DEBUG else 'production'
        }
