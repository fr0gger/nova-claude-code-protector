# NOVA Claude Code Protector - Shared Library Modules
# This package contains shared utilities used by all hooks.

from .session_manager import (
    generate_session_id,
    get_session_paths,
    init_session_file,
    append_event,
    get_active_session,
    finalize_session,
    get_next_event_id,
    truncate_output,
    read_session_events,
    extract_files_accessed,
    MAX_OUTPUT_SIZE,
)

__all__ = [
    "generate_session_id",
    "get_session_paths",
    "init_session_file",
    "append_event",
    "get_active_session",
    "finalize_session",
    "get_next_event_id",
    "truncate_output",
    "read_session_events",
    "extract_files_accessed",
    "MAX_OUTPUT_SIZE",
]
