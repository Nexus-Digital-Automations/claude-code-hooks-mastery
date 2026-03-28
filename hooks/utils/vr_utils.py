"""Shared VR (Verification Record) utilities — single source of truth.

Canonical check list, VR read/write helpers, transcript parsing,
and session ID resolution used by authorize-stop.sh, stop.py,
and the post_tool_use observer.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# ── Canonical check order (7 items) ──────────────────────────────────────
# Which of these are *required* is determined by the project config
# (see project_config.get_required_checks).  This list defines the
# display order and the set of valid check keys.

VR_CHECKS_ORDER: list[tuple[str, str]] = [
    ("tests",         "TESTS"),
    ("build",         "BUILD"),
    ("lint",          "LINT"),
    ("app_starts",    "APP STARTS"),
    ("frontend",      "FRONTEND"),
    ("commit_push",   "COMMIT & PUSH"),
    ("upstream_sync", "UPSTREAM SYNC"),
]

VR_CHECK_KEYS = {k for k, _ in VR_CHECKS_ORDER}


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

        truncated_evidence = evidence
        if evidence and len(evidence) > 2000:
            truncated_evidence = evidence[:1950] + f"\n[TRUNCATED — {len(evidence)} chars total]"

        record.setdefault("checks", {})[key] = {
            "status": status,
            "evidence": truncated_evidence,
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
    """Read session_id for the current project (git root).

    Primary: active_sessions.json (maps working_dir → session_id).
    Uses git root resolution to avoid CWD-drift when Claude cd's into
    subdirectories. Falls back to legacy current_task.json.
    """
    try:
        from .project_config import get_git_root
    except ImportError:
        from project_config import get_git_root
    cwd = get_git_root()

    # Primary: active_sessions.json lookup by git root
    try:
        sessions = json.loads(
            (Path.home() / ".claude/data/active_sessions.json").read_text()
        )
        # Try git root first, then exact CWD
        import os
        for lookup_dir in [cwd, os.getcwd()]:
            sid = sessions.get(lookup_dir, "")
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
            wd = ct.get("working_dir", "")
            if wd and (wd == cwd or wd.startswith(cwd + "/")):
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
