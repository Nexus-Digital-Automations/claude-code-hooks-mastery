#!/bin/bash
# Authorize a one-time stop.
# Gate 1: 10-check verification gate — refuses if any items are still pending.
# Gate 2: DeepSeek conversational evidence review (if API key is set).
# Preserves security_scan_complete=true if the scan already passed this cycle.

VR_UTILS="$HOME/.claude/hooks/utils"

TASK_ID=$(python3 -c "
import sys; sys.path.insert(0, '$VR_UTILS')
from vr_utils import get_task_id; print(get_task_id())
" 2>/dev/null || echo "default")

AUTH_FILE="$HOME/.claude/data/stop_authorization.json"
VR_FILE="$HOME/.claude/data/verification_record_${TASK_ID}.json"
mkdir -p "$HOME/.claude/data"

# Auto-run static checks (upstream_sync, lint) for pending items
STATIC_CHECKER="$HOME/.claude/hooks/utils/static_checker.py"
if [ -f "$STATIC_CHECKER" ]; then
    python3 "$STATIC_CHECKER" --vr-file "$VR_FILE" --only-pending 2>/dev/null || true
fi

# Auto-skip non-static checks for design/analysis tasks (no files modified)
CONTEXT_FILE_EARLY="$HOME/.claude/data/deepseek_context_${TASK_ID}.json"
python3 -c "
import sys; sys.path.insert(0, '$VR_UTILS')
from vr_utils import auto_skip_design_task
skipped = auto_skip_design_task('$VR_FILE', '$CONTEXT_FILE_EARLY')
if skipped:
    print(f'  Design/analysis task — auto-skipped {skipped} checks (no files modified)')
" 2>/dev/null || true

# Auto-run registered dynamic checks
DYNAMIC_VALIDATOR="$HOME/.claude/hooks/utils/dynamic_validator.py"
DC_FILE_PATH="$HOME/.claude/data/dynamic_checks.json"
if [ -f "$DYNAMIC_VALIDATOR" ] && [ -f "$DC_FILE_PATH" ]; then
    python3 "$DYNAMIC_VALIDATOR" \
        --run \
        --dc-file "$DC_FILE_PATH" \
        --vr-file "$VR_FILE" \
        --only-pending 2>/dev/null || true
fi

# ── Gate 1: 10-check verification ──────────────────────────────────────────
python3 -c "
import sys; sys.path.insert(0, '$VR_UTILS')
from vr_utils import run_gate1_check
run_gate1_check('$AUTH_FILE', '$VR_FILE')
" || exit 1

# ── Gate 2: DeepSeek conversational evidence review ──────────────────────────
DEEPSEEK_VERIFIER="$HOME/.claude/hooks/utils/deepseek_verifier.py"
CONTEXT_FILE="$HOME/.claude/data/deepseek_context_${TASK_ID}.json"
DEEPSEEK_STATE="$HOME/.claude/data/deepseek_review_state_${TASK_ID}.json"

# Refresh deepseek_context.json from the current transcript
python3 -c "
import sys; sys.path.insert(0, '$VR_UTILS')
from vr_utils import refresh_deepseek_context
refresh_deepseek_context('$CONTEXT_FILE', '$VR_FILE')
" 2>/dev/null || true

# Clear stale rejection history (preserves pending QUESTIONs and user answers)
if [ -f "$DEEPSEEK_STATE" ]; then
    python3 -c "
import sys; sys.path.insert(0, '$VR_UTILS')
from vr_utils import cleanup_stale_state
cleanup_stale_state('$DEEPSEEK_STATE')
" 2>/dev/null || true
fi

if [ -f "$DEEPSEEK_VERIFIER" ]; then
    python3 "$DEEPSEEK_VERIFIER" \
        --vr-file "$VR_FILE" \
        --context-file "$CONTEXT_FILE" \
        --state-file "$DEEPSEEK_STATE" || exit 1
fi

# ── All gates passed — write authorized: true ────────────────────────────────
python3 -c "
import json
auth_file = '$AUTH_FILE'
try:
    with open(auth_file) as f:
        state = json.load(f)
except Exception:
    state = {}
state['authorized'] = True
with open(auth_file, 'w') as f:
    json.dump(state, f)
print('\n✅ Stop authorized.\n')
"

# Clear DeepSeek state so next task starts fresh
rm -f "$DEEPSEEK_STATE" "$CONTEXT_FILE"
