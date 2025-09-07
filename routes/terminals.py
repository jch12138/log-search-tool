"""
终端路由

提供SSH终端会话管理的API接口：
- POST /terminals - 创建新的终端会话
- GET /terminals - 获取所有终端会话列表
- GET /terminals/{terminal_id} - 获取特定终端会话信息
- DELETE /terminals/{terminal_id} - 关闭终端会话
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from services.terminal_service import TerminalService

# 创建蓝图
terminals_bp = Blueprint('terminals', __name__)

# 创建终端服务实例
terminal_service = TerminalService()


@terminals_bp.route('/terminals', methods=['POST'])
def create_terminal():
    """创建新的SSH终端会话"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '请求体不能为空'
                }
            }), 400
        
        # 验证必需参数
        required_fields = ['host', 'username']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'MISSING_FIELD',
                        'message': f'缺少必需字段: {field}'
                    }
                }), 400
        
        # 验证密码或私钥
        if not data.get('password') and not data.get('private_key'):
            return jsonify({
                'success': False,
                'error': {
                    'code': 'MISSING_AUTH',
                    'message': '必须提供密码或私钥'
                }
            }), 400
        
        # 创建终端会话
        session_info = terminal_service.create_terminal(
            host=data['host'],
            port=data.get('port', 22),
            username=data['username'],
            password=data.get('password', ''),
            private_key=data.get('private_key', ''),
            initial_command=data.get('initial_command', '')
        )
        
        # 构造响应数据
        response_data = {
            'terminal_id': session_info.terminal_id,
            'session_id': session_info.session_id,
            'connection_status': session_info.status,
            'host': session_info.host,
            'created_at': session_info.created_at,
            'websocket_url': 'ws://localhost:5001/socket.io/?EIO=4&transport=websocket',
            'initial_prompt': f'{session_info.username}@{session_info.host}:~$ '
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


# 添加终端交互相关的API端点

@terminals_bp.route('/terminals/<terminal_id>/input', methods=['POST'])
def send_terminal_input(terminal_id):
    """发送命令到终端"""
    try:
        data = request.get_json()
        if not data or 'command' not in data:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '缺少command字段'
                }
            }), 400
        
        terminal_service.send_command(terminal_id, data['command'])
        
        return jsonify({
            'success': True,
            'data': {
                'message': '命令已发送',
                'terminal_id': terminal_id,
                'command': data['command']
            }
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
                'message': f'发送命令失败: {str(e)}'
            }
        }), 500


@terminals_bp.route('/terminals/<terminal_id>/output', methods=['GET'])
def get_terminal_output(terminal_id):
    """获取终端输出"""
    try:
        output = terminal_service.get_output(terminal_id)
        
        return jsonify({
            'success': True,
            'data': {
                'terminal_id': terminal_id,
                'output': output,
                'timestamp': 'iso-timestamp-here'  # 可以添加实际时间戳
            }
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
                'message': f'获取输出失败: {str(e)}'
            }
        }), 500
