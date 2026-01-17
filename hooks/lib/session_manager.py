"""
Session Manager Module for NOVA Claude Code Protector.

This module provides the foundation for session capture, managing:
- Session ID generation (unique, timestamp-based)
- Storage path resolution
- Session file initialization (JSON Lines format)
- Event appending (fail-open, <0.5ms performance target)
- Session state utilities

All functions follow fail-open philosophy: never crash, always log errors.
"""

import json
import logging
import platform
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Configure logging to stderr (never stdout - that's for Claude Code communication)
logging.basicConfig(
    level=logging.WARNING,
    format="[NOVA %(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("nova-protector.session")

# Constants
NOVA_DIR_NAME = ".nova-protector"
SESSIONS_DIR_NAME = "sessions"
REPORTS_DIR_NAME = "reports"
SESSION_FILE_EXT = ".jsonl"
ACTIVE_SESSION_MARKER = ".active"


def generate_session_id() -> str:
    """
    Generate a unique session ID in format: YYYY-MM-DD_HH-MM-SS_abc123

    The timestamp uses underscores instead of colons for filesystem safety.
    The 6-character hash suffix ensures uniqueness even for rapid session creation.

    Returns:
        str: Session ID like "2026-01-10_16-30-45_a1b2c3"
    """
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")
    # Generate 6 random hex characters for uniqueness
    hash_suffix = secrets.token_hex(3)  # 3 bytes = 6 hex chars
    return f"{timestamp}_{hash_suffix}"


def get_session_paths(project_dir: Union[str, Path]) -> Dict[str, Path]:
    """
    Get paths for session storage and create directories if needed.

    Args:
        project_dir: The project root directory

    Returns:
        dict with 'sessions' and 'reports' Path objects
    """
    project_path = Path(project_dir)
    nova_dir = project_path / NOVA_DIR_NAME

    paths = {
        "sessions": nova_dir / SESSIONS_DIR_NAME,
        "reports": nova_dir / REPORTS_DIR_NAME,
    }

    # Create directories if they don't exist (fail-open)
    for name, path in paths.items():
        try:
            path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning(f"Failed to create {name} directory at {path}: {e}")

    return paths


def init_session_file(session_id: str, project_dir: Union[str, Path]) -> Optional[Path]:
    """
    Initialize a new session file with an init record.

    Creates a .jsonl file and writes the initial record containing:
    - session_id
    - timestamp (ISO 8601)
    - platform
    - project_dir

    Args:
        session_id: The unique session identifier
        project_dir: The project root directory

    Returns:
        Path to the created session file, or None on failure
    """
    try:
        paths = get_session_paths(project_dir)
        session_file = paths["sessions"] / f"{session_id}{SESSION_FILE_EXT}"

        init_record = {
            "type": "init",
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "platform": platform.system().lower(),
            "project_dir": str(Path(project_dir).resolve()),
        }

        # Write init record as first line
        with open(session_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(init_record, separators=(",", ":")) + "\n")

        # Create active session marker
        marker_file = paths["sessions"] / ACTIVE_SESSION_MARKER
        marker_file.write_text(session_id, encoding="utf-8")

        logger.debug(f"Session initialized: {session_id}")
        return session_file

    except Exception as e:
        logger.warning(f"Failed to initialize session file: {e}")
        return None


def append_event(session_id: str, project_dir: Union[str, Path], event_data: Dict[str, Any]) -> bool:
    """
    Append an event record to the session file.

    Performance target: < 0.5ms for file I/O.
    Error handling: Fail-open - never raises, returns False on failure.

    Args:
        session_id: The session identifier
        project_dir: The project root directory
        event_data: The event data to append (must be JSON-serializable)

    Returns:
        True on success, False on failure
    """
    try:
        paths = get_session_paths(project_dir)
        session_file = paths["sessions"] / f"{session_id}{SESSION_FILE_EXT}"

        if not session_file.exists():
            logger.warning(f"Session file not found: {session_file}")
            return False

        # Ensure event has type field
        if "type" not in event_data:
            event_data = {"type": "event", **event_data}

        # Append as single JSON line (compact format for performance)
        with open(session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_data, separators=(",", ":")) + "\n")

        return True

    except Exception as e:
        logger.warning(f"Failed to append event: {e}")
        return False  # Fail open - don't crash


def get_active_session(project_dir: Union[str, Path]) -> Optional[str]:
    """
    Get the currently active session ID for a project, if any.

    Args:
        project_dir: The project root directory

    Returns:
        Session ID string if active session exists, None otherwise
    """
    try:
        paths = get_session_paths(project_dir)
        marker_file = paths["sessions"] / ACTIVE_SESSION_MARKER

        if marker_file.exists():
            session_id = marker_file.read_text(encoding="utf-8").strip()
            session_file = paths["sessions"] / f"{session_id}{SESSION_FILE_EXT}"

            if session_file.exists():
                return session_id
            else:
                # Marker exists but session file is gone - clean up
                marker_file.unlink(missing_ok=True)

        return None

    except Exception as e:
        logger.warning(f"Failed to get active session: {e}")
        return None


def finalize_session(session_id: str, project_dir: Union[str, Path]) -> Optional[Path]:
    """
    Finalize a session by removing the active marker.

    The session .jsonl file remains intact for report generation.

    Args:
        session_id: The session identifier
        project_dir: The project root directory

    Returns:
        Path to the session file, or None on failure
    """
    try:
        paths = get_session_paths(project_dir)
        marker_file = paths["sessions"] / ACTIVE_SESSION_MARKER
        session_file = paths["sessions"] / f"{session_id}{SESSION_FILE_EXT}"

        # Remove active marker
        if marker_file.exists():
            current_session = marker_file.read_text(encoding="utf-8").strip()
            if current_session == session_id:
                marker_file.unlink()

        if session_file.exists():
            logger.debug(f"Session finalized: {session_id}")
            return session_file
        else:
            logger.warning(f"Session file not found during finalization: {session_id}")
            return None

    except Exception as e:
        logger.warning(f"Failed to finalize session: {e}")
        return None


def get_next_event_id(session_id: str, project_dir: Union[str, Path]) -> int:
    """
    Get the next sequential event ID for a session.

    Reads existing events and returns max ID + 1.
    For the first event, returns 1.

    Args:
        session_id: The session identifier
        project_dir: The project root directory

    Returns:
        Next sequential event ID (starting from 1)
    """
    try:
        events = read_session_events(session_id, project_dir)
        if not events:
            return 1

        # Find max ID among event and user_prompt records (not init records)
        event_ids = [
            e.get("id", 0)
            for e in events
            if e.get("type") in ("event", "user_prompt") and isinstance(e.get("id"), int)
        ]

        if not event_ids:
            return 1

        return max(event_ids) + 1

    except Exception as e:
        logger.warning(f"Failed to get next event ID: {e}")
        return 1  # Fail-open: return 1 as default


# Default output truncation limit (10KB)
MAX_OUTPUT_SIZE = 10 * 1024


def truncate_output(text: str, max_bytes: int = MAX_OUTPUT_SIZE) -> Tuple[Optional[str], Optional[int]]:
    """
    Truncate output if it exceeds max_bytes.

    Args:
        text: The output text to potentially truncate
        max_bytes: Maximum size in bytes (default 10KB)

    Returns:
        Tuple of (truncated_text, original_size_or_None)
        If not truncated, original_size is None
    """
    if not text:
        return text, None

    try:
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text, None

        # Truncate at byte boundary, decode safely
        truncated_bytes = encoded[:max_bytes]
        truncated = truncated_bytes.decode("utf-8", errors="ignore")

        original_size = len(encoded)
        marker = f"\n[TRUNCATED - original size: {original_size / 1024:.1f} KB]"

        return truncated + marker, original_size

    except Exception as e:
        logger.warning(f"Failed to truncate output: {e}")
        return text, None  # Fail-open: return original


def read_session_events(session_id: str, project_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    """
    Read all events from a session file.

    This is a utility function for report generation.

    Args:
        session_id: The session identifier
        project_dir: The project root directory

    Returns:
        List of event dictionaries, empty list on failure
    """
    try:
        paths = get_session_paths(project_dir)
        session_file = paths["sessions"] / f"{session_id}{SESSION_FILE_EXT}"

        if not session_file.exists():
            logger.debug(f"Session file not found: {session_file}")
            return []

        events = []
        with open(session_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse line: {e}")
                        continue

        return events

    except Exception as e:
        logger.warning(f"Failed to read session events: {e}")
        return []


import re

# Regex patterns for extracting file paths from Bash commands
_BASH_PATH_PATTERN = re.compile(
    r'(?:^|\s)('
    r'/[^\s"\'<>|;&]+|'          # Absolute paths: /path/to/file
    r'\./[^\s"\'<>|;&]+|'        # Relative paths: ./file
    r'\.\./[^\s"\'<>|;&]+|'      # Parent paths: ../file
    r'~/[^\s"\'<>|;&]+'          # Home paths: ~/file
    r')'
)


def _extract_paths_from_bash(command: str) -> List[str]:
    """
    Extract file paths from a bash command.

    Handles:
    - Absolute paths (/path/to/file)
    - Relative paths (./file, ../file)
    - Home directory paths (~/file)

    Filters out:
    - CLI flags (-rf, --option)
    - URLs (http://, https://, ftp://)

    Args:
        command: The bash command string

    Returns:
        List of extracted file paths
    """
    if not command:
        return []

    paths = []

    for match in _BASH_PATH_PATTERN.finditer(command):
        path = match.group(1).strip()

        # Skip if it's empty or just whitespace
        if not path:
            continue

        # Skip CLI flags (shouldn't match, but safety check)
        if path.startswith('-'):
            continue

        # Skip URLs
        if '://' in path:
            continue

        # Clean trailing punctuation that might have been captured
        path = path.rstrip('.,;:)')

        if path:
            paths.append(path)

    return paths


def extract_files_accessed(tool_name: str, tool_input: Optional[Dict[str, Any]]) -> List[str]:
    """
    Extract file paths accessed by a tool.

    Extracts paths from tool_input based on the tool type:
    - Read/Edit/Write: file_path field
    - Glob/Grep: path field
    - Bash: regex extraction from command

    Args:
        tool_name: Name of the tool (Read, Edit, Bash, etc.)
        tool_input: The tool's input parameters

    Returns:
        List of file paths, empty list if none
    """
    if not tool_input:
        return []

    paths = []

    try:
        # Direct path extraction for file-based tools
        if tool_name in ("Read", "Edit", "Write"):
            file_path = tool_input.get("file_path")
            if file_path and isinstance(file_path, str):
                paths.append(file_path)

        elif tool_name in ("Glob", "Grep"):
            path = tool_input.get("path")
            if path and isinstance(path, str):
                paths.append(path)

        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            if command and isinstance(command, str):
                paths.extend(_extract_paths_from_bash(command))

        elif tool_name == "NotebookEdit":
            notebook_path = tool_input.get("notebook_path")
            if notebook_path and isinstance(notebook_path, str):
                paths.append(notebook_path)

        # Deduplicate while preserving order
        seen = set()
        unique_paths = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                unique_paths.append(p)

        return unique_paths

    except Exception as e:
        logger.warning(f"Failed to extract files accessed: {e}")
        return []  # Fail-open


def calculate_session_statistics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate aggregate statistics from session events.

    Args:
        events: List of event dictionaries from read_session_events()

    Returns:
        Dictionary with statistics:
        - total_events: count of event records
        - user_prompts: count of user prompt records
        - total_prompt_chars: total characters in user prompts
        - tools_used: dict mapping tool names to counts
        - files_touched: count of unique files
        - warnings: count of warned verdicts
        - blocked: count of blocked verdicts
        - duration_seconds: session duration (if init record exists)
    """
    stats = {
        "total_events": 0,
        "user_prompts": 0,
        "total_prompt_chars": 0,
        "tools_used": {},
        "files_touched": 0,
        "warnings": 0,
        "blocked": 0,
        "duration_seconds": 0,
        # MCP-specific statistics
        "mcp_calls": 0,
        "mcp_servers": {},  # server_name -> call count
        "mcp_errors": 0,
        # Skill-specific statistics
        "skill_calls": 0,
        "skills_used": {},  # skill_name -> call count
        "skill_errors": 0,
    }

    try:
        # Filter to event records (tool calls)
        event_records = [e for e in events if e.get("type") == "event"]
        stats["total_events"] = len(event_records)

        # Count user prompts
        prompt_records = [e for e in events if e.get("type") == "user_prompt"]
        stats["user_prompts"] = len(prompt_records)
        stats["total_prompt_chars"] = sum(e.get("prompt_length", 0) for e in prompt_records)

        # Count tools used, MCP statistics, and Skill statistics
        tools = {}
        all_files = set()
        mcp_servers = {}
        skills_used = {}

        for event in event_records:
            tool_name = event.get("tool_name", "unknown")
            tools[tool_name] = tools.get(tool_name, 0) + 1

            # Collect files accessed
            files = event.get("files_accessed", [])
            if isinstance(files, list):
                all_files.update(files)

            # Count verdicts
            verdict = event.get("nova_verdict", "allowed")
            if verdict == "warned":
                stats["warnings"] += 1
            elif verdict == "blocked":
                stats["blocked"] += 1

            # Count MCP calls
            if event.get("is_mcp"):
                stats["mcp_calls"] += 1
                server = event.get("mcp_server", "unknown")
                mcp_servers[server] = mcp_servers.get(server, 0) + 1
                if event.get("is_error"):
                    stats["mcp_errors"] += 1

            # Count Skill calls
            if event.get("is_skill"):
                stats["skill_calls"] += 1
                skill_name = event.get("skill_name", "unknown")
                skills_used[skill_name] = skills_used.get(skill_name, 0) + 1
                if event.get("is_error"):
                    stats["skill_errors"] += 1

        stats["tools_used"] = tools
        stats["files_touched"] = len(all_files)
        stats["mcp_servers"] = mcp_servers
        stats["skills_used"] = skills_used

        # Calculate duration from init record if available
        init_record = next((e for e in events if e.get("type") == "init"), None)
        if init_record and event_records:
            try:
                # Get session start from init
                start_str = init_record.get("timestamp", "")
                # Get last event end time
                last_event = event_records[-1]
                end_str = last_event.get("timestamp_end", "")

                if start_str and end_str:
                    start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                    stats["duration_seconds"] = int((end - start).total_seconds())
            except Exception:
                pass  # Keep duration_seconds as 0

    except Exception as e:
        logger.warning(f"Failed to calculate statistics: {e}")

    return stats


def estimate_activity_metrics(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Estimate session activity metrics from captured tool events.

    Uses heuristic: ~4 characters per token (standard approximation).
    This provides rough estimates without needing OTel or wrapper scripts.

    Args:
        events: List of event dictionaries from read_session_events()

    Returns:
        Dictionary with estimated metrics:
        - estimated_input_tokens: approx tokens from tool inputs
        - estimated_output_tokens: approx tokens from tool outputs
        - tool_calls: count of tool executions
        - total_duration_ms: sum of tool execution times
        - is_estimate: True (flag for UI disclaimer)
    """
    metrics = {
        "estimated_input_tokens": 0,
        "estimated_output_tokens": 0,
        "tool_calls": 0,
        "total_duration_ms": 0,
        "is_estimate": True,
    }

    try:
        # Filter to only event records (not init records)
        event_records = [e for e in events if e.get("type") == "event"]
        metrics["tool_calls"] = len(event_records)

        total_input_chars = 0
        total_output_chars = 0

        for event in event_records:
            # Measure tool_input size (serialize to get character count)
            tool_input = event.get("tool_input")
            if tool_input:
                try:
                    input_str = json.dumps(tool_input, separators=(",", ":"))
                    total_input_chars += len(input_str)
                except (TypeError, ValueError):
                    pass

            # Measure tool_output size
            tool_output = event.get("tool_output")
            if tool_output:
                output_str = str(tool_output)
                total_output_chars += len(output_str)

            # Sum durations
            duration = event.get("duration_ms", 0)
            if isinstance(duration, (int, float)):
                metrics["total_duration_ms"] += int(duration)

        # Convert chars to estimated tokens (heuristic: ~4 chars per token)
        metrics["estimated_input_tokens"] = total_input_chars // 4
        metrics["estimated_output_tokens"] = total_output_chars // 4

    except Exception as e:
        logger.warning(f"Failed to estimate activity metrics: {e}")

    return metrics


def build_session_object(
    session_id: str,
    project_dir: Union[str, Path],
    session_end_time: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build a complete session object for report generation.

    Reads all events from the session file and constructs a complete
    session object with metadata, events, and statistics.

    Args:
        session_id: The session identifier
        project_dir: The project root directory
        session_end_time: Optional ISO timestamp for session end

    Returns:
        Complete session dictionary, or minimal error object on failure
    """
    try:
        events = read_session_events(session_id, project_dir)

        # Extract init record for metadata
        init_record = next((e for e in events if e.get("type") == "init"), None)
        # Include both tool events and user prompts for conversation trace
        event_records = [e for e in events if e.get("type") in ("event", "user_prompt")]

        # Build session object
        session = {
            "session_id": session_id,
            "session_start": init_record.get("timestamp", "") if init_record else "",
            "session_end": session_end_time or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "platform": init_record.get("platform", platform.system().lower()) if init_record else platform.system().lower(),
            "project_dir": init_record.get("project_dir", str(project_dir)) if init_record else str(project_dir),
            "events": event_records,
            "summary": {
                "ai_summary": None,  # Will be filled by ai_summary module
                **calculate_session_statistics(events)
            }
        }

        return session

    except Exception as e:
        logger.warning(f"Failed to build session object: {e}")
        # Return minimal session object on error
        return {
            "session_id": session_id,
            "session_start": "",
            "session_end": session_end_time or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "platform": platform.system().lower(),
            "project_dir": str(project_dir),
            "events": [],
            "summary": {
                "ai_summary": None,
                "total_events": 0,
                "tools_used": {},
                "files_touched": 0,
                "warnings": 0,
                "blocked": 0,
                "duration_seconds": 0,
            },
            "error": str(e)
        }
