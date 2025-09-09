"""DEPRECATED shim: use app.services.terminal.service.TerminalService instead."""

from app.services.terminal.service import (  # noqa: F401
    TerminalService,
    TerminalSession,
)
