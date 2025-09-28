"""
Deprecated shim for Settings.

Please use `app.config.system_settings.Settings` instead. This module remains
to avoid import errors during transition but simply re-exports the new class.
"""

from .system_settings import Settings  # re-export

__all__ = ["Settings"]
