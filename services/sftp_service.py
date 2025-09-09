"""DEPRECATED shim: use app.services.sftp.service.SFTPService instead."""

from app.services.sftp.service import (  # noqa: F401
    SFTPService,
    SFTPConnection,
)
