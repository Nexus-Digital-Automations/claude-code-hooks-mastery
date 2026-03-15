#!/bin/bash
# Record code/script/API execution evidence in verification_record.json.
# USE THIS WHENEVER CODE CAN BE RUN. If you modified a script, run it.
# If you modified a function, call it. If you built a tool, invoke it.
# Use REAL-WORLD inputs — replicate how the code is actually used in practice,
# not trivial/dummy calls. Only skip if execution is genuinely impossible
# (no interpreter, no valid test input available).
#
# Usage (pipe mode — preferred, works for any executable):
#   bash myscript.sh --arg value 2>&1 | bash ~/.claude/commands/check-api.sh
#   curl http://localhost:3000/api/health 2>&1 | bash ~/.claude/commands/check-api.sh
#   python -c "from mymodule import process; print(process({'x': 1}))" 2>&1 | bash ~/.claude/commands/check-api.sh
#   node -e "const fn = require('./fn'); console.log(fn(42))" 2>&1 | bash ~/.claude/commands/check-api.sh
#
# Usage (description mode — when execution output isn't capturable):
#   bash ~/.claude/commands/check-api.sh "ran sandbox-run.sh --check tests --cmd 'pytest', exit 0, ✅ Tests recorded"
#   bash ~/.claude/commands/check-api.sh "called POST /api/users with {email:...}, got 201 {id: 42}"
#
# Usage (skip — only when execution is genuinely impossible):
#   bash ~/.claude/commands/check-api.sh --skip "pure config/docs change, no executable code modified"

VR_FILE=".claude/data/verification_record.json"
CHECK_KEY="api"
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
        echo "   Example: bash ~/.claude/commands/check-api.sh --skip \"no API endpoints, pure CLI tool\"" >&2
        exit 1
    fi
    python3 -c "$UPDATE_PY" "$VR_FILE" "$CHECK_KEY" "skipped" "" "$REASON"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        exit 1
    fi
    echo "✅ API/code invocation skipped: $REASON"
elif [ ! -t 0 ]; then
    # Pipe mode: stdin is not a terminal
    OUTPUT=$(cat)
    if [ -z "$OUTPUT" ]; then
        echo "❌ No output received. Did you pipe your command?" >&2
        echo "   Example: curl http://localhost:3000/api/health 2>&1 | bash ~/.claude/commands/check-api.sh" >&2
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
    echo "✅ API/code invocation recorded"
else
    # Description mode
    DESCRIPTION="${1:-}"
    if [ -z "$DESCRIPTION" ] || [ "${#DESCRIPTION}" -lt 50 ]; then
        echo "❌ Description too short (min 50 chars). Include: what was run/called, what real-world input/args were used, what output was seen." >&2
        echo "   Example: bash ~/.claude/commands/check-api.sh \"ran check-api.sh with --skip flag, got ✅ message, exit 0\"" >&2
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
    echo "✅ API/code invocation recorded"
fi
