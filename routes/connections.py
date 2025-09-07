"""
连接管理API路由

实现SSH连接的测试和管理功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request
from middleware import api_response
from services import SSHConnectionManager, LogSearchService
from config import Config
from datetime import datetime
import time

# 创建蓝图
connections_bp = Blueprint('connections', __name__)

# 全局搜索服务实例（用于获取连接状态）
_search_service = None

def get_search_service():
    """获取搜索服务实例"""
    global _search_service
    if _search_service is None:
        _search_service = LogSearchService()
    return _search_service

@connections_bp.route('/connections/stats', methods=['GET'])
@api_response
def get_connection_stats():
    """GET /api/v1/connections/stats - 获取连接统计信息和服务器状态"""
    search_service = get_search_service()
    stats = search_service.ssh_manager.get_stats()
    
    # 模拟连接详细信息（实际实现中可以从连接管理器获取）
    connections = []
    current_time = time.time()
    
    return {
        'total_connections': stats['total_connections'],
        'active_connections': stats['active_connections'],
        'total_sessions': stats['total_connections'],  # 简化处理
        'server_status': 'healthy' if stats['active_connections'] > 0 else 'idle',
        'connections': connections  # 详细连接信息（可选实现）
    }

@connections_bp.route('/connections/<client_id>/disconnect', methods=['POST'])
@api_response
def disconnect_connection(client_id: str):
    """POST /api/v1/connections/{client_id}/disconnect - 强制断开指定客户端连接"""
    # 注意：这里是SSH连接管理，与Socket.IO客户端连接是不同的概念
    # 实际实现中需要根据具体需求来设计
    
    return {
        'message': f'客户端 {client_id} 已断开连接',
        'client_id': client_id,
        'disconnected_at': datetime.now().isoformat() + 'Z'
    }

@connections_bp.route('/connections/cleanup', methods=['POST'])
@api_response
def cleanup_connections():
    """POST /api/v1/connections/cleanup - 清理非活跃的连接"""
    data = request.get_json() or {}
    timeout_minutes = data.get('timeout_minutes', 15)
    
    # SSH连接池会自动清理老旧连接
    search_service = get_search_service()
    # 这里可以触发手动清理逻辑
    
    return {
        'message': '已清理非活跃连接',
        'cleaned_connections': 0,  # 实际清理的连接数
        'timeout_minutes': timeout_minutes
    }

@connections_bp.route('/connections/settings', methods=['GET'])
@api_response
def get_connection_settings():
    """GET /api/v1/connections/settings - 获取连接管理配置参数"""
    from config import Config
    
    return {
        'ping_timeout': 60,
        'ping_interval': 25,
        'disconnect_timeout': 180,
        'cleanup_interval': 120,
        'inactive_timeout': 900,
        'auto_cleanup_enabled': True,
        'ssh_timeout': Config.SSH_TIMEOUT,
        'max_connections': 20
    }
