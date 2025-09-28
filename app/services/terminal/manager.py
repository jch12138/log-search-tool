"""Shared singleton terminal service (migrated)."""

from .service import TerminalService
from app.config.system_settings import Settings

_settings = Settings()
terminal_service = TerminalService(
	idle_timeout=_settings.TERMINAL_IDLE_TIMEOUT,
	check_interval=_settings.TERMINAL_IDLE_CHECK_INTERVAL,
)

__all__ = ['terminal_service', 'TerminalService']
