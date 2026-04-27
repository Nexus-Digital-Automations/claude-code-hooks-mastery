#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///
"""GPT-5 Mini Protocol Compliance Reviewer — Claude Code entry point.

Independent reviewer that audits Claude Code's work before stop is allowed.
Runs check commands in a sandbox (subprocess), builds a review packet with
raw outputs, and sends it to GPT-5 Mini for evaluation.

The reviewer does NOT trust Claude Code's self-reported verification record.
It runs checks itself and lets the LLM evaluate the raw output.

Shared logic (ReviewPacket, ReviewerConfig, format_packet_for_prompt,
call_reviewer) lives in review_types.py. Also used by hooks/claw_stop.py.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

# Fix Python environment
for _var in ['PYTHONHOME', 'PYTHONPATH']:
    if _var in os.environ:
        del os.environ[_var]

try:
    from dotenv import load_dotenv
    # Always load ~/.claude/.env first (hooks run from project CWD, not ~/.claude)
    load_dotenv(Path.home() / ".claude" / ".env")
    load_dotenv()  # Also load project-level .env (may override)
except ImportError:
    pass

# Add utils dir to path
sys.path.insert(0, str(Path(__file__).parent))

from review_types import (  # noqa: E402
    ReviewPacket,
    ReviewerConfig,
    SandboxResult,
    call_reviewer,
    format_packet_for_prompt,
)

_CLAUDE_DIR = Path.home() / ".claude"
_DATA_DIR = _CLAUDE_DIR / "data"


def load_reviewer_config() -> ReviewerConfig:
    """Load from ~/.claude/data/reviewer_config.json, falling back to defaults."""
    config_file = _DATA_DIR / "reviewer_config.json"
    try:
        if config_file.exists():
            data = json.loads(config_file.read_text())
            return ReviewerConfig(**{
                k: v for k, v in data.items()
                if k in ReviewerConfig.__dataclass_fields__
            })
    except Exception:
        pass
    return ReviewerConfig()


# ── Agent Commentary Summarization (Ollama local model) ──────────────

def _redact_secrets(text: str) -> str:
    """Redact potential secrets and PII from text before forwarding.

    Patterns: API keys, tokens, passwords, emails, private keys, JWTs.
    """
    import re

    patterns = [
        # API keys and tokens (generic long hex/base64 strings after key= or token=)
        (r'(?i)(api[_-]?key|token|secret|password|passwd|auth)\s*[=:]\s*["\']?([A-Za-z0-9_\-/.+]{20,})["\']?',
         r'\1=***REDACTED***'),
        # Bearer tokens
        (r'(?i)(Bearer\s+)([A-Za-z0-9_\-/.+]{20,})',
         r'\1***REDACTED***'),
        # AWS keys
        (r'(AKIA[0-9A-Z]{16})', '***AWS_KEY_REDACTED***'),
        # Private key blocks
        (r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----',
         '***PRIVATE_KEY_REDACTED***'),
        # JWTs (eyJ...)
        (r'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
         '***JWT_REDACTED***'),
        # Email addresses
        (r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
         '***EMAIL_REDACTED***'),
        # Generic long secrets (32+ char hex strings)
        (r'(?<![a-fA-F0-9])[a-fA-F0-9]{32,}(?![a-fA-F0-9])',
         '***HEX_REDACTED***'),
    ]

    result = text
    for pattern, replacement in patterns:
        result = re.sub(pattern, replacement, result)
    return result


def _extract_assistant_text(transcript_path: str, task_started_at: str = "") -> str:
    """Extract all assistant text messages from the JSONL transcript.

    Filters to entries after task_started_at. Returns concatenated text.
    """
    if not transcript_path or not Path(transcript_path).exists():
        return ""

    texts: list[str] = []
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue

                if task_started_at:
                    entry_ts = entry.get("timestamp", "")
                    if entry_ts and entry_ts < task_started_at:
                        continue

                msg = entry.get("message", {})
                if msg.get("role") != "assistant":
                    continue

                content = msg.get("content", [])
                if isinstance(content, str):
                    if content.strip():
                        texts.append(content.strip())
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = (block.get("text") or "").strip()
                            if text:
                                texts.append(text)
    except Exception:
        pass

    return "\n\n---\n\n".join(texts)


def _summarize_with_ollama(text: str) -> str:
    """Summarize text using llama3.2:1b via Ollama. Returns summary or empty string."""
    import urllib.request
    import urllib.error

    if not text.strip():
        return ""

    prompt = (
        "Summarize the key actions, decisions, and claims this AI coding agent made "
        "during its work session. Focus on:\n"
        "- What the agent said it did (files created, modified, fixed)\n"
        "- Decisions it made and why\n"
        "- Status updates and completion claims\n"
        "- Any errors it encountered and how it handled them\n\n"
        "Be thorough but organized. Use bullet points.\n\n"
        "AGENT MESSAGES:\n" + text
    )

    payload = json.dumps({
        "model": "llama3.2:1b",
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result.get("response", "").strip()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"  [reviewer] Ollama summarization failed ({exc}), skipping", file=sys.stderr)
        return ""
    except Exception as exc:
        print(f"  [reviewer] Ollama error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return ""


def summarize_agent_commentary(transcript_path: str, task_started_at: str = "") -> str:
    """Extract and summarize agent commentary from the session transcript.

    Uses llama3.2:1b via Ollama for local, free summarization.
    Returns empty string on any failure (non-blocking).
    """
    raw_text = _extract_assistant_text(transcript_path, task_started_at)
    if not raw_text:
        return ""

    # Redact secrets/PII before sending to local model
    raw_text = _redact_secrets(raw_text)

    return _summarize_with_ollama(raw_text)


# ── Sandbox Check Execution ───────────────────────────────────────────

# SandboxResult is imported from review_types


def run_sandbox_checks(
    project_root: Path,
    config: dict,
    reviewer_config: ReviewerConfig | None = None,
    task_started_at: str = "",
) -> dict[str, SandboxResult]:
    """Run ALL required check commands independently in subprocess sandbox.

    Does NOT trust Claude Code's VR. Runs checks fresh and captures raw output.
    task_started_at scopes the git log to commits made during the current task.
    """
    if reviewer_config is None:
        reviewer_config = load_reviewer_config()

    try:
        from project_config import get_required_checks, evaluate_output
    except ImportError:
        return {}

    required = get_required_checks(config, files_modified=True)
    checks_conf = config.get("checks", {})
    results: dict[str, SandboxResult] = {}

    # Build command map from config
    run_commands: dict[str, str] = {}
    for key, conf in checks_conf.items():
        if isinstance(conf, dict) and conf.get("run_command"):
            run_commands[key] = conf["run_command"]

    for key in required:
        # Skip checks that don't have shell commands (handled separately)
        if key in ("upstream_sync", "security", "commit_push", "happy_path",
                    "app_starts", "execution"):
            continue

        cmd = run_commands.get(key)
        if not cmd:
            results[key] = SandboxResult(
                check_key=key, command="", exit_code=-1,
                stdout="", stderr="", passed=False,
                skipped=True, skip_reason="No run_command configured",
            )
            continue

        timeout = (reviewer_config.sandbox_timeout_frontend
                   if key == "frontend"
                   else reviewer_config.sandbox_timeout)

        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(project_root),
            )
            stdout = (r.stdout or "")[:3000]
            stderr = (r.stderr or "")[:1500]

            # Evaluate pass/fail using project_config patterns
            check_conf = checks_conf.get(key, {})
            if not isinstance(check_conf, dict):
                check_conf = {}
            passed = evaluate_output(r.stdout or "", r.stderr or "", check_conf) == "passed"
            # Override: non-zero exit code always means failure
            if r.returncode != 0:
                passed = False

            results[key] = SandboxResult(
                check_key=key, command=cmd, exit_code=r.returncode,
                stdout=stdout, stderr=stderr, passed=passed,
            )
        except subprocess.TimeoutExpired:
            results[key] = SandboxResult(
                check_key=key, command=cmd, exit_code=-1,
                stdout="", stderr=f"Command timed out after {timeout}s",
                passed=False, timed_out=True,
            )
        except FileNotFoundError:
            results[key] = SandboxResult(
                check_key=key, command=cmd, exit_code=-1,
                stdout="", stderr=f"Command not found: {cmd.split()[0]}",
                passed=False, skipped=True,
                skip_reason=f"Command not found: {cmd.split()[0]}",
            )
        except Exception as exc:
            results[key] = SandboxResult(
                check_key=key, command=cmd, exit_code=-1,
                stdout="", stderr=str(exc)[:500],
                passed=False,
            )

    # Always run git checks (read-only)
    # Scope git log to commits since the current task started (if known)
    _git_log_cmd = (
        f'git log --oneline --after="{task_started_at}" -20'
        if task_started_at
        else "git log --oneline -5"
    )
    for git_key, git_cmd in [
        ("_git_status", "git status --porcelain --ignore-submodules"),
        ("_git_diff", "git diff --stat"),
        ("_git_diff_content", "git diff HEAD"),
        ("_git_log", _git_log_cmd),
        ("_git_show_stat", "git show HEAD --stat"),
        ("_git_show_content", "git show HEAD"),
    ]:
        try:
            # Actual diff content gets a larger truncation limit
            stdout_limit = 5000 if git_key in ("_git_diff_content", "_git_show_content") else 2000
            r = subprocess.run(
                git_cmd, shell=True, capture_output=True, text=True,
                timeout=15, cwd=str(project_root),
            )
            results[git_key] = SandboxResult(
                check_key=git_key, command=git_cmd,
                exit_code=r.returncode,
                stdout=(r.stdout or "")[:stdout_limit],
                stderr=(r.stderr or "")[:500],
                passed=r.returncode == 0,
            )
        except Exception:
            pass

    # Build session diff: all commits the agent made since task_started_at.
    # git show HEAD only covers the last commit; this covers N commits in a session.
    # Find the oldest task commit, then diff from its parent to HEAD.
    if task_started_at:
        try:
            log_r = subprocess.run(
                f'git log --after="{task_started_at}" --format="%H"',
                shell=True, capture_output=True, text=True,
                timeout=15, cwd=str(project_root),
            )
            hashes = [h.strip() for h in log_r.stdout.strip().splitlines() if h.strip()]
            if hashes:
                oldest = hashes[-1]  # git log is newest-first
                diff_cmd = f"git diff {oldest}^..HEAD"
                diff_r = subprocess.run(
                    diff_cmd, shell=True, capture_output=True, text=True,
                    timeout=30, cwd=str(project_root),
                )
                results["_session_diff"] = SandboxResult(
                    check_key="_session_diff", command=diff_cmd,
                    exit_code=diff_r.returncode,
                    stdout=(diff_r.stdout or "")[:8000],
                    stderr=(diff_r.stderr or "")[:500],
                    passed=diff_r.returncode == 0,
                )
        except Exception:
            pass

    return results


def _resolve_session_id(session_id: str) -> str:
    """Resolve canonical session ID (mirrors stop.py logic).

    Prefers harness-provided ID when its VR exists to prevent cross-session
    contamination from concurrent sessions overwriting active_sessions.json.
    """
    # 1. Harness-provided ID is authoritative if its VR file exists
    if (_DATA_DIR / f"verification_record_{session_id}.json").exists():
        return session_id
    # 2. Fallback: active_sessions.json (compact/restart)
    try:
        sessions_file = _DATA_DIR / "active_sessions.json"
        if sessions_file.exists():
            sessions = json.loads(sessions_file.read_text())
            try:
                from project_config import get_git_root
                git_root = get_git_root()
                for lookup_dir in [git_root, os.getcwd()]:
                    resolved = sessions.get(lookup_dir, "")
                    if resolved and (_DATA_DIR / f"verification_record_{resolved}.json").exists():
                        return resolved
            except Exception as exc:
                print(f"  [reviewer] git_root lookup failed, falling back to cwd: {exc}", file=sys.stderr)
                cwd = os.getcwd()
                resolved = sessions.get(cwd, "")
                if resolved and (_DATA_DIR / f"verification_record_{resolved}.json").exists():
                    return resolved
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  [reviewer] active_sessions.json read failed: {exc}", file=sys.stderr)
    return session_id


def build_review_packet(
    session_id: str,
    last_assistant_message: str = "",
) -> ReviewPacket:
    """Gather all context needed for a protocol review.

    Reads user requests, specs, project config, runs sandbox checks,
    checks git state and root cleanliness. Never raises.

    NOTE: session_id is treated as authoritative (already resolved by caller).
    """
    packet = ReviewPacket(
        session_id=session_id,
        last_assistant_message=last_assistant_message or "",
        timestamp=datetime.now().isoformat(),
    )

    # 0. Task identity — load from current_task_{session_id}.json
    current_task: dict = {}
    try:
        task_file = _DATA_DIR / f"current_task_{session_id}.json"
        if task_file.exists():
            current_task = json.loads(task_file.read_text())
    except Exception:
        pass
    packet.task_id = current_task.get("task_id", "")
    packet.prompt_id = current_task.get("prompt_id", "")
    packet.agent_id = current_task.get("agent_id", "")
    packet.task_started_at = current_task.get("task_started_at", "")

    # 1. User requests — filtered to current task only
    try:
        req_file = _DATA_DIR / f"user_requests_{session_id}.json"
        if req_file.exists():
            all_requests = json.loads(req_file.read_text())
            if packet.task_id:
                # Primary: match task_id (entries written after this fix have this field)
                task_reqs = [r for r in all_requests if r.get("task_id") == packet.task_id]
                # Fallback for old entries without task_id: use only the most-recent request.
                # Do NOT filter by task_started_at — it is unreliable for follow-up tasks
                # because is_followup=True causes it to be inherited from an earlier task,
                # which would include requests from prior tasks in the same session.
                packet.user_requests = task_reqs if task_reqs else all_requests[-1:]
            else:
                packet.user_requests = all_requests
    except Exception:
        pass

    # 2. Spec status
    try:
        from project_config import get_git_root
        project_root = Path(get_git_root())
    except Exception:
        project_root = Path.cwd()

    try:
        specs_dir = project_root / "specs"
        if specs_dir.is_dir():
            for spec_file in sorted(specs_dir.glob("*.md")):
                try:
                    content = spec_file.read_text(errors='replace')
                    if not content.startswith("---"):
                        continue
                    parts = content.split("---", 2)
                    if len(parts) < 3:
                        continue
                    fm = parts[1]
                    status = title = ""
                    for line in fm.split("\n"):
                        line = line.strip()
                        if line.startswith("status:"):
                            status = line[7:].strip()
                        elif line.startswith("title:"):
                            title = line[6:].strip().strip("'\"")
                    if status not in ("active", "in-progress", "planning"):
                        continue
                    body = parts[2]
                    unchecked = body.count("- [ ]")
                    checked = body.count("- [x]")
                    packet.spec_status.append({
                        "file": spec_file.name,
                        "title": title,
                        "status": status,
                        "checked": checked,
                        "unchecked": unchecked,
                        "total": checked + unchecked,
                        "body": body[:3000],
                    })
                except Exception:
                    continue
    except Exception:
        pass

    # 3. Project config + sandbox checks
    try:
        from project_config import load_config
        config = load_config(project_root)
        packet.project_config = {
            k: v for k, v in config.items()
            if k in ("project_type", "has_frontend", "has_tests", "has_build",
                      "has_app", "has_typecheck")
        }

        # Run sandbox checks (pass task_started_at to scope git log)
        sandbox = run_sandbox_checks(project_root, config,
                                     task_started_at=packet.task_started_at)
        for key, result in sandbox.items():
            packet.sandbox_results[key] = asdict(result)

        # Extract git results from sandbox
        if "_git_status" in sandbox:
            packet.git_status = sandbox["_git_status"].stdout
        if "_git_diff" in sandbox:
            packet.git_diff = sandbox["_git_diff"].stdout
        if "_git_diff_content" in sandbox:
            packet.git_diff_content = sandbox["_git_diff_content"].stdout
        if "_git_log" in sandbox:
            packet.git_log = sandbox["_git_log"].stdout
        if "_git_show_stat" in sandbox:
            packet.git_show_stat = sandbox["_git_show_stat"].stdout
        if "_git_show_content" in sandbox:
            packet.git_show_content = sandbox["_git_show_content"].stdout
        if "_session_diff" in sandbox:
            packet.session_diff_content = sandbox["_session_diff"].stdout
    except Exception:
        pass

    # 4. Root cleanliness (reuse stop.py logic inline)
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from stop import check_root_cleanliness
        is_clean, violations = check_root_cleanliness()
        packet.root_clean = is_clean
        packet.root_violations = violations
    except Exception:
        pass

    # 5. File-size advisory + justification registry
    try:
        from file_size_scanner import scan_oversized_files
        from file_size_registry import FileSizeRegistry
        packet.oversized_files = scan_oversized_files(project_root)
        packet.file_size_reasons = FileSizeRegistry(project_root).load().as_review_dict()
    except Exception as exc:
        print(f"  [reviewer] file-size scan failed: {exc}", file=sys.stderr)

    # 6. Agent commentary summary (Ollama local model)
    try:
        transcript_path = current_task.get("transcript_path", "")
        if transcript_path:
            packet.agent_commentary_summary = summarize_agent_commentary(
                transcript_path, packet.task_started_at,
            )
    except Exception as exc:
        print(f"  [reviewer] Commentary summarization failed: {exc}", file=sys.stderr)

    # 7. Approved plan file — scoped to current task (prevents cross-session contamination)
    try:
        plan_path_str = current_task.get("plan_file", "")
        if plan_path_str:
            plan_path = Path(plan_path_str)
            if plan_path.exists():
                packet.plan_content = plan_path.read_text(errors="replace")
        else:
            # Fallback: newest plan whose mtime predates this task's start time
            # (backward compat for tasks without plan_file set)
            plans_dir = _CLAUDE_DIR / "plans"
            if plans_dir.is_dir():
                task_start = packet.task_started_at
                plan_files = sorted(
                    plans_dir.glob("*.md"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                for pf in plan_files:
                    if not task_start:
                        # No task timestamp — use newest (legacy behavior)
                        packet.plan_content = pf.read_text(errors="replace")
                        break
                    pf_mtime = datetime.fromtimestamp(pf.stat().st_mtime).isoformat()
                    if pf_mtime <= task_start:
                        packet.plan_content = pf.read_text(errors="replace")
                        break
    except (OSError, PermissionError) as exc:
        print(f"  [reviewer] Plan file load failed: {exc}", file=sys.stderr)

    # 8. Verification artifacts from output/ (committed .txt/.diff files)
    try:
        output_dir = project_root / "output"
        if output_dir.is_dir():
            for artifact in sorted(output_dir.glob("*.txt")) + sorted(output_dir.glob("*.diff")):
                try:
                    content = artifact.read_text(errors="replace")
                    # Cap each artifact at 3000 chars to keep packet manageable
                    packet.verification_artifacts[artifact.name] = content[:3000]
                except Exception:
                    continue
    except Exception:
        pass

    return packet


# format_packet_for_prompt is imported from review_types


# ── Conversation Management ───────────────────────────────────────────

def _conversation_file(session_id: str) -> Path:
    return _DATA_DIR / f"review_conversation_{session_id}.json"


def load_conversation(session_id: str, task_id: str = "") -> list[dict]:
    """Load conversation history, clearing it if project root or task_id changed.

    Clears on project-root change (cross-project contamination) and on task_id
    change (cross-task contamination within the same session). Both cases would
    inject stale context from a different review scope into the LLM.

    Backward compat: files written in the old plain-list format are returned
    as-is (no root/task check) and migrated to the wrapper format on next save.
    """
    try:
        f = _conversation_file(session_id)
        if not f.exists():
            return []
        raw = json.loads(f.read_text())
        # Old format: plain list — return as-is, no root/task check possible
        if isinstance(raw, list):
            return raw
        # New format: {"project_root": "...", "task_id": "...", "messages": [...]}
        if isinstance(raw, dict) and "messages" in raw:
            stored_root = raw.get("project_root", "")
            stored_task = raw.get("task_id", "")
            # Clear if task changed (cross-task contamination within same session)
            if task_id and stored_task and stored_task != task_id:
                print(
                    f"[reviewer] Clearing stale conversation — "
                    f"task changed ({stored_task[:8]!r} → {task_id[:8]!r})",
                    file=sys.stderr,
                )
                f.unlink(missing_ok=True)
                return []
            # Clear if project root changed (cross-project contamination)
            if stored_root:
                try:
                    from project_config import get_git_root
                    current_root = get_git_root()
                    if current_root != stored_root:
                        print(
                            f"[reviewer] Clearing stale conversation — "
                            f"project root changed ({stored_root!r} → {current_root!r})",
                            file=sys.stderr,
                        )
                        f.unlink(missing_ok=True)
                        return []
                except Exception:
                    pass  # Can't verify root — proceed with stored history
            return raw["messages"]
    except Exception:
        pass
    return []


def save_conversation(session_id: str, messages: list[dict], task_id: str = "") -> None:
    """Persist conversation history with project root and task_id metadata.

    Stores both so that load_conversation() can detect cross-project and
    cross-task contamination on reload.
    """
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        project_root = ""
        try:
            from project_config import get_git_root
            project_root = get_git_root()
        except Exception:
            pass
        _conversation_file(session_id).write_text(
            json.dumps(
                {"project_root": project_root, "task_id": task_id, "messages": messages},
                indent=2,
            )
        )
    except Exception:
        pass


def clear_conversation(session_id: str) -> None:
    """Reset conversation for a new review cycle."""
    try:
        f = _conversation_file(session_id)
        if f.exists():
            f.unlink(missing_ok=True)
    except Exception:
        pass


# ── System Prompt ─────────────────────────────────────────────────────

def load_system_prompt() -> str | None:
    """Read the protocol compliance reference as the system prompt."""
    ref_file = _CLAUDE_DIR / "docs" / "protocol-compliance-reference.md"
    try:
        if ref_file.exists():
            return ref_file.read_text()
    except Exception:
        pass
    return None


# call_reviewer is imported from review_types


# ── Approval Management ───────────────────────────────────────────────

def _approval_file(session_id: str) -> Path:
    return _DATA_DIR / f"reviewer_approval_{session_id}.json"


def check_approval(session_id: str, task_id: str = "") -> bool:
    """Check if reviewer has already approved this session's current task."""
    try:
        f = _approval_file(session_id)
        if f.exists():
            data = json.loads(f.read_text())
            if not data.get("approved", False):
                return False
            # Verify task_id matches — prevents cross-task approval bleed
            stored_task = data.get("task_id", "")
            if task_id and stored_task and stored_task != task_id:
                return False
            return True
    except Exception:
        pass
    return False


def write_approval(session_id: str, result: dict, task_id: str = "") -> None:
    """Write reviewer approval file, scoped to the current task_id."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _approval_file(session_id).write_text(json.dumps({
            "approved": True,
            "task_id": task_id,
            "timestamp": datetime.now().isoformat(),
            "round_count": result.get("round_count", 1),
            "summary": result.get("summary", ""),
            "model": result.get("model", ""),
        }, indent=2))
    except Exception:
        pass


def reset_approval(session_id: str) -> None:
    """Clear reviewer approval (called on stop reset / session start)."""
    try:
        f = _approval_file(session_id)
        if f.exists():
            f.unlink(missing_ok=True)
    except Exception:
        pass


# ── Main Review Loop ──────────────────────────────────────────────────

@dataclass
class ReviewResult:
    approved: bool = False
    round_count: int = 0
    findings: list[dict] = field(default_factory=list)
    summary: str = ""
    error: str = ""


def run_review(
    session_id: str,
    last_assistant_message: str = "",
) -> ReviewResult:
    """Execute a single review round.

    1. Build review packet (including sandbox checks)
    2. Load or initialize conversation
    3. Send packet as user message
    4. Parse response
    5. If APPROVED: write approval file
    6. If FINDINGS: return findings (caller shows them)
    7. If ERROR: return with error detail

    NOTE: session_id is treated as authoritative (already resolved by
    stop.py). Do NOT re-resolve — _resolve_session_id here previously
    caused mismatches because it lacks the VR-file-existence guard that
    stop.py's version has, leading to approval files written under the
    wrong session ID.
    """
    config = load_reviewer_config()

    if not config.enabled:
        return ReviewResult(
            approved=True, summary="Reviewer disabled in config",
        )

    if not os.getenv("OPENAI_API_KEY"):
        return ReviewResult(
            approved=True,
            summary="Reviewer skipped — OPENAI_API_KEY not set",
            error="no_api_key",
        )

    # Load system prompt
    system_prompt = load_system_prompt()
    if not system_prompt:
        return ReviewResult(
            approved=True,
            summary="Reviewer skipped — protocol reference not found",
            error="no_system_prompt",
        )

    # Build review packet
    packet = build_review_packet(session_id, last_assistant_message=last_assistant_message)
    packet_text = format_packet_for_prompt(packet)

    # Load conversation history — scoped by task_id to prevent cross-task contamination
    history = load_conversation(session_id, task_id=packet.task_id)
    round_count = len([m for m in history if m.get("role") == "user"]) + 1

    if round_count >= config.max_rounds:
        return ReviewResult(
            approved=True,
            summary=f"Max review rounds ({config.max_rounds}) reached — auto-approving",
            round_count=round_count,
        )

    # Build messages — summarize stale history after 3 rounds to reduce context pollution
    messages = [{"role": "system", "content": system_prompt}]
    if round_count >= 3 and history:
        # Condense prior rounds into a summary instead of full history
        prior_findings = []
        for msg in history:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                try:
                    data = json.loads(content)
                    for f in data.get("findings", []):
                        cat = f.get("category", "?")
                        sev = f.get("severity", "?")
                        desc = f.get("description", "")[:100]
                        prior_findings.append(f"[{sev}] {cat}: {desc}")
                except (json.JSONDecodeError, TypeError):
                    pass
        if prior_findings:
            summary = (
                f"PRIOR ROUNDS SUMMARY (rounds 1-{round_count - 1}):\n"
                f"The following findings were raised in prior rounds. "
                f"Some may have been resolved since then — evaluate the "
                f"CURRENT packet fresh, not based on prior findings:\n\n"
                + "\n".join(f"- {f}" for f in prior_findings)
            )
            messages.append({"role": "user", "content": summary})
            messages.append({"role": "assistant", "content": '{"verdict": "FINDINGS", "summary": "See prior rounds."}'})
    else:
        messages.extend(history)

    # Extract last user request for explicit instruction
    last_request_text = "(no request captured)"
    if packet.user_requests:
        last_req = packet.user_requests[-1]
        last_request_text = last_req.get("prompt", "(empty)")[:300]

    messages.append({
        "role": "user",
        "content": (
            f"## REVIEW ROUND {round_count}\n\n"
            f"Review the following work for protocol compliance.\n\n"
            f"**MANDATORY PASS/FAIL CHECK:** The most recent user request was:\n"
            f"> {last_request_text}\n\n"
            f"Your response MUST include an explicit line:\n"
            f"  LAST REQUEST: PASS — <brief explanation>\n"
            f"  OR\n"
            f"  LAST REQUEST: FAIL — <what is missing or incomplete>\n\n"
            f"If the last request is FAIL, the overall verdict MUST be FINDINGS.\n\n"
            f"{packet_text}"
        ),
    })

    # Call GPT-5 Mini
    response = call_reviewer(messages, config)

    # Save conversation (append this round)
    history.append({
        "role": "user",
        "content": f"[Round {round_count} review packet — {packet.timestamp}]",
    })
    history.append({
        "role": "assistant",
        "content": json.dumps(response),
    })
    save_conversation(session_id, history, task_id=packet.task_id)

    # Process response
    if response.get("verdict") == "ERROR":
        return ReviewResult(
            approved=True,
            summary=f"Reviewer error (non-blocking): {response.get('detail', 'unknown')}",
            error=response.get("detail", "unknown"),
            round_count=round_count,
        )

    if response.get("verdict") == "APPROVED":
        result = ReviewResult(
            approved=True,
            summary=response.get("summary", "Approved"),
            round_count=round_count,
        )
        write_approval(session_id, {
            "round_count": round_count,
            "summary": response.get("summary", ""),
            "model": config.model,
        }, task_id=packet.task_id)
        return result

    # FINDINGS
    findings = response.get("findings", [])
    return ReviewResult(
        approved=False,
        findings=findings,
        summary=response.get("summary", "Issues found"),
        round_count=round_count,
    )


# ── CLI Entry Point ───────────────────────────────────────────────────

def main():
    """Command line interface for manual review triggering."""
    import argparse

    parser = argparse.ArgumentParser(description="GPT-5 Mini Protocol Compliance Reviewer")
    parser.add_argument("session_id", nargs="?", default=None,
                        help="Session ID (auto-resolved from active_sessions if omitted)")
    parser.add_argument("--last-message", default="",
                        help="Last assistant message for category 14 review")
    parser.add_argument("--json", action="store_true",
                        help="Output structured JSON (exit 0=APPROVED, 1=FINDINGS, 2=ERROR)")
    args = parser.parse_args()

    session_id = args.session_id or "default"

    # Try to resolve session ID if not provided
    if args.session_id is None:
        try:
            sessions_file = _DATA_DIR / "active_sessions.json"
            if sessions_file.exists():
                sessions = json.loads(sessions_file.read_text())
                cwd = os.getcwd()
                session_id = sessions.get(cwd, session_id)
        except Exception:
            pass

    config = load_reviewer_config()

    if not args.json:
        print(f"Running protocol review (session: {session_id[:8]}...)")
        print(f"Model: {config.model}")
        print()

    result = run_review(session_id, last_assistant_message=args.last_message)

    if args.json:
        output = {
            "approved": result.approved,
            "round_count": result.round_count,
            "summary": result.summary,
            "error": result.error,
            "findings": result.findings,
        }
        print(json.dumps(output))
        if result.approved:
            sys.exit(0)
        elif result.error:
            sys.exit(2)
        else:
            sys.exit(1)
    else:
        if result.approved:
            print(f"APPROVED (round {result.round_count})")
            print(f"  {result.summary}")
            if result.error:
                print(f"  Note: {result.error}")
        else:
            print(f"FINDINGS (round {result.round_count}/{config.max_rounds})")
            print()
            for finding in result.findings:
                sev = "BLOCK" if finding.get("severity") == "blocking" else "ADVSR"
                print(f"  [{sev}] [{finding.get('category', '?')}]")
                print(f"    {finding.get('description', '')}")
                if finding.get("evidence"):
                    print(f"    Evidence: {finding['evidence'][:200]}")
                if finding.get("evidence_needed"):
                    print(f"    Needed: {finding['evidence_needed']}")
                print()
            print(f"Summary: {result.summary}")


if __name__ == "__main__":
    main()
