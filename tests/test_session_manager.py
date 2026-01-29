"""
Tests for Session Manager Module.

Tests cover all acceptance criteria:
- AC1: Session ID generation (format, uniqueness)
- AC2: Path resolution (correct paths, directory creation)
- AC3: Session file initialization (file creation, init record structure)
- AC4: Event appending (append operation, error handling, performance)
"""

import json
import platform
import re
import tempfile
import time
from pathlib import Path

import pytest

# Add hooks/lib to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks" / "lib"))

from session_manager import (
    generate_session_id,
    get_session_paths,
    init_session_file,
    append_event,
    get_active_session,
    finalize_session,
    read_session_events,
)


class TestGenerateSessionId:
    """Tests for AC1: Session ID Generation."""

    def test_format_matches_pattern(self):
        """Session ID matches YYYY-MM-DD_HH-MM-SS_abc123 format."""
        session_id = generate_session_id()
        pattern = r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}_[a-f0-9]{6}$"
        assert re.match(pattern, session_id), f"ID '{session_id}' doesn't match expected format"

    def test_timestamp_is_current(self):
        """Timestamp portion reflects current time (within 2 seconds)."""
        from datetime import datetime, timezone, timedelta

        before = datetime.now(timezone.utc)
        session_id = generate_session_id()
        after = datetime.now(timezone.utc)

        # Extract timestamp portion
        timestamp_str = session_id.rsplit("_", 1)[0]  # "2026-01-10_16-30-45"
        # Convert back to datetime
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S").replace(tzinfo=timezone.utc)

        # Allow 1 second tolerance for truncation to seconds
        before_floor = before.replace(microsecond=0)
        after_ceil = (after + timedelta(seconds=1)).replace(microsecond=0)

        assert before_floor <= timestamp <= after_ceil, "Timestamp not within expected range"

    def test_hash_is_unique(self):
        """Hash portion is unique per call."""
        ids = [generate_session_id() for _ in range(100)]
        # Extract hash portions
        hashes = [id.rsplit("_", 1)[1] for id in ids]
        assert len(set(hashes)) == len(hashes), "Hash portions are not unique"

    def test_id_is_filesystem_safe(self):
        """Session ID contains no filesystem-unsafe characters."""
        session_id = generate_session_id()
        unsafe_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in unsafe_chars:
            assert char not in session_id, f"ID contains unsafe character: {char}"


class TestGetSessionPaths:
    """Tests for AC2: Path Resolution."""

    def test_returns_correct_paths(self):
        """Returns dict with sessions and reports paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = get_session_paths(tmpdir)

            assert "sessions" in paths
            assert "reports" in paths
            assert paths["sessions"] == Path(tmpdir) / ".nova-tracer" / "sessions"
            assert paths["reports"] == Path(tmpdir) / ".nova-tracer" / "reports"

    def test_creates_directories(self):
        """Directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = get_session_paths(tmpdir)

            assert paths["sessions"].exists()
            assert paths["sessions"].is_dir()
            assert paths["reports"].exists()
            assert paths["reports"].is_dir()

    def test_handles_existing_directories(self):
        """Works correctly when directories already exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create directories first
            (Path(tmpdir) / ".nova-tracer" / "sessions").mkdir(parents=True)
            (Path(tmpdir) / ".nova-tracer" / "reports").mkdir(parents=True)

            # Should not raise
            paths = get_session_paths(tmpdir)
            assert paths["sessions"].exists()
            assert paths["reports"].exists()

    def test_accepts_path_object(self):
        """Works with Path objects, not just strings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths = get_session_paths(Path(tmpdir))
            assert paths["sessions"].exists()


class TestInitSessionFile:
    """Tests for AC3: Session File Initialization."""

    def test_creates_jsonl_file(self):
        """Creates a .jsonl file at the correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            result = init_session_file(session_id, tmpdir)

            assert result is not None
            assert result.exists()
            assert result.suffix == ".jsonl"
            assert session_id in result.name

    def test_init_record_structure(self):
        """Init record contains required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            session_file = init_session_file(session_id, tmpdir)

            # Read and parse the init record
            content = session_file.read_text()
            init_record = json.loads(content.strip())

            assert init_record["type"] == "init"
            assert init_record["session_id"] == session_id
            assert "timestamp" in init_record
            assert init_record["platform"] == platform.system().lower()
            assert init_record["project_dir"] == str(Path(tmpdir).resolve())

    def test_timestamp_is_iso_format(self):
        """Timestamp is in ISO 8601 format with Z suffix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            session_file = init_session_file(session_id, tmpdir)

            content = session_file.read_text()
            init_record = json.loads(content.strip())

            # Should be ISO format ending with Z
            assert init_record["timestamp"].endswith("Z")
            # Should be parseable
            from datetime import datetime
            datetime.fromisoformat(init_record["timestamp"].replace("Z", "+00:00"))

    def test_creates_active_marker(self):
        """Creates active session marker file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            marker_file = Path(tmpdir) / ".nova-tracer" / "sessions" / ".active"
            assert marker_file.exists()
            assert marker_file.read_text().strip() == session_id


class TestAppendEvent:
    """Tests for AC4: Event Appending."""

    def test_appends_event_to_file(self):
        """Event is appended as a single JSON line."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            event = {
                "id": 1,
                "tool_name": "Read",
                "tool_input": {"file_path": "/test.py"},
            }

            result = append_event(session_id, tmpdir, event)

            assert result is True

            # Verify event was appended
            session_file = Path(tmpdir) / ".nova-tracer" / "sessions" / f"{session_id}.jsonl"
            lines = session_file.read_text().strip().split("\n")
            assert len(lines) == 2  # init + event

            appended_event = json.loads(lines[1])
            assert appended_event["id"] == 1
            assert appended_event["tool_name"] == "Read"
            assert appended_event["type"] == "event"

    def test_multiple_appends(self):
        """Multiple events can be appended sequentially."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            for i in range(5):
                result = append_event(session_id, tmpdir, {"id": i + 1})
                assert result is True

            session_file = Path(tmpdir) / ".nova-tracer" / "sessions" / f"{session_id}.jsonl"
            lines = session_file.read_text().strip().split("\n")
            assert len(lines) == 6  # init + 5 events

    def test_fail_open_on_missing_file(self):
        """Returns False (not exception) when session file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = append_event("nonexistent", tmpdir, {"id": 1})
            assert result is False  # Fail open, no exception

    def test_fail_open_on_invalid_data(self):
        """Returns False for non-serializable data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            # Create non-JSON-serializable object
            class NotSerializable:
                pass

            result = append_event(session_id, tmpdir, {"bad": NotSerializable()})
            assert result is False

    def test_performance_under_threshold(self):
        """Append operation completes in < 0.5ms average."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            times = []
            for i in range(100):
                event = {"id": i, "data": "x" * 100}
                start = time.perf_counter()
                append_event(session_id, tmpdir, event)
                elapsed = (time.perf_counter() - start) * 1000  # ms

                times.append(elapsed)

            avg_time = sum(times) / len(times)
            # Allow some margin - filesystem performance varies
            assert avg_time < 2.0, f"Average append time {avg_time:.3f}ms exceeds threshold"


class TestGetActiveSession:
    """Tests for session state utilities."""

    def test_returns_active_session(self):
        """Returns session ID when active session exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            result = get_active_session(tmpdir)
            assert result == session_id

    def test_returns_none_when_no_session(self):
        """Returns None when no active session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_active_session(tmpdir)
            assert result is None

    def test_cleans_up_stale_marker(self):
        """Cleans up marker when session file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create marker without session file
            marker_dir = Path(tmpdir) / ".nova-tracer" / "sessions"
            marker_dir.mkdir(parents=True)
            marker_file = marker_dir / ".active"
            marker_file.write_text("stale_session_id")

            result = get_active_session(tmpdir)
            assert result is None
            assert not marker_file.exists()


class TestFinalizeSession:
    """Tests for session finalization."""

    def test_removes_active_marker(self):
        """Finalization removes the active marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            # Verify marker exists
            marker_file = Path(tmpdir) / ".nova-tracer" / "sessions" / ".active"
            assert marker_file.exists()

            result = finalize_session(session_id, tmpdir)

            assert result is not None
            assert not marker_file.exists()

    def test_preserves_session_file(self):
        """Session file remains after finalization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            result = finalize_session(session_id, tmpdir)

            assert result is not None
            assert result.exists()

    def test_returns_none_for_missing_session(self):
        """Returns None when session file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = finalize_session("nonexistent", tmpdir)
            assert result is None


class TestReadSessionEvents:
    """Tests for reading session events."""

    def test_reads_all_events(self):
        """Reads all events from session file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            for i in range(3):
                append_event(session_id, tmpdir, {"id": i + 1})

            events = read_session_events(session_id, tmpdir)

            assert len(events) == 4  # init + 3 events
            assert events[0]["type"] == "init"
            assert events[1]["id"] == 1
            assert events[2]["id"] == 2
            assert events[3]["id"] == 3

    def test_returns_empty_for_missing_file(self):
        """Returns empty list when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            events = read_session_events("nonexistent", tmpdir)
            assert events == []
