#!/bin/bash
# Record error/edge case test description in verification_record.json.
# Description must be specific: what bad input, what error was expected, what happened.
#
# Usage:
#   bash ~/.claude/commands/check-error-cases.sh "submitted login form with wrong password, got 401 error displayed, tried empty email, got validation error, browser console had zero errors"
# Usage (skip with reason):
#   bash ~/.claude/commands/check-error-cases.sh --skip "internal utility with no user-facing error states"

VR_FILE="$HOME/.claude/data/verification_record.json"
CHECK_KEY="error_cases"
mkdir -p ".claude/data"

UPDATE_PY='
import json, sys, os
from datetime import datetime
vr_file, check_key, status, evidence_file, skip_reason = sys.argv[1:6]
skip_reason = skip_reason if skip_reason else None
evidence = None
if evidence_file and os.path.exists(evidence_file):
    with open(evidence_file) as ef:
        evidence = ef.read(8000).strip() or None
    try:
        os.unlink(evidence_file)
    except Exception:
        pass
try:
    with open(vr_file) as f:
        record = json.load(f)
except Exception:
    record = {}
record.setdefault("checks", {})[check_key] = {
    "status": status,
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "evidence": evidence,
    "skip_reason": skip_reason
}
with open(vr_file, "w") as f:
    json.dump(record, f, indent=2)
'

if [ "$1" = "--skip" ]; then
    if [ -z "$2" ]; then
        echo "❌ Skip reason required" >&2
        exit 1
    fi
    echo "$UPDATE_PY" | python3 - "$VR_FILE" "$CHECK_KEY" "skipped" "None" "$2"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        exit 1
    fi
    echo "✅ Error cases skipped"
elif [ -n "$1" ]; then
    # description mode
    echo "$UPDATE_PY" | python3 - "$VR_FILE" "$CHECK_KEY" "passed" "None" "None"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        exit 1
    fi
    echo "✅ Error cases recorded (description mode)"
else
    # pipe mode
    TMPFILE=$(mktemp)
    cat > "$TMPFILE"
    echo "$UPDATE_PY" | python3 - "$VR_FILE" "$CHECK_KEY" "passed" "$TMPFILE" "None"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        rm -f "$TMPFILE"
        exit 1
    fi
    echo "✅ Error cases recorded"
fi