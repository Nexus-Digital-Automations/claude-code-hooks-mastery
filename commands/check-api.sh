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
#   python -c "from mymodule import process; print(process('real_data'))" 2>&1 | bash ~/.claude/commands/check-api.sh
# Usage (skip with reason):
#   bash ~/.claude/commands/check-api.sh --skip "no executable code in this change"

VR_FILE="$HOME/.claude/data/verification_record.json"
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
record[check_key] = {
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
    echo "✅ API/code invocation skipped"
else
    TMPFILE=$(mktemp)
    cat > "$TMPFILE"
    echo "$UPDATE_PY" | python3 - "$VR_FILE" "$CHECK_KEY" "passed" "$TMPFILE" "None"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        rm -f "$TMPFILE"
        exit 1
    fi
    echo "✅ API/code invocation recorded"
fi