#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
NOVA Claude Code Protector - User Prompt Capture Hook

This hook fires on UserPromptSubmit to capture user prompts for debugging and tracing.
Prompts are saved to the session JSONL alongside tool events for a complete conversation trace.

Exit codes:
  0 = Success (always - fail-open design)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib directory to path for imports
lib_dir = Path(__file__).parent / "lib"
sys.path.insert(0, str(lib_dir))

from session_manager import append_event, get_active_session, get_next_event_id


def main() -> None:
    """
    Main entry point for the UserPromptSubmit hook.

    Reads prompt from stdin, saves to session JSONL.
    Always exits 0 (fail-open design).
    """
    try:
        # Parse input from Claude Code
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError:
            sys.exit(0)

        # Extract prompt text
        prompt = input_data.get("prompt", "")
        if not prompt:
            sys.exit(0)

        # Use CLAUDE_PROJECT_DIR if available, fallback to cwd
        project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

        # Get active session
        session_id = get_active_session(project_dir)
        if not session_id:
            # No active session - nothing to capture
            sys.exit(0)

        # Get next event ID for this session
        event_id = get_next_event_id(session_id, project_dir)

        # Build prompt record
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        prompt_record = {
            "type": "user_prompt",
            "id": event_id,
            "timestamp": timestamp,
            "prompt": prompt,
            "prompt_length": len(prompt),
        }

        # Append to session JSONL
        append_event(session_id, project_dir, prompt_record)

    except Exception:
        pass  # Fail-open: never crash, never block

    sys.exit(0)


if __name__ == "__main__":
    main()
