"""Connection management routes (migrated inline)."""

from __future__ import annotations

from flask import Blueprint, request
from app.middleware import api_response
from app.services import LogSearchService
from datetime import datetime

connections_bp = Blueprint('connections', __name__)
_search_service: LogSearchService | None = None


def _get_search_service() -> LogSearchService:
	global _search_service
	if _search_service is None:
		_search_service = LogSearchService()
	return _search_service


@connections_bp.route('/connections/stats', methods=['GET'])
@api_response
def get_connection_stats():
	svc = _get_search_service()
	stats = svc.ssh_manager.get_stats()
	return {
		'total_connections': stats['total_connections'],
		'active_connections': stats['active_connections'],
		'total_sessions': stats['total_connections'],
		'server_status': 'healthy' if stats['active_connections'] > 0 else 'idle',
		'connections': []
	}


@connections_bp.route('/connections/<client_id>/disconnect', methods=['POST'])
@api_response
def disconnect_connection(client_id: str):
	return {
		'message': f'客户端 {client_id} 已断开连接',
		'client_id': client_id,
		'disconnected_at': datetime.now().isoformat() + 'Z'
	}


@connections_bp.route('/connections/cleanup', methods=['POST'])
@api_response
def cleanup_connections():
	data = request.get_json() or {}
	timeout_minutes = data.get('timeout_minutes', 15)
	_get_search_service()  # ensure initialized
	return {
		'message': '已清理非活跃连接',
		'cleaned_connections': 0,
		'timeout_minutes': timeout_minutes
	}


@connections_bp.route('/connections/settings', methods=['GET'])
@api_response
def get_connection_settings():
	from app.config.system_settings import Settings
	_settings = Settings()
	return {
		'ping_timeout': 60,
		'ping_interval': 25,
		'disconnect_timeout': 180,
		'cleanup_interval': 120,
		'inactive_timeout': 900,
		'auto_cleanup_enabled': True,
		'ssh_timeout': _settings.SSH_TIMEOUT,
		'max_connections': 20
	}

__all__ = ['connections_bp']
