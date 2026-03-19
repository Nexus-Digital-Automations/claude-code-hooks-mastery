#!/bin/bash
# Authorize a one-time stop.
# Gate 1: 10-check verification gate — refuses if any items are still pending.
# Gate 2: DeepSeek conversational evidence review (if API key is set).
# Preserves security_scan_complete=true if the scan already passed this cycle.
AUTH_FILE="$HOME/.claude/data/stop_authorization.json"
VR_FILE="$HOME/.claude/data/verification_record.json"
mkdir -p "$HOME/.claude/data"

# Auto-run static checks (upstream_sync, lint) for pending items
STATIC_CHECKER="$HOME/.claude/hooks/utils/static_checker.py"
if [ -f "$STATIC_CHECKER" ]; then
    python3 "$STATIC_CHECKER" --vr-file "$VR_FILE" --only-pending 2>/dev/null || true
fi

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
python3 - "$AUTH_FILE" "$VR_FILE" << 'PYEOF'
import json, sys
from datetime import datetime

auth_file = sys.argv[1]
vr_file = sys.argv[2]

# ── Verification record check ───────────────────────────────────────────────

CHECKS_ORDER = [
    ("tests",        "TESTS              "),
    ("build",        "BUILD              "),
    ("lint",         "LINT               "),
    ("app_starts",   "APP STARTS         "),
    ("api",          "CODE/SCRIPT/API EXECUTION"),
    ("frontend",     "FRONTEND VALIDATION"),
    ("happy_path",   "HAPPY PATH         "),
    ("error_cases",  "ERROR CASES        "),
    ("commit_push",  "COMMIT & PUSH      "),
    ("upstream_sync","UPSTREAM SYNC      "),
]

RUN_CMDS = {
    "tests":       "pytest 2>&1 | bash ~/.claude/commands/check-tests.sh\n     npm test 2>&1 | bash ~/.claude/commands/check-tests.sh",
    "build":       "npm run build 2>&1 | bash ~/.claude/commands/check-build.sh\n     tsc --noEmit 2>&1 | bash ~/.claude/commands/check-build.sh",
    "lint":        "npm run lint 2>&1 | bash ~/.claude/commands/check-lint.sh\n     ruff check . 2>&1 | bash ~/.claude/commands/check-lint.sh",
    "app_starts":  "npm start 2>&1 | head -30 | bash ~/.claude/commands/check-app-starts.sh\n     python main.py 2>&1 | head -30 | bash ~/.claude/commands/check-app-starts.sh",
    "api":         "bash SCRIPT.sh --args 2>&1 | bash ~/.claude/commands/check-api.sh\n"
                   "     curl http://localhost:PORT/api/ENDPOINT 2>&1 | bash ~/.claude/commands/check-api.sh\n"
                   '     bash ~/.claude/commands/check-api.sh "ran X with args Y, got output Z (min 50 chars)"',
    "frontend":    'npx playwright test 2>&1 | bash ~/.claude/commands/check-frontend.sh\n     bash ~/.claude/commands/check-frontend.sh "opened http://..., verified X, clicked Y, saw Z, console: zero errors (min 50 chars)"',
    "happy_path":  'bash ~/.claude/commands/check-happy-path.sh "describe what you tested..."',
    "error_cases": 'bash ~/.claude/commands/check-error-cases.sh "describe error cases you tested..."',
    "commit_push": 'git add -p && git commit -m "msg" && git push\n     bash ~/.claude/commands/check-commit-push.sh "committed N files on branch X, pushed to origin"',
    "upstream_sync": (
        "# Auto-runs via static_checker.py — re-run authorize-stop to trigger.\n"
        '     bash ~/.claude/commands/check-upstream-sync.sh --skip "not a fork — no upstream remote"'
    ),
}

SKIP_CMDS = {
    "tests":       'bash ~/.claude/commands/check-tests.sh --skip "reason"',
    "build":       'bash ~/.claude/commands/check-build.sh --skip "reason"',
    "lint":        'bash ~/.claude/commands/check-lint.sh --skip "reason"',
    "app_starts":  'bash ~/.claude/commands/check-app-starts.sh --skip "reason"',
    "api":         'bash ~/.claude/commands/check-api.sh --skip "reason"',
    "frontend":    'bash ~/.claude/commands/check-frontend.sh --skip "reason"',
    "happy_path":  'bash ~/.claude/commands/check-happy-path.sh --skip "reason"',
    "error_cases": 'bash ~/.claude/commands/check-error-cases.sh --skip "reason"',
    "commit_push":  'bash ~/.claude/commands/check-commit-push.sh --skip "reason"',
    "upstream_sync": 'bash ~/.claude/commands/check-upstream-sync.sh --skip "not a fork — no upstream remote"',
}

DYNAMIC_CHECKS = {"tests", "build", "app_starts", "api", "frontend"}
STATIC_CHECKS = {"upstream_sync", "lint"}

# Load verification record
try:
    with open(vr_file) as f:
        record = json.load(f)
    checks = record.get("checks", {})
except Exception:
    checks = {}

# Load dynamic checks state
dc_file = str(Path.home() / ".claude/data/dynamic_checks.json")
try:
    with open(dc_file) as f:
        dc_data = json.load(f)
    dc_checks = dc_data.get("checks", {})
except Exception:
    dc_checks = {}

# Evaluate each item
pending = []
done = []
for key, label in CHECKS_ORDER:
    item = checks.get(key, {})
    status = item.get("status", "pending")
    if status == "pending":
        pending.append((key, label))
    else:
        ts = item.get("timestamp", "")
        ts_short = ts[11:16] if ts else "?"  # HH:MM
        ev = item.get("evidence") or item.get("skip_reason") or ""
        ev_short = ev[:60].replace("\n", " ") if ev else ""
        done.append((key, label, status, ts_short, ev_short))

if pending:
    lines = [
        "",
        "❌ Cannot authorize — verification incomplete:",
        "",
    ]
    # Show done items
    for key, label, status, ts_short, ev_short in done:
        mark = "✅" if status == "done" else "⏭ "
        ev_display = f' — "{ev_short}"' if ev_short else ""
        lines.append(f"  {mark} {label}  [{status} @ {ts_short}]{ev_display}")

    # Show pending items with smart context
    lines.append("")
    for key, label in pending:
        lines.append(f"  ❌ {label}  not verified")
        if key in STATIC_CHECKS:
            lines.append(f"     This check auto-runs — re-run authorize-stop to trigger it.")
            lines.append(f"     Or skip: {SKIP_CMDS[key]}")
        elif key in DYNAMIC_CHECKS:
            dc_entry = dc_checks.get(key, {})
            if dc_entry.get("deepseek_approved"):
                lines.append(f"     Registered: {dc_entry['command'][:70]}")
                lines.append(f"     Will auto-run — re-run authorize-stop.sh to execute it.")
            else:
                lines.append(f"     Option 1 — Register for auto-run (preferred):")
                lines.append(f'       bash ~/.claude/commands/register-dynamic-check.sh \\')
                lines.append(f'         --check {key} \\')
                lines.append(f'         --command "<your command>" \\')
                lines.append(f'         --pattern "<expected output substring>" \\')
                lines.append(f'         --description "<what this validates (min 20 chars)>"')
                lines.append(f"     Option 2 — Manual pipe (legacy):")
                lines.append(f"       {RUN_CMDS[key]}")
                lines.append(f"     Or skip: {SKIP_CMDS[key]}")
        else:
            lines.append(f"     Run: {RUN_CMDS[key]}")
            lines.append(f"     Or skip: {SKIP_CMDS[key]}")
        lines.append("")

    lines.append("Complete the missing items, then run authorize-stop again.")
    lines.append("")
    print("\n".join(lines))
    sys.exit(1)

# ── All 10 checks verified — print summary (auth write happens after DeepSeek gate) ──

try:
    with open(auth_file) as f:
        state = json.load(f)
except Exception:
    state = {}

scan_done = state.get("security_scan_complete", False)

# Print verified summary
lines = ["", "✅ All 10 checks verified"]
for key, label, status, ts_short, ev_short in done:
    mark = "✅" if status == "done" else "⏭ "
    ev_display = f' — "{ev_short}"' if ev_short else ""
    lines.append(f"   {mark} {label}  [{status} @ {ts_short}]{ev_display}")

if scan_done:
    lines.append("")
    lines.append("   (scan already passed — will proceed to stop)")
else:
    lines.append("")
    lines.append("   (security scan will run on next stop)")
lines.append("")
print("\n".join(lines))
PYEOF

# Exit if Gate 1 failed (PYEOF exited with non-zero)
[ $? -ne 0 ] && exit 1

# ── Gate 2: DeepSeek conversational evidence review ──────────────────────────
DEEPSEEK_VERIFIER="$HOME/.claude/hooks/utils/deepseek_verifier.py"
CONTEXT_FILE="$HOME/.claude/data/deepseek_context.json"
SESSION_ID=$(python3 -c "
import json, os
from pathlib import Path
vr = Path(os.path.expanduser('~/.claude/data/verification_record.json'))
if vr.exists():
    try:
        d = json.loads(vr.read_text())
        print(d.get('session_id', 'default'))
    except Exception:
        print('default')
else:
    print('default')
" 2>/dev/null || echo "default")
DEEPSEEK_STATE="$HOME/.claude/data/deepseek_review_state_${SESSION_ID}.json"

# Refresh deepseek_context.json from the current transcript before calling the
# verifier. The stop hook writes it once (and it goes stale); authorize-stop
# may be called many times after the agent runs more commands, so we need
# up-to-date bash_commands / files_modified for DeepSeek ground truth.
python3 - "$CONTEXT_FILE" "$VR_FILE" << 'REFRESH_EOF'
import json, sys
from pathlib import Path

context_file = Path(sys.argv[1])
vr_file = Path(sys.argv[2])

# Load existing context (created by stop hook) for non-bash fields
try:
    existing = json.loads(context_file.read_text())
except Exception:
    existing = {}

# Find transcript path from existing context (stop hook put it there) OR by
# scanning the most-recently-modified session JSONL in known locations.
transcript_path = existing.get("transcript_path", "")
if not transcript_path or not Path(transcript_path).exists():
    # Fallback: find most recent JSONL, filtered by session_id when available
    session_id = existing.get("session_id", "")
    candidates = sorted(
        Path.home().glob(".claude/projects/**/*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True
    )
    if session_id:
        matched = [p for p in candidates if session_id in p.name]
        transcript_path = str(matched[0]) if matched else ""
    else:
        transcript_path = str(candidates[0]) if candidates else ""

# Determine task start time from verification record
task_start_ts = ""
try:
    task_start_ts = json.loads(vr_file.read_text()).get("reset_at", "")
except Exception:
    pass

files_modified, bash_commands = [], []
if transcript_path and Path(transcript_path).exists():
    try:
        with open(transcript_path) as tf:
            for line in tf:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                if task_start_ts:
                    entry_ts = entry.get("timestamp", "")
                    if entry_ts and entry_ts < task_start_ts:
                        continue
                msg = entry.get("message", {})
                role = msg.get("role", "")
                content = msg.get("content", [])
                if role == "assistant" and isinstance(content, list):
                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "tool_use":
                            name = block.get("name", "")
                            inp = block.get("input", {}) or {}
                            if name in ("Edit", "Write", "MultiEdit"):
                                fp = inp.get("file_path", "")
                                if fp and fp not in files_modified:
                                    files_modified.append(fp)
                            elif name == "Bash":
                                cmd = (inp.get("command") or "").strip()
                                if cmd:
                                    bash_commands.append(cmd[:200])
        bash_commands = bash_commands[-30:]
    except Exception:
        pass

# Merge: keep existing fields, overwrite bash_commands + files_modified
existing["bash_commands"] = bash_commands
existing["files_modified"] = files_modified
context_file.write_text(json.dumps(existing, indent=2))
REFRESH_EOF

if [ -f "$DEEPSEEK_VERIFIER" ]; then
    python3 "$DEEPSEEK_VERIFIER" \
        --vr-file "$VR_FILE" \
        --context-file "$CONTEXT_FILE" \
        --state-file "$DEEPSEEK_STATE" || exit 1
fi

# ── All gates passed — write authorized: true ────────────────────────────────
python3 - "$AUTH_FILE" << 'AUTHEOF'
import json, sys
auth_file = sys.argv[1]
try:
    with open(auth_file) as f:
        state = json.load(f)
except Exception:
    state = {}
state["authorized"] = True
with open(auth_file, "w") as f:
    json.dump(state, f)
print("\n✅ Stop authorized.\n")
AUTHEOF

# Clear DeepSeek state so next task starts fresh
rm -f "$DEEPSEEK_STATE" "$CONTEXT_FILE"
