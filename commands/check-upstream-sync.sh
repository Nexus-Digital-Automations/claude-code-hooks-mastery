#!/bin/bash
# Record upstream sync status in verification_record.json.
# Normally auto-run by static_checker.py via authorize-stop.sh.
# Manual skip: bash ~/.claude/commands/check-upstream-sync.sh --skip "not a fork"

SESSION_ID=$(python3 -c "
import sys; from pathlib import Path
sys.path.insert(0, str(Path.home() / '.claude/hooks/utils'))
from vr_utils import get_session_id; print(get_session_id())
" 2>/dev/null || echo "default")
VR_FILE="$HOME/.claude/data/verification_record_${SESSION_ID}.json"
CHECK_KEY="upstream_sync"
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
        echo "   Example: bash ~/.claude/commands/check-upstream-sync.sh --skip \"not a fork, no upstream remote\"" >&2
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
    echo "✅ Upstream sync skipped: $REASON"
elif [ "$1" = "--result" ]; then
    # Called by static_checker.py with pre-computed result string
    RESULT="${2:-}"
    if [ -z "$RESULT" ]; then
        echo "❌ --result requires a description" >&2
        exit 1
    fi
    TMPFILE=$(mktemp)
    printf '%s' "$RESULT" > "$TMPFILE"
    python3 -c "$UPDATE_PY" "$VR_FILE" "$CHECK_KEY" "done" "$TMPFILE" ""
    echo "✅ Upstream sync recorded"
else
    echo "ℹ️  upstream_sync is a static check — it auto-runs when you run authorize-stop.sh." >&2
    echo "   To skip: bash ~/.claude/commands/check-upstream-sync.sh --skip \"not a fork\"" >&2
    exit 1
fi