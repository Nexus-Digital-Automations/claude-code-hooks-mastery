#!/bin/bash
# Record frontend validation in verification_record.json.
# Requires actually running browser tests or opening the UI and verifying it works.
#
# Usage (pipe mode — preferred):
#   npx playwright test 2>&1 | bash ~/.claude/commands/check-frontend.sh
#   npm run test:e2e 2>&1 | bash ~/.claude/commands/check-frontend.sh
#
# Usage (description mode — when using MCP browser tools or Puppeteer manually):
#   bash ~/.claude/commands/check-frontend.sh "opened http://localhost:3000/dashboard, verified new Export button visible and clickable, clicked it, saw download dialog appear, checked browser console: zero errors"
#
# Usage (skip with reason):
#   bash ~/.claude/commands/check-frontend.sh --skip "no frontend, this is a backend-only service"

VR_FILE=".claude/data/verification_record.json"
CHECK_KEY="frontend"
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
        echo "   Example: bash ~/.claude/commands/check-frontend.sh --skip \"no frontend, backend-only service\"" >&2
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
    echo "✅ Frontend validation skipped: $REASON"
elif [ ! -t 0 ]; then
    # Pipe mode: stdin is not a terminal
    OUTPUT=$(cat)
    if [ -z "$OUTPUT" ]; then
        echo "❌ No output received. Did you pipe your command?" >&2
        echo "   Example: npx playwright test 2>&1 | bash ~/.claude/commands/check-frontend.sh" >&2
        exit 1
    fi
    TMPFILE=$(mktemp)
    printf '%s' "$OUTPUT" > "$TMPFILE"
    python3 -c "$UPDATE_PY" "$VR_FILE" "$CHECK_KEY" "done" "$TMPFILE" ""
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        rm -f "$TMPFILE"
        exit 1
    fi
    echo "✅ Frontend validation recorded"
else
    # Description mode
    DESCRIPTION="${1:-}"
    if [ -z "$DESCRIPTION" ] || [ "${#DESCRIPTION}" -lt 50 ]; then
        echo "❌ Description too short (min 50 chars). Include: URL visited, interactions performed, and whether console was clean." >&2
        echo "   Example: bash ~/.claude/commands/check-frontend.sh \"opened http://localhost:3000/dashboard, verified new Export button visible and clickable, saw download dialog, console: zero errors\"" >&2
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
    echo "✅ Frontend validation recorded"
fi
