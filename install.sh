#!/bin/bash
#
# NOVA Claude Code Protector - Installer
# =======================================
#
# Installs NOVA protection hooks for Claude Code.
# Registers hooks globally in ~/.claude/settings.json
#
# Four protection hooks:
# - SessionStart: Initialize session tracking
# - PreToolUse: Block dangerous commands before execution
# - PostToolUse: Scan tool outputs for prompt injection
# - SessionEnd: Generate session report
#
# Usage:
#   ./install.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

print_header() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════════╗"
    echo "║      NOVA Claude Code Protector - Installation             ║"
    echo "║  Session Tracking + Security Scanning + Reports            ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}!${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }

# Get script directory (NOVA installation location)
NOVA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Verify we're in the right directory
verify_source_files() {
    local missing=0
    for hook in "session-start.py" "user-prompt-capture.py" "pre-tool-guard.py" "post-tool-nova-guard.py" "session-end.py"; do
        if [[ ! -f "$NOVA_DIR/hooks/$hook" ]]; then
            print_error "Missing: hooks/$hook"
            missing=1
        fi
    done
    if [[ $missing -eq 1 ]]; then
        print_error "Source files not found."
        print_error "Run this script from the nova_claude_code_protector directory."
        exit 1
    fi
}

# Claude settings paths
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

print_header
print_info "NOVA Directory: $NOVA_DIR"
print_info "Claude Settings: $SETTINGS_FILE"
echo ""

# =============================================================================
# Verify Source Files
# =============================================================================

echo -e "${BOLD}Verifying source files...${NC}"
verify_source_files
print_success "All hook scripts found"
echo ""

# =============================================================================
# Check Prerequisites
# =============================================================================

echo -e "${BOLD}Checking prerequisites...${NC}"
echo ""

# Check for UV
if ! command -v uv &> /dev/null; then
    print_warning "UV is not installed."
    read -p "Install UV now? [Y/n] " install_uv
    if [[ "${install_uv:-Y}" =~ ^[Yy] ]]; then
        echo "Installing UV..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
        print_success "UV installed"
    else
        print_error "UV is required. Install from: https://docs.astral.sh/uv/"
        exit 1
    fi
else
    print_success "UV is installed"
fi

# Check for jq (needed for JSON manipulation)
if ! command -v jq &> /dev/null; then
    print_warning "jq is not installed (needed for settings.json manipulation)."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        read -p "Install jq via Homebrew? [Y/n] " install_jq
        if [[ "${install_jq:-Y}" =~ ^[Yy] ]]; then
            brew install jq
            print_success "jq installed"
        else
            print_error "jq is required. Install via: brew install jq"
            exit 1
        fi
    else
        print_error "jq is required. Install via your package manager."
        exit 1
    fi
else
    print_success "jq is installed"
fi

# Check Python version
python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
major="${python_version%%.*}"
minor="${python_version#*.}"
if [[ "$major" -ge 3 && "$minor" -ge 10 ]]; then
    print_success "Python $python_version detected"
else
    print_warning "Python 3.10+ recommended (found: $python_version)"
fi

echo ""

# =============================================================================
# Create ~/.claude Directory If Needed
# =============================================================================

echo -e "${BOLD}Setting up Claude directory...${NC}"
echo ""

if [[ ! -d "$CLAUDE_DIR" ]]; then
    mkdir -p "$CLAUDE_DIR"
    print_success "Created ~/.claude directory"
else
    print_success "~/.claude directory exists"
fi

# =============================================================================
# Register NOVA Hooks in settings.json
# =============================================================================

echo -e "${BOLD}Registering NOVA hooks...${NC}"
echo ""

# Define NOVA hooks configuration
NOVA_HOOKS=$(cat <<EOF
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "uv run $NOVA_DIR/hooks/session-start.py"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "uv run $NOVA_DIR/hooks/user-prompt-capture.py"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run $NOVA_DIR/hooks/pre-tool-guard.py"
          }
        ]
      },
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "uv run $NOVA_DIR/hooks/pre-tool-guard.py"
          }
        ]
      },
      {
        "matcher": "Edit",
        "hooks": [
          {
            "type": "command",
            "command": "uv run $NOVA_DIR/hooks/pre-tool-guard.py"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "uv run $NOVA_DIR/hooks/post-tool-nova-guard.py",
            "timeout": 120
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "uv run $NOVA_DIR/hooks/session-end.py"
          }
        ]
      }
    ]
  }
}
EOF
)

# Function to merge hooks preserving existing ones
merge_hooks() {
    local existing="$1"
    local nova="$2"

    # Use jq to deep merge, with NOVA hooks added to existing arrays
    echo "$existing" | jq --argjson nova "$nova" '
        # Helper function to check if a hook command contains NOVA path
        def is_nova_hook: .command | test("nova_claude_code_protector|nova-guard");

        # Remove any existing NOVA hooks from an array
        def remove_nova_hooks: map(select(
            if .hooks then
                .hooks | map(select(is_nova_hook | not)) | length > 0
            else
                is_nova_hook | not
            end
        )) | map(
            if .hooks then
                .hooks = (.hooks | map(select(is_nova_hook | not)))
            else
                .
            end
        ) | map(select(
            if .hooks then (.hooks | length > 0) else true end
        ));

        # Merge hook arrays
        .hooks.SessionStart = ((.hooks.SessionStart // []) | remove_nova_hooks) + ($nova.hooks.SessionStart // []) |
        .hooks.UserPromptSubmit = ((.hooks.UserPromptSubmit // []) | remove_nova_hooks) + ($nova.hooks.UserPromptSubmit // []) |
        .hooks.PreToolUse = ((.hooks.PreToolUse // []) | remove_nova_hooks) + ($nova.hooks.PreToolUse // []) |
        .hooks.PostToolUse = ((.hooks.PostToolUse // []) | remove_nova_hooks) + ($nova.hooks.PostToolUse // []) |
        .hooks.SessionEnd = ((.hooks.SessionEnd // []) | remove_nova_hooks) + ($nova.hooks.SessionEnd // [])
    '
}

# Handle settings.json creation or update
if [[ ! -f "$SETTINGS_FILE" ]]; then
    # Create new settings.json with NOVA hooks
    echo "$NOVA_HOOKS" | jq '.' > "$SETTINGS_FILE"
    print_success "Created settings.json with NOVA hooks"
else
    # Backup existing settings
    cp "$SETTINGS_FILE" "$SETTINGS_FILE.backup.$(date +%Y%m%d%H%M%S)"
    print_info "Backed up existing settings.json"

    # Read existing settings
    existing_settings=$(cat "$SETTINGS_FILE")

    # Check if it has hooks section
    if echo "$existing_settings" | jq -e '.hooks' > /dev/null 2>&1; then
        # Merge NOVA hooks with existing hooks
        merged=$(merge_hooks "$existing_settings" "$NOVA_HOOKS")
        echo "$merged" | jq '.' > "$SETTINGS_FILE"
        print_success "Merged NOVA hooks with existing hooks"
    else
        # Add hooks section to existing settings
        echo "$existing_settings" | jq --argjson nova "$NOVA_HOOKS" '. + {hooks: $nova.hooks}' > "$SETTINGS_FILE"
        print_success "Added NOVA hooks to existing settings"
    fi
fi

# Verify registration
hook_count=$(jq '.hooks | keys | length' "$SETTINGS_FILE" 2>/dev/null || echo "0")
print_success "Registered $hook_count hook types in settings.json"

echo ""

# =============================================================================
# Make Hook Scripts Executable
# =============================================================================

echo -e "${BOLD}Setting permissions...${NC}"
chmod +x "$NOVA_DIR/hooks/"*.py 2>/dev/null || true
print_success "Made hook scripts executable"

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Installation Complete!                        ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

print_info "NOVA hooks registered:"
echo "      • SessionStart       → session-start.py (session tracking)"
echo "      • UserPromptSubmit   → user-prompt-capture.py (conversation capture)"
echo "      • PreToolUse         → pre-tool-guard.py (dangerous command blocking)"
echo "      • PostToolUse        → post-tool-nova-guard.py (prompt injection scanning)"
echo "      • SessionEnd         → session-end.py (report generation)"
echo ""

print_info "Next steps:"
echo ""
echo "  1. ${BOLD}Restart Claude Code${NC} to activate hooks"
echo ""
echo "  2. ${BOLD}Start a session${NC} - NOVA will automatically:"
echo "     • Track all tool usage"
echo "     • Block dangerous commands"
echo "     • Scan for prompt injection"
echo "     • Generate session reports"
echo ""
echo "  3. ${BOLD}View reports${NC} in:"
echo "     {project}/.nova-protector/reports/"
echo ""
echo "  Reports include estimated activity metrics (tokens, processing time)"
echo "  based on tool input/output data - no additional setup needed!"
echo ""

print_info "To uninstall, run: ./uninstall.sh"
echo ""
print_warning "First run will download ML models (~1GB) for semantic detection"
echo ""
