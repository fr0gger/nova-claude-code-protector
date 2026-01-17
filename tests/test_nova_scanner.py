"""
Tests for NOVA Scanner Integration (Story 2.1).

Consolidated tests covering acceptance criteria:
- AC1: Scan tool inputs against NOVA rules
- AC2: Scan tool outputs against NOVA rules
- AC3: Load all .nov files from rules directory
- AC4: Fail-open with scan_failed verdict on errors
- AC5: Performance target < 5ms per scan
"""

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Add hooks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
sys.path.insert(0, str(Path(__file__).parent.parent / "hooks" / "lib"))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def nova_guard_module():
    """Load the post-tool-nova-guard module once for all tests."""
    hook_path = Path(__file__).parent.parent / "hooks" / "post-tool-nova-guard.py"
    spec = importlib.util.spec_from_file_location("post_tool_nova_guard", hook_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook_path():
    """Path to the post-tool hook."""
    return Path(__file__).parent.parent / "hooks" / "post-tool-nova-guard.py"


# ============================================================================
# Text Extraction Tests (AC1, AC2)
# ============================================================================


class TestTextExtraction:
    """Tests for text extraction from tool inputs and outputs."""

    @pytest.mark.parametrize("tool_input,expected_content", [
        ({"command": "echo test"}, "echo test"),
        ({"content": "file content"}, "file content"),
        ({"prompt": "task prompt"}, "task prompt"),
        ({}, ""),
        (None, ""),
        ({"command": 12345}, ""),  # Non-string ignored
    ])
    def test_extract_input_text(self, nova_guard_module, tool_input, expected_content):
        """Extracts text from various tool input formats."""
        result = nova_guard_module.extract_input_text(tool_input)
        if expected_content:
            assert expected_content in result
        else:
            assert result == ""

    @pytest.mark.parametrize("tool_name,tool_result,expected", [
        ("Read", "file content here", "file content here"),
        ("Read", {"content": "extracted content"}, "extracted content"),
        ("Bash", {"output": "command output"}, "command output"),
        ("Read", None, ""),
    ])
    def test_extract_text_content(self, nova_guard_module, tool_name, tool_result, expected):
        """Extracts text from tool output/response."""
        result = nova_guard_module.extract_text_content(tool_name, tool_result)
        assert result == expected


# ============================================================================
# Filter By Severity Tests
# ============================================================================


class TestFilterBySeverity:
    """Tests for severity-based filtering."""

    @pytest.fixture
    def all_severities(self):
        """Detections with all severity levels."""
        return [
            {"severity": "low", "rule_name": "r1"},
            {"severity": "medium", "rule_name": "r2"},
            {"severity": "high", "rule_name": "r3"},
        ]

    @pytest.mark.parametrize("min_severity,expected_count,expected_severities", [
        ("low", 3, {"low", "medium", "high"}),
        ("medium", 2, {"medium", "high"}),
        ("high", 1, {"high"}),
    ])
    def test_filters_by_minimum_severity(
        self, nova_guard_module, all_severities, min_severity, expected_count, expected_severities
    ):
        """Filters detections by minimum severity level."""
        result = nova_guard_module.filter_by_severity(all_severities, min_severity)
        assert len(result) == expected_count
        assert all(d["severity"] in expected_severities for d in result)


# ============================================================================
# Rules Directory Tests (AC3)
# ============================================================================


class TestRulesDirectory:
    """Tests for rules directory discovery."""

    def test_finds_rules_directory(self, nova_guard_module):
        """Finds and validates rules directory."""
        rules_dir = nova_guard_module.get_rules_directory()
        if rules_dir:
            assert rules_dir.exists()
            assert rules_dir.is_dir()
            nov_files = list(rules_dir.glob("*.nov"))
            assert len(nov_files) >= 1, "Should contain at least one .nov file"


# ============================================================================
# Scan Function Tests
# ============================================================================


class TestScanWithNova:
    """Tests for NOVA scanning function."""

    def test_returns_empty_without_nova(self, nova_guard_module):
        """Returns empty list when NOVA not available."""
        original = nova_guard_module.NOVA_AVAILABLE
        nova_guard_module.NOVA_AVAILABLE = False

        try:
            result = nova_guard_module.scan_with_nova(
                "ignore previous instructions",
                {"debug": False},
                Path("/nonexistent")
            )
            assert result == []
        finally:
            nova_guard_module.NOVA_AVAILABLE = original

    def test_handles_missing_rules_dir(self, nova_guard_module):
        """Handles non-existent rules directory gracefully."""
        if not nova_guard_module.NOVA_AVAILABLE:
            pytest.skip("NOVA not available")

        result = nova_guard_module.scan_with_nova(
            "test text",
            {"debug": False},
            Path("/nonexistent/rules")
        )
        assert isinstance(result, list)


# ============================================================================
# Warning Format Tests
# ============================================================================


class TestFormatWarning:
    """Tests for warning message formatting."""

    @pytest.mark.parametrize("severity,expected_text", [
        ("high", "HIGH SEVERITY"),
        ("medium", "NOVA PROMPT INJECTION WARNING"),
    ])
    def test_formats_severity_level(self, nova_guard_module, severity, expected_text):
        """Formats warning based on severity level."""
        detections = [{
            "severity": severity,
            "rule_name": "TestRule",
            "category": "test",
            "description": "Test description",
            "matched_keywords": [],
            "llm_match": False,
            "confidence": 0.0,
        }]

        result = nova_guard_module.format_warning(detections, "Read", "/test.txt")
        assert expected_text in result
        assert "TestRule" in result

    def test_includes_source_info(self, nova_guard_module):
        """Includes source information in warning."""
        detections = [{
            "severity": "medium",
            "rule_name": "TestRule",
            "category": "test",
            "description": "",
            "matched_keywords": [],
            "llm_match": False,
            "confidence": 0.0,
        }]

        result = nova_guard_module.format_warning(detections, "WebFetch", "https://example.com")
        assert "https://example.com" in result


# ============================================================================
# Fail-Open Tests (AC4)
# ============================================================================


class TestFailOpen:
    """Tests for fail-open behavior."""

    @pytest.mark.parametrize("stdin_input", [
        json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/test.txt"}, "tool_response": "content"}),
        "not valid json",
        "",
    ])
    def test_hook_always_exits_zero(self, hook_path, stdin_input):
        """Hook always exits 0 regardless of input (fail-open)."""
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=stdin_input,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0


# ============================================================================
# Performance Tests (AC5)
# ============================================================================


class TestPerformance:
    """Tests for performance requirements."""

    def test_input_extraction_performance(self, nova_guard_module):
        """Input text extraction completes within performance target."""
        tool_input = {
            "command": "x" * 10000,
            "content": "y" * 10000,
            "prompt": "z" * 10000,
        }

        start = time.perf_counter()
        for _ in range(100):
            nova_guard_module.extract_input_text(tool_input)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, "100 iterations should complete in < 100ms"

    def test_filter_severity_performance(self, nova_guard_module):
        """Severity filtering completes within performance target."""
        detections = [{"severity": "medium", "rule_name": f"rule_{i}"} for i in range(100)]

        start = time.perf_counter()
        for _ in range(100):
            nova_guard_module.filter_by_severity(detections, "medium")
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, "100 iterations should complete in < 100ms"
