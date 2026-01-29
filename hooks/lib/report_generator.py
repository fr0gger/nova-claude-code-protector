"""
Report Generator Module for Nova-tracer.
Agent Monitoring and Visibility

Converts session JSON data to self-contained HTML reports.

Story 3.2: Report Generator Module
- Generates complete, self-contained HTML reports
- All CSS embedded in <style> tags
- All JavaScript embedded in <script> tags
- Session data embedded as const SESSION_DATA = {...}
- Includes aggregate statistics and metadata
"""

import html
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="[NOVA %(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("nova-tracer.report")

# Nova-tracer version
NOVA_VERSION = "0.1.0"

# Tool icons (SVG) - Simple, recognizable icons for each tool type
TOOL_ICONS = {
    "Read": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
        <polyline points="14 2 14 8 20 8"></polyline>
        <line x1="16" y1="13" x2="8" y2="13"></line>
        <line x1="16" y1="17" x2="8" y2="17"></line>
        <polyline points="10 9 9 9 8 9"></polyline>
    </svg>''',
    "Edit": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
    </svg>''',
    "Write": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
    </svg>''',
    "Bash": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polyline points="4 17 10 11 4 5"></polyline>
        <line x1="12" y1="19" x2="20" y2="19"></line>
    </svg>''',
    "Glob": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </svg>''',
    "Grep": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
    </svg>''',
    "WebFetch": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="2" y1="12" x2="22" y2="12"></line>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
    </svg>''',
    "WebSearch": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="2" y1="12" x2="22" y2="12"></line>
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
    </svg>''',
    "Task": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
        <circle cx="12" cy="16" r="1"></circle>
    </svg>''',
    "_default": '''<svg class="tool-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"></circle>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
    </svg>''',
    # MCP (Model Context Protocol) server icon - network/connection symbol
    "MCP": '''<svg class="tool-icon mcp-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"></circle>
        <path d="M12 2v4m0 12v4M2 12h4m12 0h4"></path>
        <path d="M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"></path>
    </svg>''',
    # Skill icon - lightning bolt / slash command symbol
    "Skill": '''<svg class="tool-icon skill-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
    </svg>''',
}


def get_tool_icon(tool_name: str) -> str:
    """Get the SVG icon for a tool type."""
    # Check for MCP tools first (mcp__ or mcp_ prefix)
    if tool_name.startswith("mcp__") or tool_name.startswith("mcp_"):
        return TOOL_ICONS["MCP"]
    # Check for Skill tool
    if tool_name == "Skill":
        return TOOL_ICONS["Skill"]
    return TOOL_ICONS.get(tool_name, TOOL_ICONS["_default"])


def _format_timestamp(timestamp: str) -> str:
    """Format an ISO timestamp for display."""
    if not timestamp:
        return "N/A"
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return timestamp[:19] if len(timestamp) >= 19 else timestamp


def _json_for_html(data: Any) -> str:
    """
    Convert data to JSON and escape for safe embedding in HTML script tags.

    Prevents XSS by escaping characters that could break out of script context.
    """
    json_str = json.dumps(data, default=str)
    # Escape characters that could break out of script tag or cause issues
    json_str = json_str.replace("<", "\\u003c")
    json_str = json_str.replace(">", "\\u003e")
    json_str = json_str.replace("&", "\\u0026")
    return json_str


def generate_html_report(session_data: Dict[str, Any]) -> str:
    """
    Generate a self-contained HTML report from session data.

    Args:
        session_data: Complete session object with events and summary

    Returns:
        Complete HTML string
    """
    try:
        session_id = session_data.get("session_id", "unknown")
        summary = session_data.get("summary", {})
        events = session_data.get("events", [])

        # Extract metadata
        session_start = session_data.get("session_start", "")
        session_end = session_data.get("session_end", "")
        platform = session_data.get("platform", "unknown")
        project_dir = session_data.get("project_dir", "")

        # Format timestamps for display
        start_display = _format_timestamp(session_start)
        end_display = _format_timestamp(session_end)

        # Calculate health status
        detected = summary.get("blocked", 0)  # "blocked" in data = high-severity detections
        warnings = summary.get("warnings", 0)

        if detected > 0:
            health_status = "DETECTED"
            health_color = "#ef4444"
            health_subtitle = f"{detected} detected, {warnings} warnings"
        elif warnings > 0:
            health_status = "WARNINGS"
            health_color = "#f59e0b"
            health_subtitle = f"{warnings} warnings"
        else:
            health_status = "CLEAN"
            health_color = "#22c55e"
            health_subtitle = ""

        # Format duration
        duration_seconds = summary.get("duration_seconds", 0)
        if duration_seconds >= 3600:
            duration_str = f"{duration_seconds // 3600}h {(duration_seconds % 3600) // 60}m"
        elif duration_seconds >= 60:
            duration_str = f"{duration_seconds // 60}m {duration_seconds % 60}s"
        else:
            duration_str = f"{duration_seconds}s"

        # Build events HTML and timeline
        events_html = _generate_events_html(events)
        timeline_html = _generate_timeline_html(events)

        # Build tools breakdown
        tools_used = summary.get("tools_used", {})
        tools_html = ""
        for tool, count in sorted(tools_used.items(), key=lambda x: -x[1]):
            tool_icon = get_tool_icon(tool)
            tools_html += f'<div class="tool-item"><span class="tool-name">{tool_icon}{html.escape(tool)}</span><span class="tool-count">{count}</span></div>'

        # AI Summary (or fallback)
        ai_summary = summary.get("ai_summary")
        if not ai_summary:
            total = summary.get("total_events", 0)
            files = summary.get("files_touched", 0)
            ai_summary = f"Session completed {total} tool calls over {duration_str}. Modified {files} files. {warnings} warnings, {detected} detected."

        # Activity metrics (estimated from session data)
        activity_metrics = session_data.get("activity_metrics")
        activity_html = _generate_activity_metrics_html(activity_metrics) if activity_metrics else ""

        # MCP Server Activity section
        mcp_html = _generate_mcp_section_html(summary)

        # Agent Skills Activity section
        skill_html = _generate_skill_section_html(summary)

        # Conversation trace (user prompts + tool calls)
        conversation_html = _generate_conversation_trace_html(events, summary)

        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nova-tracer Session Report - {html.escape(session_id)}</title>
    <style>
        :root {{
            --color-allowed: #22c55e;
            --color-warned: #f59e0b;
            --color-detected: #ef4444;
            --color-neutral: #6b7280;
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
        }}
        .header-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }}
        .logo {{ font-size: 1.5rem; font-weight: bold; }}
        .logo span {{ color: var(--color-allowed); }}
        .health-badge-container {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
        }}
        .health-badge {{
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-weight: bold;
            color: white;
            background: {health_color};
        }}
        .health-subtitle {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }}
        .session-id {{ color: var(--text-secondary); font-size: 0.875rem; }}
        .summary {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}
        .summary h2 {{ margin-bottom: 1rem; font-size: 1.25rem; }}
        .summary p {{ color: var(--text-secondary); }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        .stat-value {{ font-size: 2rem; font-weight: bold; }}
        .stat-label {{ color: var(--text-secondary); font-size: 0.875rem; }}
        .stat-card.warnings .stat-value {{ color: var(--color-warned); }}
        .stat-card.detected .stat-value {{ color: var(--color-detected); }}
        .tools-section {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}
        .tools-section h2 {{ margin-bottom: 1rem; font-size: 1.25rem; }}
        .tool-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .tool-item:last-child {{ border-bottom: none; }}
        .tool-name {{ display: flex; align-items: center; gap: 0.5rem; }}
        .tool-count {{ color: var(--text-secondary); }}
        .events-section {{ margin-bottom: 2rem; }}
        .events-section h2 {{ margin-bottom: 1rem; font-size: 1.25rem; }}
        .event-card {{
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.5rem;
            border-left: 4px solid var(--color-allowed);
        }}
        .event-card.warned {{ border-left-color: var(--color-warned); }}
        .event-card.detected {{ border-left-color: var(--color-detected); }}
        .event-header {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            cursor: pointer;
            padding: 0.5rem 0;
        }}
        .event-header:hover {{
            background: rgba(255,255,255,0.05);
            margin: 0 -1rem;
            padding: 0.5rem 1rem;
            border-radius: 4px;
        }}
        .event-id {{
            color: var(--text-secondary);
            font-family: monospace;
            font-size: 0.75rem;
            min-width: 2rem;
        }}
        .event-tool {{ font-weight: bold; display: flex; align-items: center; gap: 0.5rem; flex: 1; }}
        .tool-icon {{ width: 18px; height: 18px; flex-shrink: 0; }}
        .event-time {{ color: var(--text-secondary); font-size: 0.875rem; font-family: monospace; }}
        .event-verdict {{
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
        }}
        .event-verdict.allowed {{ background: rgba(34, 197, 94, 0.2); color: var(--color-allowed); }}
        .event-verdict.warned {{ background: rgba(245, 158, 11, 0.2); color: var(--color-warned); }}
        .event-verdict.detected {{ background: rgba(239, 68, 68, 0.2); color: var(--color-detected); }}
        .expand-icon {{
            color: var(--text-secondary);
            transition: transform 0.2s ease;
            font-size: 0.75rem;
        }}
        .event-card.expanded .expand-icon {{
            transform: rotate(180deg);
        }}
        .event-details {{
            padding: 1rem 0;
            border-top: 1px solid rgba(255,255,255,0.1);
            margin-top: 0.5rem;
        }}
        .detail-section {{
            margin-bottom: 1rem;
        }}
        .detail-section:last-child {{
            margin-bottom: 0;
        }}
        .detail-label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}
        .detail-value {{
            background: rgba(0,0,0,0.2);
            padding: 0.75rem;
            border-radius: 6px;
            overflow-x: auto;
        }}
        .detail-value pre {{
            margin: 0;
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace;
            font-size: 0.8125rem;
            white-space: pre-wrap;
            word-break: break-word;
            line-height: 1.5;
        }}
        .detail-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1rem;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        .meta-item strong {{
            color: var(--text-primary);
        }}
        .files-list {{
            list-style: none;
            padding: 0;
            margin: 0;
            font-family: monospace;
            font-size: 0.8125rem;
        }}
        .files-list li {{
            padding: 0.25rem 0.5rem;
            background: rgba(0,0,0,0.2);
            margin-bottom: 0.25rem;
            border-radius: 4px;
        }}
        .truncation-indicator {{
            color: var(--color-warned);
            font-size: 0.75rem;
            font-style: italic;
            margin-top: 0.5rem;
        }}
        .nova-verdict-section {{
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
        }}
        .nova-verdict-section .detail-label {{
            color: var(--color-detected);
        }}
        .event-card.warned .nova-verdict-section {{
            background: rgba(245, 158, 11, 0.1);
            border-color: rgba(245, 158, 11, 0.3);
        }}
        .event-card.warned .nova-verdict-section .detail-label {{
            color: var(--color-warned);
        }}
        .nova-details {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            align-items: center;
        }}
        .nova-severity {{
            font-weight: bold;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }}
        .nova-severity.low {{ color: var(--color-allowed); }}
        .nova-severity.medium {{ color: var(--color-warned); }}
        .nova-severity.high {{ color: #f97316; }}
        .nova-severity.critical {{ color: var(--color-detected); }}
        .nova-scan-time {{
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        .nova-rules {{
            width: 100%%;
            font-family: monospace;
            font-size: 0.875rem;
            color: var(--text-primary);
        }}
        .event-files-collapsed {{
            color: var(--text-secondary);
            font-size: 0.8125rem;
        }}
        .event-card.highlighted {{
            animation: highlight-pulse 2s ease-out;
            box-shadow: 0 0 0 2px var(--color-allowed);
        }}
        @keyframes highlight-pulse {{
            0% {{ box-shadow: 0 0 0 4px rgba(34, 197, 94, 0.6); }}
            100% {{ box-shadow: 0 0 0 2px transparent; }}
        }}
        .timeline-container {{
            display: flex;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .timeline {{
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
            min-width: 120px;
            max-width: 150px;
            position: sticky;
            top: 1rem;
            height: fit-content;
            max-height: calc(100vh - 2rem);
            overflow-y: auto;
            padding-right: 0.5rem;
        }}
        .timeline-node {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.375rem 0.5rem;
            border-radius: 6px;
            cursor: pointer;
            background: var(--bg-secondary);
            border-left: 3px solid var(--color-allowed);
            transition: background 0.2s, transform 0.1s;
            font-size: 0.75rem;
        }}
        .timeline-node:hover {{
            background: rgba(255,255,255,0.1);
            transform: translateX(2px);
        }}
        .timeline-node.warned {{ border-left-color: var(--color-warned); }}
        .timeline-node.detected {{
            border-left-color: var(--color-detected);
            background: rgba(239, 68, 68, 0.1);
        }}
        .timeline-node .node-icon {{ width: 14px; height: 14px; flex-shrink: 0; }}
        .timeline-node .node-time {{ color: var(--text-secondary); font-family: monospace; }}
        .events-list {{ flex: 1; }}
        .metadata-section {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}
        .metadata-section h2 {{ margin-bottom: 1rem; font-size: 1.25rem; }}
        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
        }}
        .metadata-item {{
            display: flex;
            flex-direction: column;
        }}
        .metadata-label {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.25rem;
        }}
        .metadata-value {{
            font-family: monospace;
            font-size: 0.875rem;
            word-break: break-all;
        }}
        .activity-section {{
            background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }}
        .activity-section h2 {{
            margin-bottom: 0.5rem;
            font-size: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .activity-section h2::before {{
            content: "📊";
        }}
        .estimate-badge {{
            font-size: 0.65rem;
            background: rgba(251, 191, 36, 0.2);
            color: #fbbf24;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-weight: normal;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .activity-disclaimer {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            margin-bottom: 1rem;
            font-style: italic;
        }}
        .activity-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 1rem;
        }}
        .activity-metric {{
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        .activity-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #60a5fa;
        }}
        .activity-value.tokens {{
            color: #fbbf24;
        }}
        .activity-label {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }}
        .footer {{
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.875rem;
            padding: 2rem 0;
        }}
        .conversation-section {{
            background: var(--bg-secondary);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}
        .conversation-section h2 {{
            margin-bottom: 1rem;
            font-size: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .conversation-section h2::before {{
            content: "💬";
        }}
        .conversation-trace {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        .trace-entry {{
            display: flex;
            align-items: flex-start;
            gap: 0.75rem;
        }}
        .trace-time {{
            font-family: monospace;
            font-size: 0.75rem;
            color: var(--text-secondary);
            min-width: 60px;
            padding-top: 0.5rem;
        }}
        .trace-label {{
            font-size: 0.65rem;
            font-weight: bold;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
            min-width: 50px;
            text-align: center;
        }}
        .trace-prompt .trace-label {{
            background: rgba(99, 102, 241, 0.2);
            color: #818cf8;
        }}
        .trace-tool .trace-label {{
            background: rgba(34, 197, 94, 0.2);
            color: var(--color-allowed);
        }}
        .trace-tool.warned .trace-label {{
            background: rgba(245, 158, 11, 0.2);
            color: var(--color-warned);
        }}
        .trace-tool.detected .trace-label {{
            background: rgba(239, 68, 68, 0.2);
            color: var(--color-detected);
        }}
        .trace-content {{
            flex: 1;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            font-size: 0.875rem;
            line-height: 1.5;
        }}
        .trace-prompt .trace-content {{
            border-left: 3px solid #818cf8;
        }}
        .trace-tool .trace-content {{
            border-left: 3px solid var(--color-allowed);
            font-family: monospace;
            font-size: 0.8125rem;
        }}
        .trace-tool.warned .trace-content {{
            border-left-color: var(--color-warned);
        }}
        .trace-tool.detected .trace-content {{
            border-left-color: var(--color-detected);
        }}
        .trace-tool.error .trace-label {{
            background: rgba(239, 68, 68, 0.2);
            color: var(--color-detected);
        }}
        .trace-tool.error .trace-content {{
            border-left-color: var(--color-detected);
            background: rgba(239, 68, 68, 0.05);
        }}
        .trace-tool-summary {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .trace-tool-summary .tool-icon {{
            width: 14px;
            height: 14px;
        }}
        .trace-tool-detail {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }}
        .prompt-text {{
            white-space: pre-wrap;
            word-break: break-word;
        }}
        .prompt-truncated {{
            color: var(--text-secondary);
            font-style: italic;
            font-size: 0.75rem;
            margin-top: 0.5rem;
        }}
        .conversation-stats {{
            display: flex;
            gap: 1.5rem;
            margin-bottom: 1rem;
            padding: 0.75rem 1rem;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            font-size: 0.875rem;
        }}
        .conversation-stats span {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        .conversation-stats strong {{
            color: var(--text-primary);
        }}
        /* MCP (Model Context Protocol) Styling */
        .mcp-section {{
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, var(--bg-secondary) 100%);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-left: 4px solid #8b5cf6;
        }}
        .mcp-section h2 {{
            margin-bottom: 1rem;
            font-size: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #a78bfa;
        }}
        .mcp-section h2::before {{
            content: "🔌";
        }}
        .mcp-summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        .mcp-stat {{
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        .mcp-stat-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #a78bfa;
        }}
        .mcp-stat-label {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }}
        .mcp-servers-breakdown {{
            margin-top: 1rem;
        }}
        .mcp-servers-breakdown h3 {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        .mcp-server-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            margin-bottom: 0.25rem;
            border-left: 3px solid #8b5cf6;
        }}
        .mcp-server-name {{
            font-family: monospace;
            color: #a78bfa;
        }}
        .mcp-server-count {{
            color: var(--text-secondary);
        }}
        .mcp-icon {{
            color: #a78bfa;
        }}
        .event-card.mcp {{
            border-left-color: #8b5cf6;
        }}
        .mcp-badge {{
            background: rgba(139, 92, 246, 0.2);
            color: #a78bfa;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-size: 0.65rem;
            font-weight: bold;
            margin-left: 0.5rem;
        }}
        .trace-mcp .trace-label {{
            background: rgba(139, 92, 246, 0.2);
            color: #a78bfa;
        }}
        .trace-mcp .trace-content {{
            border-left-color: #8b5cf6;
        }}
        .timeline-node.mcp {{
            border-left-color: #8b5cf6;
        }}
        /* Skill (Agent Skills) Styling - Orange/Amber theme */
        .skill-section {{
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, var(--bg-secondary) 100%);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border-left: 4px solid #f59e0b;
        }}
        .skill-section h2 {{
            margin-bottom: 1rem;
            font-size: 1.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            color: #fbbf24;
        }}
        .skill-section h2::before {{
            content: "⚡";
        }}
        .skill-summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        .skill-stat {{
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        .skill-stat-value {{
            font-size: 1.5rem;
            font-weight: bold;
            color: #fbbf24;
        }}
        .skill-stat-label {{
            color: var(--text-secondary);
            font-size: 0.75rem;
            margin-top: 0.25rem;
        }}
        .skill-breakdown {{
            margin-top: 1rem;
        }}
        .skill-breakdown h3 {{
            font-size: 0.875rem;
            color: var(--text-secondary);
            margin-bottom: 0.5rem;
        }}
        .skill-item {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0.75rem;
            background: rgba(0,0,0,0.2);
            border-radius: 6px;
            margin-bottom: 0.25rem;
            border-left: 3px solid #f59e0b;
        }}
        .skill-name {{
            font-family: monospace;
            color: #fbbf24;
        }}
        .skill-count {{
            color: var(--text-secondary);
        }}
        .skill-icon {{
            color: #fbbf24;
        }}
        .event-card.skill {{
            border-left-color: #f59e0b;
        }}
        .skill-badge {{
            background: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            font-size: 0.65rem;
            font-weight: bold;
            margin-left: 0.5rem;
        }}
        .trace-skill .trace-label {{
            background: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
        }}
        .trace-skill .trace-content {{
            border-left-color: #f59e0b;
        }}
        .timeline-node.skill {{
            border-left-color: #f59e0b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-top">
                <div class="logo">Nova<span>-tracer</span></div>
                <div class="health-badge-container">
                    <div class="health-badge">{health_status}</div>
                    {f'<div class="health-subtitle">{health_subtitle}</div>' if health_subtitle else ''}
                </div>
            </div>
            <div class="session-id">Session: {html.escape(session_id)}</div>
        </div>

        <div class="summary">
            <h2>Session Summary</h2>
            <p>{html.escape(ai_summary)}</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{summary.get("total_events", 0)}</div>
                <div class="stat-label">Total Events</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{duration_str}</div>
                <div class="stat-label">Duration</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{summary.get("files_touched", 0)}</div>
                <div class="stat-label">Files Touched</div>
            </div>
            <div class="stat-card warnings">
                <div class="stat-value">{warnings}</div>
                <div class="stat-label">Warnings</div>
            </div>
            <div class="stat-card detected">
                <div class="stat-value">{detected}</div>
                <div class="stat-label">Detected</div>
            </div>
        </div>

        {activity_html}

        {mcp_html}

        {skill_html}

        {conversation_html}

        <div class="tools-section">
            <h2>Tools Used</h2>
            {tools_html if tools_html else '<p style="color: var(--text-secondary)">No tools used</p>'}
        </div>

        <div class="events-section">
            <h2>Event Timeline</h2>
            {f'<div class="timeline-container">{timeline_html}<div class="events-list">{events_html}</div></div>' if events_html else '<p style="color: var(--text-secondary)">No events recorded</p>'}
        </div>

        <div class="metadata-section">
            <h2>Session Metadata</h2>
            <div class="metadata-grid">
                <div class="metadata-item">
                    <span class="metadata-label">Platform</span>
                    <span class="metadata-value">{html.escape(platform)}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Project Directory</span>
                    <span class="metadata-value">{html.escape(project_dir) if project_dir else 'N/A'}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Session Start</span>
                    <span class="metadata-value">{html.escape(start_display)}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Session End</span>
                    <span class="metadata-value">{html.escape(end_display)}</span>
                </div>
                <div class="metadata-item">
                    <span class="metadata-label">Nova-tracer Version</span>
                    <span class="metadata-value">{NOVA_VERSION}</span>
                </div>
            </div>
        </div>

        <div class="footer">
            Generated by Nova-tracer v{NOVA_VERSION}<br>
            Agent Monitoring and Visibility<br>
            Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>

    <script>
        // Session data embedded for interactive features (Story 4.x)
        const SESSION_DATA = {_json_for_html(session_data)};

        // Timeline navigation - scroll to event card and highlight
        function scrollToEvent(eventId) {{
            const card = document.getElementById('event-' + eventId);
            if (card) {{
                card.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                card.classList.add('highlighted');
                setTimeout(() => card.classList.remove('highlighted'), 2000);
            }}
        }}

        // Toggle event card expand/collapse (Story 4.4)
        function toggleEvent(eventId) {{
            const card = document.getElementById('event-' + eventId);
            const details = document.getElementById('details-' + eventId);
            if (card && details) {{
                if (card.classList.contains('expanded')) {{
                    card.classList.remove('expanded');
                    details.style.display = 'none';
                }} else {{
                    card.classList.add('expanded');
                    details.style.display = 'block';
                }}
            }}
        }}
    </script>
</body>
</html>'''

        return html_content

    except Exception as e:
        logger.warning(f"Failed to generate HTML report: {e}")
        return _generate_error_report(str(e))


def _generate_mcp_section_html(summary: Dict[str, Any]) -> str:
    """
    Generate HTML for the MCP Server Activity section.

    Shows MCP-specific statistics including server breakdown.

    Args:
        summary: Session summary containing MCP stats

    Returns:
        HTML string for the MCP section, or empty string if no MCP calls
    """
    mcp_calls = summary.get("mcp_calls", 0)
    if mcp_calls == 0:
        return ""  # Don't show section if no MCP calls

    mcp_servers = summary.get("mcp_servers", {})
    mcp_errors = summary.get("mcp_errors", 0)
    servers_count = len(mcp_servers)

    # Build server breakdown rows
    server_rows = ""
    for server, count in sorted(mcp_servers.items(), key=lambda x: -x[1]):
        server_rows += f'''
            <div class="mcp-server-item">
                <span class="mcp-server-name">{html.escape(server)}</span>
                <span class="mcp-server-count">{count} calls</span>
            </div>'''

    return f'''
        <div class="mcp-section">
            <h2>MCP Server Activity</h2>
            <div class="mcp-summary-grid">
                <div class="mcp-stat">
                    <div class="mcp-stat-value">{mcp_calls}</div>
                    <div class="mcp-stat-label">MCP Calls</div>
                </div>
                <div class="mcp-stat">
                    <div class="mcp-stat-value">{servers_count}</div>
                    <div class="mcp-stat-label">Servers Used</div>
                </div>
                <div class="mcp-stat">
                    <div class="mcp-stat-value">{mcp_errors}</div>
                    <div class="mcp-stat-label">Errors</div>
                </div>
            </div>
            {f'<div class="mcp-servers-breakdown"><h3>Server Breakdown</h3>{server_rows}</div>' if server_rows else ''}
        </div>
    '''


def _generate_skill_section_html(summary: Dict[str, Any]) -> str:
    """
    Generate HTML for the Agent Skills Activity section.

    Shows Skill-specific statistics including skill breakdown.

    Args:
        summary: Session summary containing Skill stats

    Returns:
        HTML string for the Skill section, or empty string if no Skill calls
    """
    skill_calls = summary.get("skill_calls", 0)
    if skill_calls == 0:
        return ""  # Don't show section if no Skill calls

    skills_used = summary.get("skills_used", {})
    skill_errors = summary.get("skill_errors", 0)
    skills_count = len(skills_used)

    # Build skill breakdown rows
    skill_rows = ""
    for skill, count in sorted(skills_used.items(), key=lambda x: -x[1]):
        # Format skill name (handle namespaced skills like bmad:bmm:workflows:dev-story)
        display_name = skill.split(":")[-1] if ":" in skill else skill
        skill_rows += f'''
            <div class="skill-item">
                <span class="skill-name" title="{html.escape(skill)}">{html.escape(display_name)}</span>
                <span class="skill-count">{count} calls</span>
            </div>'''

    return f'''
        <div class="skill-section">
            <h2>Agent Skills Activity</h2>
            <div class="skill-summary-grid">
                <div class="skill-stat">
                    <div class="skill-stat-value">{skill_calls}</div>
                    <div class="skill-stat-label">Skill Invocations</div>
                </div>
                <div class="skill-stat">
                    <div class="skill-stat-value">{skills_count}</div>
                    <div class="skill-stat-label">Skills Used</div>
                </div>
                <div class="skill-stat">
                    <div class="skill-stat-value">{skill_errors}</div>
                    <div class="skill-stat-label">Errors</div>
                </div>
            </div>
            {f'<div class="skill-breakdown"><h3>Skill Breakdown</h3>{skill_rows}</div>' if skill_rows else ''}
        </div>
    '''


def _generate_activity_metrics_html(activity_metrics: Optional[Dict[str, Any]]) -> str:
    """
    Generate HTML for the Session Activity section.

    Shows estimated token usage based on tool input/output character counts.
    Uses heuristic: ~4 characters per token.

    Args:
        activity_metrics: Dictionary with estimated metrics from session_manager

    Returns:
        HTML string for the activity section, or empty string if no metrics
    """
    if not activity_metrics:
        return ""

    tool_calls = activity_metrics.get("tool_calls", 0)
    if tool_calls == 0:
        return ""  # Don't show section if no tool calls recorded

    # Get estimated values
    input_tokens = activity_metrics.get("estimated_input_tokens", 0)
    output_tokens = activity_metrics.get("estimated_output_tokens", 0)
    total_duration_ms = activity_metrics.get("total_duration_ms", 0)

    # Format token counts with ~ prefix for estimates
    def format_tokens(n: int) -> str:
        if n >= 1_000_000:
            return f"~{n / 1_000_000:.1f}M"
        elif n >= 1_000:
            return f"~{n / 1_000:.1f}K"
        return f"~{n}"

    # Format duration
    def format_duration(ms: int) -> str:
        if ms >= 60_000:
            return f"{ms / 60_000:.1f}m"
        elif ms >= 1_000:
            return f"{ms / 1_000:.1f}s"
        return f"{ms}ms"

    return f'''
        <div class="activity-section">
            <h2>Session Activity <span class="estimate-badge">Estimated</span></h2>
            <p class="activity-disclaimer">Based on tool input/output data. Actual API usage may vary.</p>
            <div class="activity-grid">
                <div class="activity-metric">
                    <div class="activity-value">{tool_calls}</div>
                    <div class="activity-label">Tool Calls</div>
                </div>
                <div class="activity-metric">
                    <div class="activity-value tokens">{format_tokens(input_tokens)}</div>
                    <div class="activity-label">Input Tokens</div>
                </div>
                <div class="activity-metric">
                    <div class="activity-value tokens">{format_tokens(output_tokens)}</div>
                    <div class="activity-label">Output Tokens</div>
                </div>
                <div class="activity-metric">
                    <div class="activity-value">{format_duration(total_duration_ms)}</div>
                    <div class="activity-label">Processing Time</div>
                </div>
            </div>
        </div>
    '''


def _generate_conversation_trace_html(events: list, summary: dict) -> str:
    """
    Generate HTML for the Conversation Trace section.

    Shows user prompts interleaved with tool calls chronologically.
    This provides a complete debugging trace of the session.

    Args:
        events: List of events (includes both user_prompt and event types)
        summary: Session summary with prompt stats

    Returns:
        HTML string for the conversation trace section
    """
    if not events:
        return ""

    # Separate prompts and tools, then merge by timestamp
    all_entries = []

    for event in events:
        event_type = event.get("type")
        timestamp = event.get("timestamp") or event.get("timestamp_start", "")

        if event_type == "user_prompt":
            all_entries.append({
                "type": "prompt",
                "timestamp": timestamp,
                "prompt": event.get("prompt", ""),
                "prompt_length": event.get("prompt_length", 0),
            })
        elif event_type == "event":
            all_entries.append({
                "type": "tool",
                "timestamp": timestamp,
                "tool_name": event.get("tool_name", "Unknown"),
                "verdict": event.get("nova_verdict", "allowed"),
                "is_error": event.get("is_error", False),
                "files_accessed": event.get("files_accessed", []),
                "tool_input": event.get("tool_input"),
                "tool_output": event.get("tool_output", ""),
                # MCP metadata
                "is_mcp": event.get("is_mcp", False),
                "mcp_server": event.get("mcp_server"),
                "mcp_function": event.get("mcp_function"),
                # Skill metadata
                "is_skill": event.get("is_skill", False),
                "skill_name": event.get("skill_name"),
                "skill_args": event.get("skill_args"),
            })

    # Sort by timestamp
    all_entries.sort(key=lambda x: x.get("timestamp", ""))

    if not all_entries:
        return ""

    # Count prompts and tools
    prompt_count = summary.get("user_prompts", 0)
    tool_count = summary.get("total_events", 0)
    mcp_count = summary.get("mcp_calls", 0)
    skill_count = summary.get("skill_calls", 0)

    html_parts = ['<div class="conversation-section">']
    html_parts.append('<h2>Conversation Trace</h2>')

    # Stats bar
    if prompt_count > 0 or tool_count > 0:
        mcp_stat = f'<span>🔌 <strong>{mcp_count}</strong> MCP calls</span>' if mcp_count > 0 else ''
        skill_stat = f'<span>⚡ <strong>{skill_count}</strong> skill calls</span>' if skill_count > 0 else ''
        html_parts.append(f'''
            <div class="conversation-stats">
                <span>👤 <strong>{prompt_count}</strong> prompts</span>
                <span>🔧 <strong>{tool_count}</strong> tool calls</span>
                {mcp_stat}
                {skill_stat}
            </div>
        ''')

    html_parts.append('<div class="conversation-trace">')

    for entry in all_entries:
        timestamp = entry.get("timestamp", "")
        # Format timestamp to HH:MM:SS
        time_str = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                time_str = timestamp[11:19] if len(timestamp) >= 19 else ""

        if entry["type"] == "prompt":
            prompt_text = entry.get("prompt", "")
            prompt_length = entry.get("prompt_length", 0)

            # Truncate long prompts for display
            max_display = 500
            truncated = len(prompt_text) > max_display
            display_text = prompt_text[:max_display] if truncated else prompt_text

            truncation_notice = ""
            if truncated:
                truncation_notice = f'<div class="prompt-truncated">[Showing first {max_display} of {prompt_length} characters]</div>'

            html_parts.append(f'''
                <div class="trace-entry trace-prompt">
                    <span class="trace-time">{html.escape(time_str)}</span>
                    <span class="trace-label">USER</span>
                    <div class="trace-content">
                        <div class="prompt-text">{html.escape(display_text)}</div>
                        {truncation_notice}
                    </div>
                </div>
            ''')

        elif entry["type"] == "tool":
            tool_name = entry.get("tool_name", "Unknown")
            verdict = entry.get("verdict", "allowed")
            is_error = entry.get("is_error", False)
            files = entry.get("files_accessed", [])
            tool_input = entry.get("tool_input")
            tool_output = entry.get("tool_output", "")
            # MCP metadata
            is_mcp = entry.get("is_mcp", False)
            mcp_server = entry.get("mcp_server")
            mcp_function = entry.get("mcp_function")
            # Skill metadata
            is_skill = entry.get("is_skill", False)
            skill_name = entry.get("skill_name")
            skill_args = entry.get("skill_args")

            # Apply error class if this tool call failed
            if is_error:
                verdict_class = "error"
            else:
                # Map "blocked" verdict to "detected" CSS class (passive detection, not active blocking)
                verdict_class = "detected" if verdict == "blocked" else verdict if verdict in ("allowed", "warned") else "allowed"

            # Add MCP/Skill class for styled tools
            if is_mcp:
                entry_class = "trace-mcp"
            elif is_skill:
                entry_class = "trace-skill"
            else:
                entry_class = "trace-tool"
            tool_icon = get_tool_icon(tool_name)

            # Determine label: MCP:server for MCP, SKILL for skills, TOOL/ERROR for others
            if is_error:
                trace_label = "ERROR"
            elif is_mcp and mcp_server:
                trace_label = f"MCP:{mcp_server}"
            elif is_skill:
                trace_label = "SKILL"
            else:
                trace_label = "TOOL"

            # Display name: function for MCP, skill name for skills, full name for others
            if is_mcp and mcp_function:
                display_name = mcp_function
            elif is_skill and skill_name:
                # Show skill name (handle namespaced skills)
                display_name = f"/{skill_name.split(':')[-1]}" if ":" in skill_name else f"/{skill_name}"
            else:
                display_name = tool_name

            # Build tool detail (file path or brief summary)
            detail = ""
            if is_error and tool_output:
                # Show error message
                error_msg = tool_output[:100] if len(tool_output) > 100 else tool_output
                # Clean up the [ERROR] prefix for display
                error_msg = error_msg.replace("[ERROR] ", "").replace("[ERROR]", "")
                detail = f"❌ {error_msg}"
            elif files:
                detail = files[0]
                if len(files) > 1:
                    detail += f" (+{len(files) - 1} more)"
            elif tool_input:
                # Try to extract a brief summary from tool_input
                if isinstance(tool_input, dict):
                    if "file_path" in tool_input:
                        detail = tool_input["file_path"]
                    elif "url" in tool_input:
                        detail = tool_input["url"]
                    elif "command" in tool_input:
                        cmd = tool_input["command"]
                        detail = cmd[:60] + "..." if len(cmd) > 60 else cmd
                    elif "pattern" in tool_input:
                        detail = f"pattern: {tool_input['pattern']}"
                    elif "query" in tool_input:
                        # MCP search tools often use "query"
                        query = tool_input["query"]
                        detail = f"query: {query[:50]}..." if len(query) > 50 else f"query: {query}"

            detail_html = f'<div class="trace-tool-detail">{html.escape(detail)}</div>' if detail else ""

            html_parts.append(f'''
                <div class="trace-entry {entry_class} {verdict_class}">
                    <span class="trace-time">{html.escape(time_str)}</span>
                    <span class="trace-label">{html.escape(trace_label)}</span>
                    <div class="trace-content">
                        <div class="trace-tool-summary">
                            {tool_icon}
                            <span>{html.escape(display_name)}</span>
                        </div>
                        {detail_html}
                    </div>
                </div>
            ''')

    html_parts.append('</div>')  # Close conversation-trace
    html_parts.append('</div>')  # Close conversation-section

    return "".join(html_parts)


def _generate_timeline_html(events: list) -> str:
    """Generate HTML for the visual timeline with clickable nodes."""
    if not events:
        return ""

    # Filter to only tool events for the timeline (not user_prompt)
    tool_events = [e for e in events if e.get("type") == "event"]
    if not tool_events:
        return ""

    html_parts = ['<div class="timeline">']

    for idx, event in enumerate(tool_events):
        tool_name = event.get("tool_name", "Unknown")
        verdict = event.get("nova_verdict", "allowed")
        timestamp = event.get("timestamp_start", "")

        # Format timestamp to HH:MM:SS
        time_str = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                time_str = timestamp[11:19] if len(timestamp) >= 19 else ""

        # Map "blocked" verdict to "detected" CSS class (passive detection, not active blocking)
        verdict_class = "detected" if verdict == "blocked" else verdict if verdict in ("allowed", "warned") else "allowed"
        tool_icon = get_tool_icon(tool_name)

        html_parts.append(f'''
            <div class="timeline-node {verdict_class}" data-event-id="{idx}" onclick="scrollToEvent({idx})">
                <span class="node-icon">{tool_icon}</span>
                <span class="node-time">{html.escape(time_str)}</span>
            </div>''')

    html_parts.append('</div>')
    return "".join(html_parts)


def _format_content_for_display(content: Any, max_size: int = 10000) -> tuple[str, bool]:
    """
    Format content for display with truncation if needed.

    Args:
        content: The content to format (can be string, dict, list, etc.)
        max_size: Maximum size in characters before truncation

    Returns:
        Tuple of (formatted_string, was_truncated)
    """
    if content is None:
        return "", False

    # Convert to string
    if isinstance(content, (dict, list)):
        try:
            content_str = json.dumps(content, indent=2, default=str)
        except Exception:
            content_str = str(content)
    else:
        content_str = str(content)

    # Check if truncation needed
    original_size = len(content_str)
    if original_size > max_size:
        truncated = content_str[:max_size]
        return truncated, True

    return content_str, False


def _generate_events_html(events: list) -> str:
    """Generate HTML for expandable event cards."""
    # Filter to only tool events (not user_prompt)
    tool_events = [e for e in events if e.get("type") == "event"]
    if not tool_events:
        return ""

    html_parts = []

    for idx, event in enumerate(tool_events):
        tool_name = event.get("tool_name", "Unknown")
        verdict = event.get("nova_verdict", "allowed")
        timestamp = event.get("timestamp_start", "")
        files = event.get("files_accessed", [])
        duration_ms = event.get("duration_ms")
        working_dir = event.get("working_dir", "")
        tool_input = event.get("tool_input")
        tool_output = event.get("tool_output")

        # NOVA verdict details
        nova_severity = event.get("nova_severity")
        nova_rules_matched = event.get("nova_rules_matched", [])
        nova_scan_time_ms = event.get("nova_scan_time_ms")

        # MCP metadata
        is_mcp = event.get("is_mcp", False)
        mcp_server = event.get("mcp_server")
        mcp_function = event.get("mcp_function")

        # Skill metadata
        is_skill = event.get("is_skill", False)
        skill_name = event.get("skill_name")
        skill_args = event.get("skill_args")

        # Format timestamp
        time_str = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = dt.strftime("%H:%M:%S")
            except Exception:
                time_str = timestamp[:19] if len(timestamp) >= 19 else timestamp

        # Map "blocked" verdict to "detected" CSS class (passive detection, not active blocking)
        verdict_class = "detected" if verdict == "blocked" else verdict if verdict in ("allowed", "warned") else "allowed"
        # Add MCP/Skill class for styled border
        if is_mcp:
            special_class = "mcp"
        elif is_skill:
            special_class = "skill"
        else:
            special_class = ""

        # Get tool icon
        tool_icon = get_tool_icon(tool_name)

        # Format tool_input with truncation
        input_html = ""
        if tool_input is not None:
            input_str, input_truncated = _format_content_for_display(tool_input)
            truncation_notice = ""
            if input_truncated:
                original_size = len(str(tool_input))
                truncation_notice = f'<div class="truncation-indicator">[truncated - original size: {original_size // 1024} KB]</div>'
            input_html = f'''
                <div class="detail-section">
                    <div class="detail-label">Tool Input</div>
                    <div class="detail-value"><pre>{html.escape(input_str)}</pre></div>
                    {truncation_notice}
                </div>'''

        # Format tool_output with truncation
        output_html = ""
        if tool_output is not None:
            output_str, output_truncated = _format_content_for_display(tool_output)
            truncation_notice = ""
            if output_truncated:
                original_size = len(str(tool_output))
                truncation_notice = f'<div class="truncation-indicator">[truncated - original size: {original_size // 1024} KB]</div>'
            output_html = f'''
                <div class="detail-section">
                    <div class="detail-label">Tool Output</div>
                    <div class="detail-value"><pre>{html.escape(output_str)}</pre></div>
                    {truncation_notice}
                </div>'''

        # Duration and working_dir
        meta_html = ""
        meta_items = []
        if duration_ms is not None:
            meta_items.append(f'<span class="meta-item"><strong>Duration:</strong> {duration_ms}ms</span>')
        if working_dir:
            meta_items.append(f'<span class="meta-item"><strong>Working Dir:</strong> {html.escape(working_dir)}</span>')
        if meta_items:
            meta_html = f'<div class="detail-meta">{" ".join(meta_items)}</div>'

        # Files accessed
        files_html = ""
        if files:
            files_list = "".join(f'<li>{html.escape(f)}</li>' for f in files)
            files_html = f'''
                <div class="detail-section">
                    <div class="detail-label">Files Accessed ({len(files)})</div>
                    <ul class="files-list">{files_list}</ul>
                </div>'''

        # NOVA verdict details (for warned/detected events)
        nova_html = ""
        if verdict in ("warned", "blocked") and (nova_severity or nova_rules_matched or nova_scan_time_ms):
            nova_items = []
            if nova_severity:
                severity_class = nova_severity.lower() if nova_severity.lower() in ("low", "medium", "high", "critical") else ""
                nova_items.append(f'<span class="nova-severity {severity_class}">Severity: {html.escape(str(nova_severity))}</span>')
            if nova_scan_time_ms is not None:
                nova_items.append(f'<span class="nova-scan-time">Scan time: {nova_scan_time_ms}ms</span>')
            rules_html = ""
            if nova_rules_matched:
                if isinstance(nova_rules_matched, list):
                    rules_str = ", ".join(str(r) for r in nova_rules_matched)
                else:
                    rules_str = str(nova_rules_matched)
                rules_html = f'<div class="nova-rules">Rules matched: {html.escape(rules_str)}</div>'

            nova_html = f'''
                <div class="nova-verdict-section">
                    <div class="detail-label">NOVA Analysis</div>
                    <div class="nova-details">
                        {" ".join(nova_items)}
                        {rules_html}
                    </div>
                </div>'''

        # Collapsed files display (for collapsed view)
        files_collapsed = ""
        if files:
            files_collapsed = f'<span class="event-files-collapsed">{html.escape(", ".join(files[:2]))}'
            if len(files) > 2:
                files_collapsed += f" (+{len(files) - 2} more)"
            files_collapsed += "</span>"

        # MCP/Skill badge for special tools
        if is_mcp and mcp_server:
            tool_badge = f'<span class="mcp-badge">MCP:{html.escape(mcp_server)}</span>'
        elif is_skill and skill_name:
            # Show just the short skill name for namespaced skills
            short_name = skill_name.split(":")[-1] if ":" in skill_name else skill_name
            tool_badge = f'<span class="skill-badge">/{html.escape(short_name)}</span>'
        else:
            tool_badge = ''

        html_parts.append(f'''
            <div class="event-card {verdict_class} {special_class}" id="event-{idx}">
                <div class="event-header" onclick="toggleEvent({idx})">
                    <span class="event-id">#{idx}</span>
                    <span class="event-tool">{tool_icon}{html.escape(tool_name)}{tool_badge}</span>
                    <span class="event-verdict {verdict_class}">{verdict.upper()}</span>
                    <span class="event-time">{html.escape(time_str)}</span>
                    <span class="expand-icon">▼</span>
                </div>
                <div class="event-details" id="details-{idx}" style="display: none;">
                    {nova_html}
                    {meta_html}
                    {input_html}
                    {output_html}
                    {files_html}
                </div>
            </div>
        ''')

    return "".join(html_parts)


def _generate_error_report(error: str) -> str:
    """Generate a minimal error report when generation fails."""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Nova-tracer Report - Error</title>
    <style>
        body {{ font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; }}
        .error {{ background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; padding: 1rem; border-radius: 8px; }}
    </style>
</head>
<body>
    <h1>Nova-tracer Report</h1>
    <div class="error">
        <h2>Report Generation Error</h2>
        <p>An error occurred while generating the report:</p>
        <pre>{html.escape(error)}</pre>
    </div>
</body>
</html>'''


def save_report(html_content: str, report_path: Path) -> bool:
    """
    Save HTML report to file.

    Args:
        html_content: The HTML string to save
        report_path: Path where to save the report

    Returns:
        True on success, False on failure
    """
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(html_content, encoding="utf-8")
        return True
    except Exception as e:
        logger.warning(f"Failed to save report: {e}")
        return False
