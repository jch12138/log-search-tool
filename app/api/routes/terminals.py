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
	session = terminal_service.create_terminal(host=host, port=port, username=username, password=password, private_key='', initial_command=data.get('initial_command',''))
	return {
		'terminal_id': session.terminal_id,
		'session_id': session.session_id,
		'connection_status': session.status,
		'host': session.host,
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
	session = terminal_service.create_terminal(host=ssh.get('host'), port=ssh.get('port',22), username=ssh.get('username'), password=ssh.get('password'), private_key='', initial_command=data.get('initial_command',''))
	return {
		'terminal_id': session.terminal_id,
		'session_id': session.session_id,
		'connection_status': session.status,
		'host': session.host,
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
			'session_history': s.session_history[-10:]
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

__all__ = ['terminals_bp']
