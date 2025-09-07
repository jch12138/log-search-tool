"""
终端路由

提供SSH终端会话管理的API接口：
- POST /terminals - 通过日志配置创建会话（后端读取密码）
- GET /terminals - 获取所有终端会话列表
- GET /terminals/{terminal_id} - 获取特定终端会话信息
- DELETE /terminals/{terminal_id} - 关闭终端会话
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from services.terminal_manager import terminal_service
from services import ConfigService
from config import Config

# 创建蓝图
terminals_bp = Blueprint('terminals', __name__)

# 使用共享的终端服务实例（供Socket与REST共用）


def _create_from_config(data):
    """根据日志配置创建终端会话的公共实现"""
    log_name = data.get('log_name')
    ssh_index = data.get('ssh_index')
    if log_name is None or ssh_index is None:
        return None, (jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_REQUEST',
                'message': '缺少必需字段: log_name 或 ssh_index'
            }
        }), 400)

    # 读取配置
    config_service = ConfigService(Config.CONFIG_FILE_PATH)
    log_cfg = config_service.get_log_by_name(log_name)
    if not log_cfg:
        return None, (jsonify({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': f'未找到日志配置: {log_name}'
            }
        }), 404)

    sshs = getattr(log_cfg, 'sshs', []) or []
    try:
        ssh_index = int(ssh_index)
    except Exception:
        return None, (jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_REQUEST',
                'message': 'ssh_index 必须是整数'
            }
        }), 400)

    if ssh_index < 0 or ssh_index >= len(sshs):
        return None, (jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_ARGUMENT',
                'message': 'ssh_index 超出范围'
            }
        }), 400)

    ssh = sshs[ssh_index]
    host = ssh.get('host')
    port = ssh.get('port', 22)
    username = ssh.get('username')
    password = ssh.get('password')
    if not password:
        return None, (jsonify({
            'success': False,
            'error': {
                'code': 'INVALID_CONFIG',
                'message': '该SSH配置未提供密码，无法自动连接'
            }
        }), 400)

    session_info = terminal_service.create_terminal(
        host=host,
        port=port,
        username=username,
        password=password,
        private_key='',
        initial_command=data.get('initial_command', '')
    )

    response_data = {
        'terminal_id': session_info.terminal_id,
        'session_id': session_info.session_id,
        'connection_status': session_info.status,
        'host': session_info.host,
        'created_at': session_info.created_at,
        'initial_prompt': f"{session_info.username}@{session_info.host}:~$ "
    }
    return response_data, None


@terminals_bp.route('/terminals', methods=['POST'])
def create_terminal():
    """通过日志配置创建会话（不允许手动提供主机/密码）"""
    try:
        data = request.get_json() or {}
        resp, err = _create_from_config(data)
        if err:
            return err
        return jsonify({ 'success': True, 'data': resp })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'创建终端会话失败: {str(e)}'
            }
        }), 500


@terminals_bp.route('/terminals/connect-by-config', methods=['POST'])
def create_terminal_by_config():
    """兼容别名：与 POST /terminals 相同，后续可移除"""
    try:
        data = request.get_json() or {}
        resp, err = _create_from_config(data)
        if err:
            return err
        return jsonify({ 'success': True, 'data': resp })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'创建终端会话失败: {str(e)}'
            }
        }), 500


@terminals_bp.route('/terminals', methods=['GET'])
def get_terminals():
    """获取当前所有活跃终端会话列表"""
    try:
        terminals_data = terminal_service.get_terminals()
        
        return jsonify({
            'success': True,
            'data': terminals_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'获取终端列表失败: {str(e)}'
            }
        }), 500


@terminals_bp.route('/terminals/<terminal_id>', methods=['GET'])
def get_terminal(terminal_id):
    """获取特定终端会话的详细信息"""
    try:
        session_info = terminal_service.get_terminal(terminal_id)
        
        if not session_info:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'NOT_FOUND',
                    'message': f'终端会话不存在: {terminal_id}'
                }
            }), 404
        
        # 构造详细响应数据
        response_data = {
            'terminal_id': session_info.terminal_id,
            'session_id': session_info.session_id,
            'host': session_info.host,
            'port': session_info.port,
            'username': session_info.username,
            'status': session_info.status,
            'created_at': session_info.created_at,
            'last_activity': session_info.last_activity,
            'current_directory': session_info.current_directory,
            'current_prompt': f'{session_info.username}@{session_info.host}:{session_info.current_directory}$ ',
            'session_history': session_info.session_history[-10:]  # 只返回最近10条记录
        }
        
        return jsonify({
            'success': True,
            'data': response_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'获取终端信息失败: {str(e)}'
            }
        }), 500


@terminals_bp.route('/terminals/<terminal_id>', methods=['DELETE'])
def delete_terminal(terminal_id):
    """关闭并删除指定的终端会话"""
    try:
        result = terminal_service.close_terminal(terminal_id)
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': str(e)
            }
        }), 404
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'关闭终端会话失败: {str(e)}'
            }
        }), 500


# 终端输入/输出的REST端点已移除，改为通过 Socket.IO 实时推送
