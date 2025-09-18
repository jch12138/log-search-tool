"""Terminal (SSH session) routes (migrated inline)."""

from __future__ import annotations

from flask import Blueprint, request, jsonify
from app.services.terminal import TerminalService  # direct service if needed
from app.services.terminal.manager import terminal_service  # singleton
from app.services import ConfigService
from config import Config

terminals_bp = Blueprint('terminals', __name__)


def _create_from_server_id(server_id: str, data: dict):
	if '@' not in server_id or ':' not in server_id:
		return None, (jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'无效的服务器ID'}}), 400)
	try:
		user_host, port_s = server_id.rsplit(':',1)
		username, host = user_host.split('@',1)
		port = int(port_s)
	except Exception:
		return None, (jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'无效的服务器ID'}}), 400)
	cfg = ConfigService(Config.CONFIG_FILE_PATH)
	password = None
	for item in cfg.get_log_summary():  # summary names
		log_cfg = cfg.get_log_by_name(item['name'])
		if not log_cfg: continue
		for ssh in getattr(log_cfg,'sshs',[]) or []:
			if ssh.get('host')==host and ssh.get('port',22)==port and ssh.get('username')==username:
				password = ssh.get('password'); break
		if password: break
	if not password:
		return None, (jsonify({'success': False,'error': {'code':'INVALID_CONFIG','message': f'未找到服务器 {server_id} 的密码配置'}}), 400)
	session = terminal_service.create_terminal(host=host, port=port, username=username, password=password, private_key='', initial_command=data.get('initial_command',''), env_init=bool(data.get('env_init', True)))
	return {
		'terminal_id': session.terminal_id,
		'session_id': session.session_id,
		'connection_status': session.status,
		'host': session.host,
		'username': session.username,
		'created_at': session.created_at
	}, None


def _create_from_log_config(log_name, ssh_index, data):
	cfg = ConfigService(Config.CONFIG_FILE_PATH)
	log_cfg = cfg.get_log_by_name(log_name)
	if not log_cfg:
		return None, (jsonify({'success': False,'error': {'code':'NOT_FOUND','message': f'未找到日志配置: {log_name}'}}), 404)
	sshs = getattr(log_cfg,'sshs',[]) or []
	try:
		ssh_index = int(ssh_index)
	except Exception:
		return None, (jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'ssh_index 必须是整数'}}), 400)
	if ssh_index < 0 or ssh_index >= len(sshs):
		return None, (jsonify({'success': False,'error': {'code':'INVALID_ARGUMENT','message':'ssh_index 超出范围'}}), 400)
	ssh = sshs[ssh_index]
	if not ssh.get('password'):
		return None, (jsonify({'success': False,'error': {'code':'INVALID_CONFIG','message':'该SSH配置未提供密码，无法自动连接'}}), 400)
	session = terminal_service.create_terminal(host=ssh.get('host'), port=ssh.get('port',22), username=ssh.get('username'), password=ssh.get('password'), private_key='', initial_command=data.get('initial_command',''), env_init=bool(data.get('env_init', True)))
	return {
		'terminal_id': session.terminal_id,
		'session_id': session.session_id,
		'connection_status': session.status,
		'host': session.host,
		'username': session.username,
		'created_at': session.created_at,
		'initial_prompt': f"{session.username}@{session.host}:~$ "
	}, None


def _create_from_config(data):
	log_name = data.get('log_name'); ssh_index = data.get('ssh_index'); server_id = data.get('server_id')
	if server_id:
		return _create_from_server_id(server_id, data)
	if log_name is not None and ssh_index is not None:
		return _create_from_log_config(log_name, ssh_index, data)
	return None, (jsonify({'success': False,'error': {'code':'INVALID_REQUEST','message':'缺少必需字段: 需要 (log_name + ssh_index) 或 server_id'}}), 400)


@terminals_bp.route('/terminals', methods=['POST'])
def create_terminal():
	try:
		data = request.get_json() or {}
		resp, err = _create_from_config(data)
		if err: return err
		return jsonify({'success': True,'data': resp})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'创建终端会话失败: {e}'}}), 500


@terminals_bp.route('/terminals/connect-by-config', methods=['POST'])
def create_terminal_by_config():
	try:
		data = request.get_json() or {}
		resp, err = _create_from_config(data)
		if err: return err
		return jsonify({'success': True,'data': resp})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'创建终端会话失败: {e}'}}), 500


@terminals_bp.route('/terminals', methods=['GET'])
def get_terminals():
	try:
		return jsonify({'success': True,'data': terminal_service.get_terminals()})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'获取终端列表失败: {e}'}}), 500


@terminals_bp.route('/terminals/<terminal_id>', methods=['GET'])
def get_terminal(terminal_id):
	try:
		s = terminal_service.get_terminal(terminal_id)
		if not s:
			return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': f'终端会话不存在: {terminal_id}'}}), 404
		return jsonify({'success': True,'data': {
			'terminal_id': s.terminal_id,
			'session_id': s.session_id,
			'host': s.host,
			'port': s.port,
			'username': s.username,
			'status': s.status,
			'created_at': s.created_at,
			'last_activity': s.last_activity,
			'current_directory': s.current_directory,
			'current_prompt': f'{s.username}@{s.host}:{s.current_directory}$ ',
				'session_history': (s.session_history or [])[-10:],
				'encodings': {
					'last_detected': terminal_service.sessions.get(terminal_id, {}).get('encoding'),
					'forced': terminal_service.sessions.get(terminal_id, {}).get('forced_encoding'),
				},
				'env_init': terminal_service.sessions.get(terminal_id, {}).get('env_init', False),
				'locale': terminal_service.sessions.get(terminal_id, {}).get('last_locale')
		}})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'获取终端信息失败: {e}'}}), 500


@terminals_bp.route('/terminals/<terminal_id>', methods=['DELETE'])
def delete_terminal(terminal_id):
	try:
		result = terminal_service.close_terminal(terminal_id)
		return jsonify({'success': True,'data': result})
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'关闭终端会话失败: {e}'}}), 500


@terminals_bp.route('/terminals/<terminal_id>/encoding', methods=['POST'])
def set_terminal_encoding(terminal_id):
	"""Set or clear a forced encoding for a terminal session.

	Request JSON: {"encoding": "gb18030"} or {"encoding": null} to clear.
	"""
	try:
		data = request.get_json() or {}
		enc = data.get('encoding')
		with terminal_service._lock:  # internal lock for thread safety
			sd = terminal_service.sessions.get(terminal_id)
			if not sd:
				return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': '终端会话不存在'}}), 404
			if enc:
				# basic whitelist to avoid arbitrary injection
				allowed = {'utf-8','gb18030','gbk','big5','shift_jis','latin-1'}
				if enc.lower() not in allowed:
					return jsonify({'success': False,'error': {'code':'INVALID_ARGUMENT','message': f'不支持的编码: {enc}'}}), 400
				sd['forced_encoding'] = enc.lower()
			else:
				sd['forced_encoding'] = None
		return jsonify({'success': True,'data': {'terminal_id': terminal_id,'forced_encoding': sd.get('forced_encoding')}})
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'设置编码失败: {e}'}}), 500


@terminals_bp.route('/terminals/<terminal_id>/size', methods=['POST'])
def resize_terminal(terminal_id):
	"""Resize PTY for better wrapping.

	Request JSON: {"cols": <int>, "rows": <int>}.
	"""
	try:
		data = request.get_json() or {}
		cols = int(data.get('cols',0)); rows = int(data.get('rows',0))
		if cols <=0 or rows <=0:
			return jsonify({'success': False,'error': {'code':'INVALID_ARGUMENT','message': 'cols/rows 必须为正整数'}}), 400
		terminal_service.resize_terminal(terminal_id, cols, rows)
		return jsonify({'success': True,'data': {'terminal_id': terminal_id,'cols': cols,'rows': rows}})
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'调整终端大小失败: {e}'}}), 500


@terminals_bp.route('/terminals/<terminal_id>/locale', methods=['POST'])
def set_terminal_locale(terminal_id):
	"""Set or auto-detect a UTF-8 locale for the remote session.

	Request JSON examples:
	{"locale": "en_US.UTF-8"}
	{"auto": true}
	"""
	try:
		data = request.get_json() or {}
		locale = data.get('locale')
		auto = bool(data.get('auto'))
		result = terminal_service.set_locale(terminal_id, locale=locale, auto=auto)
		return jsonify({'success': True,'data': result})
	except ValueError as e:
		return jsonify({'success': False,'error': {'code':'NOT_FOUND','message': str(e)}}), 404
	except Exception as e:  # noqa
		return jsonify({'success': False,'error': {'code':'INTERNAL','message': f'设置 locale 失败: {e}'}}), 500

__all__ = ['terminals_bp']
