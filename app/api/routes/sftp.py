"""SFTP routes (migrated inline).

Provides SFTP file management APIs:
- POST /sftp/connect
- POST /sftp/connect-by-config
- POST /sftp/disconnect
- GET  /sftp/connections
- POST /sftp/list
- GET/POST /sftp/download
- POST /sftp/batch-download
- POST /sftp/upload
- POST /sftp/mkdir
- POST /sftp/delete
"""

from __future__ import annotations

import os
import tempfile
from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

from app.services import SFTPService, ConfigService
from config import Config

sftp_bp = Blueprint('sftp', __name__)
_sftp_service = SFTPService()


@sftp_bp.route('/sftp/connect', methods=['POST'])
def connect_sftp():
	try:
		data = request.get_json() or {}
		for f in ('host','username','password'):
			if f not in data:
				return jsonify({'success': False,'error': {'code':'MISSING_FIELD','message': f'缺少必需字段: {f}'}}), 400
		info = _sftp_service.connect(
			host=data['host'],
			port=data.get('port', 22),
			username=data['username'],
			password=data['password'],
			connection_name=data.get('connection_name',''))
		return jsonify({'success': True,'data': {
			'connection_id': info.connection_id,
			'message': f'成功连接到 {info.host}:{info.port}',
			'connected_at': info.connected_at
		}})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'SFTP连接失败: {e}'}}), 500


@sftp_bp.route('/sftp/connect-by-config', methods=['POST'])
def connect_sftp_by_config():
	try:
		data = request.get_json() or {}
		log_name = data.get('log_name')
		ssh_index = data.get('ssh_index')
		if log_name is None or ssh_index is None:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'缺少必需字段: log_name 或 ssh_index'}}), 400
		cfg = ConfigService(Config.CONFIG_FILE_PATH)
		log_cfg = cfg.get_log_by_name(log_name)
		if not log_cfg:
			return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': f'未找到日志配置: {log_name}'}}), 404
		sshs = getattr(log_cfg,'sshs',[]) or []
		try:
			ssh_index = int(ssh_index)
		except Exception:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'ssh_index 必须是整数'}}), 400
		if ssh_index < 0 or ssh_index >= len(sshs):
			return jsonify({'success': False,'error': {'code':'INVALID_ARGUMENT','message':'ssh_index 超出范围'}}), 400
		ssh = sshs[ssh_index]
		if not ssh.get('password'):
			return jsonify({'success': False,'error': {'code':'INVALID_CONFIG','message':'该SSH配置未提供密码，无法自动连接'}}), 400
		info = _sftp_service.connect(
			host=ssh.get('host'),
			port=ssh.get('port',22),
			username=ssh.get('username'),
			password=ssh.get('password'),
			connection_name=data.get('connection_name') or f"{log_cfg.name} - {ssh.get('host')}{'#'+str(ssh_index+1) if len(sshs)>1 else ''}"
		)
		return jsonify({'success': True,'data': {
			'connection_id': info.connection_id,
			'message': f'成功连接到 {info.host}:{info.port}',
			'connected_at': info.connected_at
		}})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'通过配置连接失败: {e}'}}), 500


@sftp_bp.route('/sftp/disconnect', methods=['POST'])
def disconnect_sftp():
	try:
		data = request.get_json() or {}
		cid = data.get('connection_id')
		if not cid:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'缺少connection_id字段'}}), 400
		result = _sftp_service.disconnect(cid)
		return jsonify({'success': True,'data': result})
	except ValueError as e:  # noqa
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'断开连接失败: {e}'}}), 500


@sftp_bp.route('/sftp/connections', methods=['GET'])
def get_connections():
	try:
		data = _sftp_service.get_connections()
		return jsonify({'success': True,'data': data})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'获取连接列表失败: {e}'}}), 500


@sftp_bp.route('/sftp/list', methods=['POST'])
def list_directory():
	try:
		data = request.get_json() or {}
		cid = data.get('connection_id')
		if not cid:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'缺少connection_id字段'}}), 400
		info = _sftp_service.list_directory(cid, data.get('path','.'))
		return jsonify({'success': True,'data': info})
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'列出目录失败: {e}'}}), 500


@sftp_bp.route('/sftp/download', methods=['GET', 'POST'])
def download_file():
	try:
		if request.method == 'POST':
			data = request.get_json(silent=True) or {}
			cid = data.get('connection_id'); remote = data.get('remote_path')
		else:
			cid = request.args.get('connection_id'); remote = request.args.get('remote_path')
		if not cid or not remote:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'请提供connection_id和remote_path'}}), 400
		temp_path, filename = _sftp_service.download_file(cid, remote)
		return send_file(temp_path, as_attachment=True, download_name=filename, mimetype='application/octet-stream')
	except ValueError as e:  # noqa
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'下载文件失败: {e}'}}), 500


@sftp_bp.route('/sftp/batch-download', methods=['POST'])
def batch_download():
	try:
		data = request.get_json() or {}
		cid = data.get('connection_id'); paths = data.get('paths') or []
		if not cid or not paths:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'缺少connection_id或paths字段'}}), 400
		zip_path, zip_filename = _sftp_service.batch_download(cid, paths)
		return send_file(zip_path, as_attachment=True, download_name=zip_filename, mimetype='application/zip')
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'批量下载失败: {e}'}}), 500


@sftp_bp.route('/sftp/upload', methods=['POST'])
def upload_file():
	try:
		cid = request.form.get('connection_id'); remote_path = request.form.get('remote_path')
		if not cid or not remote_path:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'请提供connection_id和remote_path'}}), 400
		if 'file' not in request.files:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'没有选择文件'}}), 400
		f = request.files['file']
		if not f.filename:
			return jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'没有选择文件'}}), 400
		filename = secure_filename(f.filename)
		tmp = tempfile.NamedTemporaryFile(delete=False)
		f.save(tmp.name); tmp.close()
		try:
			result = _sftp_service.upload_file(cid, tmp.name, remote_path, filename)
			return jsonify({'success': True,'data': result})
		finally:
			try: os.unlink(tmp.name)  # noqa
			except Exception: pass
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'上传文件失败: {e}'}}), 500


@sftp_bp.route('/sftp/mkdir', methods=['POST'])
def create_directory():
	try:
		data = request.get_json() or {}
		for f in ('connection_id','remote_path','dir_name'):
			if f not in data:
				return jsonify({'success': False,'error': {'code':'MISSING_FIELD','message': f'缺少必需字段: {f}'}}), 400
		result = _sftp_service.create_directory(data['connection_id'], data['remote_path'], data['dir_name'])
		return jsonify({'success': True,'data': result})
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'创建目录失败: {e}'}}), 500


@sftp_bp.route('/sftp/delete', methods=['POST'])
def delete_item():
	try:
		data = request.get_json() or {}
		if 'connection_id' not in data or 'remote_path' not in data:
			return jsonify({'success': False,'error': {'code':'MISSING_FIELD','message':'缺少必需字段: connection_id 或 remote_path'}}), 400
		result = _sftp_service.delete_item(data['connection_id'], data['remote_path'], data.get('is_directory', False))
		return jsonify({'success': True,'data': result})
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'删除失败: {e}'}}), 500

__all__ = ['sftp_bp']
