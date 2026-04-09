#!/bin/bash
# Provide Claude's answer to Qwen's clarifying question.
# Usage: bash ~/.claude/commands/answer-qwen.sh "your answer here"
#
# After running this, re-run authorize-stop to continue the review.

# Use agent_id for state file scoping (prevents cross-session contamination).
# Falls back to task_id for backward compatibility.
VR_UTILS="$HOME/.claude/hooks/utils"

# Get session_id for session-scoped file lookup
SESSION_ID=$(python3 -c "
import sys; sys.path.insert(0, '$VR_UTILS')
from vr_utils import get_session_id; print(get_session_id())
" 2>/dev/null || echo "default")

# Prefer agent_id from session-scoped identity file
SCOPE_ID=$(python3 -c "
import json
from pathlib import Path
sid = '$SESSION_ID'
# Try session-scoped first
f = Path.home() / f'.claude/data/agent_identity_{sid}.json'
if not f.exists():
    f = Path.home() / '.claude/data/agent_identity.json'
try:
    d = json.loads(f.read_text())
    aid = d.get('agent_id', '')
    if aid:
        print(aid)
    else:
        raise ValueError
except Exception:
    print('default')
" 2>/dev/null || echo "default")
STATE_FILE="$HOME/.claude/data/qwen_review_state_${SCOPE_ID}.json"
ANSWER="$1"

if [ -z "$ANSWER" ]; then
    echo "❌ Usage: answer-qwen.sh \"your answer here\"" >&2
    exit 1
fi

if [ ! -f "$STATE_FILE" ]; then
    echo "❌ No pending Qwen question found. Run authorize-stop first." >&2
    exit 1
fi

python3 - "$STATE_FILE" "$ANSWER" << 'PYEOF'
import json, sys
state_file, answer = sys.argv[1], sys.argv[2]
try:
    data = json.loads(open(state_file).read())
    msgs = data.get("messages", [])
    # Verify there's an open question (last assistant message starts with QUESTION:)
    last_asst = next(
        (m["content"] for m in reversed(msgs) if m["role"] == "assistant"), ""
    )
    # Allow responding after both questions AND rejection verdicts
    if not last_asst:
        print("❌ No conversation state found. Run authorize-stop first.", file=sys.stderr)
        sys.exit(1)
    # Detect what the last message was for better output messaging
    is_question = last_asst.strip().startswith("QUESTION:")
    msgs.append({"role": "user", "content": answer})
    data["messages"] = msgs
    open(state_file, "w").write(json.dumps(data, indent=2))
    if is_question:
        print("✅ Answer recorded. Re-run authorize-stop to continue the review.")
    else:
        print("✅ Additional context recorded. Re-run authorize-stop to continue the conversation.")
except Exception as e:
    print(f"❌ Failed to record answer: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
