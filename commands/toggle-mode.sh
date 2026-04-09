#!/usr/bin/env bash
# Toggle between claude and qwen agent modes.
# Usage: bash toggle-mode.sh [claude|qwen]
#   No argument → toggle current mode
#   Argument    → set explicitly

set -euo pipefail

MODE_FILE="$HOME/.claude/data/agent_mode.json"

# Ensure data directory exists
mkdir -p "$(dirname "$MODE_FILE")"

# Read current mode (default: claude)
if [[ -f "$MODE_FILE" ]]; then
    CURRENT=$(python3 -c "import json; print(json.load(open('$MODE_FILE')).get('mode','claude'))" 2>/dev/null || echo "claude")
else
    CURRENT="claude"
fi

# Determine new mode
if [[ $# -ge 1 ]]; then
    case "$1" in
        claude|qwen)
            NEW="$1"
            ;;
        *)
            echo "Usage: toggle-mode.sh [claude|qwen]" >&2
            exit 1
            ;;
    esac
else
    # Toggle
    if [[ "$CURRENT" == "claude" ]]; then
        NEW="qwen"
    else
        NEW="claude"
    fi
fi

# Write updated mode file (preserve other fields)
python3 -c "
import json, sys
from datetime import datetime
from pathlib import Path

mode_file = Path('$MODE_FILE')
if mode_file.exists():
    try:
        data = json.loads(mode_file.read_text())
    except Exception:
        data = {}
else:
    data = {}

data['mode'] = '$NEW'
data['last_switched'] = datetime.now().isoformat()
data['preferred_provider'] = 'qwen' if '$NEW' == 'qwen' else ''
data.setdefault('qwen_profile', 'qwen3-delegation')
data.setdefault('qwen_plan_mode', True)
data.setdefault('delegation_policy', {
    'code_tasks': True,
    'research_tasks': False,
    'config_tasks': False,
    'docs_tasks': False,
})

mode_file.write_text(json.dumps(data, indent=2) + '\n')
"

echo "Mode switched to: $NEW (was: $CURRENT)"
