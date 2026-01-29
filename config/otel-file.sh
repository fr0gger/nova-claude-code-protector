#!/bin/bash
# Nova-tracer OpenTelemetry Configuration - File Output
# Agent Monitoring and Visibility
# Exports OTel data to files for Nova-tracer to consume
#
# Usage:
#   source /path/to/nova_claude_code_protector/config/otel-file.sh
#   claude 2>&1 | tee -a ~/.nova-otel.log
#

# Enable telemetry
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# Export to console (will be captured to file via tee)
export OTEL_METRICS_EXPORTER=console
export OTEL_LOGS_EXPORTER=console

# Log user prompts for full tracing
export OTEL_LOG_USER_PROMPTS=1

# Standard export intervals
export OTEL_METRIC_EXPORT_INTERVAL=60000   # 60 seconds
export OTEL_LOGS_EXPORT_INTERVAL=5000      # 5 seconds

# Include all metadata
export OTEL_METRICS_INCLUDE_SESSION_ID=true
export OTEL_METRICS_INCLUDE_VERSION=true
export OTEL_METRICS_INCLUDE_ACCOUNT_UUID=true

# Nova-tracer tracking
export OTEL_RESOURCE_ATTRIBUTES="nova.enabled=true,nova.version=0.1.0"

# Create log directory
NOVA_OTEL_DIR="${HOME}/.nova-tracer/otel"
mkdir -p "$NOVA_OTEL_DIR"

echo "🛡️  Nova-tracer OpenTelemetry enabled - logging to $NOVA_OTEL_DIR"
echo ""
echo "To capture output, run:"
echo "  claude 2>&1 | tee -a $NOVA_OTEL_DIR/\$(date +%Y-%m-%d).log"
