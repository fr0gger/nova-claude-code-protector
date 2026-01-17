"""
Configuration Module for NOVA Claude Code Protector.

Provides centralized configuration management with sensible defaults.
Loads optional YAML configuration from config/nova-protector.yaml.

Story 5.2: Configuration and Extensibility
- Sensible defaults when no config file exists
- Custom report output directory
- AI summary toggle
- Custom rules loading
- Unknown keys handling with warnings
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format="[NOVA %(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("nova-protector.config")


# Known configuration keys
KNOWN_KEYS = {
    "report_output_dir",
    "ai_summary_enabled",
    "output_truncation_kb",
    "custom_rules_dir",
    # LLM/scanning config keys (from nova-config.yaml)
    "llm_provider",
    "model",
    "enable_keywords",
    "enable_semantics",
    "enable_llm",
    "semantic_threshold",
    "llm_threshold",
    "llm_timeout",
    "max_content_length",
    "min_severity",
    "rule_files",
    "debug",
    "log_file",
}


@dataclass
class NovaConfig:
    """
    Configuration for NOVA Claude Code Protector.

    All fields have sensible defaults that work out of the box.
    """

    # Report settings
    report_output_dir: str = ""  # Empty = use default {project}/.nova-protector/reports/

    # AI Summary settings
    ai_summary_enabled: bool = True  # Use AI summaries when API key present

    # Output settings
    output_truncation_kb: int = 10  # Maximum size in KB for tool outputs

    # Rules settings
    custom_rules_dir: str = "rules/"  # Directory for custom .nov files

    # Internal: path to NOVA installation directory
    nova_dir: str = field(default="", repr=False)

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Ensure output_truncation_kb is positive
        if self.output_truncation_kb < 1:
            logger.warning(
                f"output_truncation_kb must be positive, using default (10KB)"
            )
            self.output_truncation_kb = 10

    def get_report_output_dir(self, project_dir: Path) -> Path:
        """
        Get the report output directory for a project.

        Args:
            project_dir: The project directory

        Returns:
            Path to the report output directory
        """
        if self.report_output_dir:
            # Custom directory specified
            custom_path = Path(self.report_output_dir)
            if custom_path.is_absolute():
                return custom_path
            else:
                # Relative to project directory
                return project_dir / custom_path
        else:
            # Default: {project}/.nova-protector/reports/
            return project_dir / ".nova-protector" / "reports"

    def get_truncation_bytes(self) -> int:
        """Get the truncation limit in bytes."""
        return self.output_truncation_kb * 1024

    def get_custom_rules_path(self) -> Optional[Path]:
        """
        Get the path to the custom rules directory.

        Returns:
            Path to custom rules directory, or None if not configured
        """
        if not self.nova_dir or not self.custom_rules_dir:
            return None

        rules_path = Path(self.nova_dir) / self.custom_rules_dir
        if rules_path.exists() and rules_path.is_dir():
            return rules_path
        return None


def _find_nova_dir() -> Optional[Path]:
    """
    Find the NOVA installation directory.

    Looks for the directory containing the hooks/ folder.
    Uses the location of this file to determine the path.

    Returns:
        Path to NOVA directory, or None if not found
    """
    # This file is at hooks/lib/config.py
    # NOVA_DIR is two levels up
    try:
        config_file = Path(__file__).resolve()
        nova_dir = config_file.parent.parent.parent
        if (nova_dir / "hooks").exists():
            return nova_dir
    except Exception:
        pass
    return None


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Dictionary of configuration values
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, using defaults")
        return {}

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
            return config if config else {}
    except FileNotFoundError:
        # Config file doesn't exist, use defaults
        return {}
    except yaml.YAMLError as e:
        logger.warning(f"Error parsing config file: {e}")
        return {}
    except Exception as e:
        logger.warning(f"Error loading config file: {e}")
        return {}


def _warn_unknown_keys(config: Dict[str, Any]) -> None:
    """
    Log warnings for unknown configuration keys.

    Args:
        config: Configuration dictionary to check
    """
    unknown_keys = set(config.keys()) - KNOWN_KEYS
    for key in sorted(unknown_keys):
        logger.warning(f"Unknown configuration key: '{key}' (ignored)")


def load_config(config_path: Optional[Path] = None) -> NovaConfig:
    """
    Load NOVA configuration from file with sensible defaults.

    Args:
        config_path: Optional path to config file. If None, looks for
                    config/nova-protector.yaml in NOVA_DIR.

    Returns:
        NovaConfig object with loaded or default values
    """
    # Find NOVA directory
    nova_dir = _find_nova_dir()

    # Determine config file path
    if config_path is None and nova_dir:
        config_path = nova_dir / "config" / "nova-protector.yaml"

    # Load config from file
    config_dict: Dict[str, Any] = {}
    if config_path and config_path.exists():
        config_dict = _load_yaml_config(config_path)
        # Warn about unknown keys
        _warn_unknown_keys(config_dict)

    # Build config object with defaults
    config = NovaConfig(
        report_output_dir=config_dict.get("report_output_dir", ""),
        ai_summary_enabled=config_dict.get("ai_summary_enabled", True),
        output_truncation_kb=config_dict.get("output_truncation_kb", 10),
        custom_rules_dir=config_dict.get("custom_rules_dir", "rules/"),
        nova_dir=str(nova_dir) if nova_dir else "",
    )

    return config


def get_default_config() -> NovaConfig:
    """
    Get the default configuration without loading from file.

    Useful for testing or when config file loading should be skipped.

    Returns:
        NovaConfig object with all default values
    """
    nova_dir = _find_nova_dir()
    return NovaConfig(nova_dir=str(nova_dir) if nova_dir else "")


# Global config instance (lazy-loaded)
_config: Optional[NovaConfig] = None


def get_config() -> NovaConfig:
    """
    Get the global configuration instance.

    Loads config on first call, returns cached instance thereafter.

    Returns:
        NovaConfig object
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """
    Reset the global configuration instance.

    Forces config to be reloaded on next get_config() call.
    Useful for testing.
    """
    global _config
    _config = None
