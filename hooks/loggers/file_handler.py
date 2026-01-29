"""
Nova-tracer - File Handler Plugin.
Agent Monitoring and Visibility

Writes JSON-formatted log entries to a file named after the session ID.
Files are placed in .nova-tracer/logs/ by default.

Configuration in nova-config.yaml:
    logging:
      handlers:
        - file
      file:
        output_dir: ""  # Empty = default .nova-tracer/logs/
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict

# =============================================================================
# PLUGIN EXPORTS
# =============================================================================

HANDLER_NAME = "file"


def create_handler(config: Dict[str, Any], session_id: str) -> logging.Handler:
    """
    Create a file handler for the given session.
    
    Args:
        config: Logging configuration dictionary
        session_id: Current session ID (used for filename)
        
    Returns:
        Configured logging.FileHandler instance
    """
    # Get file-specific configuration
    file_config = config.get("file", {})
    output_dir = file_config.get("output_dir", "")

    # Determine output directory
    if output_dir:
        log_dir = Path(output_dir)
        if not log_dir.is_absolute():
            # Relative to project directory
            project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
            log_dir = Path(project_dir) / output_dir
    else:
        # Default: .nova-tracer/logs/
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
        log_dir = Path(project_dir) / ".nova-tracer" / "logs"

    # Create directory if needed
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create log file with session_id as filename
    log_file = log_dir / f"{session_id}.log"


    # Create and configure handler
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)  # Let logger level control filtering

    return handler


