"""
SFTP路由

提供SFTP文件管理的API接口：
- POST /sftp/connect - 建立SFTP连接
- POST /sftp/connect-by-config - 通过日志配置建立SFTP连接（无需前端提供密码）
- POST /sftp/disconnect - 断开SFTP连接
- GET /sftp/connections - 列出所有活跃的SFTP连接
- POST /sftp/list - 列出指定路径下的文件和目录
- GET/POST /sftp/download - 下载单个文件
- POST /sftp/batch-download - 批量下载多个文件
- POST /sftp/upload - 上传文件
- POST /sftp/mkdir - 创建目录
- POST /sftp/delete - 删除文件或目录

注意：日志配置的SSH连接信息已合并到 GET /api/v1/logs?include_ssh=true
"""

import sys
import os
import tempfile
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
from services.sftp_service import SFTPService
from services import ConfigService
from config import Config

# 创建蓝图
sftp_bp = Blueprint('sftp', __name__)

# 创建SFTP服务实例
sftp_service = SFTPService()


@sftp_bp.route('/sftp/connect', methods=['POST'])
def connect_sftp():
    """建立SFTP连接到指定服务器"""
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
        required_fields = ['host', 'username', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'MISSING_FIELD',
                        'message': f'缺少必需字段: {field}'
                    }
                }), 400
        
        # 连接SFTP
        connection_info = sftp_service.connect(
            host=data['host'],
            port=data.get('port', 22),
            username=data['username'],
            password=data['password'],
            connection_name=data.get('connection_name', '')
        )
        
        # 构造响应数据
        response_data = {
            'connection_id': connection_info.connection_id,
            'message': f'成功连接到 {connection_info.host}:{connection_info.port}',
            'connected_at': connection_info.connected_at
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
                'message': f'SFTP连接失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/connect-by-config', methods=['POST'])
def connect_sftp_by_config():
    """通过日志配置建立SFTP连接（后端读取密码）
    请求体: { log_name: str, ssh_index: int, connection_name?: str }
    """
    try:
        data = request.get_json() or {}
        log_name = data.get('log_name')
        ssh_index = data.get('ssh_index')
        if log_name is None or ssh_index is None:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '缺少必需字段: log_name 或 ssh_index'
                }
            }), 400

        # 读取配置，定位SSH条目
        config_service = ConfigService(Config.CONFIG_FILE_PATH)
        log_cfg = config_service.get_log_by_name(log_name)
        if not log_cfg:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'NOT_FOUND',
                    'message': f'未找到日志配置: {log_name}'
                }
            }), 404

        sshs = getattr(log_cfg, 'sshs', []) or []
        try:
            ssh_index = int(ssh_index)
        except Exception:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': 'ssh_index 必须是整数'
                }
            }), 400

        if ssh_index < 0 or ssh_index >= len(sshs):
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_ARGUMENT',
                    'message': 'ssh_index 超出范围'
                }
            }), 400

        ssh = sshs[ssh_index]
        host = ssh.get('host')
        port = ssh.get('port', 22)
        username = ssh.get('username')
        password = ssh.get('password')
        if not password:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_CONFIG',
                    'message': '该SSH配置未提供密码，无法自动连接'
                }
            }), 400

        # 连接
        connection_info = sftp_service.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            connection_name=data.get('connection_name') or f"{log_cfg.name} - {host}{'#'+str(ssh_index+1) if len(sshs)>1 else ''}"
        )

        response_data = {
            'connection_id': connection_info.connection_id,
            'message': f'成功连接到 {connection_info.host}:{connection_info.port}',
            'connected_at': connection_info.connected_at
        }

        return jsonify({ 'success': True, 'data': response_data })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'通过配置连接失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/disconnect', methods=['POST'])
def disconnect_sftp():
    """断开指定的SFTP连接"""
    try:
        data = request.get_json()
        if not data or 'connection_id' not in data:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '缺少connection_id字段'
                }
            }), 400
        
        result = sftp_service.disconnect(data['connection_id'])
        
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
                'message': f'断开连接失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/connections', methods=['GET'])
def get_connections():
    """列出所有活跃的SFTP连接"""
    try:
        connections_data = sftp_service.get_connections()
        
        return jsonify({
            'success': True,
            'data': connections_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL',
                'message': f'获取连接列表失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/list', methods=['POST'])
def list_directory():
    """列出指定路径下的文件和目录"""
    try:
        data = request.get_json()
        if not data or 'connection_id' not in data:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '缺少connection_id字段'
                }
            }), 400
        
        directory_info = sftp_service.list_directory(
            connection_id=data['connection_id'],
            path=data.get('path', '.')
        )
        
        return jsonify({
            'success': True,
            'data': directory_info
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
                'message': f'列出目录失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/download', methods=['GET', 'POST'])
def download_file():
    """下载单个文件（支持GET查询参数或POST JSON）"""
    try:
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            connection_id = data.get('connection_id')
            remote_path = data.get('remote_path')
        else:
            connection_id = request.args.get('connection_id')
            remote_path = request.args.get('remote_path')
        
        if not all([connection_id, remote_path]):
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '请提供connection_id和remote_path'
                }
            }), 400
        
        # 下载文件到临时目录
        temp_path, filename = sftp_service.download_file(connection_id, remote_path)
        
        # 发送文件
        return send_file(
            temp_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/octet-stream'
        )
        
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
                'message': f'下载文件失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/batch-download', methods=['POST'])
def batch_download():
    """批量下载多个文件，打包为ZIP文件"""
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
        
        connection_id = data.get('connection_id')
        paths = data.get('paths', [])
        
        if not connection_id or not paths:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '缺少connection_id或paths字段'
                }
            }), 400
        
        # 创建ZIP文件
        zip_path, zip_filename = sftp_service.batch_download(connection_id, paths)
        
        # 发送ZIP文件
        return send_file(
            zip_path,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
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
                'message': f'批量下载失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/upload', methods=['POST'])
def upload_file():
    """上传文件到远程服务器"""
    try:
        connection_id = request.form.get('connection_id')
        remote_path = request.form.get('remote_path')
        
        if not all([connection_id, remote_path]):
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '请提供connection_id和remote_path'
                }
            }), 400
        
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '没有选择文件'
                }
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': {
                    'code': 'INVALID_REQUEST',
                    'message': '没有选择文件'
                }
            }), 400
        
        # 保存上传的文件到临时目录
        filename = secure_filename(file.filename)
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file.save(temp_file.name)
        temp_file.close()
        
        try:
            # 上传文件
            result = sftp_service.upload_file(connection_id, temp_file.name, remote_path, filename)
            
            return jsonify({
                'success': True,
                'data': result
            })
            
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_file.name)
            except:
                pass
        
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
                'message': f'上传文件失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/mkdir', methods=['POST'])
def create_directory():
    """在远程服务器创建目录"""
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
        required_fields = ['connection_id', 'remote_path', 'dir_name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'MISSING_FIELD',
                        'message': f'缺少必需字段: {field}'
                    }
                }), 400
        
        result = sftp_service.create_directory(
            connection_id=data['connection_id'],
            remote_path=data['remote_path'],
            dir_name=data['dir_name']
        )
        
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
                'message': f'创建目录失败: {str(e)}'
            }
        }), 500


@sftp_bp.route('/sftp/delete', methods=['POST'])
def delete_item():
    """删除远程文件或目录"""
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
        required_fields = ['connection_id', 'remote_path']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'MISSING_FIELD',
                        'message': f'缺少必需字段: {field}'
                    }
                }), 400
        
        result = sftp_service.delete_item(
            connection_id=data['connection_id'],
            remote_path=data['remote_path'],
            is_directory=data.get('is_directory', False)
        )
        
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
                'message': f'删除失败: {str(e)}'
            }
        }), 500
