"""
Shared TerminalService instance for use across REST routes and Socket.IO.
"""
from .terminal_service import TerminalService

# Singleton instance
terminal_service = TerminalService()
