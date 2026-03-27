#!/bin/bash
# Record lint results in verification_record.json.
# Usage (run linter and pipe output):
#   npm run lint 2>&1 | bash ~/.claude/commands/check-lint.sh
#   ruff check . 2>&1 | bash ~/.claude/commands/check-lint.sh
#   cargo clippy 2>&1 | bash ~/.claude/commands/check-lint.sh
# Usage (skip with reason):
#   bash ~/.claude/commands/check-lint.sh --skip "no linter configured for this project"

SESSION_ID=$(python3 -c "
import sys; from pathlib import Path
sys.path.insert(0, str(Path.home() / '.claude/hooks/utils'))
from vr_utils import get_session_id; print(get_session_id())
" 2>/dev/null || echo "default")
VR_FILE="$HOME/.claude/data/verification_record_${SESSION_ID}.json"
CHECK_KEY="lint"
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
_session_id = None
try:
    # Try session-scoped current_task first, fall back to legacy global
    import glob as _cg
    _ct_candidates = sorted(_cg.glob(os.path.expanduser("~/.claude/data/current_task_*.json")), key=os.path.getmtime, reverse=True)
    _ct_path = _ct_candidates[0] if _ct_candidates else os.path.expanduser("~/.claude/data/current_task.json")
    with open(_ct_path) as _ctf:
        _ct = json.load(_ctf)
        _session_id = _ct.get("session_id")
except Exception:
    pass
try:
    with open(vr_file) as f:
        record = json.load(f)
except Exception:
    record = {}
record.setdefault("session_id", _session_id)
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
    echo "✅ Lint skipped"
else
    TMPFILE=$(mktemp)
    cat > "$TMPFILE"
    echo "$UPDATE_PY" | python3 - "$VR_FILE" "$CHECK_KEY" "passed" "$TMPFILE" "None"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to write verification record" >&2
        rm -f "$TMPFILE"
        exit 1
    fi
    echo "✅ Lint recorded"
fi