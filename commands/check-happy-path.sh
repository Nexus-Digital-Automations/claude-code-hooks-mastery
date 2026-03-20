#!/bin/bash
# Record happy path test description in verification_record.json.
# Description must be specific: what input, what action, what result you observed.
#
# Usage:
#   bash ~/.claude/commands/check-happy-path.sh "navigated to /login, entered test@example.com / password123, clicked submit, redirected to /dashboard, saw welcome message"
# Usage (skip with reason):
#   bash ~/.claude/commands/check-happy-path.sh --skip "config-only change, no user-facing happy path"

VR_FILE="$HOME/.claude/data/verification_record.json"
CHECK_KEY="happy_path"
mkdir -p "$HOME/.claude/data"

UPDATE_PY='
import json, sys, os
from datetime import datetime
vr_file, check_key, status, evidence_file, skip_reason = sys.argv[1:6]
evidence = None
if evidence_file and os.path.exists(evidence_file):
    with open(evidence_file) as ef:
        evidence = ef.read(8000).strip() or None
    try:
        os.unlink(evidence_file)
    except Exception:
        pass
_cur_sid = None
try:
    with open(os.path.expanduser("~/.claude/data/current_task.json")) as _ctf:
        _cur_sid = json.load(_ctf).get("session_id")
except Exception:
    pass
try:
    with open(vr_file) as f:
        record = json.load(f)
except Exception:
    record = {}
if _cur_sid and record.get("session_id") and record["session_id"] != _cur_sid:
    record = {"reset_at": datetime.now().isoformat(), "session_id": _cur_sid, "checks": {}}
record.setdefault("checks", {})[check_key] = {
    "status": status,
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "evidence": evidence,
    "skip_reason": skip_reason if skip_reason != "None" else None
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
    echo "✅ Happy path skipped"
else
    if [ -z "$1" ]; then
        echo "❌ Description required" >&2
        exit 1
    fi
    TMPFILE=$(mktemp)
    echo "$1" > "$TMPFILE"
    echo "$UPDATE_PY" | python3 - "$VR_FILE" "$CHECK_KEY" "passed" "$TMPFILE" "None"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        rm -f "$TMPFILE"
        exit 1
    fi
    echo "✅ Happy path recorded"
fi