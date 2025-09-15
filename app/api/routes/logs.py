"""Logs routes (migrated) – updated to use new app.services namespace only."""
import os
import logging
import io
from flask import Blueprint, request, send_file
from app.middleware import api_response
from app.services import ConfigService, LogSearchService, SSHConnectionManager
from app.models import SearchParams
from config import Config

logs_bp = Blueprint('logs', __name__)

config_service = ConfigService(Config.CONFIG_FILE_PATH)
search_service = LogSearchService()
logger = logging.getLogger(__name__)

@logs_bp.route('/logs', methods=['GET'])
@api_response
def list_logs():
	include_ssh = request.args.get('include_ssh', '').lower() == 'true'
	if include_ssh:
		logs_summary = config_service.get_log_summary()
		log_configs = []
		for log in logs_summary:
			log_config = config_service.get_log_by_name(log['name'])
			if log_config and hasattr(log_config, 'sshs') and log_config.sshs:
				for idx, ssh_config in enumerate(log_config.sshs):
					suffix = f"#{idx+1}" if len(log_config.sshs) > 1 else ""
					connection_name = f"{log_config.name} - {ssh_config.get('host','unknown')}{suffix}"
					log_configs.append({
						'log_name': log_config.name,
						'connection_name': connection_name,
						'host': ssh_config.get('host', ''),
						'ip': ssh_config.get('host', ''),
						'port': ssh_config.get('port', 22),
						'username': ssh_config.get('username', ''),
						'password': '***',
						'log_path': ssh_config.get('path') or getattr(log_config, 'path', ''),
						'ssh_index': idx,
						'group': log_config.group
					})
		return {'log_configs': log_configs, 'total': len(log_configs)}
	else:
		logs_summary = config_service.get_log_summary()
		return {'logs': logs_summary, 'total': len(logs_summary)}

@logs_bp.route('/logs/<log_name>', methods=['GET'])
@api_response
def get_log_detail(log_name: str):
	log_detail = config_service.get_log_detail(log_name)
	if not log_detail:
		raise FileNotFoundError(f'未找到日志配置: {log_name}')
	return log_detail

@logs_bp.route('/logs/<log_name>/files', methods=['GET'])
@api_response
def get_log_files(log_name: str):
	log_config = config_service.get_log_by_name(log_name)
	if not log_config:
		raise FileNotFoundError(f'未找到日志配置: {log_name}')
	all_files = []
	for ssh_config in log_config.sshs:
		try:
			log_path = ssh_config.get('path') or getattr(log_config, 'path', '') or ''
			if not log_path:
				continue
			files = search_service.get_log_files(ssh_config, log_path)
			all_files.extend(files)
		except Exception:
			continue
	return {'files': all_files, 'log_name': log_name, 'total_files': len(all_files)}

@logs_bp.route('/logs/<log_name>/search', methods=['POST'])
@api_response
def search_log(log_name: str):
	client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
	if ',' in client_ip:
		client_ip = client_ip.split(',')[0].strip()
	log_config = config_service.get_log_by_name(log_name)
	if not log_config:
		raise FileNotFoundError(f'未找到日志配置: {log_name}')
	data = request.get_json() or {}
	search_params = SearchParams(
		keyword=data.get('keyword', ''),
		search_mode=data.get('search_mode', 'keyword'),
		context_span=int(data.get('context_span', 5)),
		use_regex=bool(data.get('use_regex', False)),
		reverse_order=bool(data.get('reverse_order', False)),
		use_file_filter=bool(data.get('use_file_filter', False)),
		selected_file=data.get('selected_file'),
		selected_files=data.get('selected_files'),
		max_lines=int(data['max_lines']) if 'max_lines' in data and str(data['max_lines']).isdigit() else None
	)
	logger.info(f"[SEARCH] IP: {client_ip} | Log: {log_name} | Keyword: '{search_params.keyword}' | Mode: {search_params.search_mode}")
	result = search_service.search_multi_host(log_config.to_dict(), search_params)
	logger.info(f"[SEARCH RESULT] IP: {client_ip} | Log: {log_name} | Matches: {result.total_results} | Time: {result.total_search_time:.3f}s")
	return result.to_dict()

@logs_bp.route('/logs/download', methods=['GET'])
def download_log_file():
	host = request.args.get('host')
	file_path = request.args.get('file_path')
	log_name = request.args.get('log_name')
	if not host or not file_path:
		from flask import jsonify
		return jsonify({'success': False,'error': {'code': 'VALIDATION_ERROR','message': '缺少必要参数: host 和 file_path'}}), 400
	ssh_config = None
	if log_name:
		log_config = config_service.get_log_by_name(log_name)
		if log_config and hasattr(log_config, 'sshs'):
			for ssh in log_config.sshs:
				if ssh.get('host') == host:
					ssh_config = ssh; break
	if not ssh_config:
		logs_summary = config_service.get_log_summary()
		for log in logs_summary:
			log_config = config_service.get_log_by_name(log['name'])
			if log_config and hasattr(log_config, 'sshs'):
				for ssh in log_config.sshs:
					if ssh.get('host') == host:
						ssh_config = ssh; break
				if ssh_config: break
	if not ssh_config:
		from flask import jsonify
		return jsonify({'success': False,'error': {'code': 'NOT_FOUND','message': f'未找到主机 {host} 的SSH配置'}}), 404
	try:
		ssh_manager = SSHConnectionManager()
		conn = ssh_manager.get_connection(ssh_config)
		if not conn:
			from flask import jsonify
			return jsonify({'success': False,'error': {'code': 'CONNECTION_ERROR','message': 'SSH连接失败'}}), 500
		# 若 file_path 包含占位符，先进行解析
		from app.services.utils.filename_resolver import resolve_log_filename
		if any(ph in file_path for ph in ['{YYYY}', '{MM}', '{DD}', '{N}']):
			try:
				resolved = resolve_log_filename(file_path, ssh_conn=conn)
				file_path = resolved
			except Exception as _e:  # noqa
				logger.warning(f"下载前解析文件名占位符失败: {file_path} - {_e}")
		command = f"cat '{file_path}'"
		stdout, stderr, exit_code = conn.execute_command(command, timeout=60)
		if exit_code != 0:
			from flask import jsonify
			return jsonify({'success': False,'error': {'code': 'INTERNAL','message': f'读取文件失败: {stderr}'}}), 500
		if not stdout:
			stdout = ''
		from datetime import datetime
		file_name = os.path.basename(file_path) or 'log'
		ts = datetime.now().strftime('%Y%m%d_%H%M%S')
		download_filename = f"{host}_{file_name}_{ts}"
		if not download_filename.endswith('.log'):
			download_filename += '.log'
		file_obj = io.BytesIO(stdout.encode('utf-8'))
		file_obj.seek(0)
		import flask
		if tuple(map(int, flask.__version__.split('.'))) >= (2,0,0):
			return send_file(file_obj, mimetype='text/plain', as_attachment=True, download_name=download_filename)
		else:
			from flask import Response
			return Response(file_obj.getvalue(), mimetype='text/plain', headers={'Content-Disposition': f'attachment; filename="{download_filename}"'})
	except Exception as e:
		logger.error(f"下载文件失败: {e}")
		from flask import jsonify
		return jsonify({'success': False,'error': {'code': 'INTERNAL','message': f'下载文件失败: {e}'}}), 500
	finally:
		if 'ssh_manager' in locals():
			ssh_manager.close_all()

__all__ = ['logs_bp']
