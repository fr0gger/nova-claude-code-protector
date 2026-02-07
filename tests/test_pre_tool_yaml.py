"""
Tests for Pre-Tool YAML Configuration (pre-tool-yaml branch).

Tests the YAML-based configuration approach that uses nova-config.yaml
with support for enabled/disabled rules.
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest.mock import patch

import pytest


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def hook_path():
    """Path to the pre-tool hook."""
    return Path(__file__).parent.parent / "hooks" / "pre-tool-guard.py"


@pytest.fixture
def config_path():
    """Path to nova-config.yaml."""
    return Path(__file__).parent.parent / "config" / "nova-config.yaml"


@pytest.fixture
def backup_config(config_path):
    """Backup and restore config file around tests."""
    backup = config_path.with_suffix(".yaml.bak")
    original_content = None

    if config_path.exists():
        original_content = config_path.read_text()

    yield config_path

    # Restore original
    if original_content is not None:
        config_path.write_text(original_content)
    elif backup.exists():
        backup.rename(config_path)


# ============================================================================
# Structure Tests
# ============================================================================


class TestHookStructure:
    """Tests for hook file structure."""

    def test_hook_file_exists(self, hook_path):
        """Hook file should exist."""
        assert hook_path.exists()

    def test_hook_requires_pyyaml(self, hook_path):
        """Hook should declare pyyaml dependency."""
        content = hook_path.read_text()
        assert "pyyaml" in content.lower()
        assert 'dependencies = ["pyyaml"]' in content or "dependencies = ['pyyaml']" in content


# ============================================================================
# Configuration Tests
# ============================================================================


class TestConfigLoading:
    """Tests for YAML config loading."""

    def test_loads_nova_config(self, hook_path, backup_config):
        """Config is loaded from nova-config.yaml."""
        # Write test config
        backup_config.write_text("""
dangerous_patterns:
  - pattern: '\\btest_pattern\\b'
    reason: "Test pattern loaded"
    enabled: true
protected_files: []
dangerous_content_patterns: []
""")

        # Reload module to pick up config
        spec = spec_from_file_location("pre_tool_guard", hook_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check pattern was loaded
        reasons = [r for _, r in module.DANGEROUS_PATTERNS]
        assert "Test pattern loaded" in reasons

    def test_enabled_false_excludes_pattern(self, hook_path, backup_config):
        """Patterns with enabled=false are excluded."""
        backup_config.write_text("""
dangerous_patterns:
  - pattern: '\\bdisabled_pattern\\b'
    reason: "This should not be loaded"
    enabled: false
  - pattern: '\\benabled_pattern\\b'
    reason: "This should be loaded"
    enabled: true
protected_files: []
dangerous_content_patterns: []
""")

        # Reload module
        spec = spec_from_file_location("pre_tool_guard", hook_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        reasons = [r for _, r in module.DANGEROUS_PATTERNS]
        assert "This should not be loaded" not in reasons
        assert "This should be loaded" in reasons

    def test_default_enabled_true(self, hook_path, backup_config):
        """Patterns without enabled field default to enabled=true."""
        backup_config.write_text("""
dangerous_patterns:
  - pattern: '\\bno_enabled_field\\b'
    reason: "Pattern without enabled field"
protected_files: []
dangerous_content_patterns: []
""")

        # Reload module
        spec = spec_from_file_location("pre_tool_guard", hook_path)
        module = module_from_spec(spec)
        spec.loader.exec_module(module)

        reasons = [r for _, r in module.DANGEROUS_PATTERNS]
        assert "Pattern without enabled field" in reasons


# ============================================================================
# Integration Tests
# ============================================================================


class TestBlocking:
    """Integration tests for blocking behavior."""

    def test_blocks_dangerous_command(self, hook_path):
        """Default dangerous commands are blocked."""
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /"},
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2  # Blocked
        output = json.loads(result.stdout)
        assert output["decision"] == "block"

    def test_allows_safe_command(self, hook_path):
        """Safe commands are allowed."""
        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"},
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0  # Allowed

    def test_blocks_protected_file(self, hook_path):
        """Protected files are blocked."""
        hook_input = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/home/user/.claude/settings.json",
                "content": "test",
            },
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2  # Blocked

    def test_custom_pattern_blocks_when_enabled(self, hook_path, backup_config):
        """Custom patterns from config block commands when enabled."""
        backup_config.write_text("""
dangerous_patterns:
  - pattern: '\\bcustom_dangerous\\b'
    reason: "Custom pattern blocking"
    enabled: true
protected_files: []
dangerous_content_patterns: []
""")

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "run custom_dangerous command"},
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2  # Blocked
        output = json.loads(result.stdout)
        assert "Custom pattern blocking" in output["reason"]

    def test_custom_pattern_allows_when_disabled(self, hook_path, backup_config):
        """Custom patterns from config allow commands when disabled."""
        backup_config.write_text("""
dangerous_patterns:
  - pattern: '\\bcustom_disabled\\b'
    reason: "This is disabled"
    enabled: false
protected_files: []
dangerous_content_patterns: []
""")

        hook_input = {
            "tool_name": "Bash",
            "tool_input": {"command": "run custom_disabled command"},
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0  # Allowed


# ============================================================================
# Protected Files Tests
# ============================================================================


class TestProtectedFiles:
    """Tests for protected files from config."""

    def test_custom_protected_file_blocks_when_enabled(self, hook_path, backup_config):
        """Custom protected files block when enabled."""
        backup_config.write_text("""
dangerous_patterns: []
protected_files:
  - pattern: '(^|/)\\.env$'
    reason: "Environment file protected"
    enabled: true
dangerous_content_patterns: []
""")

        hook_input = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/app/.env",
                "content": "SECRET=test",
            },
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 2  # Blocked
        output = json.loads(result.stdout)
        assert "Environment file protected" in output["reason"]

    def test_custom_protected_file_allows_when_disabled(self, hook_path, backup_config):
        """Custom protected files allow when disabled."""
        backup_config.write_text("""
dangerous_patterns: []
protected_files:
  - pattern: '(^|/)\\.env$'
    reason: "Environment file protected"
    enabled: false
dangerous_content_patterns: []
""")

        hook_input = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "/app/.env",
                "content": "PUBLIC=test",
            },
        }

        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input=json.dumps(hook_input),
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0  # Allowed


# ============================================================================
# Fail-Open Tests
# ============================================================================


class TestFailOpen:
    """Tests for fail-open behavior."""

    def test_invalid_input_fails_open(self, hook_path):
        """Invalid JSON input allows operation (fail-open)."""
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            input="not valid json",
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0  # Allowed

    def test_missing_config_uses_defaults(self, hook_path, config_path):
        """Missing config file uses default patterns."""
        # Temporarily rename config
        backup = config_path.with_suffix(".yaml.bak")
        config_path.rename(backup)

        try:
            hook_input = {
                "tool_name": "Bash",
                "tool_input": {"command": "rm -rf /"},
            }

            result = subprocess.run(
                [sys.executable, str(hook_path)],
                input=json.dumps(hook_input),
                capture_output=True,
                text=True,
            )

            # Should still block - defaults are hardcoded
            assert result.returncode == 2
        finally:
            backup.rename(config_path)
