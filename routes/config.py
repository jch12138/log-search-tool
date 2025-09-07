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
    """PUT /api/v1/config - 覆盖保存完整配置
    前端可能不会提交未修改的密码字段，这里需要与现有配置合并，避免将密码置空。
    规则：
      - 如果提交了 password 字段且非空，使用新值。
      - 如果未提交或为空，则沿用旧配置中的密码（如果存在）。
    """
    incoming = request.get_json()
    if not incoming:
        raise ValueError('请求体不能为空')

    # 读取现有配置以合并敏感字段
    existing = config_service.load_config() or {}
    existing_logs = { (log.get('name') or '', log.get('path') or ''): log for log in existing.get('logs', []) }

    merged = {
        'settings': incoming.get('settings', existing.get('settings', {})),
        'logs': []
    }

    for log in incoming.get('logs', []):
        # 合并单个日志配置
        key = (log.get('name') or '', log.get('path') or '')
        old_log = existing_logs.get(key)
        new_log = {
            'name': log.get('name'),
            'path': log.get('path'),
            'group': log.get('group'),
            'description': log.get('description'),
            'sshs': []
        }

        # 以 host+port+username 做ssh项的匹配键
        old_ssh_map = {}
        if old_log and isinstance(old_log.get('sshs'), list):
            for s in old_log['sshs']:
                key_ssh = (s.get('host'), s.get('port'), s.get('username'))
                old_ssh_map[key_ssh] = s

        for s in log.get('sshs', []) or []:
            key_ssh = (s.get('host'), s.get('port'), s.get('username'))
            old_s = old_ssh_map.get(key_ssh, {})
            merged_pwd = s.get('password') if s.get('password') else old_s.get('password')
            ns = {
                'host': s.get('host'),
                'port': s.get('port'),
                'username': s.get('username'),
            }
            if merged_pwd:
                ns['password'] = merged_pwd
            new_log['sshs'].append(ns)

        merged['logs'].append(new_log)

    # 保存配置（会自动验证和备份）
    config_service.save_config(merged)

    # 统计信息
    logs_count = len(merged.get('logs', []))

    return {
        'message': '配置保存成功',
        'saved_at': datetime.now().isoformat() + 'Z',
        'logs_count': logs_count,
        'backup_created': f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
    }
