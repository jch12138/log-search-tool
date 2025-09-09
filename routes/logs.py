"""Deprecated legacy route file.

All routes moved to app.api.routes.logs
This stub remains to avoid import errors; will be removed later.
"""

from flask import Blueprint

logs_bp = Blueprint('logs_legacy_removed', __name__)

__all__ = ['logs_bp']
