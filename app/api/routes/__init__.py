from flask import Blueprint

from .logs import logs_bp  # noqa
from .sftp import sftp_bp  # noqa
from .terminals import terminals_bp  # noqa
from .connections import connections_bp  # noqa
from .config import config_bp  # noqa
from .servers import servers_bp  # noqa
from .account import account_bp  # noqa
from .workspace import workspace_bp  # noqa

def register_routes(app):
    """Register all API blueprints under /api/v1 prefix."""
    for bp in (logs_bp, sftp_bp, terminals_bp, connections_bp, config_bp, servers_bp):
        app.register_blueprint(bp, url_prefix='/api/v1')
    
    # account_bp 需要单独注册，因为它有子路径
    app.register_blueprint(account_bp, url_prefix='/api/v1/account')
    
    # workspace_bp 站点管理
    app.register_blueprint(workspace_bp, url_prefix='/api/v1/workspace')

__all__ = ['register_routes']

