"""
服务器管理路由

提供服务器连接管理的API接口，将服务器信息与日志路径解耦
"""

import sys
import os
import logging
from typing import Dict, List, Any, Set
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request
from middleware import api_response
from services import ConfigService
from config import Config

# 创建蓝图
servers_bp = Blueprint('servers', __name__)

# 初始化服务
config_service = ConfigService(Config.CONFIG_FILE_PATH)

# 创建logger
logger = logging.getLogger(__name__)

@servers_bp.route('/servers', methods=['GET'])
@api_response
def list_servers():
    """GET /api/v1/servers - 获取去重后的服务器列表
    
    查询参数：
    - type: 'all' | 'sftp' | 'terminal' - 返回特定类型的服务器信息
    """
    server_type = request.args.get('type', 'all')
    
    # 获取所有日志配置
    logs_summary = config_service.get_log_summary()
    
    # 用于去重的服务器集合
    unique_servers: Dict[str, Dict[str, Any]] = {}
    server_logs_mapping: Dict[str, List[Dict[str, Any]]] = {}
    
    for log in logs_summary:
        log_config = config_service.get_log_by_name(log['name'])
        if not log_config or not hasattr(log_config, 'sshs') or not log_config.sshs:
            continue
            
        for idx, ssh_config in enumerate(log_config.sshs):
            host = ssh_config.get('host', '')
            port = ssh_config.get('port', 22)
            username = ssh_config.get('username', '')
            
            # 生成服务器唯一标识
            server_key = f"{username}@{host}:{port}"
            
            # 如果是新服务器，添加到唯一列表
            if server_key not in unique_servers:
                # 生成友好的服务器名称
                server_name = _generate_server_name(host, username)
                
                unique_servers[server_key] = {
                    'server_id': server_key,
                    'server_name': server_name,
                    'host': host,
                    'port': port,
                    'username': username,
                    'connection_count': 0,
                    'log_configs': []
                }
                server_logs_mapping[server_key] = []
            
            # 添加日志配置到该服务器
            log_info = {
                'log_name': log_config.name,
                'log_path': log_config.path,
                'group': log_config.group,
                'ssh_index': idx,
                'description': getattr(log_config, 'description', '') or f"{log_config.name} 日志"
            }
            
            unique_servers[server_key]['log_configs'].append(log_info)
            unique_servers[server_key]['connection_count'] += 1
    
    # 转换为列表格式
    servers_list = list(unique_servers.values())
    
    # 根据类型过滤结果
    if server_type == 'sftp':
        # SFTP 需要的字段（简化版）
        return {
            'servers': [
                {
                    'server_id': server['server_id'],
                    'server_name': server['server_name'],
                    'host': server['host'],
                    'port': server['port'],
                    'username': server['username'],
                    'log_configs': server['log_configs'],  # 保留以供后端使用
                    'type': 'sftp'
                }
                for server in servers_list
            ],
            'total': len(servers_list)
        }
    elif server_type == 'terminal':
        # 终端需要的字段（简化版）
        return {
            'servers': [
                {
                    'server_id': server['server_id'],
                    'server_name': server['server_name'],
                    'host': server['host'],
                    'port': server['port'],
                    'username': server['username'],
                    'log_configs': server['log_configs'],  # 保留以供后端使用
                    'type': 'terminal'
                }
                for server in servers_list
            ],
            'total': len(servers_list)
        }
    else:
        # 返回完整信息
        return {
            'servers': servers_list,
            'total': len(servers_list)
        }

@servers_bp.route('/servers/<server_id>/logs', methods=['GET'])
@api_response
def get_server_logs(server_id: str):
    """GET /api/v1/servers/{server_id}/logs - 获取指定服务器上的所有日志配置"""
    # 解析 server_id (格式: username@host:port)
    try:
        if '@' not in server_id or ':' not in server_id:
            raise ValueError("无效的服务器ID格式")
        
        username_host, port_str = server_id.rsplit(':', 1)
        username, host = username_host.split('@', 1)
        port = int(port_str)
    except (ValueError, TypeError) as e:
        raise ValueError(f"无效的服务器ID: {server_id}")
    
    # 获取该服务器上的所有日志配置
    logs_summary = config_service.get_log_summary()
    server_logs = []
    
    for log in logs_summary:
        log_config = config_service.get_log_by_name(log['name'])
        if not log_config or not hasattr(log_config, 'sshs') or not log_config.sshs:
            continue
            
        for idx, ssh_config in enumerate(log_config.sshs):
            if (ssh_config.get('host') == host and 
                ssh_config.get('port', 22) == port and 
                ssh_config.get('username') == username):
                
                server_logs.append({
                    'log_name': log_config.name,
                    'log_path': log_config.path,
                    'group': log_config.group,
                    'ssh_index': idx,
                    'description': getattr(log_config, 'description', '') or f"{log_config.name} 日志"
                })
    
    return {
        'server_id': server_id,
        'logs': server_logs,
        'total': len(server_logs)
    }

def _generate_server_name(host: str, username: str) -> str:
    """生成友好的服务器名称"""
    # 如果主机名包含域名，提取主机名部分
    if '.' in host:
        hostname = host.split('.')[0]
    else:
        hostname = host
    
    # 如果用户名是常见的系统用户名，使用主机名
    if username.lower() in ['root', 'admin', 'administrator']:
        return hostname
    else:
        return f"{hostname}({username})"
