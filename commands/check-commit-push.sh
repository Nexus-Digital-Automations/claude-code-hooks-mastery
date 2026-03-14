#!/bin/bash
# Record git commit and push status in verification_record.json.
# Confirm what was committed, to which branch, and that it was pushed.
#
# Usage (committed and pushed):
#   bash ~/.claude/commands/check-commit-push.sh "committed 3 files on feat/my-feature, pushed to origin"
# Usage (skip with reason):
#   bash ~/.claude/commands/check-commit-push.sh --skip "no changes to commit — read-only task"

VR_FILE=".claude/data/verification_record.json"
CHECK_KEY="commit_push"
mkdir -p ".claude/data"

UPDATE_PY='
import json, sys, os
from datetime import datetime
vr_file, check_key, status, evidence_file, skip_reason = sys.argv[1:6]
skip_reason = skip_reason if skip_reason else None
evidence = None
if evidence_file and os.path.exists(evidence_file):
    with open(evidence_file) as ef:
        evidence = ef.read(2000).strip() or None
    try:
        os.unlink(evidence_file)
    except Exception:
        pass
try:
    with open(vr_file) as f:
        record = json.load(f)
except Exception:
    record = {"reset_at": datetime.now().isoformat(), "checks": {}}
checks = record.setdefault("checks", {})
checks[check_key] = {
    "status": status,
    "evidence": evidence,
    "timestamp": datetime.now().isoformat(),
    "skip_reason": skip_reason,
}
with open(vr_file, "w") as f:
    json.dump(record, f, indent=2)
'

if [ "$1" = "--skip" ]; then
    REASON="${2:-}"
    if [ -z "$REASON" ] || [ "${#REASON}" -lt 10 ]; then
        echo "❌ Skip reason required (min 10 chars)." >&2
        echo "   Example: bash ~/.claude/commands/check-commit-push.sh --skip \"no changes to commit — read-only task\"" >&2
        exit 1
    fi
    python3 -c "$UPDATE_PY" "$VR_FILE" "$CHECK_KEY" "skipped" "" "$REASON"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        exit 1
    fi
    echo "✅ Commit/push skipped: $REASON"
else
    DESCRIPTION="${1:-}"
    if [ -z "$DESCRIPTION" ] || [ "${#DESCRIPTION}" -lt 20 ]; then
        echo "❌ Description too short (min 20 chars). Include: what files, which branch, pushed/not pushed." >&2
        echo "   Example: bash ~/.claude/commands/check-commit-push.sh \"committed 2 files on main, pushed to origin\"" >&2
        exit 1
    fi
    TMPFILE=$(mktemp)
    printf '%s' "$DESCRIPTION" > "$TMPFILE"
    python3 -c "$UPDATE_PY" "$VR_FILE" "$CHECK_KEY" "done" "$TMPFILE" ""
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        rm -f "$TMPFILE"
        exit 1
    fi
    echo "✅ Commit/push recorded"
fi
