# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml"]
# ///
"""
Nova-tracer - PreToolUse Hook (Fast Blocking)
Agent Monitoring and Visibility
=============================================================

Fast pre-execution check that blocks dangerous commands BEFORE execution.
Uses simple pattern matching for speed - full NOVA scanning happens in PostToolUse.

Supports configurable compliance rules via nova-config.yaml.
Config location: {nova_dir}/config/nova-config.yaml

Configurable sections in nova-config.yaml:
  - dangerous_patterns: Additional bash command patterns to block
  - protected_files: Additional file paths to protect
  - dangerous_content_patterns: Additional content patterns to block

Each pattern supports an optional 'enabled' field (default: true).

Exit codes:
  0 = Allow tool execution
  2 = Block tool execution (dangerous command detected)

JSON output for blocks:
  {"decision": "block", "reason": "[Nova-tracer] Blocked: {reason}"}
"""

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


def load_config() -> Dict[str, Any]:
    """Load the nova-config.yaml configuration file.

    Returns an empty dict if the config cannot be loaded.
    """
    # Determine config path relative to this script
    script_dir = Path(__file__).parent.resolve()
    config_path = script_dir.parent / "config" / "nova-config.yaml"

    if not config_path.exists():
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        # Fail-open: if config is invalid, use defaults only
        return {}


def extend_patterns_from_config(
    base_patterns: List[Tuple[str, str]],
    config_key: str,
    config: Dict[str, Any]
) -> List[Tuple[str, str]]:
    """Extend a base pattern list with patterns from config.

    Config patterns should be a list of dicts with 'pattern', 'reason', and optional 'enabled' keys.
    Patterns with enabled=false are skipped.
    """
    extended = list(base_patterns)
    config_patterns = config.get(config_key, [])

    if not config_patterns:
        return extended

    for item in config_patterns:
        if isinstance(item, dict) and "pattern" in item and "reason" in item:
            # Skip disabled rules (default is enabled=true)
            if not item.get("enabled", True):
                continue
            extended.append((item["pattern"], item["reason"]))

    return extended


# Protected file paths - these should not be modified by the agent
PROTECTED_FILES: List[Tuple[str, str]] = [
    (r'(^|/)\.claude/settings\.json$', "Claude settings file"),
]

# Default dangerous command patterns to block (security baseline)
DEFAULT_BASH_PATTERNS: List[Tuple[str, str]] = [
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

    # Block skills management commands
    (r'\bnpx\s+skills\s+add', "Skills add command blocked"),
    (r'\bnpx\s+skills\s+find', "Skills find command blocked"),
]

# Default write content patterns to block (security baseline)
# Note: These patterns target actual malicious payloads, not legitimate code.
# innerHTML, document.write are valid JS APIs - we only block suspicious combinations.
DEFAULT_CONTENT_PATTERNS: List[Tuple[str, str]] = [
    # XSS: Block eval with user-controlled input patterns
    (r'eval\s*\(\s*(location|document\.URL|document\.cookie|window\.name)', "XSS eval injection"),
    # XSS: Block document.write with script injection
    (r'document\.write\s*\([^)]*<script', "XSS document.write injection"),
    # SQL injection patterns
    (r";\s*DROP\s+TABLE", "SQL injection attempt"),
    (r"UNION\s+SELECT.*FROM", "SQL injection attempt"),
    (r"'\s*OR\s+'1'\s*=\s*'1", "SQL injection attempt"),
]

# Load config and extend patterns with custom values from nova-config.yaml
_config = load_config()
PROTECTED_FILES = extend_patterns_from_config(PROTECTED_FILES, "protected_files", _config)
DANGEROUS_PATTERNS = extend_patterns_from_config(DEFAULT_BASH_PATTERNS, "dangerous_patterns", _config)
DANGEROUS_CONTENT_PATTERNS = extend_patterns_from_config(
    DEFAULT_CONTENT_PATTERNS, "dangerous_content_patterns", _config
)


def check_protected_file(file_path: str) -> Optional[str]:
    """Check if a file path is protected from modification.

    Returns the reason if protected, None if allowed.
    """
    if not file_path:
        return None

    for pattern, reason in PROTECTED_FILES:
        if re.search(pattern, file_path):
            return reason

    return None


def check_dangerous_command(command: str) -> Optional[str]:
    """Check if a bash command is dangerous.

    Returns the reason if dangerous, None if safe.
    """
    if not command:
        return None

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

    # Check Write content and protected files
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        block_reason = check_protected_file(file_path)
        if not block_reason:
            content = tool_input.get("content", "")
            block_reason = check_dangerous_content(content)

    # Check Edit content and protected files
    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        block_reason = check_protected_file(file_path)
        if not block_reason:
            new_string = tool_input.get("new_string", "")
            block_reason = check_dangerous_content(new_string)

    if block_reason:
        # Block the operation
        output = {
            "decision": "block",
            "reason": f"[Nova-tracer] Blocked: {block_reason}"
        }
        print(json.dumps(output))
        # Note: Telemetry logging disabled for performance - each hook is a new process
        # and log_event() re-parses config + discovers plugins on every call
        sys.exit(2)

    # Allow the operation
    sys.exit(0)

if __name__ == "__main__":
    main()
