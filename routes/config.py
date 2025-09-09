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
    
    # 构建现有日志的映射 - 使用name作为主键，path作为辅助匹配
    existing_logs = {}
    for log in existing.get('logs', []):
        name = log.get('name', '').strip()
        path = log.get('path', '').strip()
        group = log.get('group', '').strip()
        # 使用多层键确保唯一性
        key = f"{name}|{group}|{path}"
        existing_logs[key] = log
        # 同时使用name作为简单键，用于处理新增情况
        if name and name not in existing_logs:
            existing_logs[name] = log

    merged = {
        'settings': incoming.get('settings', existing.get('settings', {})),
        'logs': []
    }

    for log in incoming.get('logs', []):
        name = log.get('name', '').strip()
        path = log.get('path', '').strip()
        group = log.get('group', '').strip()
        
        # 尝试匹配现有配置
        key = f"{name}|{group}|{path}"
        old_log = existing_logs.get(key)
        
        # 如果精确匹配失败，尝试按名称匹配（用于处理修改了group或path的情况）
        if not old_log and name:
            old_log = existing_logs.get(name)
        
        new_log = {
            'name': name,
            'path': path,
            'group': group,
            'description': log.get('description'),
            'sshs': []
        }

        # 构建SSH映射 - 以 host+port+username 做ssh项的匹配键
        old_ssh_map = {}
        if old_log and isinstance(old_log.get('sshs'), list):
            for s in old_log['sshs']:
                host = s.get('host', '').strip()
                port = s.get('port', 22)
                username = s.get('username', '').strip()
                ssh_key = f"{host}:{port}@{username}"
                old_ssh_map[ssh_key] = s

        for s in log.get('sshs', []) or []:
            host = s.get('host', '').strip()
            port = s.get('port', 22)
            username = s.get('username', '').strip()
            ssh_key = f"{host}:{port}@{username}"
            
            old_s = old_ssh_map.get(ssh_key, {})
            
            # 密码合并逻辑：新密码优先，否则保持旧密码
            new_password = s.get('password', '').strip()
            old_password = old_s.get('password', '')
            merged_password = new_password if new_password else old_password
            
            ns = {
                'host': host,
                'port': port,
                'username': username,
            }
            if merged_password:
                ns['password'] = merged_password
                
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
