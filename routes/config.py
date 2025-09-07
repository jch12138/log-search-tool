"""
配置管理API路由

实现配置的增删改查操作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request
from middleware import api_response
from services import ConfigService
from models import LogConfig
from config import Config

from flask import Blueprint, request
from middleware import api_response
from services import ConfigService
from config import Config
from datetime import datetime

# 创建蓝图
config_bp = Blueprint('config', __name__)

# 初始化服务
config_service = ConfigService(Config.CONFIG_FILE_PATH)

@config_bp.route('/config', methods=['GET'])
@api_response
def get_config():
    """GET /api/v1/config - 获取当前完整的系统配置"""
    config = config_service.load_config()
    
    # 脱敏处理
    if 'logs' in config:
        for log in config['logs']:
            if 'sshs' in log:
                for ssh in log['sshs']:
                    if 'password' in ssh:
                        ssh['password'] = '***'
    
    return config

@config_bp.route('/config', methods=['PUT'])
@api_response
def update_config():
    """PUT /api/v1/config - 覆盖保存完整配置"""
    data = request.get_json()
    if not data:
        raise ValueError('请求体不能为空')
    
    # 保存配置（会自动验证和备份）
    config_service.save_config(data)
    
    # 统计信息
    logs_count = len(data.get('logs', []))
    
    return {
        'message': '配置保存成功',
        'saved_at': datetime.now().isoformat() + 'Z',
        'logs_count': logs_count,
        'backup_created': f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
    }
