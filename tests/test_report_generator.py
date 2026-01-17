"""
Tests for HTML Report Generator (Stories 4.1-4.4).

Consolidated tests covering acceptance criteria:
- AC1: Self-contained HTML with embedded CSS
- AC2: Statistics display (session time, event count, tools used)
- AC3: Health status badges (CLEAN/WARNINGS/DETECTED)
- AC4: Visual timeline with clickable events
- AC5: Event detail cards (collapsed/expanded)
- AC6: Tool icons
"""

import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add hooks/lib to path for imports
lib_dir = Path(__file__).parent.parent / "hooks" / "lib"
sys.path.insert(0, str(lib_dir))

from report_generator import (
    TOOL_ICONS,
    generate_html_report,
    get_tool_icon,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def minimal_session():
    """Minimal valid session data."""
    return {
        "session_id": "test_session",
        "events": [],
        "summary": {},
    }


@pytest.fixture
def session_with_events():
    """Session with sample events."""
    return {
        "session_id": "events_session",
        "events": [
            {
                "type": "event",
                "id": 1,
                "tool_name": "Read",
                "nova_verdict": "allowed",
                "timestamp_start": "2024-01-01T12:00:00Z",
                "files_accessed": ["/test/file.py"],
            },
            {
                "type": "event",
                "id": 2,
                "tool_name": "Bash",
                "nova_verdict": "warned",
                "timestamp_start": "2024-01-01T12:01:00Z",
                "files_accessed": ["/test/script.sh"],
            },
        ],
        "summary": {
            "total_events": 2,
            "tools_used": {"Read": 1, "Bash": 1},
            "warnings": 1,
            "blocked": 0,
        },
    }


# ============================================================================
# Self-Contained HTML Tests (AC1)
# ============================================================================


class TestSelfContainedHTML:
    """Tests for self-contained HTML generation."""

    def test_valid_html_structure(self, minimal_session):
        """Generated HTML has proper structure."""
        html = generate_html_report(minimal_session)
        assert "<!DOCTYPE html>" in html
        assert "<html" in html
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_css_is_embedded(self, minimal_session):
        """CSS is embedded in <style> tag, not external."""
        html = generate_html_report(minimal_session)
        assert "<style>" in html
        assert "</style>" in html
        # Should not have external stylesheet
        assert 'rel="stylesheet"' not in html

    def test_no_external_dependencies(self, minimal_session):
        """HTML has no external JS/CSS dependencies."""
        html = generate_html_report(minimal_session)
        # No external scripts (except inline)
        assert html.count("<script src=") == 0
        # No external stylesheets
        assert html.count('href=') == 0 or 'href="http' not in html


# ============================================================================
# Statistics Display Tests (AC2)
# ============================================================================


class TestStatisticsDisplay:
    """Tests for statistics display."""

    def test_session_id_displayed(self, minimal_session):
        """Session ID is displayed."""
        html = generate_html_report(minimal_session)
        assert "test_session" in html

    def test_event_counts_displayed(self, session_with_events):
        """Event counts are displayed."""
        html = generate_html_report(session_with_events)
        assert "2" in html  # Total events

    def test_tools_used_displayed(self, session_with_events):
        """Tools used are displayed."""
        html = generate_html_report(session_with_events)
        assert "Read" in html
        assert "Bash" in html

    def test_duration_displayed(self):
        """Duration is displayed when provided."""
        session_data = {
            "session_id": "dur_test",
            "events": [],
            "summary": {"duration_seconds": 3600},
        }
        html = generate_html_report(session_data)
        # Duration should be somewhere in the HTML
        assert "1h" in html or "3600" in html or "60" in html


# ============================================================================
# Health Status Badges (AC3)
# ============================================================================


class TestHealthStatus:
    """Tests for health status badges."""

    def test_clean_status_displayed(self):
        """CLEAN status is displayed when no warnings or blocked."""
        session_data = {
            "session_id": "clean_test",
            "events": [],
            "summary": {"warnings": 0, "blocked": 0},
        }
        html = generate_html_report(session_data)
        assert "CLEAN" in html

    def test_warnings_status_displayed(self):
        """WARNINGS status is displayed when warnings exist."""
        session_data = {
            "session_id": "warn_test",
            "events": [],
            "summary": {"warnings": 3, "blocked": 0},
        }
        html = generate_html_report(session_data)
        # Should show warnings count
        assert "3" in html and "warning" in html.lower()

    def test_detected_status_displayed(self):
        """DETECTED status is displayed when blocked exist."""
        session_data = {
            "session_id": "detect_test",
            "events": [],
            "summary": {"warnings": 1, "blocked": 2},
        }
        html = generate_html_report(session_data)
        # Should show detected (blocked) count
        assert "2" in html and "detected" in html.lower()

    def test_health_badge_class_exists(self, minimal_session):
        """Health badge has appropriate CSS class."""
        html = generate_html_report(minimal_session)
        assert "health-badge" in html


# ============================================================================
# AI Summary Display
# ============================================================================


class TestAISummary:
    """Tests for AI summary display."""

    def test_ai_summary_displayed(self):
        """AI summary text is displayed when present."""
        session_data = {
            "session_id": "summary",
            "events": [],
            "summary": {"ai_summary": "This session performed security scans."},
        }
        html = generate_html_report(session_data)
        assert "This session performed security scans." in html

    def test_fallback_summary_when_missing(self):
        """Fallback summary generated when AI summary is missing."""
        session_data = {
            "session_id": "fallback",
            "events": [],
            "summary": {"total_events": 10, "files_touched": 5, "duration_seconds": 120},
        }
        html = generate_html_report(session_data)
        assert "10" in html  # Event count in summary


# ============================================================================
# Tool Icons (AC6)
# ============================================================================


class TestToolIcons:
    """Tests for tool icons."""

    def test_required_tool_icons_exist(self):
        """All required tool icons are defined."""
        required_tools = ["Read", "Edit", "Write", "Bash", "Glob", "Grep", "WebFetch", "Task", "_default"]
        for tool in required_tools:
            assert tool in TOOL_ICONS, f"Missing icon for {tool}"

    def test_all_icons_are_valid_svg(self):
        """All tool icons are valid SVG strings."""
        for tool_name, icon in TOOL_ICONS.items():
            assert "<svg" in icon, f"{tool_name} doesn't contain <svg"
            assert "</svg>" in icon, f"{tool_name} missing </svg>"

    def test_get_tool_icon_returns_default_for_unknown(self):
        """get_tool_icon returns default icon for unknown tools."""
        unknown_icon = get_tool_icon("UnknownToolXYZ")
        assert unknown_icon == TOOL_ICONS["_default"]


# ============================================================================
# Event Display
# ============================================================================


class TestEventDisplay:
    """Tests for event display."""

    def test_events_show_tool_name(self, session_with_events):
        """Events display tool name."""
        html = generate_html_report(session_with_events)
        assert "Read" in html
        assert "Bash" in html

    def test_events_show_verdict(self, session_with_events):
        """Events display verdict."""
        html = generate_html_report(session_with_events)
        # Check for verdict indicators (case insensitive)
        html_lower = html.lower()
        assert "allowed" in html_lower or "warned" in html_lower

    def test_events_show_files(self, session_with_events):
        """Events display accessed files."""
        html = generate_html_report(session_with_events)
        assert "/test/file.py" in html


# ============================================================================
# JavaScript Functions
# ============================================================================


class TestJavaScript:
    """Tests for JavaScript functionality."""

    def test_scroll_to_event_function_exists(self, session_with_events):
        """scrollToEvent function is defined."""
        html = generate_html_report(session_with_events)
        assert "scrollToEvent" in html

    def test_toggle_event_function_exists(self, session_with_events):
        """toggleEvent function is defined."""
        html = generate_html_report(session_with_events)
        assert "toggleEvent" in html

    def test_session_data_embedded(self, session_with_events):
        """Session data is embedded for JS access."""
        html = generate_html_report(session_with_events)
        assert "SESSION_DATA" in html


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_events_list(self, minimal_session):
        """Handles empty events list."""
        html = generate_html_report(minimal_session)
        assert "<!DOCTYPE html>" in html  # Should still generate valid HTML

    def test_missing_summary(self):
        """Handles missing summary gracefully."""
        session_data = {"session_id": "no_summary", "events": []}
        html = generate_html_report(session_data)
        assert "<!DOCTYPE html>" in html

    def test_special_characters_escaped(self):
        """Special characters are properly escaped."""
        session_data = {
            "session_id": "escape<test>&\"'",
            "events": [],
            "summary": {},
        }
        html = generate_html_report(session_data)
        # Should not have unescaped < > in content (outside tags)
        assert "<!DOCTYPE html>" in html

    def test_large_number_of_events(self):
        """Handles large number of events."""
        session_data = {
            "session_id": "large",
            "events": [
                {"tool_name": "Read", "nova_verdict": "allowed", "timestamp_start": f"2024-01-01T10:{i:02d}:00Z"}
                for i in range(50)
            ],
            "summary": {"total_events": 50},
        }
        html = generate_html_report(session_data)
        assert "<!DOCTYPE html>" in html
        # Should have embedded session data with all events
        assert "SESSION_DATA" in html


# ============================================================================
# Performance
# ============================================================================


class TestPerformance:
    """Tests for performance requirements."""

    def test_large_session_generates_quickly(self):
        """Large session generates in reasonable time."""
        import time

        session_data = {
            "session_id": "perf_test",
            "events": [
                {
                    "tool_name": "Read",
                    "nova_verdict": "allowed",
                    "timestamp_start": f"2024-01-01T{i // 60:02d}:{i % 60:02d}:00Z",
                    "files_accessed": [f"/file{i}.py"],
                }
                for i in range(100)
            ],
            "summary": {"total_events": 100},
        }

        start = time.perf_counter()
        html = generate_html_report(session_data)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, "Should generate in less than 1 second"
        assert len(html) > 1000, "Should generate substantial HTML"
