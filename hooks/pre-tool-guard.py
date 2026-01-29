# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
Claude Code NOVA Protector - PreToolUse Hook (Fast Blocking)
=============================================================

Fast pre-execution check that blocks dangerous commands BEFORE execution.
Uses simple pattern matching for speed - full NOVA scanning happens in PostToolUse.

Exit codes:
  0 = Allow tool execution
  2 = Block tool execution (dangerous command detected)

JSON output for blocks:
  {"decision": "block", "reason": "[NOVA] Blocked: {reason}"}
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

lib_dir = Path(__file__).parent / "lib"
sys.path.insert(0, str(lib_dir))

from nova_logging import log_event

# Dangerous command patterns to block
DANGEROUS_PATTERNS: List[Tuple[str, str]] = [
    # Destructive file operations
    (r'\brm\s+(-[rf]+\s+)*(/|~|\$HOME|\$PAI_DIR|/\*)', "Destructive rm command"),
    (r'\brm\s+-rf\s+/', "rm -rf on root"),
    (r'\bsudo\s+rm\s+-rf', "sudo rm -rf"),

    # Disk operations
    (r'\bmkfs\b', "Filesystem format command"),
    (r'\bdd\s+if=.+of=/dev/', "Direct disk write"),
    (r'\bdiskutil\s+(erase|partition|zero)', "Disk utility erase"),

    # Fork bombs and system abuse
    (r':\(\)\s*\{\s*:\|:\s*&\s*\}', "Fork bomb"),
    (r'\bfork\s*bomb', "Fork bomb reference"),

    # Credential/key exfiltration
    (r'curl.+\|\s*sh', "Pipe curl to shell"),
    (r'wget.+\|\s*sh', "Pipe wget to shell"),
    (r'cat\s+.*(id_rsa|\.pem|\.key|password|credentials)', "Reading sensitive files"),

    # Dangerous redirects
    (r'>\s*/dev/sd[a-z]', "Redirect to disk device"),
    (r'>\s*/dev/null\s*2>&1\s*&', "Background with hidden output"),
]

# Write content patterns to block
# Note: These patterns target actual malicious payloads, not legitimate code.
# innerHTML, document.write are valid JS APIs - we only block suspicious combinations.
DANGEROUS_CONTENT_PATTERNS: List[Tuple[str, str]] = [
    # XSS: Block eval with user-controlled input patterns
    (r'eval\s*\(\s*(location|document\.URL|document\.cookie|window\.name)', "XSS eval injection"),
    # XSS: Block document.write with script injection
    (r'document\.write\s*\([^)]*<script', "XSS document.write injection"),
    # SQL injection patterns
    (r";\s*DROP\s+TABLE", "SQL injection attempt"),
    (r"UNION\s+SELECT.*FROM", "SQL injection attempt"),
    (r"'\s*OR\s+'1'\s*=\s*'1", "SQL injection attempt"),
]


def check_dangerous_command(command: str) -> Optional[str]:
    """Check if a bash command is dangerous.

    Returns the reason if dangerous, None if safe.
    """
    if not command:
        return None

    command_lower = command.lower()

    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return reason

    return None


def check_dangerous_content(content: str) -> Optional[str]:
    """Check if write content contains dangerous patterns.

    Returns the reason if dangerous, None if safe.
    """
    if not content:
        return None

    for pattern, reason in DANGEROUS_CONTENT_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
            return reason

    return None


def main() -> None:
    """Main entry point for the PreToolUse hook."""
    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        # Invalid input, fail open (allow)
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    block_reason = None

    # Check Bash commands
    if tool_name == "Bash":
        command = tool_input.get("command", "")
        block_reason = check_dangerous_command(command)

    # Check Write content
    elif tool_name == "Write":
        content = tool_input.get("content", "")
        block_reason = check_dangerous_content(content)

    # Check Edit content
    elif tool_name == "Edit":
        new_string = tool_input.get("new_string", "")
        block_reason = check_dangerous_content(new_string)

    if block_reason:
        # Block the operation
        output = {
            "decision": "block",
            "reason": f"[NOVA] Blocked: {block_reason}"
        }
        print(json.dumps(output))
        input_data["execution"] = {
            "verdict": "block",
            "reason": f"[NOVA] Blocked: {block_reason}"
        }
        log_event(input_data, "Tool blocked")
        sys.exit(2)

    input_data["execution"] = {
        "verdict": "allow",
        "reason": f"[NOVA] Allowed"
    }
    log_event(input_data, "Tool allowed")
    # Allow the operation
    sys.exit(0)

if __name__ == "__main__":
    main()
