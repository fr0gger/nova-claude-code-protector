"""
NOVA Claude Code Protector - Centralized Logging Module.

Provides a plugin-based logging system with handler discovery.
Handlers are loaded from hooks/loggers/ directory.

Usage:
    from nova_logging import get_logger

    logger = get_logger(session_id)
    logger.info("Event occurred", extra={"hook_input": input_data})
"""

import datetime
import importlib.util
import json
import logging
import os
import platform
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_LOG_LEVEL = "INFO"
LOGGERS_DIR_NAME = "loggers"


# =============================================================================
# JSON FORMATTER
# =============================================================================

class NovaJSONFormatter(logging.Formatter):
    """
    JSON formatter that includes extra fields in structured output.
    
    Produces JSON logs with:
    - timestamp: ISO 8601 format
    - level: Log level name
    - message: Human-readable log message
    - session_id: Session identifier (from logger name or extra)
    - All extra fields from the log record
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON."""

        message = record.getMessage()
        # Build base log structure
        log_data: Dict[str, Any] = {}

        # Add extra fields from the record
        # Skip standard LogRecord attributes
        standard_attrs = {
            "name", "args", "created", "filename", "funcName",
            "levelname", "levelno", "lineno", "module", "msecs",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "exc_info", "exc_text", "thread", "threadName",
            "message", "taskName",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                # Ensure value is JSON serializable
                try:
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        # Add exception info if present
        return json.dumps(log_data, separators=(",", ":"))


# =============================================================================
# HANDLER REGISTRY
# =============================================================================

class HandlerRegistry:
    """
    Registry that discovers and loads handler plugins from hooks/loggers/.
    
    Each plugin must export:
    - HANDLER_NAME: str - unique identifier for the handler
    - create_handler(config: dict, session_id: str) -> logging.Handler
    """

    _instance: Optional["HandlerRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "HandlerRegistry":
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._plugins: Dict[str, Any] = {}
                    cls._instance._discovered = False
        return cls._instance

    def _get_loggers_dir(self) -> Optional[Path]:
        """Get the path to the loggers directory."""
        # hooks/lib/nova_logging.py -> hooks/loggers/
        lib_dir = Path(__file__).parent
        hooks_dir = lib_dir.parent
        loggers_dir = hooks_dir / LOGGERS_DIR_NAME
        
        if loggers_dir.exists() and loggers_dir.is_dir():
            return loggers_dir
        return None

    def discover_plugins(self) -> None:
        """Discover and load all handler plugins from the loggers directory."""
        if self._discovered:
            return

        loggers_dir = self._get_loggers_dir()
        if not loggers_dir:
            self._discovered = True
            return

        # Find all Python files (except __init__.py)
        for py_file in loggers_dir.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                # Load the module
                spec = importlib.util.spec_from_file_location(
                    f"nova_loggers.{py_file.stem}",
                    py_file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Check for required exports
                    if hasattr(module, "HANDLER_NAME") and hasattr(module, "create_handler"):
                        handler_name = getattr(module, "HANDLER_NAME")
                        self._plugins[handler_name] = module

            except Exception:
                # Fail-open: skip plugins that fail to load
                pass

        self._discovered = True

    def get_handler(
        self,
        name: str,
        config: Dict[str, Any],
        session_id: str,
    ) -> Optional[logging.Handler]:
        """
        Get an instantiated handler by name.
        
        Args:
            name: Handler plugin name (e.g., "file")
            config: Logging configuration dictionary
            session_id: Current session ID
            
        Returns:
            Instantiated handler, or None if not found/failed
        """
        self.discover_plugins()

        plugin = self._plugins.get(name)
        if plugin is None:
            return None

        try:
            create_fn = getattr(plugin, "create_handler")
            return create_fn(config, session_id)
        except Exception:
            # Fail-open: return None if handler creation fails
            return None

    @property
    def available_handlers(self) -> List[str]:
        """Get list of available handler names."""
        self.discover_plugins()
        return list(self._plugins.keys())


# =============================================================================
# CONFIGURATION
# =============================================================================

def _load_logging_config() -> Dict[str, Any]:
    """
    Load logging configuration from nova-config.yaml.
    
    Returns:
        Logging configuration dictionary
    """

    # Find config file
    lib_dir = Path(__file__).parent
    config_paths = [
        lib_dir.parent.parent / "config" / "nova-config.yaml",
        lib_dir.parent / "config" / "nova-config.yaml",
    ]

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if project_dir:
        config_paths.append(
            Path(project_dir) / ".claude" / "hooks" / "nova-guard" / "config" / "nova-config.yaml"
        )

    config_dict: Dict[str, Any] = {}
    for path in config_paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config_dict = yaml.safe_load(f) or {}
                break
            except Exception:
                pass

    # Extract logging section with defaults
    logging_config = config_dict.get("logging", {})

    
    return {
        "enabled": logging_config.get("enabled", True),
        "level": logging_config.get("level", DEFAULT_LOG_LEVEL),
        "handlers": logging_config.get("handlers", []),
        **{k: v for k, v in logging_config.items() if k not in ("enabled", "level", "handlers")},
    }


# =============================================================================
# LOGGER FACTORY
# =============================================================================

# Cache for configured loggers (keyed by session_id)
_loggers: Dict[str, logging.Logger] = {}
_setup_lock = threading.Lock()


def get_logger(session_id: str) -> logging.Logger:
    """
    Get or create a logger for the specified session.
    
    The logger is configured with all enabled handlers from the plugin registry.
    The session_id is automatically included in all log records.
    
    Args:
        session_id: The session identifier (e.g., "f67dc0e8-efb4-4d6f-94f1-aefd81e5a8e2")
        
    Returns:
        Configured logging.Logger instance
    """

    with _setup_lock:
        # Check cache first
        if session_id in _loggers:
            return _loggers[session_id]

        # Load configuration
        config = _load_logging_config()

        # Create logger with session-specific name
        logger = logging.getLogger(session_id)

        # Parse log level
        level_str = config.get("level", DEFAULT_LOG_LEVEL).upper()
        level = getattr(logging, level_str, logging.INFO)
        logger.setLevel(level)

        # Prevent propagation to root logger
        logger.propagate = False

        # Clear any existing handlers
        logger.handlers.clear()


        # Check if logging is enabled
        if not config.get("enabled", True):
            # Return a logger with no handlers (silent)
            _loggers[session_id] = logger
            return logger

        # Add handlers from configuration
        registry = HandlerRegistry()
        handlers_config = config.get("handlers", [])

        for handler_name in handlers_config:
            try:
                handler = registry.get_handler(handler_name, config, session_id)
                if handler is not None:
                    # Set JSON formatter
                    handler.setFormatter(NovaJSONFormatter())
                    logger.addHandler(handler)
            except Exception:
                # Fail-open: skip handlers that fail
                pass

        # Cache the logger
        _loggers[session_id] = logger
        return logger


def reset_loggers() -> None:
    """
    Reset all cached loggers.
    
    Useful for testing or when configuration changes.
    """
    global _loggers
    with _setup_lock:
        for logger in _loggers.values():
            logger.handlers.clear()
        _loggers.clear()


def log_event(event_data: Dict[str, Any], message: Optional[str] = None) -> None:
    """
    Log an event to the session log.
    """
    session_id = event_data.get("session_id")
    # Session id is always present in the event data but 
    # we need to check for None just in case
    # TODO: add a default session id to the event data?
    if not session_id:
        return
    logger = get_logger(session_id)
    event_data["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    event_data["session_id"] = session_id
    if message:
        event_data["message"] = message
    event_data["host"] = platform.node()
    event_data["service"] = "nova-protector"
    event_data["platform"] = platform.system().lower()
    event_data["project_dir"] = os.environ.get("CLAUDE_PROJECT_DIR", "unknown")
    event_data["user"] = os.environ.get("USER", "unknown")
    logger.info(json.dumps(event_data, separators=(",", ":")))
