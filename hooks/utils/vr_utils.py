"""Shared VR (Verification Record) utilities — single source of truth.

Canonical check list, VR read/write helpers, transcript parsing,
and gate/context functions used by authorize-stop.sh, stop.py,
static_checker.py, dynamic_validator.py, and deepseek_verifier.py.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# ── Canonical check order (10 items) ──────────────────────────────────────

VR_CHECKS_ORDER: list[tuple[str, str]] = [
    ("tests",         "TESTS"),
    ("build",         "BUILD"),
    ("lint",          "LINT"),
    ("app_starts",    "APP STARTS"),
    ("api",           "CODE/SCRIPT/API EXECUTION"),
    ("frontend",      "FRONTEND VALIDATION"),
    ("happy_path",    "HAPPY PATH"),
    ("error_cases",   "ERROR CASES"),
    ("commit_push",   "COMMIT & PUSH"),
    ("upstream_sync", "UPSTREAM SYNC"),
]


# ── VR read/write helpers ─────────────────────────────────────────────────

def write_vr(
    vr_file: Path,
    key: str,
    status: str,
    evidence: str,
    session_id: str | None = None,
) -> None:
    """Atomically write one check entry to verification_record.json.

    If *session_id* is provided, the write is skipped when the file's
    ``session_id`` field doesn't match (prevents cross-session contamination).
    """
    try:
        try:
            record = json.loads(vr_file.read_text())
        except Exception:
            record = {"reset_at": datetime.now().isoformat(), "checks": {}}

        # Session guard — skip write if VR belongs to a different session
        if session_id and record.get("session_id") and record["session_id"] != session_id:
            return

        record.setdefault("checks", {})[key] = {
            "status": status,
            "evidence": evidence[:2000] if evidence else None,
            "timestamp": datetime.now().isoformat(),
            "skip_reason": None,
        }
        vr_file.write_text(json.dumps(record, indent=2))
    except Exception:
        pass  # Never block


def is_pending(vr_file: Path, key: str) -> bool:
    """Return True if the check is currently pending in the record."""
    try:
        record = json.loads(vr_file.read_text())
        return record.get("checks", {}).get(key, {}).get("status", "pending") == "pending"
    except Exception:
        return True  # Assume pending if can't read


# ── Task / Session ID helpers ─────────────────────────────────────────────

def get_task_id() -> str:
    """Read task_id from session-scoped current_task file. Returns 'default' on any error."""
    sid = get_session_id()
    for _ct_path in [
        Path.home() / f".claude/data/current_task_{sid}.json",
        Path.home() / ".claude/data/current_task.json",
    ]:
        try:
            if _ct_path.exists():
                ct = json.loads(_ct_path.read_text())
                return ct.get("task_id", "default") or "default"
        except Exception:
            continue
    return "default"


def get_session_id() -> str:
    """Read session_id for the current working directory.

    Primary: active_sessions.json (maps working_dir → session_id).
    This avoids the clobber bug where concurrent sessions overwrite a
    single global file. Falls back to legacy current_task.json.
    """
    import os
    cwd = os.getcwd()
    # Primary: active_sessions.json lookup by working_dir
    try:
        sessions = json.loads(
            (Path.home() / ".claude/data/active_sessions.json").read_text()
        )
        sid = sessions.get(cwd, "")
        if sid:
            return sid
    except Exception:
        pass
    # Fallback: session-scoped current_task files (glob for any)
    import glob as _g
    for f in sorted(_g.glob(str(Path.home() / ".claude/data/current_task_*.json")),
                    key=lambda p: Path(p).stat().st_mtime, reverse=True):
        try:
            ct = json.loads(Path(f).read_text())
            if ct.get("working_dir", "") == cwd:
                return ct.get("session_id", "default") or "default"
        except Exception:
            continue
    # Final fallback: legacy global file
    try:
        ct = json.loads((Path.home() / ".claude/data/current_task.json").read_text())
        return ct.get("session_id", "default") or "default"
    except Exception:
        return "default"


# ── Transcript parsing ────────────────────────────────────────────────────

def parse_transcript(
    transcript_path: str,
    task_start_ts: str | None = None,
) -> tuple[list[str], list[str], str]:
    """Extract files_modified, bash_commands, last_user_prompt from JSONL transcript.

    Only processes entries written AFTER *task_start_ts* (ISO-8601 string).
    Returns (files_modified, bash_commands, last_user_prompt).
    All fields are always returned; empty when transcript is unavailable.
    """
    files_modified: list[str] = []
    bash_commands: list[str] = []
    last_user_prompt = ""

    if not transcript_path or not Path(transcript_path).exists():
        return files_modified, bash_commands, last_user_prompt

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
                elif role == "user":
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text = (block.get("text") or "").strip()
                                if text:
                                    last_user_prompt = text
                    elif isinstance(content, str) and content.strip():
                        last_user_prompt = content.strip()
    except Exception:
        pass

    bash_commands = bash_commands[-30:]
    return files_modified, bash_commands, last_user_prompt


# ── Gate 1 checker (used by authorize-stop.sh) ────────────────────────────

# Display-padded labels for authorize-stop.sh Gate 1 output
_GATE1_CHECKS_ORDER = [
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

_RUN_CMDS = {
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

_SKIP_CMDS = {
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

_DYNAMIC_CHECKS = {"tests", "build", "app_starts", "api", "frontend"}
_STATIC_CHECKS = {"upstream_sync", "lint"}


def run_gate1_check(auth_file: str, vr_file: str) -> None:
    """Gate 1: 10-check verification gate. Prints status and calls sys.exit(1) if pending."""
    import sys

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

    pending = []
    done = []
    for key, label in _GATE1_CHECKS_ORDER:
        item = checks.get(key, {})
        status = item.get("status", "pending")
        if status == "pending":
            pending.append((key, label))
        else:
            ts = item.get("timestamp", "")
            ts_short = ts[11:16] if ts else "?"
            ev = item.get("evidence") or item.get("skip_reason") or ""
            ev_short = ev[:60].replace("\n", " ") if ev else ""
            done.append((key, label, status, ts_short, ev_short))

    if pending:
        lines = ["", "❌ Cannot authorize — verification incomplete:", ""]
        for key, label, status, ts_short, ev_short in done:
            mark = "✅" if status in ("done", "passed") else "⏭ "
            ev_display = f' — "{ev_short}"' if ev_short else ""
            lines.append(f"  {mark} {label}  [{status} @ {ts_short}]{ev_display}")

        lines.append("")
        for key, label in pending:
            lines.append(f"  ❌ {label}  not verified")
            if key in _STATIC_CHECKS:
                lines.append("     This check auto-runs — re-run authorize-stop to trigger it.")
                lines.append(f"     Or skip: {_SKIP_CMDS[key]}")
            elif key in _DYNAMIC_CHECKS:
                dc_entry = dc_checks.get(key, {})
                if dc_entry.get("deepseek_approved"):
                    lines.append(f"     Registered: {dc_entry['command'][:70]}")
                    lines.append("     Will auto-run — re-run authorize-stop.sh to execute it.")
                else:
                    lines.append("     Option 1 — Register for auto-run (preferred):")
                    lines.append("       bash ~/.claude/commands/register-dynamic-check.sh \\")
                    lines.append(f"         --check {key} \\")
                    lines.append('         --command "<your command>" \\')
                    lines.append('         --pattern "<expected output substring>" \\')
                    lines.append('         --description "<what this validates (min 20 chars)>"')
                    lines.append("     Option 2 — Manual pipe (legacy):")
                    lines.append(f"       {_RUN_CMDS[key]}")
                    lines.append(f"     Or skip: {_SKIP_CMDS[key]}")
            else:
                lines.append(f"     Run: {_RUN_CMDS[key]}")
                lines.append(f"     Or skip: {_SKIP_CMDS[key]}")
            lines.append("")

        lines.append("Complete the missing items, then run authorize-stop again.")
        lines.append("")
        print("\n".join(lines))
        sys.exit(1)

    # All 10 checks verified — print summary
    try:
        with open(auth_file) as f:
            state = json.load(f)
    except Exception:
        state = {}

    scan_done = state.get("security_scan_complete", False)

    lines = ["", "✅ All 10 checks verified"]
    for key, label, status, ts_short, ev_short in done:
        mark = "✅" if status in ("done", "passed") else "⏭ "
        ev_display = f' — "{ev_short}"' if ev_short else ""
        lines.append(f"   {mark} {label}  [{status} @ {ts_short}]{ev_display}")

    if scan_done:
        lines += ["", "   (scan already passed — will proceed to stop)"]
    else:
        lines += ["", "   (security scan will run on next stop)"]
    lines.append("")
    print("\n".join(lines))


# ── Auto-skip for design/analysis tasks ──────────────────────────────────

_DESIGN_TASK_SKIPPABLE = {
    "tests", "build", "app_starts", "api", "frontend",
    "happy_path", "error_cases", "commit_push",
}


def auto_skip_design_task(vr_file: str, context_file: str | None = None) -> int:
    """Auto-skip pending checks when transcript confirms no files were modified.

    Returns number of checks skipped.  Returns 0 if files were modified or
    transcript is unavailable (ambiguous — don't auto-skip).
    """
    vr_path = Path(vr_file)

    # Determine transcript path
    transcript_path = ""
    task_start_ts = ""
    if context_file and Path(context_file).exists():
        try:
            ctx = json.loads(Path(context_file).read_text())
            transcript_path = ctx.get("transcript_path", "")
            task_start_ts = ctx.get("task_started_at", "")
        except Exception:
            pass

    if not transcript_path:
        candidates = sorted(
            Path.home().glob(".claude/projects/**/*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        transcript_path = str(candidates[0]) if candidates else ""

    # Ambiguous — transcript file doesn't exist, don't auto-skip
    if not transcript_path or not Path(transcript_path).exists():
        return 0

    if not task_start_ts:
        try:
            ct = json.loads((Path.home() / ".claude/data/current_task.json").read_text())
            task_start_ts = ct.get("task_started_at", "")
        except Exception:
            pass
        if not task_start_ts:
            try:
                task_start_ts = json.loads(vr_path.read_text()).get("reset_at", "")
            except Exception:
                pass

    files_modified, _, _ = parse_transcript(transcript_path, task_start_ts)

    # Normal coding task — don't skip anything
    if files_modified:
        return 0

    # Design/analysis task — auto-skip pending checks
    skipped = 0
    for key in _DESIGN_TASK_SKIPPABLE:
        if is_pending(vr_path, key):
            write_vr(vr_path, key, "skipped", "no files modified — design/analysis task")
            skipped += 1
    return skipped


def get_agent_id() -> str:
    """Read agent_id from session-scoped agent_identity file. Returns '' on error."""
    try:
        sid = get_session_id()
        # Try session-scoped first
        f = Path.home() / f".claude/data/agent_identity_{sid}.json"
        if f.exists():
            return json.loads(f.read_text()).get("agent_id", "")
        # Fallback: legacy global file
        f = Path.home() / ".claude/data/agent_identity.json"
        if f.exists():
            return json.loads(f.read_text()).get("agent_id", "")
        return ""
    except Exception:
        return ""


# ── Context refresh (used by authorize-stop.sh) ──────────────────────────

def refresh_deepseek_context(context_file: str, vr_file: str) -> None:
    """Refresh deepseek_context.json from current identity, task, and transcript.

    Builds the context dict from scratch using authoritative sources rather
    than augmenting the existing file, preventing stale fields from prior
    tasks from leaking into the current review.
    """
    context_path = Path(context_file)
    vr_path = Path(vr_file)

    # ── Read current identity (authoritative: session_start.py) ──
    agent_id = ""
    session_id = ""
    # Use get_session_id() for concurrent-session-safe lookup
    _sid = get_session_id()
    try:
        _id_file = Path.home() / f".claude/data/agent_identity_{_sid}.json"
        if not _id_file.exists():
            _id_file = Path.home() / ".claude/data/agent_identity.json"
        identity = json.loads(_id_file.read_text())
        agent_id = identity.get("agent_id", "")
        session_id = identity.get("session_id", "")
    except Exception:
        pass

    # ── Read current task metadata (authoritative: user_prompt_submit.py) ──
    prompt_id = ""
    last_user_prompt = ""
    task_started_at = ""
    try:
        _ct_file = Path.home() / f".claude/data/current_task_{_sid}.json"
        if not _ct_file.exists():
            _ct_file = Path.home() / ".claude/data/current_task.json"
        ct = json.loads(_ct_file.read_text())
        prompt_id = ct.get("prompt_id", "")
        last_user_prompt = ct.get("prompt", "")
        task_started_at = ct.get("task_started_at", "")
    except Exception:
        pass

    # ── Determine task_start for transcript filtering ──
    task_start_ts = task_started_at
    if not task_start_ts:
        try:
            task_start_ts = json.loads(vr_path.read_text()).get("reset_at", "")
        except Exception:
            pass

    # ── Find transcript path ──
    transcript_path = ""
    candidates = sorted(
        Path.home().glob(".claude/projects/**/*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if session_id:
        matched = [p for p in candidates if session_id in p.name]
        transcript_path = str(matched[0]) if matched else ""
    if not transcript_path:
        transcript_path = str(candidates[0]) if candidates else ""

    # ── Parse transcript for files_modified and bash_commands ──
    files_modified, bash_commands, _ = parse_transcript(transcript_path, task_start_ts)

    # ── Recover stop-hook-written fields only if prompt_id matches ──
    # stop.py writes last_assistant_message and task_type at stop time.
    # Only trust these if the existing file belongs to the CURRENT prompt;
    # otherwise leave empty (safe default — DeepSeek handles empty fields).
    last_assistant_message = ""
    task_type = ""
    tool_summary = {}
    try:
        existing = json.loads(context_path.read_text())
        existing_prompt_id = existing.get("prompt_id", "")
        if existing_prompt_id and prompt_id and existing_prompt_id == prompt_id:
            last_assistant_message = existing.get("last_assistant_message", "")
            task_type = existing.get("task_type", "")
            tool_summary = existing.get("tool_summary", {})
            if not last_user_prompt:
                last_user_prompt = existing.get("last_user_prompt", "")
    except Exception:
        pass

    # ── Build fresh context dict ──
    ctx = {
        "agent_id": agent_id,
        "prompt_id": prompt_id,
        "session_id": session_id,
        "last_user_prompt": last_user_prompt,
        "last_assistant_message": last_assistant_message,
        "task_type": task_type,
        "files_modified": files_modified,
        "bash_commands": bash_commands,
        "transcript_path": transcript_path,
        "transcript_available": bool(transcript_path and Path(transcript_path).exists()),
    }
    if tool_summary:
        ctx["tool_summary"] = tool_summary

    context_path.write_text(json.dumps(ctx, indent=2))


# ── Stale state cleanup (used by authorize-stop.sh) ──────────────────────

def cleanup_stale_state(state_file: str) -> None:
    """Clear stale rejection history from DeepSeek state file.

    Preserves state ONLY when there's a pending QUESTION (either as
    the last assistant message, or when a user answer has been appended
    after a QUESTION).
    """
    path = Path(state_file)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        messages = data.get("messages", [])

        # Find the last assistant message
        last_asst_content = ""
        for m in reversed(messages):
            if m.get("role") == "assistant":
                last_asst_content = m.get("content", "").strip()
                break

        is_pending_question = last_asst_content.startswith("QUESTION:")

        # Also preserve if user has answered a question (answer-deepseek.sh flow)
        has_user_answer = (
            len(messages) >= 3
            and messages[-1].get("role") == "user"
            and any(
                m.get("role") == "assistant"
                and m.get("content", "").strip().startswith("QUESTION:")
                for m in messages
            )
        )

        if not is_pending_question and not has_user_answer:
            path.unlink(missing_ok=True)
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
