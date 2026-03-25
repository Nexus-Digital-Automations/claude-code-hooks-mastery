#!/usr/bin/env bash
# Parses a saved DeepSeek run() output file (written when token limit exceeded).
# Extracts: state, files_modified, budget_summary, final text messages.
#
# Usage: bash ~/.claude/commands/deepseek-parse-output.sh <path-to-output-file>
#
# When run() hits the token limit the full output is written to a file
# (e.g. tool-results/mcp-deepseek-agent-run-*.txt) and the tool returns a
# file-path error. This script reads that file and prints a clean summary
# instead of requiring manual jq queries.
set -euo pipefail

OUTPUT_FILE="${1:-}"
if [[ -z "$OUTPUT_FILE" || ! -f "$OUTPUT_FILE" ]]; then
  echo "Usage: $0 <path-to-output-file>"
  exit 1
fi

echo "=== DeepSeek Output Summary ==="
echo "File: $OUTPUT_FILE"
echo ""

# Extract top-level state
STATE=$(python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    print(data.get("state", "unknown"))
except Exception as e:
    print(f"parse-error: {e}")
PYEOF
)
echo "State: $STATE"

# Extract budget summary
python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    budget = data.get("budget_summary", {})
    if budget:
        print(f"API calls: {budget.get('api_calls', '?')}")
        print(f"Tokens: {budget.get('total_tokens', '?')}")
        print(f"Cost: ${budget.get('cost', '?')}")
        print(f"Iterations: {budget.get('iterations', '?')}")
    else:
        print("Budget: (not reported)")
except Exception as e:
    print(f"Budget parse error: {e}")
PYEOF

echo ""

# Extract files_modified list
python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    files = data.get("files_modified", [])
    if files:
        print(f"Files modified ({len(files)}):")
        for f in files:
            print(f"  {f}")
    else:
        print("Files modified: (none reported)")
except Exception as e:
    print(f"Files parse error: {e}")
PYEOF

echo ""

# Extract tool call stats
python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
from collections import Counter
try:
    data = json.load(open(sys.argv[1]))
    output = data.get("output", [])
    tool_calls = [e for e in output if e.get("kind") == "tool_call"]
    counts = Counter(e.get("content", {}).get("name", "unknown") for e in tool_calls)
    if counts:
        print("Tools used:")
        for name, n in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {name}: {n}")
    else:
        print("Tools used: (none)")
except Exception as e:
    print(f"Tool stats error: {e}")
PYEOF

echo ""

# Extract warnings
python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    output = data.get("output", [])
    warnings = [e for e in output if e.get("kind") == "warning"]
    if not warnings:
        print("Warnings: (none)")
    else:
        seen = set()
        unique = []
        for w in warnings:
            msg = str(w.get("content", ""))
            if msg not in seen:
                seen.add(msg)
                unique.append(msg)
        print(f"Warnings: {len(warnings)} total, {len(unique)} unique")
        for msg in unique[:3]:
            print(f"  {msg[:120]}")
except Exception as e:
    print(f"Warnings error: {e}")
PYEOF

echo ""

# Extract last meaningful text content
# Merges consecutive text_delta events into full messages, prints last 3 non-trivial ones.
python3 - "$OUTPUT_FILE" <<'PYEOF'
import json, sys
try:
    data = json.load(open(sys.argv[1]))
    output = data.get("output", [])

    # Merge consecutive text_delta events into full messages
    messages = []
    current_text = []
    for entry in output:
        etype = entry.get("kind", "")
        if etype == "text_delta":
            current_text.append(entry.get("content", ""))
        else:
            if current_text:
                messages.append({"kind": "text", "content": "".join(current_text)})
                current_text = []
            messages.append({"kind": etype, "content": str(entry)})
    if current_text:
        messages.append({"kind": "text", "content": "".join(current_text)})

    # Print last 3 non-trivial text messages (>50 chars)
    print("Last messages:")
    shown = 0
    for msg in reversed(messages):
        if msg["kind"] == "text" and len(msg["content"]) > 50:
            print(f"\n--- [{shown+1}] ---")
            print(msg["content"][:2000])
            shown += 1
            if shown >= 3:
                break
    if shown == 0:
        print("  (no substantial text messages found)")
except Exception as e:
    print(f"Messages parse error: {e}")
PYEOF
