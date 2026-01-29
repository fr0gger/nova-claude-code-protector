#!/bin/bash
#
# Nova-tracer - Uninstaller
# Agent Monitoring and Visibility
# =========================================
#
# Removes Nova-tracer hooks from ~/.claude/settings.json
# Preserves all other hooks and settings
#
# Usage:
#   ./uninstall.sh
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
    echo "║            Nova-tracer - Uninstaller                       ║"
    echo "║       Agent Monitoring and Visibility                      ║"
    echo "╚════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}!${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }
print_info() { echo -e "${BLUE}ℹ${NC} $1"; }

# Claude settings paths
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

print_header

# =============================================================================
# Check Prerequisites
# =============================================================================

# Check for jq
if ! command -v jq &> /dev/null; then
    print_error "jq is required for uninstallation."
    print_info "Install via: brew install jq (macOS) or apt install jq (Linux)"
    exit 1
fi

# =============================================================================
# Check Settings File
# =============================================================================

if [[ ! -f "$SETTINGS_FILE" ]]; then
    print_warning "No settings.json found at $SETTINGS_FILE"
    print_info "Nova-tracer hooks may not be installed."
    exit 0
fi

# =============================================================================
# Remove NOVA Hooks
# =============================================================================

echo -e "${BOLD}Removing Nova-tracer hooks from settings.json...${NC}"
echo ""

# Backup existing settings
backup_file="$SETTINGS_FILE.backup.$(date +%Y%m%d%H%M%S)"
cp "$SETTINGS_FILE" "$backup_file"
print_info "Backed up settings to: $backup_file"

# Read existing settings
existing_settings=$(cat "$SETTINGS_FILE")

# Check if hooks section exists
if ! echo "$existing_settings" | jq -e '.hooks' > /dev/null 2>&1; then
    print_warning "No hooks section found in settings.json"
    print_info "Nova-tracer hooks may not be installed."
    exit 0
fi

# Remove Nova-tracer hooks while preserving others
cleaned_settings=$(echo "$existing_settings" | jq '
    # Helper function to check if a hook command contains Nova-tracer path
    def is_nova_hook:
        if .command then
            .command | test("nova_claude_code_protector|nova-guard|session-start\\.py|session-end\\.py|pre-tool-guard\\.py|post-tool-nova-guard\\.py")
        else
            false
        end;

    # Remove Nova-tracer hooks from arrays that have direct hooks
    def remove_nova_direct: map(select(is_nova_hook | not));

    # Remove Nova-tracer hooks from arrays that have matcher-based hooks
    def remove_nova_matcher: map(
        if .hooks then
            .hooks = (.hooks | map(select(is_nova_hook | not)))
        else
            .
        end
    ) | map(select(
        if .hooks then (.hooks | length > 0) else (is_nova_hook | not) end
    ));

    # Process each hook type
    .hooks.SessionStart = ((.hooks.SessionStart // []) | remove_nova_direct | remove_nova_matcher) |
    .hooks.PreToolUse = ((.hooks.PreToolUse // []) | remove_nova_direct | remove_nova_matcher) |
    .hooks.PostToolUse = ((.hooks.PostToolUse // []) | remove_nova_direct | remove_nova_matcher) |
    .hooks.SessionEnd = ((.hooks.SessionEnd // []) | remove_nova_direct | remove_nova_matcher) |

    # Remove empty hook arrays
    .hooks = (.hooks | with_entries(select(.value | length > 0))) |

    # Remove hooks key if empty
    if (.hooks | length) == 0 then del(.hooks) else . end
')

# Write cleaned settings
echo "$cleaned_settings" | jq '.' > "$SETTINGS_FILE"

# Count remaining hooks
remaining_hooks=$(jq '.hooks | keys | length' "$SETTINGS_FILE" 2>/dev/null || echo "0")
print_success "Removed Nova-tracer hooks from settings.json"

if [[ "$remaining_hooks" -gt 0 ]]; then
    print_info "$remaining_hooks other hook types preserved"
else
    print_info "No other hooks remain in settings.json"
fi

echo ""

# =============================================================================
# Optional: Clean Up .nova-protector Directories
# =============================================================================

echo -e "${BOLD}Session data cleanup${NC}"
echo ""
print_info "Nova-tracer stores session data in {project}/.nova-tracer/ directories."
echo ""
read -p "Search for and optionally remove .nova-tracer directories? [y/N] " cleanup_choice

if [[ "${cleanup_choice:-N}" =~ ^[Yy] ]]; then
    echo ""
    print_info "Searching for .nova-tracer directories..."

    # Find all .nova-tracer directories in common project locations
    nova_dirs=()
    while IFS= read -r -d '' dir; do
        nova_dirs+=("$dir")
    done < <(find "$HOME" -maxdepth 5 -type d -name ".nova-tracer" -print0 2>/dev/null)

    if [[ ${#nova_dirs[@]} -eq 0 ]]; then
        print_info "No .nova-tracer directories found."
    else
        echo ""
        print_warning "Found ${#nova_dirs[@]} .nova-tracer directories:"
        echo ""
        for dir in "${nova_dirs[@]}"; do
            # Get directory size
            size=$(du -sh "$dir" 2>/dev/null | cut -f1)
            echo "      $dir ($size)"
        done
        echo ""
        read -p "Remove all these directories? [y/N] " remove_choice
        if [[ "${remove_choice:-N}" =~ ^[Yy] ]]; then
            for dir in "${nova_dirs[@]}"; do
                rm -rf "$dir"
                print_success "Removed: $dir"
            done
        else
            print_info "Directories preserved. Remove manually if desired."
        fi
    fi
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║              Uninstallation Complete!                      ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

print_info "Nova-tracer hooks have been removed from Claude Code."
echo ""
print_info "Restart Claude Code for changes to take effect."
echo ""
print_info "To reinstall, run: ./install.sh"
echo ""
