from flask import Blueprint

from .logs import logs_bp  # noqa
from .sftp import sftp_bp  # noqa
from .terminals import terminals_bp  # noqa
from .connections import connections_bp  # noqa
from .config import config_bp  # noqa
from .servers import servers_bp  # noqa

def register_routes(app):
    """Register all API blueprints under /api/v1 prefix."""
    for bp in (logs_bp, sftp_bp, terminals_bp, connections_bp, config_bp, servers_bp):
        app.register_blueprint(bp, url_prefix='/api/v1')

__all__ = ['register_routes']

