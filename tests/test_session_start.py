"""
Tests for Session Start Hook.

Tests cover all acceptance criteria:
- AC1: New session initialization (generate ID, create .jsonl)
- AC2: Session resume detection (detect existing active session)
- AC3: Fail-open error handling (always exit 0)
"""

import io
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

# Add hooks/lib to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks" / "lib"))

from session_manager import (
    generate_session_id,
    get_active_session,
    init_session_file,
)


class TestParseHookInput:
    """Tests for stdin parsing functionality."""

    def test_valid_json_input(self):
        """Parses valid JSON from stdin."""
        # Import the module to test
        sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
        from importlib import import_module

        # We need to import session_start module
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "session_start",
            Path(__file__).parent.parent / "hooks" / "session-start.py"
        )
        session_start = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(session_start)

        # Test with mocked stdin
        test_input = '{"session_id": "test123", "event": "session_start"}'
        with mock.patch('sys.stdin', io.StringIO(test_input)):
            with mock.patch('sys.stdin.isatty', return_value=False):
                result = session_start.parse_hook_input()

        assert result is not None
        assert result["session_id"] == "test123"
        assert result["event"] == "session_start"

    def test_empty_stdin_returns_empty_dict(self):
        """Empty stdin returns empty dict (not None)."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "session_start",
            Path(__file__).parent.parent / "hooks" / "session-start.py"
        )
        session_start = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(session_start)

        with mock.patch('sys.stdin', io.StringIO('')):
            with mock.patch('sys.stdin.isatty', return_value=False):
                result = session_start.parse_hook_input()

        assert result == {}

    def test_invalid_json_returns_none(self):
        """Invalid JSON returns None (fail-open)."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "session_start",
            Path(__file__).parent.parent / "hooks" / "session-start.py"
        )
        session_start = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(session_start)

        with mock.patch('sys.stdin', io.StringIO('not valid json {')):
            with mock.patch('sys.stdin.isatty', return_value=False):
                result = session_start.parse_hook_input()

        assert result is None


class TestNewSessionInitialization:
    """Tests for AC1: New session initialization."""

    def test_creates_new_session_file(self):
        """Creates .jsonl file when no active session exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Ensure no active session
            assert get_active_session(tmpdir) is None

            # Create new session
            session_id = generate_session_id()
            result = init_session_file(session_id, tmpdir)

            assert result is not None
            assert result.exists()
            assert result.suffix == ".jsonl"

    def test_init_record_structure(self):
        """Init record contains required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            session_file = init_session_file(session_id, tmpdir)

            content = session_file.read_text()
            init_record = json.loads(content.strip())

            assert init_record["type"] == "init"
            assert init_record["session_id"] == session_id
            assert "timestamp" in init_record
            assert "platform" in init_record
            assert "project_dir" in init_record

    def test_active_marker_created(self):
        """Active session marker file is created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            marker_file = Path(tmpdir) / ".nova-tracer" / "sessions" / ".active"
            assert marker_file.exists()
            assert marker_file.read_text().strip() == session_id


class TestSessionResumeDetection:
    """Tests for AC2: Session resume detection."""

    def test_detects_active_session(self):
        """Returns existing session ID when session is active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create an active session
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            # Check for active session
            active = get_active_session(tmpdir)

            assert active == session_id

    def test_returns_none_when_no_session(self):
        """Returns None when no active session exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            active = get_active_session(tmpdir)
            assert active is None

    def test_handle_session_start_resumes(self):
        """handle_session_start skips initialization for active session."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "session_start",
            Path(__file__).parent.parent / "hooks" / "session-start.py"
        )
        session_start = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(session_start)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first session
            session_id = generate_session_id()
            init_session_file(session_id, tmpdir)

            # Get initial file count
            sessions_dir = Path(tmpdir) / ".nova-tracer" / "sessions"
            initial_count = len(list(sessions_dir.glob("*.jsonl")))

            # Call handle_session_start (should resume, not create new)
            result = session_start.handle_session_start(tmpdir)

            assert result is True
            # Should still have same number of session files
            assert len(list(sessions_dir.glob("*.jsonl"))) == initial_count


class TestFailOpenErrorHandling:
    """Tests for AC3: Fail-open error handling."""

    def test_hook_exits_zero_on_success(self):
        """Hook exits with code 0 on successful execution."""
        hook_path = Path(__file__).parent.parent / "hooks" / "session-start.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input='{"event": "session_start"}',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )

            assert result.returncode == 0

    def test_hook_exits_zero_on_empty_input(self):
        """Hook exits with code 0 even with empty input."""
        hook_path = Path(__file__).parent.parent / "hooks" / "session-start.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input='',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )

            assert result.returncode == 0

    def test_hook_exits_zero_on_invalid_json(self):
        """Hook exits with code 0 even with invalid JSON input."""
        hook_path = Path(__file__).parent.parent / "hooks" / "session-start.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input='not valid json at all {{{',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )

            assert result.returncode == 0

    def test_logs_to_stderr_not_stdout(self):
        """Debug/error logs go to stderr, not stdout."""
        hook_path = Path(__file__).parent.parent / "hooks" / "session-start.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input='{"event": "session_start"}',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )

            # stdout should be empty (reserved for Claude feedback)
            assert result.stdout == ""


class TestIntegration:
    """Integration tests for the complete hook flow."""

    def test_full_hook_creates_session(self):
        """Running the hook creates a valid session file."""
        hook_path = Path(__file__).parent.parent / "hooks" / "session-start.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input='{"event": "session_start"}',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )

            assert result.returncode == 0

            # Check session file was created
            sessions_dir = Path(tmpdir) / ".nova-tracer" / "sessions"
            session_files = list(sessions_dir.glob("*.jsonl"))

            assert len(session_files) == 1

            # Verify init record
            content = session_files[0].read_text()
            init_record = json.loads(content.strip())

            assert init_record["type"] == "init"
            # Use realpath to handle macOS /var -> /private/var symlink
            assert init_record["project_dir"] == str(Path(tmpdir).resolve())

    def test_consecutive_runs_resume_session(self):
        """Running hook twice resumes the same session."""
        hook_path = Path(__file__).parent.parent / "hooks" / "session-start.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            # First run - creates session
            result1 = subprocess.run(
                [sys.executable, str(hook_path)],
                input='{"event": "session_start"}',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )
            assert result1.returncode == 0

            sessions_dir = Path(tmpdir) / ".nova-tracer" / "sessions"
            session_files_after_first = list(sessions_dir.glob("*.jsonl"))
            assert len(session_files_after_first) == 1

            # Second run - should resume, not create new
            result2 = subprocess.run(
                [sys.executable, str(hook_path)],
                input='{"event": "session_start"}',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )
            assert result2.returncode == 0

            session_files_after_second = list(sessions_dir.glob("*.jsonl"))
            # Should still be just one session file
            assert len(session_files_after_second) == 1

    def test_hook_executable_directly(self):
        """Hook can be executed directly with python."""
        hook_path = Path(__file__).parent.parent / "hooks" / "session-start.py"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Run with explicit python interpreter
            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input='{}',
                capture_output=True,
                text=True,
                cwd=tmpdir,
            )

            assert result.returncode == 0


class TestGetProjectDir:
    """Tests for project directory resolution."""

    def test_uses_current_working_directory(self):
        """Project dir is the current working directory."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "session_start",
            Path(__file__).parent.parent / "hooks" / "session-start.py"
        )
        session_start = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(session_start)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                project_dir = session_start.get_project_dir({})
                # Use realpath to handle macOS /var -> /private/var symlink
                assert Path(project_dir).resolve() == Path(tmpdir).resolve()
            finally:
                os.chdir(original_cwd)
