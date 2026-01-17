#!/bin/bash
# NOVA OpenTelemetry Configuration
# Source this file before running Claude Code to enable full tracing
#
# Usage:
#   source /path/to/nova_claude_code_protector/config/otel-env.sh
#   claude
#

# Enable telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# Export to console for debugging (change to 'otlp' for production)
export OTEL_METRICS_EXPORTER=console
export OTEL_LOGS_EXPORTER=console

# Log user prompts (set to 0 to disable for privacy)
export OTEL_LOG_USER_PROMPTS=1

# Faster export intervals for debugging (default: 60s metrics, 5s logs)
export OTEL_METRIC_EXPORT_INTERVAL=10000   # 10 seconds
export OTEL_LOGS_EXPORT_INTERVAL=5000      # 5 seconds

# Include session and account info in metrics
export OTEL_METRICS_INCLUDE_SESSION_ID=true
export OTEL_METRICS_INCLUDE_VERSION=true
export OTEL_METRICS_INCLUDE_ACCOUNT_UUID=true

# Custom attributes for NOVA tracking
export OTEL_RESOURCE_ATTRIBUTES="nova.enabled=true,nova.version=0.1.0"

echo "🛡️  NOVA OpenTelemetry enabled - full API tracing active"
echo "   Metrics: $OTEL_METRICS_EXPORTER"
echo "   Logs: $OTEL_LOGS_EXPORTER"
echo "   User prompts: $([ \"$OTEL_LOG_USER_PROMPTS\" = \"1\" ] && echo 'logged' || echo 'redacted')"
