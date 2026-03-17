#!/usr/bin/env bash
# suggest-improvement.sh — Log a system improvement suggestion
# Usage: suggest-improvement.sh <type> "<title>" "<description>"
# Types: bug | friction | improvement

set -euo pipefail

SUGGESTIONS_FILE="$HOME/.claude/data/improvement_suggestions.json"
VALID_TYPES=("bug" "friction" "improvement")
MIN_TITLE_LEN=5
MIN_DESC_LEN=10

# ── Argument validation ──────────────────────────────────────────────────────

if [[ $# -lt 3 ]]; then
    echo "❌ Usage: suggest-improvement.sh <type> \"<title>\" \"<description>\"" >&2
    echo "   Types: bug | friction | improvement" >&2
    exit 1
fi

TYPE="$1"
TITLE="$2"
DESCRIPTION="$3"

# Validate type
valid=false
for t in "${VALID_TYPES[@]}"; do
    [[ "$TYPE" == "$t" ]] && valid=true && break
done
if [[ "$valid" == "false" ]]; then
    echo "❌ Invalid type '$TYPE'. Must be one of: bug, friction, improvement" >&2
    exit 1
fi

# Validate title length
if [[ ${#TITLE} -lt $MIN_TITLE_LEN ]]; then
    echo "❌ Title too short (minimum $MIN_TITLE_LEN chars): '$TITLE'" >&2
    exit 1
fi

# Validate description length
if [[ ${#DESCRIPTION} -lt $MIN_DESC_LEN ]]; then
    echo "❌ Description too short (minimum $MIN_DESC_LEN chars)" >&2
    exit 1
fi

# ── Ensure suggestions file exists ──────────────────────────────────────────

if [[ ! -f "$SUGGESTIONS_FILE" ]]; then
    echo "[]" > "$SUGGESTIONS_FILE"
fi

# ── Compute next ID ──────────────────────────────────────────────────────────

# Count existing entries and increment
COUNT=$(python3 -c "
import json, sys
try:
    data = json.load(open('$SUGGESTIONS_FILE'))
    print(len(data))
except Exception:
    print(0)
")
NEXT_NUM=$(( COUNT + 1 ))
ID=$(printf "IMP-%03d" "$NEXT_NUM")

# ── Build date ───────────────────────────────────────────────────────────────

DATE=$(date +%Y-%m-%d)

# ── Append entry ─────────────────────────────────────────────────────────────

python3 - <<PYEOF
import json, sys

path = "$SUGGESTIONS_FILE"
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    data = []

entry = {
    "id": "$ID",
    "date": "$DATE",
    "source": "claude_code",
    "type": "$TYPE",
    "title": """$TITLE""",
    "description": """$DESCRIPTION""",
    "status": "pending"
}

data.append(entry)

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print('✅ Suggestion $ID logged ($TYPE): "$TITLE"')
PYEOF
