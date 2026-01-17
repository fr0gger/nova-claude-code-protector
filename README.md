# NOVA Claude Code Protector

Security monitoring and prompt injection defense for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) using the [NOVA Framework](https://github.com/fr0gger/nova-framework).

## Features

- **Session Tracking** - Captures all tool usage with timestamps and metadata
- **Prompt Injection Detection** - Three-tier scanning (keywords, semantic ML, LLM) - *passive monitoring with warnings*
- **Dangerous Command Blocking** - Actively prevents destructive operations before execution
- **MCP & Skills Tracing** - Tracks MCP server calls and Agent Skills invocations with detailed breakdowns
- **Interactive HTML Reports** - Visual timeline, conversation trace, and expandable event details
- **AI-Powered Summaries** - Intelligent session summaries via Claude Haiku
- **Configurable** - Custom report locations, detection thresholds, and rules

## Quick Start

```bash
# Clone the repository
git clone https://github.com/fr0gger/nova_claude_code_protector.git
cd nova_claude_code_protector

# Install globally (registers hooks in ~/.claude/settings.json)
./install.sh

# Restart Claude Code to activate hooks
```

That's it! NOVA will now protect all your Claude Code sessions.

## Installation

### Prerequisites

- **Python 3.10+**
- **UV** - Python package manager ([install](https://docs.astral.sh/uv/))
- **jq** - JSON processor (install via `brew install jq` on macOS)

### Install

```bash
./install.sh
```

The installer will:
1. Verify all prerequisites are installed
2. Register four NOVA hooks in `~/.claude/settings.json`
3. Preserve any existing hooks you may have configured
4. Make hook scripts executable

### Uninstall

```bash
./uninstall.sh
```

The uninstaller will:
1. Remove only NOVA hooks from settings.json
2. Preserve all other hooks and settings
3. Optionally clean up `.nova-protector/` directories

## How It Works

NOVA registers four Claude Code hooks that work together:

```
┌─────────────────────────────────────────────────────────────┐
│                    Claude Code Session                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. SessionStart Hook                                        │
│     └── Creates session JSONL file                          │
│     └── Initializes tracking with session ID                │
│                                                              │
│  2. PreToolUse Hook (Bash, Write, Edit)           [ACTIVE]  │
│     └── Scans commands BEFORE execution                     │
│     └── BLOCKS dangerous operations (rm -rf, etc.)          │
│                                                              │
│  3. PostToolUse Hook (Read, Bash, WebFetch, etc.) [PASSIVE] │
│     └── Scans tool OUTPUT for prompt injection              │
│     └── WARNS Claude if threats detected                    │
│     └── Records event with NOVA verdict                     │
│                                                              │
│  4. SessionEnd Hook                                          │
│     └── Generates interactive HTML report                   │
│     └── Creates AI-powered session summary                  │
│     └── Saves to .nova-protector/reports/                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Active vs Passive Protection

NOVA provides two modes of protection:

| Mode | Hook | Behavior | Use Case |
|------|------|----------|----------|
| **ACTIVE** | PreToolUse | Blocks execution before it happens | Dangerous commands (`rm -rf /`, `sudo rm`, etc.) |
| **PASSIVE** | PostToolUse | Warns Claude after content is read | Prompt injection in files, web pages, command output |

**Important:** Prompt injection detection is **passive**. When NOVA detects a prompt injection in a file or web page, the content has already been read by Claude. NOVA sends a warning message to Claude advising it to treat the content with suspicion, but does not prevent Claude from seeing the malicious content.

This is a limitation of the PostToolUse hook architecture - it runs *after* the tool executes. Active blocking of prompt injections would require scanning content before Claude reads it, which would involve reading files twice (once to scan, once for Claude).

**What gets actively blocked:**
- Destructive commands: `rm -rf /`, `sudo rm -rf`, `mkfs`
- Dangerous operations: `dd if=... of=/dev/`, fork bombs
- Credential exfiltration: `curl ... | sh`, reading `~/.ssh/id_rsa`

**What gets passively warned:**
- Prompt injection in files (Read tool)
- Prompt injection in web pages (WebFetch tool)
- Prompt injection in command output (Bash tool)
- Prompt injection in MCP tool responses

### Three-Tier Detection

| Tier | Method | Speed | Catches |
|------|--------|-------|---------|
| **Keywords** | Regex patterns | ~1ms | Known attack patterns, exact phrases |
| **Semantics** | ML similarity | ~50ms | Paraphrased attacks, variations |
| **LLM** | AI evaluation | ~500-2000ms | Sophisticated, novel attacks |

### Attack Categories Detected

- **Instruction Override** - "Ignore all previous instructions", fake system prompts
- **Jailbreak/Role-Playing** - DAN attempts, persona switching
- **Encoding/Obfuscation** - Base64, hex, Unicode, leetspeak
- **Context Manipulation** - False authority claims, hidden instructions

## Usage

### Automatic Protection

Once installed, NOVA works automatically:

1. **Start any Claude Code session** - SessionStart hook initializes tracking
2. **Use Claude normally** - All tool calls are monitored and scanned
3. **End your session** - SessionEnd hook generates an HTML report

### View Reports

Reports are saved to each project's `.nova-protector/reports/` directory:

```bash
# List reports for current project
ls .nova-protector/reports/

# Open a report in your browser
open .nova-protector/reports/session-abc123.html
```

### Report Features

The interactive HTML report includes:

- **Session Summary** - Duration, tool counts, security events
- **AI Summary** - Intelligent 2-3 sentence description
- **Event Timeline** - Visual chronological view of all tool calls
- **Filtering** - Filter by tool type or NOVA verdict (allowed/warned/blocked)
- **Expandable Details** - Click any event to see full input/output
- **NOVA Verdict Details** - Severity, matched rules, scan time

### Manual Testing

Test NOVA detection without running Claude Code:

```bash
# Run sample attack tests
uv run hooks/test-nova-guard.py --samples

# Test specific text
uv run hooks/test-nova-guard.py --text "ignore previous instructions"

# Test a file
uv run hooks/test-nova-guard.py --file suspicious.txt

# Interactive mode
uv run hooks/test-nova-guard.py -i
```

## Configuration

NOVA works with sensible defaults, but you can customize behavior.

### NOVA Protector Config

Edit `config/nova-protector.yaml`:

```yaml
# Report output directory
# Empty = {project}/.nova-protector/reports/ (default)
# Relative path = relative to project
# Absolute path = exact location
report_output_dir: ""

# AI-powered session summaries
# Set to false to use stats-only summaries (no API calls)
ai_summary_enabled: true

# Maximum size in KB for tool outputs in reports
# Larger outputs will be truncated
output_truncation_kb: 10

# Directory for custom NOVA rules
custom_rules_dir: "rules/"
```

### NOVA Scanning Config

Edit `config/nova-config.yaml`:

```yaml
# LLM Provider for Tier 3 detection
llm_provider: anthropic
model: claude-3-5-haiku-20241022

# Detection tiers (enable/disable)
enable_keywords: true
enable_semantics: true
enable_llm: true

# Thresholds (0.0 - 1.0)
semantic_threshold: 0.7
llm_threshold: 0.7

# Severity filter
min_severity: low  # low, medium, or high
```

### Environment Variables

```bash
# Required for AI summaries and LLM-tier detection
export ANTHROPIC_API_KEY=sk-ant-...
```

## Custom Rules

Create `.nov` files in the `rules/` directory:

```
rule MyCustomRule
{
    meta:
        description = "Detects my specific attack pattern"
        author = "Your Name"
        severity = "high"
        category = "custom"

    keywords:
        $pattern1 = /my regex pattern/i
        $pattern2 = "exact string match"

    semantics:
        $sem1 = "semantic description of attack" (0.75)

    llm:
        $llm1 = "Question for LLM to evaluate" (0.7)

    condition:
        any of ($pattern*) or $sem1 or $llm1
}
```

## File Structure

```
nova_claude_code_protector/
├── install.sh                    # Global installation script
├── uninstall.sh                  # Removal script
├── config/
│   ├── nova-config.yaml          # NOVA scanning configuration
├── rules/
│   ├── instruction_override.nov  # Override attack rules
│   ├── roleplay_jailbreak.nov    # Jailbreak attack rules
│   ├── encoding_obfuscation.nov  # Encoding attack rules
│   └── context_manipulation.nov  # Context attack rules
├── hooks/
│   ├── session-start.py          # SessionStart hook
│   ├── pre-tool-guard.py         # PreToolUse hook (blocking)
│   ├── post-tool-nova-guard.py   # PostToolUse hook (scanning)
│   ├── session-end.py            # SessionEnd hook (reports)
│   ├── test-nova-guard.py        # Testing utility
│   └── lib/
│       ├── session_manager.py    # Session tracking logic
│       ├── report_generator.py   # HTML report generation
│       ├── ai_summary.py         # AI summary generation
│       └── config.py             # Configuration management
├── tests/                        # Comprehensive test suite (483 tests)
└── test-files/                   # Sample injection files
```

## Troubleshooting

### Hooks not activating

1. Verify installation: `cat ~/.claude/settings.json | jq '.hooks'`
2. Restart Claude Code completely (quit and reopen)
3. Check hook scripts are executable: `ls -la hooks/*.py`

### Reports not generating

1. Check for active session: `ls .nova-protector/sessions/`
2. Verify write permissions in project directory
3. Check stderr for errors during session end

### ML models not loading

First run downloads ~1GB of models. If issues occur:

```bash
# Clear model cache and retry
rm -rf ~/.cache/huggingface/
uv run hooks/test-nova-guard.py --samples
```

### AI summaries not working

1. Verify API key: `echo $ANTHROPIC_API_KEY`
2. Check `ai_summary_enabled: true` in config
3. Stats-only summaries are used as fallback

## Development

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_report_generator.py -v

# Run with coverage
uv run pytest tests/ --cov=hooks/lib
```

### Test Coverage

- 483 tests covering all functionality
- Session management, report generation, AI summaries
- Configuration loading, installation scripts
- All acceptance criteria verified

## License

MIT License - See [LICENSE](LICENSE)
