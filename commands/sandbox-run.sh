#!/bin/bash
# Run a command in a tracked execution sandbox.
#
# Runs the command, captures stdout+stderr+exit code, writes a timestamped entry
# to .claude/data/sandbox_executions.json, and pipes formatted evidence to the
# appropriate check-*.sh script.
#
# Qwen reviewer sees:
#   1. This command in the session's bash history (it ran)
#   2. The sandbox_executions.json log (exact command + exit code + output)
#   3. The formatted evidence in verification_record.json
#
# Usage (command):
#   bash ~/.claude/commands/sandbox-run.sh --check tests \
#     --cmd "pytest tests/ -v --tb=short 2>&1"
#
# Usage (description, when no runnable command exists):
#   bash ~/.claude/commands/sandbox-run.sh --check happy_path \
#     --desc "called fn(x=5), got expected_value, confirmed no exception"
#
# Valid --check keys:
#   tests, build, lint, app_starts, api, frontend, happy_path, error_cases

set -euo pipefail

CHECK_KEY=""
COMMAND=""
DESC_TEXT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) CHECK_KEY="$2"; shift 2 ;;
        --cmd)   COMMAND="$2";   shift 2 ;;
        --desc)  DESC_TEXT="$2"; shift 2 ;;
        *)       echo "❌ Unknown argument: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$CHECK_KEY" ]]; then
    echo "❌ --check KEY is required" >&2
    echo "   Valid check keys: tests, build, lint, app_starts, api, frontend, happy_path, error_cases" >&2
    exit 1
fi
if [[ -z "$COMMAND" && -z "$DESC_TEXT" ]]; then
    echo "❌ Either --cmd COMMAND or --desc DESCRIPTION is required" >&2
    exit 1
fi
if [[ -n "$COMMAND" && -n "$DESC_TEXT" ]]; then
    echo "❌ Use --cmd OR --desc, not both" >&2
    exit 1
fi

# Map check key → check script name (replace _ with -)
SCRIPT_NAME="check-${CHECK_KEY//_/-}.sh"
SCRIPT_PATH="$HOME/.claude/commands/$SCRIPT_NAME"

if [[ ! -f "$SCRIPT_PATH" ]]; then
    echo "❌ No check script found for key '$CHECK_KEY' (looked for $SCRIPT_PATH)" >&2
    exit 1
fi

SANDBOX_LOG=".claude/data/sandbox_executions.json"
mkdir -p ".claude/data"

TIMESTAMP=$(date -u '+%Y-%m-%dT%H:%M:%S')

# Arg-based check scripts — dual-mode now (accept stdin OR $1), but keep
# routing as defensive fallback so old check scripts also work.
ARG_BASED="happy_path error_cases"

if [[ -n "$DESC_TEXT" ]]; then
    # --desc path: no command runs; log with null exit_code; call script with $1
    echo "▶ sandbox-run [${CHECK_KEY}]: (description)" >&2

    export _SANDBOX_CHECK="$CHECK_KEY"
    export _SANDBOX_CMD=""
    export _SANDBOX_TS="$TIMESTAMP"
    export _SANDBOX_RC="-1"
    export _SANDBOX_OUT="$DESC_TEXT"
    python3 - <<'PYEOF'
import json, os
from pathlib import Path

log_file = Path(".claude/data/sandbox_executions.json")
try:
    data = json.loads(log_file.read_text())
except Exception:
    data = {"executions": []}

rc = os.environ["_SANDBOX_RC"]
data.setdefault("executions", []).append({
    "check": os.environ["_SANDBOX_CHECK"],
    "command": None,
    "timestamp": os.environ["_SANDBOX_TS"],
    "exit_code": None,
    "stdout": os.environ.get("_SANDBOX_OUT", "")[:2000],
})

log_file.write_text(json.dumps(data, indent=2))
PYEOF

    bash "$SCRIPT_PATH" "$DESC_TEXT"

else
    # --cmd path: run command, capture output, log, then call check script
    echo "▶ sandbox-run [${CHECK_KEY}]: ${COMMAND:0:80}..." >&2

    OUTPUT=$(bash -c "$COMMAND" 2>&1)
    EXIT_CODE=$?

    export _SANDBOX_CHECK="$CHECK_KEY"
    export _SANDBOX_CMD="$COMMAND"
    export _SANDBOX_TS="$TIMESTAMP"
    export _SANDBOX_RC="$EXIT_CODE"
    export _SANDBOX_OUT="$OUTPUT"
    python3 - <<'PYEOF'
import json, os
from pathlib import Path

log_file = Path(".claude/data/sandbox_executions.json")
try:
    data = json.loads(log_file.read_text())
except Exception:
    data = {"executions": []}

data.setdefault("executions", []).append({
    "check": os.environ["_SANDBOX_CHECK"],
    "command": os.environ["_SANDBOX_CMD"],
    "timestamp": os.environ["_SANDBOX_TS"],
    "exit_code": int(os.environ["_SANDBOX_RC"]),
    "stdout": os.environ.get("_SANDBOX_OUT", "")[:2000],
})

log_file.write_text(json.dumps(data, indent=2))
PYEOF

    EVIDENCE=$(printf '[sandbox @ %s]\n$ %s\nexit: %d\n---\n%s' \
        "$TIMESTAMP" "$COMMAND" "$EXIT_CODE" "$OUTPUT")

    # Route: pipe for stdin-based scripts; arg for arg-based scripts (defensive fallback)
    if [[ " $ARG_BASED " =~ " $CHECK_KEY " ]]; then
        bash "$SCRIPT_PATH" "$EVIDENCE"
    else
        printf '%s' "$EVIDENCE" | bash "$SCRIPT_PATH"
    fi

    if [[ $EXIT_CODE -eq 0 ]]; then
        echo "✅ Command exited 0" >&2
    else
        echo "⚠️  Command exited $EXIT_CODE" >&2
    fi
fi
