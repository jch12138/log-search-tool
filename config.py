"""
应用配置文件

统一管理应用的配置参数
"""

import os
from typing import Optional

class Config:
    """应用配置类"""
    
    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # API配置
    API_PREFIX = '/api/v1'
    
    # 日志配置文件路径
    CONFIG_FILE_PATH = os.environ.get('CONFIG_FILE_PATH') or os.path.expanduser('~/.log_search_app/config.yaml')
    
    # SSH连接配置
    SSH_TIMEOUT = int(os.environ.get('SSH_TIMEOUT', '30'))
    SSH_RETRY_ATTEMPTS = int(os.environ.get('SSH_RETRY_ATTEMPTS', '3'))
    
    # 搜索配置
    MAX_SEARCH_RESULTS = int(os.environ.get('MAX_SEARCH_RESULTS', '10000'))
    SEARCH_TIMEOUT = int(os.environ.get('SEARCH_TIMEOUT', '30'))
    
    # 缓存配置
    CACHE_TTL = int(os.environ.get('CACHE_TTL', '300'))  # 5分钟
    
    # 安全配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    @classmethod
    def validate(cls) -> bool:
        """验证配置的有效性"""
        # 检查必要的配置目录
        config_dir = os.path.dirname(cls.CONFIG_FILE_PATH)
        if not os.path.exists(config_dir):
            try:
                os.makedirs(config_dir, exist_ok=True)
            except Exception:
                return False
        return True
