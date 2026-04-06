"""Claw-code-parity packet assembler.

Builds a ReviewPacket from a claw-code-parity project directory.
The packet format is identical to the Claude Code reviewer's — only the
data sources differ.

Key differences from Claude Code assembly:
- User requests come from session JSON (role=user blocks), not data/ files
- No task scoping — no task_id, no current_task file
- Agent mode is hardcoded "claw"
- Conversation persistence uses {project}/.claw/data/
- No delegation metadata (claw does not use DeepSeek)
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Ensure utils dir is on path so reviewer_core is importable
sys.path.insert(0, str(Path(__file__).parent))

from reviewer_core import ReviewPacket, ReviewerConfig, SandboxResult  # noqa: E402


# ── Session Parsing ───────────────────────────────────────────────────

def _parse_session_messages(session_file: Path) -> tuple[list[dict], str]:
    """Return (user_requests, last_assistant_message) from a claw session JSON.

    Session format:
        {"messages": [{"role": "user"|"assistant", "blocks": [{"type": "text", "text": "..."}]}]}

    Returns:
        user_requests: list of dicts with keys "prompt" and "timestamp"
        last_assistant_message: plain text of the last assistant block
    """
    user_requests: list[dict] = []
    last_assistant_message = ""

    try:
        data = json.loads(session_file.read_text())
        messages = data.get("messages", [])
        # Use file mtime as a rough timestamp base (sessions don't embed timestamps)
        mtime_ts = datetime.fromtimestamp(session_file.stat().st_mtime).isoformat()

        for msg in messages:
            role = msg.get("role", "")
            blocks = msg.get("blocks", [])
            text = "\n".join(
                b.get("text", "") for b in blocks if b.get("type") == "text"
            ).strip()

            if not text:
                continue

            if role == "user":
                user_requests.append({
                    "prompt": text,
                    "timestamp": mtime_ts,
                })
            elif role == "assistant":
                last_assistant_message = text

    except Exception:
        pass

    return user_requests, last_assistant_message


def _find_most_recent_session(working_dir: Path) -> Path | None:
    """Return the most recently modified session file, or None."""
    sessions_dir = working_dir / ".claude" / "sessions"
    if not sessions_dir.is_dir():
        return None
    candidates = list(sessions_dir.glob("session-*.json"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ── Sandbox Checks ────────────────────────────────────────────────────

def _run_sandbox_checks_claw(
    working_dir: Path,
    config: dict,
    reviewer_config: ReviewerConfig,
) -> dict[str, dict]:
    """Run configured check commands from .claude-project.json in working_dir."""
    results: dict[str, dict] = {}
    checks_conf = config.get("checks", {})

    # Build runnable commands
    run_commands: dict[str, str] = {}
    for key, conf in checks_conf.items():
        if isinstance(conf, dict) and conf.get("run_command"):
            run_commands[key] = conf["run_command"]

    skip_keys = {"upstream_sync", "security", "commit_push", "happy_path", "app_starts", "execution"}

    for key, cmd in run_commands.items():
        if key in skip_keys:
            continue

        timeout = (
            reviewer_config.sandbox_timeout_frontend
            if key == "frontend"
            else reviewer_config.sandbox_timeout
        )

        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(working_dir),
            )
            stdout = (r.stdout or "")[:3000]
            stderr = (r.stderr or "")[:1500]
            check_conf = checks_conf.get(key, {})
            if not isinstance(check_conf, dict):
                check_conf = {}

            # Simple pass/fail: non-zero = fail; check fail_patterns
            passed = r.returncode == 0
            fail_pats = check_conf.get("fail_patterns", [])
            if fail_pats:
                combined = (r.stdout or "") + (r.stderr or "")
                for pat in fail_pats:
                    if pat and pat in combined:
                        passed = False
                        break
            pass_pats = check_conf.get("pass_patterns", [])
            if pass_pats and r.returncode == 0:
                combined = (r.stdout or "") + (r.stderr or "")
                passed = any(p in combined for p in pass_pats if p)

            results[key] = asdict(SandboxResult(
                check_key=key, command=cmd, exit_code=r.returncode,
                stdout=stdout, stderr=stderr, passed=passed,
            ))
        except subprocess.TimeoutExpired:
            results[key] = asdict(SandboxResult(
                check_key=key, command=cmd, exit_code=-1,
                stdout="", stderr=f"Command timed out after {timeout}s",
                passed=False, timed_out=True,
            ))
        except Exception as exc:
            results[key] = asdict(SandboxResult(
                check_key=key, command=cmd, exit_code=-1,
                stdout="", stderr=str(exc)[:500],
                passed=False,
            ))

    # Git checks (read-only)
    for git_key, git_cmd in [
        ("_git_status", "git status --porcelain"),
        ("_git_diff", "git diff --stat"),
        ("_git_diff_content", "git diff HEAD"),
        ("_git_log", "git log --oneline -5"),
        ("_git_show_stat", "git show HEAD --stat"),
        ("_git_show_content", "git show HEAD"),
    ]:
        try:
            stdout_limit = 5000 if git_key in ("_git_diff_content", "_git_show_content") else 2000
            r = subprocess.run(
                git_cmd, shell=True, capture_output=True, text=True,
                timeout=15, cwd=str(working_dir),
            )
            results[git_key] = asdict(SandboxResult(
                check_key=git_key, command=git_cmd,
                exit_code=r.returncode,
                stdout=(r.stdout or "")[:stdout_limit],
                stderr=(r.stderr or "")[:500],
                passed=r.returncode == 0,
            ))
        except Exception:
            pass

    return results


# ── Root Cleanliness ──────────────────────────────────────────────────

_ALLOWED_ROOT_NAMES = frozenset({
    "README.md", "CLAUDE.md", ".gitignore", ".gitattributes",
    ".editorconfig", ".env.example", "Makefile",
    "Cargo.toml", "Cargo.lock", "pyproject.toml", "setup.py", "setup.cfg",
    "package.json", "package-lock.json", "yarn.lock",
    "tsconfig.json", "eslint.config.js", ".eslintrc.js", ".prettierrc",
    "Dockerfile", "docker-compose.yml",
})
_ALLOWED_ROOT_DIRS = frozenset({
    ".git", ".claude", ".claw", "src", "rust", "tests", "docs", "scripts",
    "output", "logs", "specs", "assets", "data", "sessions",
    ".validation-artifacts",
})
_ALLOWED_ROOT_SUFFIXES = frozenset({
    ".toml", ".json", ".lock", ".md", ".txt", ".sh", ".yaml", ".yml",
})


def _check_root_cleanliness(working_dir: Path) -> tuple[bool, list[str]]:
    """Scan working_dir root for unexpected files."""
    violations: list[str] = []
    try:
        for entry in working_dir.iterdir():
            name = entry.name
            if name.startswith("."):
                continue
            if entry.is_dir():
                if name not in _ALLOWED_ROOT_DIRS:
                    violations.append(f"Unexpected directory at root: {name}/")
            else:
                if name not in _ALLOWED_ROOT_NAMES and entry.suffix not in _ALLOWED_ROOT_SUFFIXES:
                    violations.append(f"Unexpected file at root: {name}")
    except Exception:
        pass
    return len(violations) == 0, violations


# ── Main Packet Builder ───────────────────────────────────────────────

def build_claw_packet(
    working_dir: Path,
    session_file: Path | None = None,
    reviewer_config: ReviewerConfig | None = None,
) -> ReviewPacket:
    """Build a ReviewPacket from a claw-code-parity project directory.

    Args:
        working_dir: Root of the claw-code-parity project.
        session_file: Explicit session JSON to use. If None, uses most recent.
        reviewer_config: Reviewer config. If None, uses defaults.

    Returns:
        Populated ReviewPacket (never raises).
    """
    if reviewer_config is None:
        reviewer_config = ReviewerConfig()

    packet = ReviewPacket(
        timestamp=datetime.now().isoformat(),
    )

    # 1. Session — user requests + last assistant message
    resolved_session = session_file or _find_most_recent_session(working_dir)
    if resolved_session and resolved_session.exists():
        # Use session filename stem as a proxy session_id
        packet.session_id = resolved_session.stem
        user_requests, last_msg = _parse_session_messages(resolved_session)
        packet.user_requests = user_requests
        packet.last_assistant_message = last_msg[:3000] if last_msg else ""
    else:
        packet.session_id = "claw-unknown"

    # 2. Spec status — identical format to Claude Code
    try:
        specs_dir = working_dir / "specs"
        if specs_dir.is_dir():
            for spec_file in sorted(specs_dir.glob("*.md")):
                try:
                    content = spec_file.read_text(errors="replace")
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

    # 3. Project config
    try:
        config_file = working_dir / ".claude-project.json"
        if config_file.exists():
            full_config = json.loads(config_file.read_text())
            packet.project_config = {
                k: v for k, v in full_config.items()
                if k in ("project_type", "has_frontend", "has_tests", "has_build",
                          "has_app", "has_typecheck")
            }

            # 4. Sandbox checks
            sandbox = _run_sandbox_checks_claw(working_dir, full_config, reviewer_config)
            packet.sandbox_results = sandbox

            # Extract git results
            if "_git_status" in sandbox:
                packet.git_status = sandbox["_git_status"].get("stdout", "")
            if "_git_diff" in sandbox:
                packet.git_diff = sandbox["_git_diff"].get("stdout", "")
            if "_git_diff_content" in sandbox:
                packet.git_diff_content = sandbox["_git_diff_content"].get("stdout", "")
            if "_git_log" in sandbox:
                packet.git_log = sandbox["_git_log"].get("stdout", "")
            if "_git_show_stat" in sandbox:
                packet.git_show_stat = sandbox["_git_show_stat"].get("stdout", "")
            if "_git_show_content" in sandbox:
                packet.git_show_content = sandbox["_git_show_content"].get("stdout", "")
    except Exception:
        pass

    # 5. Root cleanliness
    try:
        packet.root_clean, packet.root_violations = _check_root_cleanliness(working_dir)
    except Exception:
        pass

    # 6. Verification artifacts from output/ and .validation-artifacts/
    try:
        for search_dir in [working_dir / "output", working_dir / ".validation-artifacts"]:
            if not search_dir.is_dir():
                continue
            for pattern in ("*.txt", "*.diff"):
                for artifact in sorted(search_dir.glob(pattern)):
                    try:
                        content = artifact.read_text(errors="replace")
                        key = f"{search_dir.name}/{artifact.name}"
                        packet.verification_artifacts[key] = content[:3000]
                    except Exception:
                        continue
    except Exception:
        pass

    return packet
