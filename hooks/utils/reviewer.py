#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///
"""GPT-5 Mini Protocol Compliance Reviewer.

Independent reviewer that audits Claude Code's work before stop is allowed.
Runs check commands in a sandbox (subprocess), builds a review packet with
raw outputs, and sends it to GPT-5 Mini for evaluation.

The reviewer does NOT trust Claude Code's self-reported verification record.
It runs checks itself and lets the LLM evaluate the raw output.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
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

_CLAUDE_DIR = Path.home() / ".claude"
_DATA_DIR = _CLAUDE_DIR / "data"


# ── Configuration ──────────────────────────────────────────────────────

@dataclass
class ReviewerConfig:
    model: str = "gpt-5-mini"
    temperature: float = 0.2
    max_tokens: int = 2000
    max_rounds: int = 5
    timeout_per_round: int = 30
    sandbox_timeout: int = 120
    sandbox_timeout_frontend: int = 300
    strictness: str = "standard"
    enabled: bool = True


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


# ── Sandbox Check Execution ───────────────────────────────────────────

@dataclass
class SandboxResult:
    check_key: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    timed_out: bool = False
    skipped: bool = False
    skip_reason: str = ""


def run_sandbox_checks(
    project_root: Path,
    config: dict,
    reviewer_config: ReviewerConfig | None = None,
) -> dict[str, SandboxResult]:
    """Run ALL required check commands independently in subprocess sandbox.

    Does NOT trust Claude Code's VR. Runs checks fresh and captures raw output.
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
    for git_key, git_cmd in [
        ("_git_status", "git status --porcelain"),
        ("_git_diff", "git diff --stat"),
        ("_git_diff_content", "git diff HEAD"),
        ("_git_log", "git log --oneline -5"),
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

    return results


def find_nested_git_repos(project_root: Path) -> list[Path]:
    """Return direct-child directories of project_root that are git repos."""
    repos: list[Path] = []
    try:
        for child in sorted(project_root.iterdir()):
            if child.is_dir() and not child.name.startswith(".") and (child / ".git").exists():
                repos.append(child)
    except Exception:
        pass
    return repos


# ── Review Packet ─────────────────────────────────────────────────────

@dataclass
class ReviewPacket:
    session_id: str = ""
    user_requests: list[dict] = field(default_factory=list)
    spec_status: list[dict] = field(default_factory=list)
    sandbox_results: dict[str, dict] = field(default_factory=dict)
    project_config: dict = field(default_factory=dict)
    git_status: str = ""
    git_diff: str = ""
    git_diff_content: str = ""
    git_log: str = ""
    git_show_stat: str = ""
    git_show_content: str = ""
    nested_repo_activity: list[dict] = field(default_factory=list)
    agent_mode: str = "claude"
    root_clean: bool = True
    root_violations: list[str] = field(default_factory=list)
    last_assistant_message: str = ""
    timestamp: str = ""


def _resolve_session_id(session_id: str) -> str:
    """Resolve canonical session ID (mirrors stop.py logic)."""
    try:
        sessions_file = _DATA_DIR / "active_sessions.json"
        if sessions_file.exists():
            sessions = json.loads(sessions_file.read_text())
            try:
                from project_config import get_git_root
                git_root = get_git_root()
                for lookup_dir in [git_root, os.getcwd()]:
                    resolved = sessions.get(lookup_dir, "")
                    if resolved:
                        return resolved
            except Exception:
                cwd = os.getcwd()
                resolved = sessions.get(cwd, "")
                if resolved:
                    return resolved
    except Exception:
        pass
    return session_id


def build_review_packet(
    session_id: str,
    last_assistant_message: str = "",
) -> ReviewPacket:
    """Gather all context needed for a protocol review.

    Reads user requests, specs, project config, runs sandbox checks,
    checks git state and root cleanliness. Never raises.
    """
    session_id = _resolve_session_id(session_id)
    packet = ReviewPacket(
        session_id=session_id,
        last_assistant_message=last_assistant_message[:3000] if last_assistant_message else "",
        timestamp=datetime.now().isoformat(),
    )

    # 1. User requests
    try:
        req_file = _DATA_DIR / f"user_requests_{session_id}.json"
        if req_file.exists():
            packet.user_requests = json.loads(req_file.read_text())
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

        # Run sandbox checks
        sandbox = run_sandbox_checks(project_root, config)
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
    except Exception:
        pass

    # 4. Agent mode
    try:
        mode_file = _DATA_DIR / "agent_mode.json"
        if mode_file.exists():
            packet.agent_mode = json.loads(mode_file.read_text()).get("mode", "claude")
    except Exception:
        pass

    # 5. Root cleanliness (reuse stop.py logic inline)
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from stop import check_root_cleanliness
        is_clean, violations = check_root_cleanliness()
        packet.root_clean = is_clean
        packet.root_violations = violations
    except Exception:
        pass

    # 6. Nested git repo activity
    try:
        for nested in find_nested_git_repos(project_root):
            entry: dict = {"path": nested.name}
            for key, cmd in [
                ("log", "git log --oneline -5"),
                ("diff_stat", "git diff --stat"),
                ("show_stat", "git show HEAD --stat"),
            ]:
                try:
                    r = subprocess.run(
                        cmd, shell=True, capture_output=True,
                        text=True, timeout=10, cwd=str(nested),
                    )
                    entry[key] = (r.stdout or "").strip()[:1500]
                except Exception:
                    entry[key] = ""
            # Auto-detect lint command
            lint_cmd: str | None = None
            if (nested / "pyproject.toml").exists():
                lint_cmd = "ruff check . --quiet 2>&1 | tail -3"
            elif (nested / "package.json").exists():
                lint_cmd = "npm run lint --silent 2>&1 | tail -5"
            if lint_cmd:
                try:
                    r = subprocess.run(
                        lint_cmd, shell=True, capture_output=True,
                        text=True, timeout=30, cwd=str(nested),
                    )
                    entry["lint"] = f"exit={r.returncode} " + (r.stdout or "").strip()[:500]
                except Exception:
                    entry["lint"] = ""
            packet.nested_repo_activity.append(entry)
    except Exception:
        pass

    return packet


def format_packet_for_prompt(packet: ReviewPacket) -> str:
    """Convert ReviewPacket into structured text for the LLM prompt."""
    sections = []

    # Last assistant message (for Execute-Don't-Recommend check)
    sections.append("## LAST ASSISTANT MESSAGE")
    if packet.last_assistant_message:
        sections.append(packet.last_assistant_message)
    else:
        sections.append("(Not captured)")

    # User requests
    sections.append("\n## USER REQUESTS")
    if packet.user_requests:
        for i, req in enumerate(packet.user_requests, 1):
            ts = req.get("timestamp", "?")
            prompt = req.get("prompt", "(empty)")
            sections.append(f"### Message {i} [{ts}]")
            sections.append(prompt)
    else:
        sections.append("(No user requests captured)")

    # Spec status
    sections.append("\n## SPEC STATUS")
    if packet.spec_status:
        for spec in packet.spec_status:
            sections.append(
                f"- {spec['file']}: \"{spec['title']}\" "
                f"[{spec['status']}] — {spec['checked']}/{spec['total']} criteria checked"
            )
            body = spec.get("body", "").strip()
            if body:
                sections.append(f"\n```\n{body}\n```")
    else:
        sections.append("(No active specs found)")

    # Project config
    sections.append("\n## PROJECT CONFIG")
    sections.append(json.dumps(packet.project_config, indent=2))

    # Sandbox check results
    sections.append("\n## SANDBOX CHECK RESULTS (independently executed)")
    for key, result in packet.sandbox_results.items():
        if key.startswith("_git_"):
            continue  # Git results shown separately
        sections.append(f"\n### {key.upper()}")
        sections.append(f"Command: `{result.get('command', 'N/A')}`")
        if result.get("skipped"):
            sections.append(f"SKIPPED: {result.get('skip_reason', 'unknown')}")
            continue
        if result.get("timed_out"):
            sections.append("TIMED OUT — check did not complete")
            continue
        sections.append(f"Exit code: {result.get('exit_code', '?')}")
        sections.append(f"Passed: {result.get('passed', False)}")
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        if stdout.strip():
            sections.append(f"stdout:\n```\n{stdout}\n```")
        if stderr.strip():
            sections.append(f"stderr:\n```\n{stderr}\n```")

    # Git state
    sections.append("\n## GIT STATE")
    sections.append(f"### git status --porcelain\n```\n{packet.git_status or '(clean)'}\n```")
    sections.append(f"### git diff --stat\n```\n{packet.git_diff or '(no changes)'}\n```")
    sections.append(f"### git log --oneline -5\n```\n{packet.git_log or '(no commits)'}\n```")
    if packet.git_show_stat:
        sections.append(f"### git show HEAD --stat\n```\n{packet.git_show_stat}\n```")

    # Actual diff content for code quality review (categories 9-13)
    # Use working-tree diff if available; fall back to HEAD commit diff when all changes are committed
    sections.append("\n## GIT DIFF CONTENT (for code quality review)")
    diff_content = packet.git_diff_content or packet.git_show_content
    if diff_content:
        label = "working tree diff" if packet.git_diff_content else "HEAD commit diff (all changes committed)"
        sections.append(f"({label})")
        sections.append(f"```diff\n{diff_content}\n```")
    else:
        sections.append("(No diff content available — skip categories 9-13)")

    # Nested repo activity
    if packet.nested_repo_activity:
        sections.append("\n## NESTED REPO ACTIVITY")
        sections.append(
            "(These are separate git repositories inside the project root. "
            "Their changes do not appear in the git diff above.)"
        )
        for repo in packet.nested_repo_activity:
            sections.append(f"\n### {repo['path']}/")
            if repo.get("log"):
                sections.append(f"Recent commits:\n```\n{repo['log']}\n```")
            if repo.get("show_stat"):
                sections.append(f"HEAD commit:\n```\n{repo['show_stat']}\n```")
            diff = repo.get("diff_stat") or "(clean — no uncommitted changes)"
            sections.append(f"Uncommitted changes: {diff}")
            if repo.get("lint"):
                sections.append(f"Lint: `{repo['lint']}`")

    # Agent mode
    sections.append(f"\n## AGENT MODE: {packet.agent_mode}")

    # Root cleanliness
    sections.append("\n## ROOT CLEANLINESS")
    if packet.root_clean:
        sections.append("Clean — no violations")
    else:
        sections.append("VIOLATIONS:")
        for v in packet.root_violations:
            sections.append(f"  {v}")

    return "\n".join(sections)


# ── Conversation Management ───────────────────────────────────────────

def _conversation_file(session_id: str) -> Path:
    return _DATA_DIR / f"review_conversation_{session_id}.json"


def load_conversation(session_id: str) -> list[dict]:
    """Load conversation history."""
    try:
        f = _conversation_file(session_id)
        if f.exists():
            return json.loads(f.read_text())
    except Exception:
        pass
    return []


def save_conversation(session_id: str, messages: list[dict]) -> None:
    """Persist conversation history."""
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _conversation_file(session_id).write_text(
            json.dumps(messages, indent=2)
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


# ── LLM Client ────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """Extract JSON from a response that may be wrapped in markdown code blocks."""
    # Try to find JSON in code blocks
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try to find raw JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0).strip()
    return text.strip()


def call_reviewer(
    messages: list[dict],
    config: ReviewerConfig,
) -> dict:
    """Call DeepSeek Chat with conversation history.

    Returns parsed response: {"verdict": "APPROVED"|"FINDINGS", ...}
    On failure: returns {"verdict": "ERROR", "detail": "..."}.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return {"verdict": "ERROR", "detail": "DEEPSEEK_API_KEY not set"}

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")

        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            max_completion_tokens=config.max_tokens,
            response_format={"type": "json_object"},
            timeout=config.timeout_per_round,
        )
        content = (response.choices[0].message.content or "").strip()

        # Detect empty responses (broken model — don't silently auto-approve)
        if not content:
            return {
                "verdict": "ERROR",
                "detail": f"Model '{config.model}' returned empty response",
            }

        # Parse JSON from response
        json_str = _extract_json(content)
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            # Retry: ask for valid JSON
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": (
                "Your response was not valid JSON. Please respond with EXACTLY "
                "one JSON object matching the verdict format specified in your "
                "instructions. No markdown, no explanation — just the JSON."
            )})
            retry_response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                max_completion_tokens=config.max_tokens,
                response_format={"type": "json_object"},
                timeout=config.timeout_per_round,
            )
            retry_content = (retry_response.choices[0].message.content or "").strip()
            if not retry_content:
                return {
                    "verdict": "ERROR",
                    "detail": f"Model '{config.model}' returned empty response on retry",
                }
            retry_json = _extract_json(retry_content)
            parsed = json.loads(retry_json)

        if parsed.get("verdict") not in ("APPROVED", "FINDINGS"):
            return {
                "verdict": "ERROR",
                "detail": f"Invalid verdict: {parsed.get('verdict')}",
            }

        return parsed

    except json.JSONDecodeError as e:
        return {"verdict": "ERROR", "detail": f"JSON parse error: {e}"}
    except Exception as e:
        err_type = type(e).__name__
        return {"verdict": "ERROR", "detail": f"{err_type}: {str(e)[:200]}"}


# ── Approval Management ───────────────────────────────────────────────

def _approval_file(session_id: str) -> Path:
    return _DATA_DIR / f"reviewer_approval_{session_id}.json"


def check_approval(session_id: str) -> bool:
    """Check if reviewer has already approved this session."""
    session_id = _resolve_session_id(session_id)
    try:
        f = _approval_file(session_id)
        if f.exists():
            return json.loads(f.read_text()).get("approved", False)
    except Exception:
        pass
    return False


def write_approval(session_id: str, result: dict) -> None:
    """Write reviewer approval file."""
    session_id = _resolve_session_id(session_id)
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _approval_file(session_id).write_text(json.dumps({
            "approved": True,
            "timestamp": datetime.now().isoformat(),
            "round_count": result.get("round_count", 1),
            "summary": result.get("summary", ""),
            "model": result.get("model", ""),
        }, indent=2))
    except Exception:
        pass


def reset_approval(session_id: str) -> None:
    """Clear reviewer approval (called on stop reset / session start)."""
    session_id = _resolve_session_id(session_id)
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
    """
    session_id = _resolve_session_id(session_id)
    config = load_reviewer_config()

    if not config.enabled:
        return ReviewResult(
            approved=True, summary="Reviewer disabled in config",
        )

    if not os.getenv("DEEPSEEK_API_KEY"):
        return ReviewResult(
            approved=True,
            summary="Reviewer skipped — DEEPSEEK_API_KEY not set",
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

    # Load conversation history
    history = load_conversation(session_id)
    round_count = len([m for m in history if m.get("role") == "user"]) + 1

    if round_count > config.max_rounds:
        return ReviewResult(
            approved=True,
            summary=f"Max review rounds ({config.max_rounds}) reached — auto-approving",
            round_count=round_count,
        )

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": (
            f"## REVIEW ROUND {round_count}\n\n"
            f"Review the following work for protocol compliance.\n\n"
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
    save_conversation(session_id, history)

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
        })
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
