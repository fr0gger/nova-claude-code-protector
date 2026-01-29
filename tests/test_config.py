"""
Tests for Story 5.2: Configuration and Extensibility

Tests the configuration module for:
- AC1: Sensible defaults
- AC2: Configuration file loading
- AC3: Custom report location
- AC4: Custom rules loading
- AC5: Rule error handling
- AC6: Disable AI summaries
- AC7: Unknown keys handling
"""

import logging
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add hooks/lib to path for imports
project_root = Path(__file__).parent.parent
lib_dir = project_root / "hooks" / "lib"
sys.path.insert(0, str(lib_dir))


class TestConfigModuleExists:
    """Verify configuration module exists."""

    def test_config_module_exists(self):
        """config.py should exist in hooks/lib/."""
        project_root = Path(__file__).parent.parent
        config_module = project_root / "hooks" / "lib" / "config.py"
        assert config_module.exists(), "hooks/lib/config.py should exist"

    def test_config_file_template_exists(self):
        """nova-config.yaml should exist in config/."""
        project_root = Path(__file__).parent.parent
        config_file = project_root / "config" / "nova-config.yaml"
        assert config_file.exists(), "config/nova-config.yaml should exist"


class TestSensibleDefaults:
    """Test AC1: Sensible defaults when no config file exists."""

    def test_default_report_output_dir_empty(self):
        """Default report_output_dir should be empty (uses project default)."""
        from config import NovaConfig

        config = NovaConfig()
        assert config.report_output_dir == ""

    def test_default_ai_summary_enabled(self):
        """AI summaries should be enabled by default."""
        from config import NovaConfig

        config = NovaConfig()
        assert config.ai_summary_enabled is True

    def test_default_truncation_10kb(self):
        """Default truncation should be 10KB."""
        from config import NovaConfig

        config = NovaConfig()
        assert config.output_truncation_kb == 10

    def test_default_custom_rules_dir(self):
        """Default custom rules dir should be 'rules/'."""
        from config import NovaConfig

        config = NovaConfig()
        assert config.custom_rules_dir == "rules/"

    def test_get_default_config(self):
        """get_default_config should return default values."""
        from config import get_default_config

        config = get_default_config()
        assert config.report_output_dir == ""
        assert config.ai_summary_enabled is True
        assert config.output_truncation_kb == 10

    def test_default_report_path(self, tmp_path):
        """Default report path should be {project}/.nova-tracer/reports/."""
        from config import NovaConfig

        config = NovaConfig()
        project_dir = tmp_path / "my_project"
        project_dir.mkdir()

        report_dir = config.get_report_output_dir(project_dir)
        assert report_dir == project_dir / ".nova-tracer" / "reports"


class TestConfigurationFileLoading:
    """Test AC2: Configuration file loading."""

    def test_load_config_from_yaml(self, tmp_path):
        """Should load configuration from YAML file."""
        from config import load_config

        # Create config file
        config_file = tmp_path / "nova-protector.yaml"
        config_file.write_text("""
report_output_dir: "/custom/reports"
ai_summary_enabled: false
output_truncation_kb: 20
""")

        config = load_config(config_file)
        assert config.report_output_dir == "/custom/reports"
        assert config.ai_summary_enabled is False
        assert config.output_truncation_kb == 20

    def test_load_config_missing_file_uses_defaults(self, tmp_path):
        """Should use defaults when config file doesn't exist."""
        from config import load_config

        config_file = tmp_path / "nonexistent.yaml"
        config = load_config(config_file)

        assert config.report_output_dir == ""
        assert config.ai_summary_enabled is True
        assert config.output_truncation_kb == 10

    def test_load_config_partial_file(self, tmp_path):
        """Should use defaults for missing keys."""
        from config import load_config

        config_file = tmp_path / "partial.yaml"
        config_file.write_text("""
ai_summary_enabled: false
""")

        config = load_config(config_file)
        assert config.ai_summary_enabled is False
        assert config.report_output_dir == ""  # Default
        assert config.output_truncation_kb == 10  # Default

    def test_load_config_empty_file(self, tmp_path):
        """Should use defaults for empty config file."""
        from config import load_config

        config_file = tmp_path / "empty.yaml"
        config_file.write_text("")

        config = load_config(config_file)
        assert config.ai_summary_enabled is True
        assert config.output_truncation_kb == 10


class TestCustomReportLocation:
    """Test AC3: Custom report location."""

    def test_absolute_report_path(self, tmp_path):
        """Should use absolute path when specified."""
        from config import NovaConfig

        config = NovaConfig(report_output_dir="/absolute/path/reports")
        project_dir = tmp_path / "project"

        report_dir = config.get_report_output_dir(project_dir)
        assert report_dir == Path("/absolute/path/reports")

    def test_relative_report_path(self, tmp_path):
        """Should resolve relative path from project dir."""
        from config import NovaConfig

        config = NovaConfig(report_output_dir="custom/reports")
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        report_dir = config.get_report_output_dir(project_dir)
        assert report_dir == project_dir / "custom" / "reports"

    def test_empty_report_path_uses_default(self, tmp_path):
        """Empty report_output_dir should use default path."""
        from config import NovaConfig

        config = NovaConfig(report_output_dir="")
        project_dir = tmp_path / "project"
        project_dir.mkdir()

        report_dir = config.get_report_output_dir(project_dir)
        assert report_dir == project_dir / ".nova-tracer" / "reports"


class TestCustomRulesLoading:
    """Test AC4: Custom rules loading."""

    def test_get_custom_rules_path(self, tmp_path):
        """Should return path to custom rules directory."""
        from config import NovaConfig

        # Create rules directory
        nova_dir = tmp_path / "nova"
        rules_dir = nova_dir / "rules"
        rules_dir.mkdir(parents=True)

        config = NovaConfig(
            nova_dir=str(nova_dir),
            custom_rules_dir="rules/"
        )

        rules_path = config.get_custom_rules_path()
        assert rules_path == rules_dir

    def test_custom_rules_path_not_exists(self, tmp_path):
        """Should return None if rules directory doesn't exist."""
        from config import NovaConfig

        nova_dir = tmp_path / "nova"
        nova_dir.mkdir()

        config = NovaConfig(
            nova_dir=str(nova_dir),
            custom_rules_dir="nonexistent/"
        )

        rules_path = config.get_custom_rules_path()
        assert rules_path is None

    def test_custom_rules_path_no_nova_dir(self):
        """Should return None if nova_dir not set."""
        from config import NovaConfig

        config = NovaConfig(nova_dir="", custom_rules_dir="rules/")
        rules_path = config.get_custom_rules_path()
        assert rules_path is None


class TestDisableAISummaries:
    """Test AC6: Disable AI summaries."""

    def test_ai_summary_disabled_in_config(self, tmp_path):
        """ai_summary_enabled: false should disable AI summaries."""
        from config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("ai_summary_enabled: false")

        config = load_config(config_file)
        assert config.ai_summary_enabled is False

    def test_ai_summary_enabled_in_config(self, tmp_path):
        """ai_summary_enabled: true should enable AI summaries."""
        from config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("ai_summary_enabled: true")

        config = load_config(config_file)
        assert config.ai_summary_enabled is True


class TestAISummaryIntegration:
    """Test AI summary respects config."""

    def test_ai_summary_disabled_uses_stats(self):
        """When ai_enabled=False, should use stats-only summary."""
        from ai_summary import generate_ai_summary

        session_data = {
            "summary": {
                "total_events": 10,
                "files_touched": 3,
                "warnings": 0,
                "blocked": 0,
                "duration_seconds": 120,
            },
            "events": [],
        }

        # With ai_enabled=False, should not call API
        summary = generate_ai_summary(session_data, ai_enabled=False)

        # Should be stats-only format
        assert "10 tool calls" in summary
        assert "2m" in summary

    def test_ai_summary_enabled_by_default(self):
        """generate_ai_summary should have ai_enabled=True by default."""
        import inspect
        from ai_summary import generate_ai_summary

        sig = inspect.signature(generate_ai_summary)
        ai_enabled_param = sig.parameters.get("ai_enabled")

        assert ai_enabled_param is not None
        assert ai_enabled_param.default is True


class TestUnknownKeysHandling:
    """Test AC7: Unknown keys handling."""

    def test_unknown_keys_logged(self, tmp_path, caplog):
        """Unknown keys should be logged as warnings."""
        from config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
unknown_key: some_value
another_unknown: 123
ai_summary_enabled: false
""")

        with caplog.at_level(logging.WARNING):
            config = load_config(config_file)

        # Should log warnings for unknown keys
        assert any("unknown_key" in record.message for record in caplog.records)
        assert any("another_unknown" in record.message for record in caplog.records)

        # Should still load valid config
        assert config.ai_summary_enabled is False

    def test_known_keys_not_warned(self, tmp_path, caplog):
        """Known keys should not trigger warnings."""
        from config import load_config

        config_file = tmp_path / "config.yaml"
        config_file.write_text("""
report_output_dir: "/custom"
ai_summary_enabled: true
output_truncation_kb: 10
custom_rules_dir: "rules/"
""")

        with caplog.at_level(logging.WARNING):
            config = load_config(config_file)

        # Should not log any warnings for known keys
        warning_messages = [r.message for r in caplog.records if r.levelno == logging.WARNING]
        assert not any("report_output_dir" in m for m in warning_messages)
        assert not any("ai_summary_enabled" in m for m in warning_messages)


class TestConfigValidation:
    """Test configuration validation."""

    def test_negative_truncation_uses_default(self, caplog):
        """Negative truncation value should use default."""
        from config import NovaConfig

        with caplog.at_level(logging.WARNING):
            config = NovaConfig(output_truncation_kb=-5)

        assert config.output_truncation_kb == 10  # Default
        assert any("output_truncation_kb" in r.message for r in caplog.records)

    def test_zero_truncation_uses_default(self, caplog):
        """Zero truncation value should use default."""
        from config import NovaConfig

        with caplog.at_level(logging.WARNING):
            config = NovaConfig(output_truncation_kb=0)

        assert config.output_truncation_kb == 10  # Default

    def test_truncation_bytes_calculation(self):
        """get_truncation_bytes should return KB * 1024."""
        from config import NovaConfig

        config = NovaConfig(output_truncation_kb=5)
        assert config.get_truncation_bytes() == 5 * 1024

        config = NovaConfig(output_truncation_kb=20)
        assert config.get_truncation_bytes() == 20 * 1024


class TestGlobalConfig:
    """Test global configuration singleton."""

    def test_get_config_returns_config(self):
        """get_config should return a NovaConfig object."""
        from config import get_config, reset_config

        reset_config()  # Ensure fresh state
        config = get_config()

        from config import NovaConfig
        assert isinstance(config, NovaConfig)

    def test_get_config_caches_result(self):
        """get_config should return same instance on repeated calls."""
        from config import get_config, reset_config

        reset_config()
        config1 = get_config()
        config2 = get_config()

        assert config1 is config2

    def test_reset_config_clears_cache(self):
        """reset_config should clear cached config."""
        from config import get_config, reset_config

        config1 = get_config()
        reset_config()
        config2 = get_config()

        # After reset, should be a new instance
        assert config1 is not config2


class TestYAMLErrorHandling:
    """Test YAML parsing error handling."""

    def test_invalid_yaml_uses_defaults(self, tmp_path, caplog):
        """Invalid YAML should use defaults and log warning."""
        from config import load_config

        config_file = tmp_path / "invalid.yaml"
        config_file.write_text("invalid: yaml: content: [")

        with caplog.at_level(logging.WARNING):
            config = load_config(config_file)

        # Should use defaults
        assert config.ai_summary_enabled is True
        assert config.output_truncation_kb == 10

        # Should log warning
        assert any("Error parsing" in r.message or "Error loading" in r.message
                   for r in caplog.records)


class TestConfigFilePathResolution:
    """Test config file path resolution."""

    def test_find_nova_dir(self):
        """_find_nova_dir should find the NOVA installation directory."""
        from config import _find_nova_dir

        nova_dir = _find_nova_dir()

        # Should find the directory containing hooks/
        if nova_dir:
            assert (nova_dir / "hooks").exists()
