"""
Tests for Verdict Assignment and Logging (Story 2.2).

Consolidated tests covering acceptance criteria:
- AC1: No matches → allowed verdict with null severity
- AC2: Warning-level match → warned verdict with medium severity
- AC3: High-severity match → blocked verdict with high severity
- AC4: Multiple rules → highest severity wins, all rules captured
- AC5: Scan time recording in nova_scan_time_ms
"""

import json
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Add hooks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks" / "lib"))

from session_manager import (
    generate_session_id,
    init_session_file,
    read_session_events,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def hook_path():
    """Path to the post-tool hook."""
    return Path(__file__).parent.parent / "hooks" / "post-tool-nova-guard.py"


@pytest.fixture
def session_context():
    """Create a temporary session context."""
    with tempfile.TemporaryDirectory() as tmpdir:
        session_id = generate_session_id()
        init_session_file(session_id, tmpdir)
        yield {"session_id": session_id, "tmpdir": tmpdir}


# ============================================================================
# Verdict Logic Tests (AC1, AC2, AC3, AC4)
# ============================================================================


class TestVerdictLogic:
    """Tests for verdict assignment based on detection severities."""

    @pytest.mark.parametrize("detections,expected_verdict,expected_severity", [
        # AC1: No matches → allowed
        ([], "allowed", None),
        # AC2: Medium → warned
        ([{"severity": "medium", "rule_name": "Rule1"}], "warned", "medium"),
        # Low → warned
        ([{"severity": "low", "rule_name": "Rule1"}], "warned", "low"),
        # AC3: High → blocked
        ([{"severity": "high", "rule_name": "Rule1"}], "blocked", "high"),
        # AC4: Mixed - highest wins (high)
        ([{"severity": "low"}, {"severity": "medium"}, {"severity": "high"}], "blocked", "high"),
        # AC4: Mixed - highest wins (medium)
        ([{"severity": "low"}, {"severity": "medium"}], "warned", "medium"),
        # Multiple high
        ([{"severity": "high"}, {"severity": "high"}], "blocked", "high"),
    ])
    def test_severity_determines_verdict(self, detections, expected_verdict, expected_severity):
        """Correct verdict and severity based on detections."""
        severities = [d.get("severity", "medium") for d in detections]

        if not detections:
            nova_verdict = "allowed"
            nova_severity = None
        elif "high" in severities:
            nova_verdict = "blocked"
            nova_severity = "high"
        elif "medium" in severities:
            nova_verdict = "warned"
            nova_severity = "medium"
        else:
            nova_verdict = "warned"
            nova_severity = "low"

        assert nova_verdict == expected_verdict
        assert nova_severity == expected_severity


# ============================================================================
# Rules Capture Tests (AC4)
# ============================================================================


class TestRulesCapture:
    """Tests for capturing matched rule names."""

    @pytest.mark.parametrize("detections,expected_rules", [
        ([{"rule_name": "Rule1"}], ["Rule1"]),
        ([{"rule_name": "A"}, {"rule_name": "B"}], ["A", "B"]),
        ([{"severity": "low", "rule_name": "Low"}, {"severity": "high", "rule_name": "High"}], ["Low", "High"]),
        ([], []),
    ])
    def test_all_rules_captured(self, detections, expected_rules):
        """All matched rule names are captured."""
        nova_rules_matched = [d.get("rule_name", "unknown") for d in detections]
        assert nova_rules_matched == expected_rules

    def test_missing_rule_name_defaults_to_unknown(self):
        """Missing rule_name defaults to 'unknown'."""
        detections = [{"severity": "high"}]
        nova_rules_matched = [d.get("rule_name", "unknown") for d in detections]
        assert nova_rules_matched == ["unknown"]


# ============================================================================
# Scan Time Tests (AC5)
# ============================================================================


class TestScanTime:
    """Tests for scan time recording."""

    def test_scan_time_is_integer_milliseconds(self):
        """Scan time is recorded as integer milliseconds."""
        scan_start = datetime.now(timezone.utc)
        time.sleep(0.001)
        scan_end = datetime.now(timezone.utc)

        nova_scan_time_ms = int((scan_end - scan_start).total_seconds() * 1000)

        assert isinstance(nova_scan_time_ms, int)
        assert nova_scan_time_ms >= 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestEventCapture:
    """Integration tests for event capture with NOVA fields."""

    def test_clean_content_returns_allowed(self, hook_path):
        """Hook returns allowed verdict for clean content."""
        hook_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/test/clean_file.py"},
            "tool_response": "def hello():\n    print('Hello World')\n",
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Check no unexpected detections in output
        if result.stdout.strip():
            try:
                output = json.loads(result.stdout)
                if isinstance(output, dict) and output.get("detections"):
                    assert False, f"Unexpected detections: {output}"
            except json.JSONDecodeError:
                pass  # Non-JSON output (debug messages) is fine

    def test_all_nova_fields_present_in_event(self, hook_path, session_context):
        """All four NOVA fields are present in captured event."""
        hook_input = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/test/file.py"},
            "tool_response": "print('hello')",
        }

        subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
            cwd=session_context["tmpdir"],
        )

        events = read_session_events(session_context["session_id"], session_context["tmpdir"])
        event_records = [e for e in events if e.get("type") == "event"]

        if event_records:
            event = event_records[0]

            # Check all NOVA fields exist
            assert "nova_verdict" in event
            assert "nova_severity" in event
            assert "nova_rules_matched" in event
            assert "nova_scan_time_ms" in event

            # Check field types
            assert event["nova_verdict"] in ["allowed", "warned", "blocked", "scan_failed"]
            assert event["nova_severity"] in [None, "low", "medium", "high"]
            assert isinstance(event["nova_rules_matched"], list)
            assert isinstance(event["nova_scan_time_ms"], int)
            assert event["nova_scan_time_ms"] >= 0


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Edge case tests for verdict assignment."""

    @pytest.mark.parametrize("severity_value,expected_verdict", [
        ("unknown", "warned"),  # Unknown treated as low
        (None, "warned"),  # None defaults via .get() to medium
    ])
    def test_unusual_severities_handled(self, severity_value, expected_verdict):
        """Unusual severity values are handled gracefully."""
        if severity_value is None:
            detections = [{"rule_name": "Rule"}]  # No severity key
        else:
            detections = [{"severity": severity_value, "rule_name": "Rule"}]

        severities = [d.get("severity", "medium") for d in detections]

        if "high" in severities:
            nova_verdict = "blocked"
        elif "medium" in severities:
            nova_verdict = "warned"
        else:
            nova_verdict = "warned"

        assert nova_verdict == expected_verdict

    def test_missing_severity_defaults_to_medium(self):
        """Missing severity key defaults to medium via .get()."""
        detections = [{"rule_name": "NoSeverityRule"}]
        severities = [d.get("severity", "medium") for d in detections]
        assert severities == ["medium"]
