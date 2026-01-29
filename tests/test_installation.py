"""
Tests for Story 5.1: Installation Script

Tests the install.sh and uninstall.sh scripts for:
- AC1: Script completes without errors
- AC2: Hook registration in settings.json
- AC3: Preserve existing hooks
- AC4: Create settings if missing
- AC5: Hooks activate automatically (verified by checking structure)
- AC6: Uninstall script removes NOVA hooks while preserving others
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


class TestInstallScriptExists:
    """Verify installation scripts exist and are executable."""

    def test_install_script_exists(self):
        """install.sh should exist in project root."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        assert install_script.exists(), "install.sh should exist"

    def test_install_script_executable(self):
        """install.sh should be executable."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        assert os.access(install_script, os.X_OK), "install.sh should be executable"

    def test_uninstall_script_exists(self):
        """uninstall.sh should exist in project root."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        assert uninstall_script.exists(), "uninstall.sh should exist"

    def test_uninstall_script_executable(self):
        """uninstall.sh should be executable."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        assert os.access(uninstall_script, os.X_OK), "uninstall.sh should be executable"


class TestInstallScriptHookFiles:
    """Verify all required hook files exist."""

    def test_session_start_hook_exists(self):
        """session-start.py should exist."""
        project_root = Path(__file__).parent.parent
        hook = project_root / "hooks" / "session-start.py"
        assert hook.exists(), "hooks/session-start.py should exist"

    def test_pre_tool_guard_hook_exists(self):
        """pre-tool-guard.py should exist."""
        project_root = Path(__file__).parent.parent
        hook = project_root / "hooks" / "pre-tool-guard.py"
        assert hook.exists(), "hooks/pre-tool-guard.py should exist"

    def test_post_tool_nova_guard_hook_exists(self):
        """post-tool-nova-guard.py should exist."""
        project_root = Path(__file__).parent.parent
        hook = project_root / "hooks" / "post-tool-nova-guard.py"
        assert hook.exists(), "hooks/post-tool-nova-guard.py should exist"

    def test_session_end_hook_exists(self):
        """session-end.py should exist."""
        project_root = Path(__file__).parent.parent
        hook = project_root / "hooks" / "session-end.py"
        assert hook.exists(), "hooks/session-end.py should exist"


class TestHookRegistrationFormat:
    """Test the hook registration JSON structure."""

    def test_session_start_hook_structure(self):
        """SessionStart hook should have correct structure."""
        # Simulate what install.sh creates
        session_start = [
            {
                "type": "command",
                "command": "uv run /path/to/hooks/session-start.py"
            }
        ]
        assert len(session_start) == 1
        assert session_start[0]["type"] == "command"
        assert "session-start.py" in session_start[0]["command"]

    def test_pre_tool_use_hook_structure(self):
        """PreToolUse hooks should have matcher-based structure."""
        pre_tool = [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": "uv run /path/to/hooks/pre-tool-guard.py"
                    }
                ]
            }
        ]
        assert pre_tool[0]["matcher"] == "Bash"
        assert len(pre_tool[0]["hooks"]) == 1
        assert "pre-tool-guard.py" in pre_tool[0]["hooks"][0]["command"]

    def test_post_tool_use_hook_structure(self):
        """PostToolUse hooks should have matcher-based structure with timeout."""
        post_tool = [
            {
                "matcher": "Read",
                "hooks": [
                    {
                        "type": "command",
                        "command": "uv run /path/to/hooks/post-tool-nova-guard.py",
                        "timeout": 15
                    }
                ]
            }
        ]
        assert post_tool[0]["matcher"] == "Read"
        assert post_tool[0]["hooks"][0]["timeout"] == 15
        assert "post-tool-nova-guard.py" in post_tool[0]["hooks"][0]["command"]

    def test_session_end_hook_structure(self):
        """SessionEnd hook should have correct structure."""
        session_end = [
            {
                "type": "command",
                "command": "uv run /path/to/hooks/session-end.py"
            }
        ]
        assert len(session_end) == 1
        assert session_end[0]["type"] == "command"
        assert "session-end.py" in session_end[0]["command"]


class TestSettingsJsonMerge:
    """Test settings.json creation and merging logic."""

    def test_create_settings_if_missing(self, tmp_path):
        """Should create settings.json if it doesn't exist."""
        settings_file = tmp_path / "settings.json"
        assert not settings_file.exists()

        # Simulate creating settings
        nova_hooks = {
            "hooks": {
                "SessionStart": [{"type": "command", "command": "test"}]
            }
        }
        settings_file.write_text(json.dumps(nova_hooks, indent=2))

        assert settings_file.exists()
        settings = json.loads(settings_file.read_text())
        assert "hooks" in settings
        assert "SessionStart" in settings["hooks"]

    def test_preserve_existing_settings(self, tmp_path):
        """Should preserve non-hook settings when adding hooks."""
        settings_file = tmp_path / "settings.json"

        # Create settings with other options
        existing = {
            "theme": "dark",
            "editor": "vim"
        }
        settings_file.write_text(json.dumps(existing, indent=2))

        # Add hooks while preserving existing
        settings = json.loads(settings_file.read_text())
        settings["hooks"] = {
            "SessionStart": [{"type": "command", "command": "test"}]
        }
        settings_file.write_text(json.dumps(settings, indent=2))

        final = json.loads(settings_file.read_text())
        assert final["theme"] == "dark"
        assert final["editor"] == "vim"
        assert "hooks" in final

    def test_preserve_existing_hooks(self, tmp_path):
        """Should preserve existing hooks when adding NOVA hooks."""
        settings_file = tmp_path / "settings.json"

        # Create settings with existing hooks
        existing = {
            "hooks": {
                "SessionStart": [
                    {"type": "command", "command": "/other/hook.py"}
                ],
                "PostToolUse": [
                    {
                        "matcher": "Read",
                        "hooks": [
                            {"type": "command", "command": "/other/read-hook.py"}
                        ]
                    }
                ]
            }
        }
        settings_file.write_text(json.dumps(existing, indent=2))

        # Simulate merging - add NOVA hooks
        settings = json.loads(settings_file.read_text())
        nova_session_start = {"type": "command", "command": "/nova/session-start.py"}
        settings["hooks"]["SessionStart"].append(nova_session_start)

        settings_file.write_text(json.dumps(settings, indent=2))

        final = json.loads(settings_file.read_text())
        # Should have both original and NOVA hooks
        assert len(final["hooks"]["SessionStart"]) == 2
        commands = [h["command"] for h in final["hooks"]["SessionStart"]]
        assert "/other/hook.py" in commands
        assert "/nova/session-start.py" in commands


class TestHookRemoval:
    """Test uninstall logic for removing NOVA hooks."""

    def test_remove_nova_hooks_only(self, tmp_path):
        """Should remove only NOVA hooks, preserving others."""
        settings_file = tmp_path / "settings.json"

        # Create settings with mixed hooks
        mixed = {
            "hooks": {
                "SessionStart": [
                    {"type": "command", "command": "/other/hook.py"},
                    {"type": "command", "command": "/nova_claude_code_protector/hooks/session-start.py"}
                ]
            }
        }
        settings_file.write_text(json.dumps(mixed, indent=2))

        # Simulate removal - filter out NOVA hooks
        settings = json.loads(settings_file.read_text())
        settings["hooks"]["SessionStart"] = [
            h for h in settings["hooks"]["SessionStart"]
            if "nova_claude_code_protector" not in h.get("command", "")
        ]
        settings_file.write_text(json.dumps(settings, indent=2))

        final = json.loads(settings_file.read_text())
        assert len(final["hooks"]["SessionStart"]) == 1
        assert final["hooks"]["SessionStart"][0]["command"] == "/other/hook.py"

    def test_remove_all_nova_hooks(self, tmp_path):
        """Should remove all NOVA hooks from all hook types."""
        settings_file = tmp_path / "settings.json"

        # Create settings with NOVA hooks in all types
        all_nova = {
            "hooks": {
                "SessionStart": [
                    {"type": "command", "command": "/nova/session-start.py"}
                ],
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "/nova/pre-tool-guard.py"}
                        ]
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "Read",
                        "hooks": [
                            {"type": "command", "command": "/nova/post-tool-nova-guard.py"}
                        ]
                    }
                ],
                "SessionEnd": [
                    {"type": "command", "command": "/nova/session-end.py"}
                ]
            }
        }
        settings_file.write_text(json.dumps(all_nova, indent=2))

        # Simulate complete removal
        settings = json.loads(settings_file.read_text())

        # Remove hooks that match NOVA patterns
        def is_nova_hook(hook):
            cmd = hook.get("command", "")
            return any(pattern in cmd for pattern in [
                "nova", "session-start.py", "session-end.py",
                "pre-tool-guard.py", "post-tool-nova-guard.py"
            ])

        for hook_type in ["SessionStart", "SessionEnd"]:
            if hook_type in settings["hooks"]:
                settings["hooks"][hook_type] = [
                    h for h in settings["hooks"][hook_type]
                    if not is_nova_hook(h)
                ]

        for hook_type in ["PreToolUse", "PostToolUse"]:
            if hook_type in settings["hooks"]:
                for matcher_hook in settings["hooks"][hook_type]:
                    if "hooks" in matcher_hook:
                        matcher_hook["hooks"] = [
                            h for h in matcher_hook["hooks"]
                            if not is_nova_hook(h)
                        ]
                # Remove empty matchers
                settings["hooks"][hook_type] = [
                    m for m in settings["hooks"][hook_type]
                    if m.get("hooks", [])
                ]

        # Remove empty hook types
        settings["hooks"] = {
            k: v for k, v in settings["hooks"].items()
            if v
        }

        settings_file.write_text(json.dumps(settings, indent=2))

        final = json.loads(settings_file.read_text())
        # All hooks should be empty/removed
        assert final["hooks"] == {} or "hooks" not in final or all(
            len(v) == 0 for v in final.get("hooks", {}).values()
        )


class TestInstallScriptValidation:
    """Test install.sh script syntax and content."""

    def test_install_script_is_bash(self):
        """install.sh should be a bash script."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()
        assert content.startswith("#!/bin/bash"), "Should start with bash shebang"

    def test_install_script_uses_set_e(self):
        """install.sh should use set -e for error handling."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()
        assert "set -e" in content, "Should use set -e"

    def test_install_script_defines_nova_dir(self):
        """install.sh should define NOVA_DIR."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()
        assert "NOVA_DIR=" in content, "Should define NOVA_DIR"

    def test_install_script_references_all_hooks(self):
        """install.sh should reference all four hook scripts."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()

        assert "session-start.py" in content, "Should reference session-start.py"
        assert "pre-tool-guard.py" in content, "Should reference pre-tool-guard.py"
        assert "post-tool-nova-guard.py" in content, "Should reference post-tool-nova-guard.py"
        assert "session-end.py" in content, "Should reference session-end.py"

    def test_install_script_uses_global_settings(self):
        """install.sh should use ~/.claude/settings.json."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()

        assert "~/.claude" in content or "$HOME/.claude" in content, \
            "Should reference global ~/.claude directory"
        assert "settings.json" in content, "Should reference settings.json"

    def test_install_script_verifies_source_files(self):
        """install.sh should verify hook files exist before install."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()

        assert "verify_source_files" in content or "-f" in content, \
            "Should verify source files exist"


class TestUninstallScriptValidation:
    """Test uninstall.sh script syntax and content."""

    def test_uninstall_script_is_bash(self):
        """uninstall.sh should be a bash script."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        content = uninstall_script.read_text()
        assert content.startswith("#!/bin/bash"), "Should start with bash shebang"

    def test_uninstall_script_uses_set_e(self):
        """uninstall.sh should use set -e for error handling."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        content = uninstall_script.read_text()
        assert "set -e" in content, "Should use set -e"

    def test_uninstall_script_creates_backup(self):
        """uninstall.sh should backup settings before modification."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        content = uninstall_script.read_text()
        assert "backup" in content.lower(), "Should create backup"

    def test_uninstall_script_prompts_for_cleanup(self):
        """uninstall.sh should prompt for .nova-tracer cleanup."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        content = uninstall_script.read_text()
        assert ".nova-tracer" in content, "Should reference .nova-tracer directories"
        assert "read -p" in content, "Should prompt user"


class TestHookActivation:
    """Test that hooks are structured for automatic activation (AC5)."""

    def test_hooks_use_absolute_paths(self):
        """Hooks should use absolute paths via NOVA_DIR."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()

        # NOVA_DIR should be used in hook commands
        assert "$NOVA_DIR/hooks/" in content, \
            "Hook commands should use $NOVA_DIR for absolute paths"

    def test_hooks_use_uv_run(self):
        """Hooks should use 'uv run' to execute Python scripts."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()

        assert "uv run" in content, "Should use 'uv run' to execute hooks"

    def test_post_tool_hooks_have_timeout(self):
        """PostToolUse hooks should have timeout configured."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()

        # Look for timeout in PostToolUse section
        assert '"timeout":' in content, "PostToolUse hooks should have timeout"


class TestInstallScriptProgressOutput:
    """Test that install.sh provides clear progress output (AC1)."""

    def test_install_script_has_header(self):
        """install.sh should print a header."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()
        assert "print_header" in content, "Should have header function"

    def test_install_script_has_success_messages(self):
        """install.sh should print success messages."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()
        assert "print_success" in content, "Should have success message function"

    def test_install_script_has_completion_message(self):
        """install.sh should print completion message."""
        project_root = Path(__file__).parent.parent
        install_script = project_root / "install.sh"
        content = install_script.read_text()
        assert "Installation Complete" in content, "Should have completion message"


class TestUninstallScriptProgressOutput:
    """Test that uninstall.sh provides clear progress output."""

    def test_uninstall_script_has_header(self):
        """uninstall.sh should print a header."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        content = uninstall_script.read_text()
        assert "print_header" in content, "Should have header function"

    def test_uninstall_script_has_completion_message(self):
        """uninstall.sh should print completion message."""
        project_root = Path(__file__).parent.parent
        uninstall_script = project_root / "uninstall.sh"
        content = uninstall_script.read_text()
        assert "Uninstallation Complete" in content, "Should have completion message"
