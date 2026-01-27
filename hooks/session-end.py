#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["anthropic", "pyyaml"]
# ///
"""
NOVA Claude Code Protector - Session End Hook

This hook fires when a Claude Code session ends.
It finalizes the session JSONL, generates an HTML report, and cleans up.

Exit codes:
  0 = Success (always - fail-open design)
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add lib directory to path for imports
lib_dir = Path(__file__).parent / "lib"
sys.path.insert(0, str(lib_dir))

from ai_summary import generate_ai_summary
from report_generator import generate_html_report, save_report
from session_manager import (
    build_session_object,
    estimate_activity_metrics,
    finalize_session,
    get_active_session,
    get_session_paths,
)

from config import get_config

# Configure logging - only warnings and errors to stderr
logging.basicConfig(
    level=logging.WARNING,
    format="[NOVA %(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("nova-protector.session-end")


def main() -> None:
    """
    Main entry point for the SessionEnd hook.

    Reads session info from stdin, generates HTML report, finalizes session.
    Always exits 0 (fail-open design).
    """
    try:
        # Load configuration
        config = get_config()

        # Parse input from Claude Code
        try:
            input_data = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse stdin JSON: {e}")
            sys.exit(0)

        # Claude Code provides its own session_id (UUID format), but we ignore it
        # because NOVA generates its own timestamp-based session IDs
        session_end_time = input_data.get("session_end_time", "")

        # Use CLAUDE_PROJECT_DIR if available, fallback to cwd
        project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", str(Path.cwd())))

        # Get NOVA's active session ID (timestamp format, not Claude's UUID)
        session_id = get_active_session(str(project_dir))

        if not session_id:
            logger.warning("No active NOVA session found, cannot generate report")
            sys.exit(0)

        # Build complete session object
        session_data = build_session_object(
            session_id=session_id,
            project_dir=project_dir,
            session_end_time=session_end_time or None,
        )

        # Calculate estimated activity metrics from session events
        # Uses character count heuristic (~4 chars per token) - no wrapper needed
        activity_metrics = estimate_activity_metrics(session_data.get("events", []))
        session_data["activity_metrics"] = activity_metrics
        logger.debug(f"Estimated activity: {activity_metrics.get('tool_calls', 0)} tool calls")

        # Generate AI summary and add to session data
        # Respects ai_summary_enabled config setting
        ai_summary = generate_ai_summary(
            session_data,
            ai_enabled=config.ai_summary_enabled,
        )
        session_data["summary"]["ai_summary"] = ai_summary

        # Generate HTML report
        html_content = generate_html_report(session_data)

        # Determine report output directory from config
        report_dir = config.get_report_output_dir(project_dir)
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{session_id}.html"

        if save_report(html_content, report_path):
            logger.info(f"Report saved: {report_path}")
        else:
            logger.warning(f"Failed to save report to {report_path}")

        # Finalize session (remove active marker)
        finalize_session(session_id, project_dir)

        # Success
        sys.exit(0)

    except Exception as e:
        # Fail-open: log error but exit 0
        logger.warning(f"Session end hook error: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
