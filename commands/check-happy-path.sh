#!/bin/bash
# Record happy path test description in verification_record.json.
# Description must be specific: what input, what action, what result you observed.
#
# Usage:
#   bash ~/.claude/commands/check-happy-path.sh "navigated to /login, entered test@example.com / password123, clicked submit, redirected to /dashboard, saw welcome message"
# Usage (skip with reason):
#   bash ~/.claude/commands/check-happy-path.sh --skip "config-only change, no user-facing happy path"

VR_FILE=".claude/data/verification_record.json"
CHECK_KEY="happy_path"
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
        echo "   Example: bash ~/.claude/commands/check-happy-path.sh --skip \"config-only change, no user-facing happy path\"" >&2
        exit 1
    fi
    # Reject "pre-existing" and similar cop-out skip reasons
    _REASON_LOWER=$(echo "$REASON" | tr '[:upper:]' '[:lower:]')
    if echo "$_REASON_LOWER" | grep -qE 'pre.?exist|already.fail|was.fail|before.my.change|before.this.change|not.caused.by|unrelated.to.my'; then
        echo "❌ Skip reason rejected: 'pre-existing failures' is not a valid reason." >&2
        echo "   Fix the failures, or use a specific reason with documented user approval." >&2
        exit 1
    fi
    python3 -c "$UPDATE_PY" "$VR_FILE" "$CHECK_KEY" "skipped" "" "$REASON"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        exit 1
    fi
    echo "✅ Happy path skipped: $REASON"
else
    if [ -n "$1" ]; then
        DESCRIPTION="$1"
    else
        DESCRIPTION=$(cat)
    fi
    if [ -z "$DESCRIPTION" ] || [ "${#DESCRIPTION}" -lt 150 ]; then
        echo "❌ Description too short (min 150 chars). Must demonstrate EACH requested feature." >&2
        echo "   Example: 'created deck, added 2 cards via modal, ran quiz (Q: What is 7×8? → A: 56, Got It), deleted card (count updated 2→1), edited card question (saved + visible), Due Today mode showed 1 due card'" >&2
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
    echo "✅ Happy path recorded"
fi
