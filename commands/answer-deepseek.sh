#!/bin/bash
# Provide Claude's answer to DeepSeek's clarifying question.
# Usage: bash ~/.claude/commands/answer-deepseek.sh "your answer here"
#
# After running this, re-run authorize-stop to continue the review.

TASK_ID=$(python3 -c "
import json, os
from pathlib import Path
ct = Path(os.path.expanduser('~/.claude/data/current_task.json'))
if ct.exists():
    try:
        d = json.loads(ct.read_text())
        print(d.get('task_id', 'default'))
    except Exception:
        print('default')
else:
    print('default')
" 2>/dev/null || echo "default")
STATE_FILE="$HOME/.claude/data/deepseek_review_state_${TASK_ID}.json"
ANSWER="$1"

if [ -z "$ANSWER" ]; then
    echo "❌ Usage: answer-deepseek.sh \"your answer here\"" >&2
    exit 1
fi

if [ ! -f "$STATE_FILE" ]; then
    echo "❌ No pending DeepSeek question found. Run authorize-stop first." >&2
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
