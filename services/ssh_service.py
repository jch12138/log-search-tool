"""
SSH连接管理器

负责管理SSH连接池和执行远程命令
"""

"""DEPRECATED shim: use app.services.ssh.manager instead."""

from app.services.ssh.manager import (  # noqa: F401
    SSHConnection,
    SSHConnectionManager,
)
