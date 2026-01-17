"""
Tests for the AI Summary Module.

Consolidated tests covering:
- Stats-only fallback summary generation
- Prompt building
- API failure handling
- Successful API calls
- Edge cases
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add hooks/lib to path for imports
lib_dir = Path(__file__).parent.parent / "hooks" / "lib"
sys.path.insert(0, str(lib_dir))

from ai_summary import (
    HAIKU_MODEL,
    MAX_SUMMARY_TOKENS,
    _build_summary_prompt,
    generate_ai_summary,
    generate_stats_summary,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_session_data():
    """Create sample session data for testing."""
    return {
        "session_id": "2026-01-10_16-30-45_abc123",
        "session_start": "2026-01-10T16:30:45Z",
        "session_end": "2026-01-10T17:30:45Z",
        "platform": "darwin",
        "project_dir": "/test/project",
        "events": [
            {"type": "event", "id": 1, "tool_name": "Read", "nova_verdict": "allowed"},
            {"type": "event", "id": 2, "tool_name": "Edit", "nova_verdict": "allowed"},
            {"type": "event", "id": 3, "tool_name": "Bash", "nova_verdict": "warned"},
        ],
        "summary": {
            "ai_summary": None,
            "total_events": 3,
            "tools_used": {"Read": 1, "Edit": 1, "Bash": 1},
            "files_touched": 2,
            "warnings": 1,
            "blocked": 0,
            "duration_seconds": 3600,
        },
    }


@pytest.fixture
def empty_session_data():
    """Create empty session data for testing."""
    return {
        "session_id": "2026-01-10_16-30-45_xyz789",
        "events": [],
        "summary": {
            "total_events": 0,
            "tools_used": {},
            "files_touched": 0,
            "warnings": 0,
            "blocked": 0,
            "duration_seconds": 5,
        },
    }


# ============================================================================
# Stats Summary Tests
# ============================================================================


class TestStatsSummary:
    """Tests for stats-only fallback summary generation."""

    def test_basic_format(self, sample_session_data):
        """Stats summary includes tool calls, duration, and files."""
        summary = generate_stats_summary(sample_session_data)
        assert "3 tool calls" in summary
        assert "1h" in summary  # 3600 seconds
        assert "2 files" in summary

    def test_includes_warnings_and_blocked(self):
        """Stats summary includes warning and blocked counts."""
        session_data = {
            "summary": {
                "total_events": 5,
                "files_touched": 1,
                "warnings": 3,
                "blocked": 2,
                "duration_seconds": 60,
            },
            "events": [],
        }
        summary = generate_stats_summary(session_data)
        assert "3 warnings" in summary
        assert "2 blocked" in summary

    @pytest.mark.parametrize("seconds,expected", [
        (5, "5s"),
        (125, "2m 5s"),
        (7260, "2h 1m"),
        (0, "0s"),
        (36000, "10h"),
    ])
    def test_duration_formatting(self, seconds, expected):
        """Duration is formatted correctly for various lengths."""
        session_data = {
            "summary": {
                "total_events": 1,
                "files_touched": 0,
                "warnings": 0,
                "blocked": 0,
                "duration_seconds": seconds,
            },
            "events": [],
        }
        summary = generate_stats_summary(session_data)
        assert expected in summary

    def test_empty_session(self, empty_session_data):
        """Empty session produces valid summary."""
        summary = generate_stats_summary(empty_session_data)
        assert "0 tool calls" in summary
        assert "5s" in summary


# ============================================================================
# Prompt Builder Tests
# ============================================================================


class TestPromptBuilder:
    """Tests for the prompt builder function."""

    def test_prompt_includes_required_info(self, sample_session_data):
        """Prompt includes project dir, duration, events, and security info."""
        prompt = _build_summary_prompt(sample_session_data)

        assert "/test/project" in prompt
        assert "hour" in prompt.lower()
        assert "Read" in prompt and "Edit" in prompt
        assert "1 warnings" in prompt
        assert "Read (allowed)" in prompt
        assert "Bash" in prompt and "warned" in prompt

    def test_truncates_long_event_list(self):
        """Prompt truncates event list for many events."""
        session_data = {
            "summary": {
                "total_events": 15,
                "tools_used": {"Read": 15},
                "files_touched": 5,
                "warnings": 0,
                "blocked": 0,
                "duration_seconds": 300,
            },
            "events": [{"tool_name": "Read", "nova_verdict": "allowed"} for _ in range(15)],
            "project_dir": "/test",
        }
        prompt = _build_summary_prompt(session_data)
        assert "and 5 more events" in prompt


# ============================================================================
# No API Key Tests
# ============================================================================


class TestNoAPIKey:
    """Tests for AI summary without API key."""

    def test_falls_back_to_stats_summary(self, sample_session_data):
        """Missing API key falls back to stats summary without error."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ANTHROPIC_API_KEY", None)
            summary = generate_ai_summary(sample_session_data)

        assert "tool calls" in summary
        assert isinstance(summary, str)


# ============================================================================
# API Failure Tests
# ============================================================================


class TestAPIFailure:
    """Tests for AI summary API failure handling."""

    @pytest.mark.parametrize("error_type", [
        "connection",
        "rate_limit",
        "status",
        "unexpected",
    ])
    def test_errors_fall_back_to_stats(self, sample_session_data, error_type):
        """Various API errors fall back to stats summary."""
        import anthropic as real_anthropic

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_client_class:
                if error_type == "connection":
                    mock_client_class.return_value.messages.create.side_effect = \
                        real_anthropic.APIConnectionError(request=MagicMock())
                elif error_type == "rate_limit":
                    mock_client_class.return_value.messages.create.side_effect = \
                        real_anthropic.RateLimitError(
                            message="Rate limited",
                            response=MagicMock(status_code=429),
                            body={}
                        )
                elif error_type == "status":
                    mock_client_class.return_value.messages.create.side_effect = \
                        real_anthropic.APIStatusError(
                            message="Server error",
                            response=MagicMock(status_code=500),
                            body={}
                        )
                else:
                    mock_client_class.return_value.messages.create.side_effect = \
                        Exception("Unexpected error")

                summary = generate_ai_summary(sample_session_data)

        assert "tool calls" in summary  # Falls back to stats

    def test_empty_response_falls_back(self, sample_session_data):
        """Empty API response falls back to stats summary."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_client_class:
                mock_response = MagicMock()
                mock_response.content = []
                mock_client_class.return_value.messages.create.return_value = mock_response

                summary = generate_ai_summary(sample_session_data)

        assert "tool calls" in summary


# ============================================================================
# API Success Tests
# ============================================================================


class TestAPISuccess:
    """Tests for successful AI summary generation."""

    def test_returns_ai_summary(self, sample_session_data):
        """Successful API call returns AI-generated summary."""
        expected_summary = "This session focused on file editing tasks."

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_client_class:
                mock_content = MagicMock()
                mock_content.text = expected_summary
                mock_response = MagicMock()
                mock_response.content = [mock_content]
                mock_client_class.return_value.messages.create.return_value = mock_response

                summary = generate_ai_summary(sample_session_data)

        assert summary == expected_summary

    def test_uses_haiku_model_and_correct_tokens(self, sample_session_data):
        """API call uses Claude Haiku model with correct max_tokens."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_client_class:
                mock_content = MagicMock()
                mock_content.text = "Test summary"
                mock_response = MagicMock()
                mock_response.content = [mock_content]
                mock_client_class.return_value.messages.create.return_value = mock_response

                generate_ai_summary(sample_session_data)

                call_args = mock_client_class.return_value.messages.create.call_args
                assert call_args.kwargs["model"] == HAIKU_MODEL
                assert call_args.kwargs["max_tokens"] == MAX_SUMMARY_TOKENS

    def test_strips_whitespace_from_response(self, sample_session_data):
        """Whitespace is stripped from API response."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            with patch("anthropic.Anthropic") as mock_client_class:
                mock_content = MagicMock()
                mock_content.text = "  Summary with whitespace  \n"
                mock_response = MagicMock()
                mock_response.content = [mock_content]
                mock_client_class.return_value.messages.create.return_value = mock_response

                summary = generate_ai_summary(sample_session_data)

        assert summary == "Summary with whitespace"


# ============================================================================
# Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_missing_summary_dict(self):
        """Handles missing summary dictionary."""
        session_data = {"events": [], "project_dir": "/test"}
        summary = generate_stats_summary(session_data)
        assert "0 tool calls" in summary

    def test_missing_events_list(self):
        """Handles missing events list."""
        session_data = {"summary": {"total_events": 5, "duration_seconds": 60}}
        summary = generate_stats_summary(session_data)
        assert "5 tool calls" in summary

    def test_summary_stored_in_session_data(self, sample_session_data):
        """Summary can be stored in session data correctly."""
        summary = generate_ai_summary(sample_session_data)
        sample_session_data["summary"]["ai_summary"] = summary

        assert sample_session_data["summary"]["ai_summary"] is not None
        assert isinstance(sample_session_data["summary"]["ai_summary"], str)
