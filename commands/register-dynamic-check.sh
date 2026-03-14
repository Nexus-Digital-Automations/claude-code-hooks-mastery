#!/bin/bash
# Register a project-specific dynamic check command.
# The command will be DeepSeek-reviewed, then auto-run by authorize-stop.sh.
#
# Usage:
#   bash ~/.claude/commands/register-dynamic-check.sh \
#     --check tests \
#     --command "pytest tests/ -v --tb=short" \
#     --pattern "passed" \
#     --description "Runs the pytest suite for this Django project"
#
# Valid --check keys: tests, build, app_starts, api, frontend

VALIDATOR="$HOME/.claude/hooks/utils/dynamic_validator.py"
DC_FILE=".claude/data/dynamic_checks.json"

CHECK_KEY=""
COMMAND=""
PATTERN=""
DESCRIPTION=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --check)       CHECK_KEY="$2";    shift 2 ;;
        --command)     COMMAND="$2";      shift 2 ;;
        --pattern)     PATTERN="$2";      shift 2 ;;
        --description) DESCRIPTION="$2"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 1 ;;
    esac
done

# Validate required args
if [ -z "$CHECK_KEY" ] || [ -z "$COMMAND" ] || [ -z "$PATTERN" ] || [ -z "$DESCRIPTION" ]; then
    echo "❌ Usage: register-dynamic-check.sh --check KEY --command CMD --pattern PATTERN --description TEXT" >&2
    echo "   Valid check keys: tests, build, app_starts, api, frontend" >&2
    exit 1
fi

if [ ! -f "$VALIDATOR" ]; then
    echo "❌ dynamic_validator.py not found at $VALIDATOR" >&2
    exit 1
fi

python3 "$VALIDATOR" \
    --pre-review \
    --check "$CHECK_KEY" \
    --command "$COMMAND" \
    --pattern "$PATTERN" \
    --description "$DESCRIPTION" \
    --dc-file "$DC_FILE"
