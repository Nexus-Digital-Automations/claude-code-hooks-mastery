#!/usr/bin/env bash
# Usage:
#   qwen-post-run-check.sh --snapshot    # call BEFORE run(), records HEAD SHA + mtimes
#   qwen-post-run-check.sh --check       # call AFTER run(), diffs and reports
#
# State file: ~/.claude/data/qwen_run_snapshot.json
#
# Purpose: When run() returns state != "completed" (e.g. timeout/running), the agent
# may continue writing files in the background. This script surfaces those mutations
# so they can be reviewed and either reverted or committed before code review proceeds.
set -euo pipefail

SNAPSHOT_FILE="$HOME/.claude/data/qwen_run_snapshot.json"
ACTION="${1:---check}"

case "$ACTION" in
  --snapshot)
    # Record HEAD SHA and timestamp
    HEAD_SHA=$(git rev-parse HEAD 2>/dev/null || echo "no-git")
    TIMESTAMP=$(date +%s)
    WORKING_DIR=$(pwd)
    printf '{"head_sha":"%s","timestamp":%s,"working_dir":"%s"}\n' \
      "$HEAD_SHA" "$TIMESTAMP" "$WORKING_DIR" > "$SNAPSHOT_FILE"
    echo "Snapshot recorded: $HEAD_SHA @ $TIMESTAMP"
    ;;

  --check)
    if [[ ! -f "$SNAPSHOT_FILE" ]]; then
      echo "No snapshot found — run with --snapshot before delegating."
      exit 1
    fi

    SNAPSHOT_DIR=$(python3 - "$SNAPSHOT_FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
print(d['working_dir'])
PYEOF
)
    HEAD_SHA=$(python3 - "$SNAPSHOT_FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
print(d['head_sha'])
PYEOF
)
    SNAPSHOT_TIME=$(python3 - "$SNAPSHOT_FILE" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
print(d['timestamp'])
PYEOF
)
    NOW=$(date +%s)
    ELAPSED=$(( NOW - SNAPSHOT_TIME ))

    echo "=== Qwen Post-Run File Check ==="
    echo "Working dir: $SNAPSHOT_DIR"
    echo "Snapshot: $HEAD_SHA (${ELAPSED}s ago)"
    echo ""

    # Check for uncommitted changes since snapshot
    pushd "$SNAPSHOT_DIR" > /dev/null
    MODIFIED=$(git diff --name-only HEAD 2>/dev/null || echo "")
    UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null || echo "")
    popd > /dev/null

    if [[ -z "$MODIFIED" && -z "$UNTRACKED" ]]; then
      echo "✓ No unexpected file mutations detected."
      rm -f "$SNAPSHOT_FILE"
      exit 0
    fi

    echo "⚠️  FILES MODIFIED AFTER run() RETURNED:"
    echo ""
    [[ -n "$MODIFIED" ]] && echo "Modified (tracked):" && echo "$MODIFIED" | sed 's/^/  /'
    [[ -n "$UNTRACKED" ]] && echo "New (untracked):" && echo "$UNTRACKED" | sed 's/^/  /'
    echo ""
    echo "ACTION REQUIRED:"
    echo "  • Review each file above — are these changes expected?"
    echo "  • If unexpected (post-timeout corruption): git checkout <files>"
    echo "  • If intentional: git add + commit with explanation"
    echo "  • Do NOT proceed with review until unexpected mutations are resolved."
    rm -f "$SNAPSHOT_FILE"
    exit 1
    ;;
  *)
    echo "Usage: $0 [--snapshot | --check]"
    exit 1
    ;;
esac
