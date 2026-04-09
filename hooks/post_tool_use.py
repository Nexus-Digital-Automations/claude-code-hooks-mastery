#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import re
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Add hooks directory to path for utils imports
sys.path.insert(0, str(Path(__file__).parent))

# Fix Python environment warnings
for var in ['PYTHONHOME', 'PYTHONPATH']:
    if var in os.environ:
        del os.environ[var]

# Linter commands by file extension
LINTER_MAP = {
    # Python
    '.py': ['ruff', 'check', '--output-format=concise'],

    # JavaScript/TypeScript
    '.js': ['eslint', '--format=stylish'],
    '.ts': ['eslint', '--format=stylish'],
    '.tsx': ['eslint', '--format=stylish'],
    '.jsx': ['eslint', '--format=stylish'],

    # Go
    '.go': ['go', 'vet'],

    # Rust
    '.rs': ['cargo', 'clippy', '--message-format=short', '--'],

    # C/C++
    '.c': ['clang-tidy'],
    '.cpp': ['clang-tidy'],
    '.cc': ['clang-tidy'],
    '.cxx': ['clang-tidy'],
    '.h': ['clang-tidy'],
    '.hpp': ['clang-tidy'],

    # C#
    '.cs': ['dotnet', 'format', '--verify-no-changes'],
}


def _handle_background_app_starts(command: str, stdout: str, stderr: str) -> str:
    """Evaluate app_starts for commands that appear to be backgrounded.

    When a command ends with ' &' or contains '&>' (redirect), the process
    runs in background and the Bash tool captures only the shell's job-control
    output (e.g. '[1] 12345'), not the app's startup messages.

    Strategy:
    1. If a redirect file is specified (&>/tmp/foo.log), try reading it.
    2. Otherwise, check only for explicit fail patterns; absent those, return
       "passed" because the process was successfully spawned.
    """
    combined = stdout + "\n" + stderr
    app_fail_patterns = ["EADDRINUSE", "Error:", "Cannot find", "command not found"]
    app_pass_patterns = [r"listening", r"started", r"ready", r"running"]

    # Try to read the redirect file (e.g. &>/tmp/server.log)
    redirect_match = re.search(r'&>\s*(\S+)', command)
    if redirect_match:
        redirect_path = redirect_match.group(1).rstrip('&').strip()
        try:
            redirect_file = Path(redirect_path)
            if redirect_file.exists():
                file_content = redirect_file.read_text(errors='replace')[:2000]
                if file_content.strip():
                    # Re-evaluate using file content
                    for fp in app_fail_patterns:
                        if fp.lower() in file_content.lower():
                            return "failed"
                    for pp in app_pass_patterns:
                        if re.search(pp, file_content, re.IGNORECASE):
                            return "passed"
        except Exception:
            pass

    # No file content available — check combined output for explicit failures only
    for fp in app_fail_patterns:
        if fp.lower() in combined.lower():
            return "failed"

    # Background process spawned with no error evidence → passed
    return "passed"


def _detect_git_push_from_output(
    session_id: str, command: str, stdout: str, stderr: str, vr_file: Path
) -> None:
    """Detect git push that ran inside a shell script by scanning its output.

    When 'bash scripts/deploy.sh' calls 'git push' internally, the hook only
    sees the outer command. This function looks for git push output signatures
    in stdout/stderr to infer a successful push, then writes VR commit_push.
    """
    try:
        combined = stdout + "\n" + stderr

        # Git push output signatures (any of these indicates a push occurred)
        _PUSH_SIGS = [
            r"To (?:git@|https?://)",      # "To github.com:user/repo"
            r"\b\w+\s+->\s+\w+\b",         # "main -> main"
            r"remote: Resolving deltas",
            r"remote: Counting objects",
            r"Branch .+ set up to track",
        ]
        push_detected = any(re.search(p, combined, re.IGNORECASE) for p in _PUSH_SIGS)
        if not push_detected:
            return

        # Reject if push clearly failed
        if any(p in combined.lower() for p in ["rejected", "error: failed", "error: src refspec"]):
            return

        # Verify the push actually landed via rev-list (same as normal push handler)
        try:
            branch_r = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True, text=True, timeout=5,
            )
            branch = branch_r.stdout.strip() or "main"
            rev_r = subprocess.run(
                ["git", "rev-list", f"origin/{branch}...HEAD", "--count"],
                capture_output=True, text=True, timeout=5,
            )
            unpushed = int(rev_r.stdout.strip() or "0")
            if unpushed > 0:
                return  # Commits still local — push didn't land
        except Exception:
            pass  # Proceed even if we can't verify rev-list

        # Load/update commit_push state
        state_file = Path.home() / f".claude/data/commit_push_state_{session_id}.json"
        state = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except Exception:
                pass

        state["push_observed"] = True
        state["push_evidence"] = (
            f"Detected from script output: {command[:100]}\n"
            f"{combined[:300]}"
        )

        # Infer commit from git show (push implies a commit exists)
        if not state.get("commit_observed"):
            try:
                show_r = subprocess.run(
                    ["git", "show", "--name-only", "--format="],
                    capture_output=True, text=True, timeout=5,
                )
                committed_files = [
                    f.strip() for f in show_r.stdout.strip().split("\n") if f.strip()
                ]
                if committed_files:
                    state["commit_observed"] = True
                    state["commit_evidence"] = (
                        f"Inferred from script push: "
                        f"{len(committed_files)} file(s): {', '.join(committed_files[:5])}"
                    )
            except Exception:
                state["commit_observed"] = True
                state["commit_evidence"] = "Inferred from push output in script"

        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state))

        # Write VR when both commit + push are observed
        if state.get("commit_observed") and state.get("push_observed"):
            from utils.vr_utils import write_vr
            evidence = (
                f"[auto via script] {command[:100]}\n"
                f"commit: {state.get('commit_evidence', '')}\n"
                f"push: {state.get('push_evidence', '')}"
            )
            write_vr(vr_file, "commit_push", "passed", evidence, session_id=session_id)
    except Exception:
        pass  # Never block the hook


def observe_bash_check(session_id: str, tool_input: dict, tool_response) -> None:
    """Auto-record verification checks by observing Bash command outputs.

    Matches the command against the project's .claude-project.json config
    (or generic fallback patterns) and writes to the verification record.
    Never raises — observation is best-effort.
    """
    try:
        from utils.project_config import get_git_root, load_config, match_command, evaluate_output
        from utils.vr_utils import write_vr

        command = (tool_input.get("command") or "").strip()
        if not command:
            return

        # Extract stdout/stderr from tool_response (format varies)
        if isinstance(tool_response, dict):
            stdout = tool_response.get("stdout", "") or ""
            stderr = tool_response.get("stderr", "") or ""
        elif isinstance(tool_response, str):
            stdout = tool_response
            stderr = ""
        else:
            stdout = str(tool_response) if tool_response else ""
            stderr = ""

        project_root = Path(get_git_root())
        config = load_config(project_root)
        result = match_command(command, config)
        if not result:
            return

        check_key, check_conf = result
        vr_file = Path.home() / f".claude/data/verification_record_{session_id}.json"

        # commit_push needs both git commit + git push
        if check_key == "commit_push":
            _handle_commit_push(session_id, command, stdout, stderr, vr_file)
            # Still scan output for push signatures (belt-and-suspenders)
            _detect_git_push_from_output(session_id, command, stdout, stderr, vr_file)
            return

        # Check for non-zero exit code in tool response
        # Claude Code Bash tool includes "Exit code N" on failure
        exit_code = None
        raw = stdout if isinstance(tool_response, str) else str(tool_response)
        if "Exit code" in raw:
            for line in raw.split("\n"):
                stripped = line.strip()
                if stripped.startswith("Exit code"):
                    try:
                        exit_code = int(stripped.split()[-1])
                    except (ValueError, IndexError):
                        pass
                    break

        # app_starts: backgrounded commands need special handling
        if check_key == "app_starts":
            cmd_trimmed = command.rstrip()
            if cmd_trimmed.endswith('&') or '&>' in command:
                status = _handle_background_app_starts(command, stdout, stderr)
            else:
                status = evaluate_output(stdout, stderr, check_conf)
        else:
            status = evaluate_output(stdout, stderr, check_conf)

        # Non-zero exit code overrides pattern-based pass to failed
        if exit_code is not None and exit_code != 0 and status == "passed":
            status = "failed"

        evidence = f"[auto] $ {command[:200]}"
        if exit_code is not None:
            evidence += f"\nexit_code={exit_code}"
        evidence += f"\n{stdout[:1500]}"
        if stderr.strip():
            evidence += f"\nstderr: {stderr[:300]}"
        write_vr(vr_file, check_key, status, evidence, session_id=session_id)

        # Secondary: scan output for git push signatures (catches git push inside scripts)
        _detect_git_push_from_output(session_id, command, stdout, stderr, vr_file)
    except Exception:
        pass  # Never block the hook


def _handle_commit_push(session_id: str, command: str, stdout: str, stderr: str, vr_file: Path) -> None:
    """Track git commit + git push as two sub-states for the commit_push check.

    Verifications beyond pattern matching:
    - Commit: checks git show --name-only to reject empty commits
    - Push: checks git rev-list to verify commits actually reached the remote
    """
    try:
        from utils.vr_utils import write_vr

        state_file = Path.home() / f".claude/data/commit_push_state_{session_id}.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        state = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except Exception:
                state = {}

        cmd_lower = command.lower()
        combined = stdout + "\n" + stderr

        if "git commit" in cmd_lower and "git commit --amend" not in cmd_lower:
            if any(p in combined.lower() for p in ["files changed", "insertion", "create mode", "file changed"]):
                # Verify commit is not empty
                try:
                    show_r = subprocess.run(
                        ["git", "show", "--name-only", "--format="],
                        capture_output=True, text=True, timeout=5,
                    )
                    committed_files = [f.strip() for f in show_r.stdout.strip().split("\n") if f.strip()]
                    if committed_files:
                        state["commit_observed"] = True
                        state["commit_evidence"] = (
                            f"$ {command[:100]}\n"
                            f"{len(committed_files)} file(s): {', '.join(committed_files[:5])}"
                        )
                    else:
                        state["commit_observed"] = False
                        state["commit_evidence"] = "Commit was empty — no files"
                except Exception:
                    # Fallback: trust output-based check
                    state["commit_observed"] = True
                    state["commit_evidence"] = f"$ {command[:100]}\n{stdout[:300]}"

        if "git push" in cmd_lower and "--dry-run" not in cmd_lower:
            if "rejected" not in combined.lower() and "error" not in combined.lower():
                # Verify push actually landed via rev-list
                try:
                    branch_r = subprocess.run(
                        ["git", "branch", "--show-current"],
                        capture_output=True, text=True, timeout=5,
                    )
                    branch = branch_r.stdout.strip() or "main"
                    rev_r = subprocess.run(
                        ["git", "rev-list", f"origin/{branch}...HEAD", "--count"],
                        capture_output=True, text=True, timeout=5,
                    )
                    unpushed = int(rev_r.stdout.strip() or "0")
                    if unpushed == 0:
                        state["push_observed"] = True
                        state["push_evidence"] = (
                            f"$ {command[:100]}\n"
                            f"Verified: 0 unpushed commits on {branch}"
                        )
                    else:
                        state["push_observed"] = False
                        state["push_evidence"] = f"Push ran but {unpushed} commit(s) still unpushed"
                except Exception:
                    # Fallback: trust output-based check
                    state["push_observed"] = True
                    state["push_evidence"] = f"$ {command[:100]}\n{stdout[:300]}"

        state_file.write_text(json.dumps(state))

        # Write VR when both are observed
        if state.get("commit_observed") and state.get("push_observed"):
            evidence = (
                f"[auto] commit: {state.get('commit_evidence', '')}\n"
                f"push: {state.get('push_evidence', '')}"
            )
            write_vr(vr_file, "commit_push", "passed", evidence, session_id=session_id)
    except Exception:
        pass


# ── VR invalidation on code edit ──────────────────────────────────────────
# File extension → check keys to reset when that extension is edited.
# Editing source code after tests passed means tests must re-run.

_SOURCE_EXTS = frozenset((
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".rb", ".java", ".cs", ".cpp", ".c", ".h",
))
_FRONTEND_EXTS = frozenset((".tsx", ".jsx", ".css", ".scss", ".html", ".vue", ".svelte"))
_CONFIG_FILES = frozenset((
    "package.json", "tsconfig.json", "Cargo.toml", "pyproject.toml",
    "go.mod", "webpack.config.js", "vite.config.js", "vite.config.ts",
))


def _invalidate_stale_checks(session_id: str, file_path: str) -> None:
    """Reset verification checks that are stale due to a code edit.

    When source files change after a check was recorded, those checks
    must re-run to verify the new code. Never raises.
    """
    try:
        if not file_path:
            return

        ext = Path(file_path).suffix.lower()
        name = Path(file_path).name
        parts = Path(file_path).parts

        # Detect if this is a test file (smarter regression)
        _is_test_file = (
            "test" in name.lower()
            or "spec" in name.lower()
            or any(p in ("tests", "test", "__tests__", "spec", "specs") for p in parts)
        )

        # Determine which checks to invalidate
        to_invalidate: set[str] = set()
        if ext in _SOURCE_EXTS:
            if _is_test_file:
                # Test file edits only invalidate tests — not lint/typecheck/build
                to_invalidate.add("tests")
            else:
                # Production source edits invalidate more broadly
                to_invalidate.update(["tests", "typecheck", "execution", "happy_path", "security"])
        if ext in _FRONTEND_EXTS:
            to_invalidate.add("frontend")
        if name in _CONFIG_FILES:
            to_invalidate.add("build")

        if not to_invalidate:
            return

        vr_file = Path.home() / f".claude/data/verification_record_{session_id}.json"
        if not vr_file.exists():
            return

        record = json.loads(vr_file.read_text())

        # Session guard
        if record.get("session_id") and record["session_id"] != session_id:
            return

        checks = record.get("checks", {})
        changed = False
        now = datetime.now().isoformat()

        for key in to_invalidate:
            item = checks.get(key, {})
            status = item.get("status", "pending")
            if status in ("pending", None):
                continue  # Already pending, nothing to invalidate
            # Don't invalidate checks recorded within the last 2 seconds
            # (avoids race with the current tool invocation)
            ts = item.get("timestamp", "")
            if ts and ts > now[:17]:  # Same minute — check seconds
                try:
                    from datetime import datetime as _dt
                    check_time = _dt.fromisoformat(ts.replace("Z", "+00:00").rstrip("+00:00"))
                    now_time = _dt.now()
                    if abs((now_time - check_time).total_seconds()) < 2:
                        continue
                except Exception:
                    pass

            checks[key] = {
                "status": "pending",
                "evidence": f"[invalidated] {name} edited after {key} was recorded",
                "timestamp": now,
                "skip_reason": None,
            }
            changed = True

        if changed:
            record["checks"] = checks
            vr_file.write_text(json.dumps(record, indent=2))

            # Regress phase when checks are invalidated
            try:
                from utils.vr_utils import regress_phase
            except ImportError:
                try:
                    from vr_utils import regress_phase
                except ImportError:
                    regress_phase = None
            if regress_phase:
                for key in to_invalidate:
                    if checks.get(key, {}).get("status") == "pending":
                        regress_phase(vr_file, key)
    except Exception:
        pass  # Never block


def update_tool_tracking(session_id: str, tool_name: str, tool_input: dict) -> None:
    """Atomic read-modify-write to ~/.claude/data/sessions/{session_id}_tools.json. Never raises."""
    try:
        tools_file = Path.home() / ".claude" / "data" / "sessions" / f"{session_id}_tools.json"
        data = {}
        if tools_file.exists():
            try:
                data = json.loads(tools_file.read_text())
            except Exception:
                data = {}
        if not data:
            data = {"session_id": session_id, "edit_extensions": {},
                    "write_extensions": {}, "bash_count": 0, "read_count": 0}

        if tool_name in ("Edit", "MultiEdit"):
            ext = Path(tool_input.get("file_path", "")).suffix.lower() or ".unknown"
            data["edit_extensions"][ext] = data["edit_extensions"].get(ext, 0) + 1
        elif tool_name == "Write":
            ext = Path(tool_input.get("file_path", "")).suffix.lower() or ".unknown"
            data["write_extensions"][ext] = data["write_extensions"].get(ext, 0) + 1
        elif tool_name == "Bash":
            data["bash_count"] = data.get("bash_count", 0) + 1
        elif tool_name == "Read":
            data["read_count"] = data.get("read_count", 0) + 1
        else:
            return  # Nothing to track

        data["last_updated"] = datetime.now().isoformat()
        tools_file.parent.mkdir(parents=True, exist_ok=True)
        tools_file.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _track_qwen_result(session_id, tool_name, tool_input, tool_result):
    """Log Qwen MCP tool calls to a ring buffer (last 50 entries)."""
    ds_log = Path.home() / ".claude" / "data" / "qwen_delegations.json"
    ds_log.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    if ds_log.exists():
        try:
            entries = json.loads(ds_log.read_text())
        except Exception:
            entries = []

    # Extract action from tool name (e.g. mcp__qwen-agent__run → run)
    action = tool_name.rsplit("__", 1)[-1] if "__" in tool_name else tool_name

    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id[:8],
        "action": action,
        "task_snippet": str(tool_input.get("task", tool_input.get("prompt", "")))[:200],
        "agent_id": tool_input.get("agent_id", ""),
        "state": str(tool_result)[:200] if tool_result else "",
    }
    entries.append(entry)

    # Keep last 50 entries
    entries = entries[-50:]

    ds_log.write_text(json.dumps(entries, indent=2))


def _safe_parse_result(tool_result):
    """Return a dict from a tool result regardless of format (dict/str/MCP content list)."""
    if isinstance(tool_result, dict):
        return tool_result
    if isinstance(tool_result, str):
        try:
            parsed = json.loads(tool_result)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    if isinstance(tool_result, list):
        # MCP content items: [{"type": "text", "text": "..."}]
        for item in tool_result:
            if isinstance(item, dict) and item.get("type") == "text":
                try:
                    parsed = json.loads(item.get("text", ""))
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass
    return {}


def _find_delegation_entry(entries, agent_id, task_id):
    """Return the most recent list entry matching agent_id, falling back to task_id.

    Returns the actual dict object (not a copy) so callers can mutate it in place.
    """
    if agent_id:
        for e in reversed(entries):
            if e.get("agent_id") == agent_id:
                return e
    if task_id:
        for e in reversed(entries):
            if e.get("task_id") == task_id:
                return e
    return None


def _capture_delegation_metadata(session_id, tool_name, tool_input, tool_result):
    """Capture structured Qwen delegation metadata keyed by session + task.

    Writes/updates ~/.claude/data/delegation_meta_{session_id}.json.
    Each entry tracks one agent: plan file_changes, verification_steps,
    plan_reviewed/approved flags, terminal state, and ask_supervisor events.
    All JSON parsing is wrapped in try/except — never crashes the hook.
    """
    data_dir = Path.home() / ".claude" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    meta_file = data_dir / f"delegation_meta_{session_id}.json"

    # Resolve current task_id for scoping
    task_id = ""
    try:
        task_file = data_dir / f"current_task_{session_id}.json"
        if task_file.exists():
            task_id = json.loads(task_file.read_text()).get("task_id", "")
    except Exception:
        pass

    # Load existing entries
    entries = []
    if meta_file.exists():
        try:
            entries = json.loads(meta_file.read_text())
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []

    action = tool_name.rsplit("__", 1)[-1] if "__" in tool_name else tool_name
    result_dict = _safe_parse_result(tool_result)

    if action == "run":
        agent_id = result_dict.get("agent_id", tool_input.get("agent_id", ""))
        entry = {
            "task_id": task_id,
            "agent_id": agent_id,
            "task_snippet": str(tool_input.get("task", tool_input.get("prompt", "")))[:300],
            "profile": tool_input.get("profile", "default-delegation"),
            "working_dir": tool_input.get("working_dir", ""),
            "plan_reviewed": False,
            "plan_approved": False,
            "plan_file_changes": [],
            "plan_verification_steps": [],
            "plan_files_read": [],
            "terminal_state": None,
            "ask_supervisor_occurred": False,
        }
        entries.append(entry)

    elif action == "review":
        review_action = tool_input.get("action", "")
        agent_id = tool_input.get("agent_id", "")
        entry = _find_delegation_entry(entries, agent_id, task_id)
        if entry is None:
            return

        if review_action == "get":
            entry["plan_reviewed"] = True
            entry["plan_file_changes"] = result_dict.get("file_changes", [])
            entry["plan_verification_steps"] = result_dict.get("verification_steps", [])
            codebase = result_dict.get("codebase_analysis", {})
            if isinstance(codebase, dict):
                entry["plan_files_read"] = codebase.get("files_read", [])

        elif review_action == "approve":
            entry["plan_approved"] = True

    elif action == "poll":
        agent_id = tool_input.get("agent_id", "")
        entry = _find_delegation_entry(entries, agent_id, task_id)
        if entry is None:
            return

        state = result_dict.get("state", "")
        if state in {"completed", "limit_reached", "error", "stopped"}:
            entry["terminal_state"] = state

        # Detect ask_supervisor mid-execution
        pending = result_dict.get("pending_tool_call", {})
        if isinstance(pending, dict) and pending.get("tool") == "ask_supervisor":
            entry["ask_supervisor_occurred"] = True

    else:
        return  # setup/configure/queue/agent — not tracked here

    # Keep ring buffer at 20 entries (richer data than qwen_delegations.json)
    entries = entries[-20:]
    meta_file.write_text(json.dumps(entries, indent=2))


def lint_file(file_path):
    """
    Run appropriate linter on file based on extension.
    Returns (has_errors, output) tuple.
    """
    ext = Path(file_path).suffix.lower()

    if ext not in LINTER_MAP:
        return False, None

    linter_cmd = LINTER_MAP[ext] + [file_path]
    cwd = str(Path(file_path).parent)

    try:
        result = subprocess.run(
            linter_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=cwd
        )

        output = result.stdout.strip() or result.stderr.strip()
        has_errors = result.returncode != 0

        return has_errors, output if output else None

    except subprocess.TimeoutExpired:
        return False, None  # Timed out, don't block
    except FileNotFoundError:
        return False, None  # Linter not installed, skip gracefully
    except Exception:
        return False, None  # Any other error, skip gracefully


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        tool_result = input_data.get('tool_response', {})
        session_id = input_data.get('session_id', '')

        # Lint files after Write/Edit/MultiEdit
        if tool_name in ['Write', 'Edit', 'MultiEdit']:
            file_path = tool_input.get('file_path', '')

            if file_path:
                has_errors, lint_output = lint_file(file_path)

                if has_errors and lint_output:
                    # Block with lint errors
                    print(f"LINT ERRORS in {file_path}:", file=sys.stderr)
                    print(lint_output[:1000], file=sys.stderr)
                    sys.exit(2)  # Exit code 2 blocks the operation

        # Invalidate stale verification checks when source files change
        if session_id and tool_name in ("Write", "Edit", "MultiEdit"):
            _invalidate_stale_checks(session_id, tool_input.get("file_path", ""))

        # Auto-observe Bash commands for verification checks
        if session_id and tool_name == "Bash":
            observe_bash_check(session_id, tool_input, tool_result)

        # Track tool usage for Qwen context enrichment
        if session_id and tool_name in ("Write", "Edit", "MultiEdit", "Bash", "Read"):
            update_tool_tracking(session_id, tool_name, tool_input)

        # Track Qwen MCP delegations
        if tool_name.startswith('mcp__qwen-agent__'):
            try:
                _track_qwen_result(session_id, tool_name, tool_input, tool_result)
            except Exception:
                pass
            try:
                _capture_delegation_metadata(session_id, tool_name, tool_input, tool_result)
            except Exception:
                pass

        # Log to JSONL file (append-only, safe for concurrent access)
        log_dir = Path.home() / '.claude' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'post_tool_use.jsonl'

        with open(log_path, 'a') as f:
            f.write(json.dumps(input_data) + '\n')

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Exit cleanly on any other error
        sys.exit(0)

if __name__ == '__main__':
    main()
