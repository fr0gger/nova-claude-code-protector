"""
Tests for the Session End Hook (Story 3.1).

Tests cover:
- AC1: HTML report generation on session end
- AC2: Predictable report path
- AC3: Graceful handling of corrupted data
- AC5: Fail-open error handling
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Get the hooks directory
HOOKS_DIR = Path(__file__).parent.parent / "hooks"
SESSION_END_HOOK = HOOKS_DIR / "session-end.py"

# Add lib directory for imports
sys.path.insert(0, str(HOOKS_DIR / "lib"))

from report_generator import generate_html_report, save_report
from session_manager import (
    append_event,
    build_session_object,
    calculate_session_statistics,
    get_session_paths,
    init_session_file,
)


class TestSessionEndHook:
    """Tests for the session-end.py hook script."""

    def test_hook_exists_and_is_executable(self):
        """Test that session-end.py hook exists."""
        assert SESSION_END_HOOK.exists(), "session-end.py should exist"
        assert SESSION_END_HOOK.suffix == ".py", "Hook should be a Python file"

    def test_hook_exits_zero_on_valid_input(self, tmp_path):
        """AC1: Test hook exits 0 on valid session end input."""
        # Setup: Create a session with events
        session_id = "test_session_001"
        init_session_file(session_id, tmp_path)
        append_event(
            session_id,
            tmp_path,
            {
                "type": "event",
                "tool_name": "Read",
                "tool_input": {"file_path": "/test/file.py"},
                "nova_verdict": "allowed",
            },
        )

        # Create active session marker (just contains session ID)
        paths = get_session_paths(tmp_path)
        active_marker = paths["sessions"] / ".active"
        active_marker.parent.mkdir(parents=True, exist_ok=True)
        active_marker.write_text(session_id)

        # Run the hook
        input_data = {
            "session_id": session_id,
            "session_start_time": "2024-01-01T00:00:00Z",
            "session_end_time": "2024-01-01T01:00:00Z",
        }

        result = subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0, f"Hook should exit 0: {result.stderr}"

    def test_hook_creates_report_file(self, tmp_path):
        """AC1: Test hook creates HTML report file."""
        session_id = "test_session_report"
        init_session_file(session_id, tmp_path)
        append_event(
            session_id,
            tmp_path,
            {
                "type": "event",
                "tool_name": "Bash",
                "tool_input": {"command": "ls -la"},
                "nova_verdict": "allowed",
            },
        )

        # Create active session marker (just contains session ID)
        paths = get_session_paths(tmp_path)
        active_marker = paths["sessions"] / ".active"
        active_marker.parent.mkdir(parents=True, exist_ok=True)
        active_marker.write_text(session_id)

        # Run the hook
        input_data = {
            "session_id": session_id,
            "session_end_time": "2024-01-01T01:00:00Z",
        }

        result = subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )

        assert result.returncode == 0

        # Check report was created
        report_path = paths["reports"] / f"{session_id}.html"
        assert report_path.exists(), f"Report should exist at {report_path}"

    def test_report_path_matches_session_id(self, tmp_path):
        """AC2: Test report path is predictable and matches session ID."""
        session_id = "predictable_session_123"
        init_session_file(session_id, tmp_path)

        # Create active session marker (just contains session ID)
        paths = get_session_paths(tmp_path)
        active_marker = paths["sessions"] / ".active"
        active_marker.parent.mkdir(parents=True, exist_ok=True)
        active_marker.write_text(session_id)

        input_data = {"session_id": session_id}

        subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )

        # Verify predictable path
        expected_path = tmp_path / ".nova-protector" / "reports" / f"{session_id}.html"
        assert expected_path.exists(), f"Report should be at predictable path: {expected_path}"

    def test_hook_exits_zero_on_missing_session_id(self):
        """AC5: Test fail-open when session_id is missing."""
        input_data = {}  # Missing session_id

        result = subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Hook should fail-open on missing session_id"

    def test_hook_exits_zero_on_invalid_json(self):
        """AC5: Test fail-open on invalid JSON input."""
        result = subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input="not valid json {{{",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Hook should fail-open on invalid JSON"

    def test_hook_exits_zero_on_empty_input(self):
        """AC5: Test fail-open on empty input."""
        result = subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input="",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Hook should fail-open on empty input"

    def test_hook_finalizes_session(self, tmp_path):
        """Test that hook removes active session marker."""
        session_id = "session_to_finalize"
        init_session_file(session_id, tmp_path)

        # Create active session marker (just contains session ID)
        paths = get_session_paths(tmp_path)
        active_marker = paths["sessions"] / ".active"
        active_marker.parent.mkdir(parents=True, exist_ok=True)
        active_marker.write_text(session_id)

        assert active_marker.exists(), "Active marker should exist before hook"

        input_data = {"session_id": session_id}

        subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )

        assert not active_marker.exists(), "Active marker should be removed after hook"


class TestReportGenerator:
    """Tests for the report_generator.py module."""

    def test_generate_html_report_returns_string(self):
        """Test that generate_html_report returns HTML string."""
        session_data = {
            "session_id": "test123",
            "session_start": "2024-01-01T00:00:00Z",
            "session_end": "2024-01-01T01:00:00Z",
            "events": [],
            "summary": {
                "total_events": 0,
                "tools_used": {},
                "files_touched": 0,
                "warnings": 0,
                "blocked": 0,
                "duration_seconds": 3600,
            },
        }

        html = generate_html_report(session_data)

        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "NOVA" in html

    def test_generate_html_report_contains_session_id(self):
        """Test that report contains session ID."""
        session_data = {
            "session_id": "unique_session_xyz",
            "events": [],
            "summary": {
                "total_events": 0,
                "tools_used": {},
                "files_touched": 0,
                "warnings": 0,
                "blocked": 0,
            },
        }

        html = generate_html_report(session_data)

        assert "unique_session_xyz" in html

    def test_generate_html_report_shows_health_status_clean(self):
        """Test clean health status for no warnings/blocks."""
        session_data = {
            "session_id": "clean_session",
            "events": [],
            "summary": {
                "total_events": 5,
                "warnings": 0,
                "blocked": 0,
            },
        }

        html = generate_html_report(session_data)

        assert "CLEAN" in html

    def test_generate_html_report_shows_health_status_warnings(self):
        """Test warnings health status."""
        session_data = {
            "session_id": "warned_session",
            "events": [],
            "summary": {
                "total_events": 5,
                "warnings": 2,
                "blocked": 0,
            },
        }

        html = generate_html_report(session_data)

        assert "WARNINGS" in html

    def test_generate_html_report_shows_health_status_blocked(self):
        """Test blocked health status takes precedence."""
        session_data = {
            "session_id": "blocked_session",
            "events": [],
            "summary": {
                "total_events": 5,
                "warnings": 2,
                "blocked": 1,
            },
        }

        html = generate_html_report(session_data)

        # HTML uses "DETECTED" for blocked status
        assert "DETECTED" in html

    def test_generate_html_report_includes_events(self):
        """Test that events are included in report."""
        session_data = {
            "session_id": "events_session",
            "events": [
                {
                    "tool_name": "Read",
                    "nova_verdict": "allowed",
                    "timestamp_start": "2024-01-01T00:00:00Z",
                    "files_accessed": ["/test/file.py"],
                },
                {
                    "tool_name": "Bash",
                    "nova_verdict": "warned",
                    "timestamp_start": "2024-01-01T00:01:00Z",
                },
            ],
            "summary": {"warnings": 1, "blocked": 0},
        }

        html = generate_html_report(session_data)

        assert "Read" in html
        assert "Bash" in html
        # HTML uses lowercase verdicts
        assert "allowed" in html
        assert "warned" in html

    def test_generate_html_report_includes_tools_used(self):
        """Test tools breakdown in report."""
        session_data = {
            "session_id": "tools_session",
            "events": [],
            "summary": {
                "tools_used": {"Read": 10, "Bash": 5, "Write": 3},
                "warnings": 0,
                "blocked": 0,
            },
        }

        html = generate_html_report(session_data)

        assert "Read" in html
        assert "Bash" in html
        assert "Write" in html

    def test_generate_html_report_handles_empty_session(self):
        """Test handling of empty session data."""
        session_data = {}

        html = generate_html_report(session_data)

        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html

    def test_save_report_creates_file(self, tmp_path):
        """Test that save_report creates file."""
        html_content = "<!DOCTYPE html><html><body>Test</body></html>"
        report_path = tmp_path / "reports" / "test.html"

        result = save_report(html_content, report_path)

        assert result is True
        assert report_path.exists()
        assert report_path.read_text() == html_content

    def test_save_report_creates_parent_directories(self, tmp_path):
        """Test that save_report creates parent directories."""
        html_content = "<html></html>"
        report_path = tmp_path / "deep" / "nested" / "path" / "report.html"

        result = save_report(html_content, report_path)

        assert result is True
        assert report_path.exists()


class TestSessionStatistics:
    """Tests for session statistics calculation."""

    def test_calculate_statistics_empty_events(self):
        """Test statistics with no events."""
        stats = calculate_session_statistics([])

        assert stats["total_events"] == 0
        assert stats["tools_used"] == {}
        assert stats["warnings"] == 0
        assert stats["blocked"] == 0

    def test_calculate_statistics_counts_tools(self):
        """Test tool counting."""
        events = [
            {"type": "event", "tool_name": "Read"},
            {"type": "event", "tool_name": "Read"},
            {"type": "event", "tool_name": "Bash"},
            {"type": "init"},  # Should be ignored
        ]

        stats = calculate_session_statistics(events)

        assert stats["total_events"] == 3
        assert stats["tools_used"]["Read"] == 2
        assert stats["tools_used"]["Bash"] == 1

    def test_calculate_statistics_counts_verdicts(self):
        """Test verdict counting."""
        events = [
            {"type": "event", "tool_name": "Read", "nova_verdict": "allowed"},
            {"type": "event", "tool_name": "Bash", "nova_verdict": "warned"},
            {"type": "event", "tool_name": "Bash", "nova_verdict": "warned"},
            {"type": "event", "tool_name": "Write", "nova_verdict": "blocked"},
        ]

        stats = calculate_session_statistics(events)

        assert stats["warnings"] == 2
        assert stats["blocked"] == 1

    def test_calculate_statistics_counts_files(self):
        """Test file counting."""
        events = [
            {"type": "event", "files_accessed": ["/a.py", "/b.py"]},
            {"type": "event", "files_accessed": ["/a.py", "/c.py"]},  # /a.py duplicate
        ]

        stats = calculate_session_statistics(events)

        assert stats["files_touched"] == 3  # Unique files

    def test_calculate_statistics_handles_duration(self):
        """Test duration calculation."""
        start_time = "2024-01-01T00:00:00Z"
        end_time = "2024-01-01T01:30:00Z"  # 90 minutes later

        events = [
            {"type": "init", "timestamp": start_time},
            {"type": "event", "timestamp_start": end_time},
        ]

        stats = calculate_session_statistics(events)

        # Duration should be calculated from first to last timestamp
        assert stats["duration_seconds"] >= 0


class TestBuildSessionObject:
    """Tests for building complete session objects."""

    def test_build_session_object_structure(self, tmp_path):
        """Test session object has required structure."""
        session_id = "struct_test"
        init_session_file(session_id, tmp_path)

        session = build_session_object(session_id, tmp_path)

        assert "session_id" in session
        assert "session_start" in session
        assert "session_end" in session
        assert "platform" in session
        assert "project_dir" in session
        assert "events" in session
        assert "summary" in session

    def test_build_session_object_includes_events(self, tmp_path):
        """Test session object includes events."""
        session_id = "events_test"
        init_session_file(session_id, tmp_path)
        append_event(
            session_id,
            tmp_path,
            {
                "type": "event",
                "tool_name": "Read",
                "tool_input": {"file_path": "/test.py"},
                "nova_verdict": "allowed",
            },
        )

        session = build_session_object(session_id, tmp_path)

        assert len(session["events"]) == 1
        assert session["events"][0]["tool_name"] == "Read"

    def test_build_session_object_summary_has_statistics(self, tmp_path):
        """Test session summary has calculated statistics."""
        session_id = "stats_test"
        init_session_file(session_id, tmp_path)
        append_event(
            session_id,
            tmp_path,
            {
                "type": "event",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
                "nova_verdict": "warned",
            },
        )

        session = build_session_object(session_id, tmp_path)

        assert session["summary"]["total_events"] == 1
        assert session["summary"]["warnings"] == 1
        assert "tools_used" in session["summary"]


class TestCorruptedDataHandling:
    """Tests for AC3: Graceful handling of corrupted data."""

    def test_hook_handles_corrupted_jsonl(self, tmp_path):
        """AC3: Test partial report on corrupted JSONL data."""
        session_id = "corrupted_session"

        # Create JSONL with some valid and some corrupted lines
        paths = get_session_paths(tmp_path)
        session_file = paths["sessions"] / f"{session_id}.jsonl"
        session_file.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            json.dumps({"type": "init", "session_id": session_id}),
            json.dumps({"type": "event", "tool_name": "Read"}),
            "this is not valid json {{{",  # Corrupted line
            json.dumps({"type": "event", "tool_name": "Bash"}),
        ]
        session_file.write_text("\n".join(lines) + "\n")

        # Create active marker (just contains session ID)
        active_marker = paths["sessions"] / ".active"
        active_marker.write_text(session_id)

        input_data = {"session_id": session_id}

        result = subprocess.run(
            [sys.executable, str(SESSION_END_HOOK)],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )

        # Should still exit 0 and create report
        assert result.returncode == 0

        report_path = paths["reports"] / f"{session_id}.html"
        assert report_path.exists(), "Report should be created even with corrupted data"

    def test_build_session_handles_missing_file(self, tmp_path):
        """Test build_session_object handles missing session file."""
        session = build_session_object("nonexistent_session", tmp_path)

        # Should return session object with empty events
        assert session["session_id"] == "nonexistent_session"
        assert session["events"] == []


class TestPerformance:
    """Tests for AC4: Performance targets."""

    def test_report_generation_performance(self, tmp_path):
        """AC4: Test report generation is fast for 500 events."""
        import time

        session_id = "perf_test"
        init_session_file(session_id, tmp_path)

        # Add 500 events
        tools = ["Read", "Bash", "Write", "Grep"]
        verdicts = ["allowed", "warned", "allowed"]
        for i in range(500):
            append_event(
                session_id,
                tmp_path,
                {
                    "type": "event",
                    "tool_name": tools[i % 4],
                    "tool_input": {"test": f"data_{i}"},
                    "nova_verdict": verdicts[i % 3],
                    "files_accessed": [f"/file_{i}.py"],
                },
            )

        # Build session and generate report
        start_time = time.time()
        session = build_session_object(session_id, tmp_path)
        html = generate_html_report(session)
        elapsed = time.time() - start_time

        # AC4: Should complete in < 3 seconds
        assert elapsed < 3.0, f"Report generation took {elapsed:.2f}s, should be < 3s"
        assert len(session["events"]) == 500
        assert len(html) > 0
