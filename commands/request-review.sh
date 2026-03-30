#!/bin/bash
# Request a protocol compliance review from GPT-5 Mini.
# Can be called manually or is auto-triggered by the stop hook.
#
# Usage:
#   bash ~/.claude/commands/request-review.sh
#   bash ~/.claude/commands/request-review.sh <session_id>

set -euo pipefail

HOOKS_DIR="$HOME/.claude/hooks"
UTILS_DIR="$HOOKS_DIR/utils"
DATA_DIR="$HOME/.claude/data"

# Resolve session ID from active_sessions.json
SESSION_ID="${1:-}"
if [ -z "$SESSION_ID" ]; then
    SESSION_ID=$(python3 -c "
import json, os, sys
from pathlib import Path

sessions_file = Path.home() / '.claude/data/active_sessions.json'
if not sessions_file.exists():
    print('default')
    sys.exit(0)

try:
    sessions = json.loads(sessions_file.read_text())
    cwd = os.getcwd()
    sid = sessions.get(cwd, 'default')
    print(sid)
except Exception:
    print('default')
" 2>/dev/null || echo "default")
fi

echo "Requesting protocol review for session: ${SESSION_ID:0:8}..."
echo ""

# Run the reviewer
python3 -c "
import sys, os
sys.path.insert(0, '$UTILS_DIR')
os.chdir('$(pwd)')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from reviewer import run_review, load_reviewer_config

config = load_reviewer_config()

if not os.getenv('OPENAI_API_KEY'):
    print('  OPENAI_API_KEY not set — reviewer cannot run.')
    print('  Set the key in .env or export it, then retry.')
    sys.exit(1)

if not config.enabled:
    print('  Reviewer is disabled in reviewer_config.json.')
    sys.exit(0)

result = run_review('$SESSION_ID')

if result.approved:
    print(f'  APPROVED (round {result.round_count})')
    print(f'  {result.summary}')
    if result.error:
        print(f'  Note: {result.error}')
    print('')
    print('  Reviewer approval written. You may now stop.')
else:
    print(f'  FINDINGS (round {result.round_count}/{config.max_rounds})')
    print('')
    for finding in result.findings:
        sev = 'BLOCK' if finding.get('severity') == 'blocking' else 'ADVSR'
        cat = finding.get('category', '?')
        desc = finding.get('description', '')
        print(f'  [{sev}] [{cat}] {desc}')
        if finding.get('evidence'):
            ev = finding['evidence'][:200]
            print(f'    Evidence: {ev}')
        if finding.get('evidence_needed'):
            print(f'    Needed: {finding[\"evidence_needed\"]}')
        print('')
    print(f'  Summary: {result.summary}')
    print('')
    print('  Address the blocking findings, then run this command again.')
"
