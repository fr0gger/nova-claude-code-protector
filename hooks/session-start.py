#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
NOVA Claude Code Protector - Session Start Hook

Initializes session capture when Claude Code session starts.
Creates .jsonl file for event logging with an init record.

Hook Event: SessionStart
Fires: When Claude Code session starts or resumes

This hook implements:
- AC1: New session initialization (generate ID, create .jsonl)
- AC2: Session resume detection (detect existing active session)
- AC3: Fail-open error handling (always exit 0)
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Add hooks/lib to path for imports
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from session_manager import (
    generate_session_id,
    get_active_session,
    init_session_file,
)

# Configure logging to stderr (never stdout - reserved for Claude feedback)
logging.basicConfig(
    level=logging.WARNING,
    format="[NOVA %(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("nova-protector.session-start")


def parse_hook_input() -> Optional[Dict[str, Any]]:
    """
    Parse JSON input from stdin.

    Returns:
        Parsed JSON dict or None if parsing fails
    """
    try:
        # Check if stdin has data
        if sys.stdin.isatty():
            logger.debug("No stdin input (interactive mode)")
            return {}

        content = sys.stdin.read()
        if not content.strip():
            logger.debug("Empty stdin input")
            return {}

        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.warning(f"Invalid JSON input: {e}")
        return None
    except Exception as e:
        logger.warning(f"Error reading stdin: {e}")
        return None


def get_project_dir(hook_input: Optional[Dict[str, Any]]) -> str:
    """
    Determine the project directory.

    Uses CLAUDE_PROJECT_DIR environment variable if set by Claude Code,
    otherwise falls back to current working directory.

    Args:
        hook_input: Parsed hook input (may contain hints)

    Returns:
        Absolute path to project directory
    """
    # Use CLAUDE_PROJECT_DIR if available, fallback to cwd
    return os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())


def handle_session_start(project_dir: str) -> bool:
    """
    Handle session start event.

    Implements:
    - AC1: New session initialization
    - AC2: Session resume detection

    Args:
        project_dir: Path to the project directory

    Returns:
        True on success, False on failure (but never raises)
    """
    try:
        # AC2: Check for existing active session
        active_session = get_active_session(project_dir)

        if active_session:
            # Session already active - resume mode
            logger.debug(f"Resuming existing session: {active_session}")
            return True

        # AC1: Create new session
        session_id = generate_session_id()
        result = init_session_file(session_id, project_dir)

        if result:
            logger.debug(f"Session initialized: {session_id}")
            return True
        else:
            logger.warning("Failed to initialize session file")
            return False

    except Exception as e:
        logger.warning(f"Error in session start handler: {e}")
        return False


def print_banner() -> None:
    """Print NOVA protection active banner to stderr."""
    banner = "\033[36m🛡️  NOVA Protection Active\033[0m"
    print(banner, file=sys.stderr)


def main() -> None:
    """
    Main entry point for the session-start hook.

    Implements AC3: Fail-open error handling.
    Always exits with code 0 to never block Claude Code.
    """
    try:
        # Parse hook input from stdin
        hook_input = parse_hook_input()

        # Get project directory
        project_dir = get_project_dir(hook_input)

        # Handle session start
        success = handle_session_start(project_dir)

        if success:
            # Show banner to indicate NOVA is active
            print_banner()
        else:
            logger.debug("Session start completed with warnings")

    except Exception as e:
        # AC3: Fail-open - log error but never crash
        logger.error(f"Unexpected error in session-start hook: {e}")

    # Always exit 0 - never block Claude Code operation
    sys.exit(0)


if __name__ == "__main__":
    main()
