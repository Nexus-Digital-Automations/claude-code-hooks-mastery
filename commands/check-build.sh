#!/bin/bash
# Record build/compile results in verification_record.json.
# Usage (run build and pipe output):
#   npm run build 2>&1 | bash ~/.claude/commands/check-build.sh
#   cargo build 2>&1 | bash ~/.claude/commands/check-build.sh
#   tsc --noEmit 2>&1 | bash ~/.claude/commands/check-build.sh
# Usage (skip with reason):
#   bash ~/.claude/commands/check-build.sh --skip "Python script, no compile step"

VR_FILE="$HOME/.claude/data/verification_record.json"
CHECK_KEY="build"
mkdir -p "$HOME/.claude/data"

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
    echo "✅ Build skipped"
else
    TMPFILE=$(mktemp)
    cat > "$TMPFILE"
    echo "$UPDATE_PY" | python3 - "$VR_FILE" "$CHECK_KEY" "passed" "$TMPFILE" "None"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        rm -f "$TMPFILE"
        exit 1
    fi
    echo "✅ Build recorded"
fi