"""
NOVA Claude Code Protector - Logging Handler Plugins.

This directory contains handler plugins for the nova_logging system.
Each plugin must export:
- HANDLER_NAME: str - unique identifier for the handler
- create_handler(config: dict, session_id: str) -> logging.Handler
"""


