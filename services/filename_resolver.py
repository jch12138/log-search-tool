"""DEPRECATED: moved to app.services.utils.filename_resolver

Use from app.services.utils.filename_resolver import resolve_log_filename.
This shim will be removed after full refactor cleanup.
"""

from app.services.utils.filename_resolver import (
    resolve_log_filename,
    validate_log_filename_pattern,
    FilenameResolver,
)  # noqa: F401

