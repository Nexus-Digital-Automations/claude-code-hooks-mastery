#!/usr/bin/env bash
# Temporarily approve a spec file edit (one-time use, expires in 60 seconds)
set -euo pipefail

# Per-project state — see hooks/utils/project_config.py:get_project_data_dir.
HOME_CLAUDE="$HOME/.claude"
GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "$(pwd)")
if [ "$GIT_ROOT" = "$HOME_CLAUDE" ]; then
    DATA_DIR="$HOME_CLAUDE/data"
else
    DATA_DIR="$GIT_ROOT/.claude/data"
fi

APPROVAL_FILE="$DATA_DIR/spec_edit_approval.json"
mkdir -p "$DATA_DIR"

cat > "$APPROVAL_FILE" << EOF
{
  "approved": true,
  "timestamp": $(date +%s),
  "expires_at": $(( $(date +%s) + 60 ))
}
EOF

echo "Spec edit approved (expires in 60 seconds, one-time use)."
