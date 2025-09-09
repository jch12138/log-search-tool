"""Shared singleton terminal service (migrated)."""

import os
from .service import TerminalService

_idle_timeout = int(os.getenv('TERMINAL_IDLE_TIMEOUT', '0') or '0')
_check_interval = int(os.getenv('TERMINAL_IDLE_CHECK_INTERVAL', '30') or '30')

terminal_service = TerminalService(idle_timeout=_idle_timeout, check_interval=_check_interval)

__all__ = ['terminal_service', 'TerminalService']
