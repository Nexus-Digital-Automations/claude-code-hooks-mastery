#!/bin/bash
# Authorize a one-time stop.
# Reads project config, auto-runs missing checks, then authorizes if all pass.

VR_UTILS="$HOME/.claude/hooks/utils"

SESSION_ID=$(python3 -c "
import sys; sys.path.insert(0, '$VR_UTILS')
from vr_utils import get_session_id; print(get_session_id())
" 2>/dev/null || echo "default")

AUTH_FILE="$HOME/.claude/data/stop_authorization_${SESSION_ID}.json"
VR_FILE="$HOME/.claude/data/verification_record_${SESSION_ID}.json"
mkdir -p "$HOME/.claude/data"

# Single Python call: auto-run missing, then gate check
python3 - "$SESSION_ID" "$VR_FILE" "$AUTH_FILE" "$VR_UTILS" << 'PYEOF'
import sys, json
from pathlib import Path

session_id, vr_path_str, auth_path_str, utils_dir = sys.argv[1:5]
sys.path.insert(0, utils_dir)

from project_config import get_git_root, load_config, get_required_checks, auto_run_missing
from vr_utils import VR_CHECKS_ORDER

project_root = Path(get_git_root())
config = load_config(project_root)
vr_file = Path(vr_path_str)
auth_file = Path(auth_path_str)

# Auto-run missing checks (lint, upstream_sync, tests if run_command configured)
results = auto_run_missing(session_id, config, vr_file, project_root)
for k, v in results.items():
    print(f"  auto-ran {k}: {v}")

# Read VR
try:
    record = json.loads(vr_file.read_text())
    checks = record.get("checks", {})
except Exception:
    checks = {}

# Determine if files were modified (heuristic: any non-pending check exists)
files_modified = any(
    checks.get(k, {}).get("status") not in ("pending", None)
    for k in ("tests", "build", "lint")
)
required = get_required_checks(config, files_modified=files_modified)

pending = []
done = []
for key, label in VR_CHECKS_ORDER:
    if key not in required:
        continue
    item = checks.get(key, {})
    status = item.get("status", "pending")
    if status == "pending":
        pending.append((key, label))
    else:
        ts = item.get("timestamp", "")
        ts_short = ts[11:16] if ts else "?"
        ev = (item.get("evidence") or item.get("skip_reason") or "")[:60].replace("\n", " ")
        done.append((key, label, status, ts_short, ev))

if pending:
    lines = [f"\n  Cannot authorize — {len(pending)} required check(s) missing:", ""]
    for key, label, status, ts_short, ev in done:
        mark = "\u2705" if status in ("done", "passed") else "\u23ed "
        lines.append(f'  {mark} {label:<18} [{status} @ {ts_short}] — "{ev}"')
    lines.append("")
    for key, label in pending:
        run_cmd = config.get("checks", {}).get(key, {}).get("run_command", "")
        hint = f" — run: {run_cmd}" if run_cmd else ""
        lines.append(f"  \u274c {label:<18} not verified{hint}")
    lines += ["", "Complete missing checks, then run authorize-stop again.", ""]
    print("\n".join(lines))
    sys.exit(1)

# All required checks passed
try:
    state = json.loads(auth_file.read_text())
except Exception:
    state = {}

lines = [f"\n\u2705 All {len(done)} required checks verified"]
for key, label, status, ts_short, ev in done:
    mark = "\u2705" if status in ("done", "passed") else "\u23ed "
    lines.append(f'   {mark} {label:<18} [{status} @ {ts_short}] — "{ev}"')

state["authorized"] = True
auth_file.write_text(json.dumps(state))
lines += ["", "\u2705 Stop authorized.", ""]
print("\n".join(lines))
PYEOF
