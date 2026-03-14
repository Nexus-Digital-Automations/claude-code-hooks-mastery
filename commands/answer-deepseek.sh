#!/bin/bash
# Provide Claude's answer to DeepSeek's clarifying question.
# Usage: bash ~/.claude/commands/answer-deepseek.sh "your answer here"
#
# After running this, re-run authorize-stop to continue the review.

STATE_FILE=".claude/data/deepseek_review_state.json"
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
    if not last_asst.strip().startswith("QUESTION:"):
        print("❌ No pending question found in conversation state.", file=sys.stderr)
        sys.exit(1)
    msgs.append({"role": "user", "content": answer})
    data["messages"] = msgs
    open(state_file, "w").write(json.dumps(data, indent=2))
    print(f"✅ Answer recorded. Re-run authorize-stop to continue the review.")
except Exception as e:
    print(f"❌ Failed to record answer: {e}", file=sys.stderr)
    sys.exit(1)
PYEOF
