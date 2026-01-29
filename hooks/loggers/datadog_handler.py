import json
import logging
import os
import threading
import urllib.request
from typing import Any, Dict, List, Optional

HANDLER_NAME = "datadog"

# =============================================================================
# CONSTANTS
# =============================================================================

# Datadog Logs API endpoints by site
DATADOG_ENDPOINTS = {
    "datadoghq.com": "https://http-intake.logs.datadoghq.com/api/v2/logs",
    "datadoghq.eu": "https://http-intake.logs.datadoghq.eu/api/v2/logs",
    "us3.datadoghq.com": "https://http-intake.logs.us3.datadoghq.com"
                         "/api/v2/logs",
    "us5.datadoghq.com": "https://http-intake.logs.us5.datadoghq.com"
                         "/api/v2/logs",
    "ap1.datadoghq.com": "https://http-intake.logs.ap1.datadoghq.com"
                         "/api/v2/logs",
}

DEFAULT_SITE = "datadoghq.com"
DEFAULT_SERVICE = "nova-protector"
DEFAULT_SOURCE = "claude-code-hooks"

# Maximum message size for truncation (Datadog limit is 1MB)
MAX_MESSAGE_SIZE = 256 * 1024  # 256KB to be safe


# =============================================================================
# DATADOG HANDLER
# =============================================================================

class DatadogHandler(logging.Handler):
    """
    Logging handler that sends logs to Datadog Logs API.

    Uses urllib.request for HTTP POST requests to avoid external dependencies.
    Implements fail-open behavior: errors are silently ignored to never
    block hook execution.

    Attributes:
        api_key: Datadog API key
        endpoint: Datadog Logs API endpoint URL
        timeout: HTTP request timeout in seconds
    """

    def __init__(
        self,
        api_key: str,
        site: str = DEFAULT_SITE,
        service: str = DEFAULT_SERVICE,
        source: str = DEFAULT_SOURCE,
        tags: Optional[List[str]] = None,
        timeout: int = 5,
    ):
        """
        Initialize the Datadog handler.

        Args:
            api_key: Datadog API key (required)
            site: Datadog site (e.g., datadoghq.com, datadoghq.eu)
            service: Service name for logs
            source: Source identifier for logs
            tags: Optional list of tags to include
            timeout: HTTP request timeout in seconds
            level: Logging level threshold
        """
        super().__init__(logging.INFO)
        self._api_key = api_key
        self._endpoint = DATADOG_ENDPOINTS.get(
            site, DATADOG_ENDPOINTS[DEFAULT_SITE]
        )
        self._source = source
        self._service = service
        self._timeout = timeout
        self._tags = tags

        # Lock for thread safety
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a log record to Datadog.

        Fail-open: catches all exceptions and silently continues.

        Args:
            record: The log record to emit
        """
        record = json.loads(record.getMessage())
        record.update({
            "ddsource": self._source,
            "service": self._service,
        })

        if self._tags:
            record["ddtags"] = ",".join(self._tags)
        try:
            headers = {
                "Content-Type": "application/json",
                "DD-API-KEY": self._api_key,
            }
            request = urllib.request.Request(
                self._endpoint,
                data=json.dumps(record).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                response.read()

        except Exception:
            # Fail-open: never raise exceptions
            pass


def create_handler(config: Dict[str, Any], session_id: str) -> Optional[DatadogHandler]:
        """
        Create a Datadog handler from configuration.

        Args:
            config: Logging configuration dictionary

        Returns:
            DatadogHandler instance, or None if API key not available
        """
        # Get Datadog-specific config
        dd_config = config.get("datadog", {})

        # API key: env var takes precedence over config
        api_key = os.environ.get("DD_API_KEY", "")
        if not api_key:
            api_key = dd_config.get("api_key", "")

        if not api_key:
            # No API key available, skip Datadog handler
            return None

        site = dd_config.get("site", DEFAULT_SITE)
        service = dd_config.get("service", DEFAULT_SERVICE)
        source = dd_config.get("source", DEFAULT_SOURCE)
        tags = dd_config.get("tags", [])
        timeout = dd_config.get("timeout", 5)

        return DatadogHandler(
            api_key=api_key,
            site=site,
            service=service,
            source=source,
            tags=tags,
            timeout=timeout,
        )