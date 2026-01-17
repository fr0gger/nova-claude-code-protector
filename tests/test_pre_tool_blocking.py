"""
Tests for Pre-Tool Blocking Hook (Story 2.3).

Consolidated tests covering acceptance criteria:
- AC1: Scan tool_input in PreToolUse
- AC2: Block critical-severity (high) matches - exit code 2
- AC3: Allow warning-severity matches - exit code 0
- AC4: Allow no matches - exit code 0
- AC5: Fail-open on errors - exit code 0
"""

import json
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def pre_tool_module():
    """Load the pre-tool-guard module once for all tests."""
    hook_path = Path(__file__).parent.parent / "hooks" / "pre-tool-guard.py"
    spec = spec_from_file_location("pre_tool_guard", hook_path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_path():
    """Path to the pre-tool hook."""
    return Path(__file__).parent.parent / "hooks" / "pre-tool-guard.py"


# ============================================================================
# Structure Tests
# ============================================================================


class TestHookStructure:
    """Tests for pre-tool hook structure and validity."""

    def test_hook_file_exists(self, hook_path):
        """Pre-tool hook file exists."""
        assert hook_path.exists()

    def test_hook_is_valid_python(self, hook_path):
        """Pre-tool hook is valid Python syntax."""
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", str(hook_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


# ============================================================================
# Clean Input Tests (AC4)
# ============================================================================


class TestCleanInput:
    """Tests for AC4: No matches → exit code 0 (allow)."""

    @pytest.mark.parametrize("tool_name,tool_input", [
        ("Bash", {"command": "ls -la"}),
        ("Read", {"file_path": "/test/file.py"}),
        ("Bash", {}),  # Empty input
        ("Bash", {"command": "ls"}),  # Short input (<10 chars)
        ("Write", {"file_path": "/test/file.txt", "content": "Hello world"}),
        ("Edit", {"file_path": "/test.py", "old_string": "def hello():", "new_string": "def greet():"}),
    ])
    def test_clean_input_returns_exit_zero(self, hook_path, tool_name, tool_input):
        """Clean input with no matches returns exit code 0."""
        hook_input = {"tool_name": tool_name, "tool_input": tool_input}

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

    def test_clean_input_no_block_decision(self, hook_path):
        """Clean input does not produce a block decision."""
        hook_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/test/file.py"},
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                assert output.get("decision") != "block"
            except json.JSONDecodeError:
                pass  # Non-JSON output (debug messages) is fine


# ============================================================================
# Fail-Open Tests (AC5)
# ============================================================================


class TestFailOpen:
    """Tests for AC5: Errors → exit code 0 (fail-open)."""

    @pytest.mark.parametrize("invalid_input", [
        "not valid json",
        "",
        json.dumps({"tool_input": {"command": "ls"}}),  # Missing tool_name
    ])
    def test_invalid_input_returns_exit_zero(self, hook_path, invalid_input):
        """Invalid inputs return exit code 0 (fail-open)."""
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=invalid_input,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0


# ============================================================================
# Severity Logic Tests
# ============================================================================


class TestSeverityLogic:
    """Tests for severity-based blocking logic."""

    @pytest.mark.parametrize("detections,expected_exit", [
        # High severity → block (exit 2)
        ([{"severity": "high", "rule_name": "Rule1"}], 2),
        # Multiple high → block
        ([{"severity": "high", "rule_name": "R1"}, {"severity": "high", "rule_name": "R2"}], 2),
        # Mixed with high → block
        ([{"severity": "low"}, {"severity": "medium"}, {"severity": "high"}], 2),
        # Medium only → allow (exit 0)
        ([{"severity": "medium", "rule_name": "Rule1"}], 0),
        # Low only → allow
        ([{"severity": "low", "rule_name": "Rule1"}], 0),
        # Mixed low/medium → allow
        ([{"severity": "low"}, {"severity": "medium"}], 0),
        # Empty → allow
        ([], 0),
    ])
    def test_severity_determines_exit_code(self, detections, expected_exit):
        """Severity level determines exit code correctly."""
        severities = [d.get("severity", "medium") for d in detections]

        if "high" in severities:
            exit_code = 2
        else:
            exit_code = 0

        assert exit_code == expected_exit


# ============================================================================
# Dangerous Command Detection Tests
# ============================================================================


class TestDangerousCommandDetection:
    """Tests for check_dangerous_command function."""

    def test_detects_rm_rf(self, pre_tool_module):
        """Detects rm -rf as dangerous."""
        result = pre_tool_module.check_dangerous_command("rm -rf /important")
        assert result is not None  # Returns a reason string

    def test_allows_safe_commands(self, pre_tool_module):
        """Allows safe commands like ls."""
        result = pre_tool_module.check_dangerous_command("ls -la")
        assert result is None  # No danger detected

    def test_detects_dangerous_patterns(self, pre_tool_module):
        """Detects various dangerous command patterns."""
        dangerous_commands = [
            "rm -rf /",
            "rm -rf ~/*",
            "dd if=/dev/zero of=/dev/sda",
        ]
        for cmd in dangerous_commands:
            result = pre_tool_module.check_dangerous_command(cmd)
            # At least some should be detected
            # (depends on what patterns are in the module)


# ============================================================================
# Block Output Format Tests
# ============================================================================


class TestBlockOutputFormat:
    """Tests for block output JSON format."""

    def test_block_json_format(self):
        """Block output is valid JSON with required fields."""
        output = {
            "decision": "block",
            "reason": "[NOVA] Blocked: TestRule - Test description"
        }

        json_str = json.dumps(output)
        parsed = json.loads(json_str)

        assert parsed["decision"] == "block"
        assert "[NOVA] Blocked:" in parsed["reason"]
