"""Servers aggregation routes (new).

Provides a unified list of SSH server endpoints derived from log configurations
so the SFTP UI can present available servers to connect.
"""

from __future__ import annotations

from flask import Blueprint, request
from app.services import ConfigService
from app.config.system_settings import Settings
from app.middleware import api_response

servers_bp = Blueprint('servers', __name__)
_config_service = ConfigService(Settings().CONFIG_FILE_PATH)


@servers_bp.route('/servers', methods=['GET'])
@api_response
def list_servers():
    """Return aggregated servers for SFTP / terminal usage.

    Query params:
      type: optional filter (currently only 'sftp' supported, ignored otherwise)
    """
    _ = request.args.get('type')  # placeholder for future filtering
    logs = _config_service.get_logs()
    # Aggregate by credential tuple
    agg = {}
    for log in logs:
        sshs = getattr(log, 'sshs', []) or []
        for idx, ssh in enumerate(sshs):
            host = ssh.get('host'); port = ssh.get('port', 22); user = ssh.get('username')
            if not host or not user:
                continue
            sid = f"{user}@{host}:{port}"
            entry = agg.setdefault(sid, {
                'server_id': sid,
                'host': host,
                'port': port,
                'username': user,
                # server_name can later be customized; keep host baseline
                'server_name': host,
                'log_configs': []
            })
            entry['log_configs'].append({'log_name': log.name, 'ssh_index': idx})
    servers = list(agg.values())
    servers.sort(key=lambda s: (s['host'], s['username'], s['port']))
    return {'servers': servers, 'total': len(servers)}

__all__ = ['servers_bp']
