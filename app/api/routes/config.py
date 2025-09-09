"""Configuration management routes (migrated inline)."""

from __future__ import annotations

from flask import Blueprint, request
from app.middleware import api_response
from app.services import ConfigService
from config import Config
from datetime import datetime

config_bp = Blueprint('config', __name__)
_config_service = ConfigService(Config.CONFIG_FILE_PATH)


@config_bp.route('/config', methods=['GET'])
@api_response
def get_config():
	cfg = _config_service.load_config() or {}
	for log in cfg.get('logs', []):
		for ssh in log.get('sshs', []) or []:
			if 'password' in ssh:
				ssh['password'] = '***'
	return cfg


@config_bp.route('/config', methods=['PUT'])
@api_response
def update_config():
	incoming = request.get_json()
	if not incoming:
		raise ValueError('请求体不能为空')
	existing = _config_service.load_config() or {}
	existing_logs_map = {}
	for log in existing.get('logs', []):
		name = (log.get('name') or '').strip()
		path = (log.get('path') or '').strip()
		group = (log.get('group') or '').strip()
		key = f"{name}|{group}|{path}"
		existing_logs_map[key] = log
		if name and name not in existing_logs_map:
			existing_logs_map[name] = log
	merged = {'settings': incoming.get('settings', existing.get('settings', {})), 'logs': []}
	for log in incoming.get('logs', []) or []:
		name = (log.get('name') or '').strip()
		path = (log.get('path') or '').strip()
		group = (log.get('group') or '').strip()
		key = f"{name}|{group}|{path}"
		old_log = existing_logs_map.get(key) or (existing_logs_map.get(name) if name else None)
		new_log = {'name': name,'path': path,'group': group,'description': log.get('description'),'sshs': []}
		old_ssh_map = {}
		if old_log and isinstance(old_log.get('sshs'), list):
			for s in old_log['sshs']:
				host = (s.get('host') or '').strip(); port = s.get('port',22); user = (s.get('username') or '').strip()
				old_ssh_map[f"{host}:{port}@{user}"] = s
		for s in log.get('sshs', []) or []:
			host = (s.get('host') or '').strip(); port = s.get('port',22); user = (s.get('username') or '').strip()
			key_ssh = f"{host}:{port}@{user}"
			old_s = old_ssh_map.get(key_ssh, {})
			new_pw = (s.get('password') or '').strip()
			old_pw = old_s.get('password','')
			pw = new_pw if new_pw else old_pw
			entry = {'host': host,'port': port,'username': user}
			if pw: entry['password'] = pw
			new_log['sshs'].append(entry)
		merged['logs'].append(new_log)
	_config_service.save_config(merged)
	return {
		'message': '配置保存成功',
		'saved_at': datetime.now().isoformat() + 'Z',
		'logs_count': len(merged.get('logs', [])),
		'backup_created': f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.yaml"
	}

__all__ = ['config_bp']
