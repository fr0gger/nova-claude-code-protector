"""
AI Summary Module for Nova-tracer.
Agent Monitoring and Visibility

Generates intelligent session summaries using Claude Haiku API.
Falls back to stats-only summaries when API is unavailable.

Story 3.3: AI Summary Module
- Generate 2-3 sentence summaries via Claude Haiku
- Stats-only fallback when API key missing or call fails
- Fail-open error handling (never block report generation)
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="[NOVA %(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("nova-tracer.ai-summary")

# Claude Haiku model for summaries
HAIKU_MODEL = "claude-3-5-haiku-20241022"
MAX_SUMMARY_TOKENS = 256


def generate_stats_summary(session_data: Dict[str, Any]) -> str:
    """
    Generate a stats-only fallback summary.

    This is used when the API is unavailable or fails.

    Args:
        session_data: Complete session object with events and summary

    Returns:
        A stats-based summary string
    """
    summary = session_data.get("summary", {})
    events = session_data.get("events", [])

    total_events = summary.get("total_events", len(events))
    files_touched = summary.get("files_touched", 0)
    warnings = summary.get("warnings", 0)
    blocked = summary.get("blocked", 0)
    duration_seconds = summary.get("duration_seconds", 0)

    # Format duration
    if duration_seconds >= 3600:
        duration_str = f"{duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m"
    elif duration_seconds >= 60:
        duration_str = f"{duration_seconds // 60}m {duration_seconds % 60}s"
    else:
        duration_str = f"{duration_seconds}s"

    # Build summary
    summary_parts = [f"Session completed {total_events} tool calls over {duration_str}."]

    if files_touched > 0:
        summary_parts.append(f"Modified {files_touched} files.")

    if warnings > 0 or blocked > 0:
        security_parts = []
        if warnings > 0:
            security_parts.append(f"{warnings} warnings")
        if blocked > 0:
            security_parts.append(f"{blocked} blocked")
        summary_parts.append(f"{', '.join(security_parts)}.")

    return " ".join(summary_parts)


def _build_summary_prompt(session_data: Dict[str, Any]) -> str:
    """
    Build a prompt for the Claude API to generate a session summary.

    Args:
        session_data: Complete session object with events and summary

    Returns:
        The prompt string
    """
    summary = session_data.get("summary", {})
    events = session_data.get("events", [])
    project_dir = session_data.get("project_dir", "unknown project")

    total_events = summary.get("total_events", len(events))
    tools_used = summary.get("tools_used", {})
    files_touched = summary.get("files_touched", 0)
    warnings = summary.get("warnings", 0)
    blocked = summary.get("blocked", 0)
    duration_seconds = summary.get("duration_seconds", 0)

    # Format duration for prompt
    if duration_seconds >= 3600:
        duration_str = f"{duration_seconds // 3600} hours {(duration_seconds % 3600) // 60} minutes"
    elif duration_seconds >= 60:
        duration_str = f"{duration_seconds // 60} minutes {duration_seconds % 60} seconds"
    else:
        duration_str = f"{duration_seconds} seconds"

    # Build tools summary
    tools_summary = ", ".join(
        f"{tool}: {count}" for tool, count in sorted(tools_used.items(), key=lambda x: -x[1])[:5]
    )

    # Build condensed event list (max 10 events for context)
    event_list = []
    files_accessed = set()
    for event in events[:10]:
        tool_name = event.get("tool_name", "Unknown")
        verdict = event.get("nova_verdict", "allowed")
        tool_input = event.get("tool_input", {})

        # Extract file path if available
        file_path = tool_input.get("file_path", "")
        if file_path:
            # Get just the filename for brevity
            filename = file_path.split("/")[-1]
            files_accessed.add(filename)
            event_list.append(f"- {tool_name}: {filename} ({verdict})")
        elif tool_name == "Bash":
            cmd = tool_input.get("command", "")[:50]
            event_list.append(f"- {tool_name}: {cmd}... ({verdict})")
        else:
            event_list.append(f"- {tool_name} ({verdict})")

    if len(events) > 10:
        event_list.append(f"- ... and {len(events) - 10} more events")

    events_text = "\n".join(event_list) if event_list else "No events recorded."
    files_list = ", ".join(sorted(files_accessed)) if files_accessed else "None"

    prompt = f"""You are summarizing a Claude Code development session. Generate a 2-3 sentence summary.

SESSION DATA:
- Project: {project_dir}
- Duration: {duration_str}
- Tool calls: {total_events}
- Files modified: {files_touched}
- Files accessed: {files_list}
- Tools: {tools_summary if tools_summary else "None"}
- Security: {warnings} warnings, {blocked} blocked

EVENTS:
{events_text}

TASK: Write exactly 2-3 sentences describing what was done. Be specific about files created/modified. Do not apologize or ask for more information - just summarize based on the data above."""

    return prompt


def generate_ai_summary(
    session_data: Dict[str, Any],
    ai_enabled: bool = True,
) -> str:
    """
    Generate an AI summary of the session using Claude Haiku.
    Falls back to stats-only summary if API unavailable or disabled.

    Args:
        session_data: Complete session object with events and summary
        ai_enabled: Whether AI summaries are enabled (from config).
                   If False, uses stats-only summary without API call.

    Returns:
        A 2-3 sentence summary string
    """
    # Check if AI summaries are disabled in config
    if not ai_enabled:
        logger.info("AI summaries disabled in config, using stats-only summary")
        return generate_stats_summary(session_data)

    # Check for API key first
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set, using stats-only summary")
        return generate_stats_summary(session_data)

    # Try to import anthropic
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed, using stats-only summary")
        return generate_stats_summary(session_data)

    # Try API call
    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_summary_prompt(session_data)

        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=MAX_SUMMARY_TOKENS,
            system="You are a technical summarizer. Generate concise, factual summaries of development sessions. Never apologize or ask for clarification - always provide a summary based on available data.",
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        if response.content and len(response.content) > 0:
            summary_text = response.content[0].text.strip()
            if summary_text:
                return summary_text

        # Empty response - fall back
        logger.warning("Empty response from Claude API, using stats-only summary")
        return generate_stats_summary(session_data)

    except anthropic.APIConnectionError as e:
        logger.warning(f"API connection error: {e}, using stats-only summary")
        return generate_stats_summary(session_data)

    except anthropic.RateLimitError as e:
        logger.warning(f"API rate limit: {e}, using stats-only summary")
        return generate_stats_summary(session_data)

    except anthropic.APIStatusError as e:
        logger.warning(f"API status error: {e}, using stats-only summary")
        return generate_stats_summary(session_data)

    except Exception as e:
        logger.warning(f"Unexpected error generating AI summary: {e}, using stats-only summary")
        return generate_stats_summary(session_data)
