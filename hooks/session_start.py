#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# Add hooks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Fix Python environment warnings
for var in ['PYTHONHOME', 'PYTHONPATH']:
    if var in os.environ:
        del os.environ[var]

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def log_session_start(input_data):
    """Log session start event to logs directory."""
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'session_start.json'
    
    # Read existing log data or initialize empty list
    if log_file.exists():
        with open(log_file, 'r') as f:
            try:
                log_data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                log_data = []
    else:
        log_data = []
    
    # Append the entire input data
    log_data.append(input_data)
    
    # Write back to file with formatting
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=2)


def get_git_status():
    """Get current git status information."""
    try:
        # Get current branch
        branch_result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        
        # Get uncommitted changes count
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if status_result.returncode == 0:
            changes = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
            uncommitted_count = len(changes)
        else:
            uncommitted_count = 0
        
        return current_branch, uncommitted_count
    except Exception:
        return None, None


def get_recent_issues():
    """Get recent GitHub issues if gh CLI is available."""
    try:
        # Check if gh is available
        gh_check = subprocess.run(['which', 'gh'], capture_output=True)
        if gh_check.returncode != 0:
            return None
        
        # Get recent open issues
        result = subprocess.run(
            ['gh', 'issue', 'list', '--limit', '5', '--state', 'open'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _generate_agent_identity(session_id: str) -> str:
    """Generate a unique agent_id for this session and persist it.

    The agent_id is a UUID that uniquely identifies this session's agent.
    It scopes all Qwen reviewer state files and prevents cross-session
    contamination.

    Written to <project>/.claude/data/agent_identity_{session_id}.json
    (session-scoped to avoid clobbering across concurrent sessions).

    Returns the agent_id string.
    """
    import uuid
    from project_config import get_project_data_dir
    agent_id = str(uuid.uuid4())
    data_dir = get_project_data_dir()
    identity_file = data_dir / f"agent_identity_{session_id}.json"
    try:
        identity_file.parent.mkdir(parents=True, exist_ok=True)
        identity_file.write_text(json.dumps({
            "agent_id": agent_id,
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
        }, indent=2))
    except Exception:
        pass  # Never block session start
    return agent_id


def _register_active_session(session_id: str, working_dir: str) -> None:
    """Register this session in active_sessions.json keyed by working_dir.

    This lookup table lets shell scripts (authorize-stop.sh) find the correct
    session_id for the current working directory without a global singleton file.
    Multiple concurrent sessions write to different keys, avoiding clobber.
    """
    from project_config import get_project_data_dir
    data_dir = get_project_data_dir()
    sessions_file = data_dir / "active_sessions.json"
    try:
        sessions = {}
        if sessions_file.exists():
            sessions = json.loads(sessions_file.read_text())
        sessions[working_dir] = session_id
        sessions_file.write_text(json.dumps(sessions, indent=2))
    except Exception:
        pass  # Never block session start


def reset_verification_record(session_id: str = "unknown") -> None:
    """Clean up stale state files from previous sessions.

    Deletes VR files, legacy global files, stale session-scoped identity/task
    files, and orphaned Qwen files so the new session starts clean.
    Scoped to the current project (see project_config.get_project_data_dir).
    """
    import glob as _glob
    from project_config import get_project_data_dir
    _claude_data = get_project_data_dir()
    _claude_data.mkdir(parents=True, exist_ok=True)

    # Build set of session IDs to protect (current + all other active sessions).
    # This prevents a new session from destroying state of concurrent sessions.
    _protected_sessions: set[str] = set()
    if session_id != "unknown":
        _protected_sessions.add(session_id)
    try:
        _sessions_file = _claude_data / "active_sessions.json"
        if _sessions_file.exists():
            _active = json.loads(_sessions_file.read_text())
            if isinstance(_active, dict):
                for _sid in _active.values():
                    if isinstance(_sid, str) and _sid:
                        _protected_sessions.add(_sid)
    except Exception:
        pass  # Never block session start; fall back to protecting only current session

    def _is_protected(file_path_str: str) -> bool:
        """Return True if file belongs to any active session."""
        return any(sid in file_path_str for sid in _protected_sessions)

    # Read previous agent identity (session-scoped) for targeted cleanup
    _old_agent_id = None
    _identity_file = _claude_data / f"agent_identity_{session_id}.json"
    if not _identity_file.exists():
        # Fallback: check legacy global file
        _identity_file = _claude_data / "agent_identity.json"
    try:
        if _identity_file.exists():
            _old = json.loads(_identity_file.read_text())
            _old_agent_id = _old.get("agent_id")
    except Exception:
        pass

    # Targeted cleanup: delete state files belonging to the old agent
    if _old_agent_id:
        for _suffix in [
            f"qwen_context_{_old_agent_id}.json",
            f"qwen_review_state_{_old_agent_id}.json",
            f"qwen_review_state_{_old_agent_id}.rejections",
        ]:
            try:
                (_claude_data / _suffix).unlink(missing_ok=True)
            except Exception:
                pass

    # Delete legacy global VR
    legacy = _claude_data / "verification_record.json"
    if legacy.exists():
        try:
            legacy.unlink(missing_ok=True)
        except Exception:
            pass

    # Delete stale task-scoped VR files (skip active sessions)
    for p in _glob.glob(str(_claude_data / "verification_record_*.json")):
        if _is_protected(p):
            continue
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

    # Transfer active auth tokens to new session instead of deleting them.
    # A compact changes session_id but not project context — if the user already
    # authorized, that auth should carry forward so they don't have to re-run
    # authorize-stop.sh after every compact.
    if session_id != "unknown":
        for _auth_str in _glob.glob(str(_claude_data / "stop_authorization_*.json")):
            if session_id in _auth_str:
                continue  # Already matches new session
            try:
                _auth_data = json.loads(Path(_auth_str).read_text())
                if _auth_data.get("authorized", False):
                    # Auth was granted before compact — carry it forward
                    _new_auth = _claude_data / f"stop_authorization_{session_id}.json"
                    Path(_auth_str).rename(_new_auth)
                    continue
            except Exception:
                pass
            try:
                Path(_auth_str).unlink(missing_ok=True)
            except Exception:
                pass

    # Clean up stale session-scoped files (not matching current session)
    for _pattern in [
        "agent_identity_*.json",         # Session-scoped identity files
        "current_task_*.json",           # Session-scoped task files
        # stop_authorization_*.json handled above (auth transfer logic)
        "reviewer_approval_*.json",      # Session-scoped reviewer approval
        "review_conversation_*.json",    # Session-scoped review conversation
        "user_requests_*.json",          # Session-scoped user request log
    ]:
        for _path_str in _glob.glob(str(_claude_data / _pattern)):
            # Keep files belonging to any active session
            if _is_protected(_path_str):
                continue
            try:
                Path(_path_str).unlink(missing_ok=True)
            except Exception:
                pass

    # Clean up legacy global singleton files (replaced by session-scoped versions)
    for _legacy_name in [
        "agent_identity.json",
        "current_task.json",
        "stop_authorization.json",
    ]:
        try:
            (_claude_data / _legacy_name).unlink(missing_ok=True)
        except Exception:
            pass

    # Clean up orphaned Qwen files — only delete files older than 1 hour
    # to avoid racing with concurrent sessions.
    import time as _time
    _one_hour_ago = _time.time() - 3600
    for _pattern in [
        "qwen_context.json",
        "qwen_context_*.json",
        "qwen_review_state_*.json",
        "qwen_review_state_*.rejections",
        "qwen_run_snapshot.json",
    ]:
        for _path_str in _glob.glob(str(_claude_data / _pattern)):
            try:
                if Path(_path_str).stat().st_mtime < _one_hour_ago:
                    Path(_path_str).unlink(missing_ok=True)
            except Exception:
                pass


def load_active_specs(cwd):
    """Load active spec files from specs/ directory and return a context summary.

    Scans <cwd>/specs/*.md for files with status: active|in-progress|planning.
    Returns a formatted string for session context injection, or None.
    """
    specs_dir = Path(cwd) / "specs"
    if not specs_dir.is_dir():
        return None

    summaries = []
    try:
        for spec_file in sorted(specs_dir.glob("*.md")):
            try:
                content = spec_file.read_text()
                # Parse frontmatter (simple YAML between --- markers)
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        frontmatter = parts[1].strip()
                        title = ""
                        status = ""
                        priority = ""
                        for line in frontmatter.split("\n"):
                            line = line.strip()
                            if line.startswith("title:"):
                                title = line[6:].strip().strip("'\"")
                            elif line.startswith("status:"):
                                status = line[7:].strip()
                            elif line.startswith("priority:"):
                                priority = line[9:].strip()

                        if status in ("active", "in-progress", "planning"):
                            # Count acceptance criteria
                            body = parts[2]
                            total = body.count("- [ ]") + body.count("- [x]")
                            done = body.count("- [x]")
                            progress = f" ({done}/{total} criteria)" if total > 0 else ""
                            pri = f" [{priority}]" if priority else ""
                            summaries.append(
                                f"  - {spec_file.name}: {title}{pri} ({status}){progress}"
                            )
            except Exception:
                continue
    except Exception:
        return None

    if not summaries:
        return None

    lines = ["--- Active Specs (specs/) ---"]
    lines.extend(summaries)
    lines.append("Review these specs before starting work. Spec files are protected (read-only without user approval).")
    return "\n".join(lines)


def _spawn_background_indexer(cwd: str) -> None:
    """Spawn a detached background process to auto-index git repos.

    Only fires for git repos to avoid indexing ~/.claude, /tmp, etc.
    Reads MCP config from ~/.claude.json — single source of truth.
    Fire-and-forget: hook returns immediately, indexing runs silently.
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True, timeout=3, cwd=cwd
        )
        if result.returncode != 0:
            return
    except Exception:
        return

    indexer = Path(__file__).parent / 'auto_index_codebase.py'
    if not indexer.exists():
        return

    try:
        subprocess.Popen(
            [sys.executable, str(indexer), cwd],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def load_development_context(source, agent_id=""):
    """Load relevant development context based on session source."""
    context_parts = []

    # Add timestamp and agent identity
    context_parts.append(f"Session started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    context_parts.append(f"Session source: {source}")
    if agent_id:
        context_parts.append(f"Agent ID: {agent_id}")

    # Add session rules (autonomous + validation, concise)
    session_rules = """
--- SESSION RULES ---
1. AUTONOMOUS: Never ask permission mid-task. Decide and proceed. Fix errors immediately.
2. VALIDATE: Before declaring any task complete, run actual commands and show output.
   Minimum: tests + build. No claims without evidence.
   Format: Command: <x> | Result: ✅/❌ | Output: <actual snippet>
3. VERIFICATION PLAN: State your verification commands (pytest, npm test, build, curl) BEFORE
   implementing. Reading code (find, cat, grep) is investigation, NOT verification.
   No test/build proof = not done.
4. ROOT CLEAN: Never create files at project root except essential configs.
5. STOP: Use /authorize-stop after presenting validation proof.
6. EXECUTE DON'T RECOMMEND: If you can do it, do it. Never say "I recommend X" or "You should Y" for actions within your capability.
"""
    context_parts.append(session_rules)

    # Assemble CLAUDE.md from base + mode-specific content (auto-fix if mismatched)
    try:
        from utils.config_loader import get_config
        current_mode = get_config().get_agent_mode().get("mode", "claude")
        claude_dir = Path.home() / ".claude"
        base_file = claude_dir / "CLAUDE.base.md"
        mode_file = claude_dir / f"CLAUDE.mode.{current_mode}.md"
        dest_file = claude_dir / "CLAUDE.md"
        if base_file.exists() and mode_file.exists():
            assembled = base_file.read_text() + mode_file.read_text()
            if not dest_file.exists() or dest_file.read_text() != assembled:
                dest_file.write_text(assembled)
        elif base_file.exists():
            # Mode file missing — use base only
            base_content = base_file.read_text()
            if not dest_file.exists() or dest_file.read_text() != base_content:
                dest_file.write_text(base_content)
        else:
            # Fallback: try legacy full-copy files
            legacy_file = claude_dir / f"CLAUDE.{current_mode}.md"
            if legacy_file.exists() and dest_file.exists():
                if legacy_file.read_text() != dest_file.read_text():
                    import shutil
                    shutil.copy2(str(legacy_file), str(dest_file))
    except Exception:
        pass

    # Inject Qwen supervisor context if in qwen mode
    try:
        from utils.config_loader import get_config
        if get_config().is_qwen_mode():
            session_rules_qwen = """
QWEN DELEGATION MODE — THIS OVERRIDES CLAUDE.md'S "AUTONOMOUS OPERATION" RULE

You are the architect and quality gate. Qwen builds code but is not as
strong a coder as you — expect mistakes. Its code will often have missing error
handling, wrong variable names, logic bugs, and incomplete implementations.
Thorough review and testing catch real problems every time.

BEFORE DELEGATING — WRITE A TASK DESCRIPTION (not a full plan):
- Features: what to build as a numbered list
- Constraints: what NOT to change, what to preserve
- Verification criteria: how you will validate each feature
Scale to the task: 5-10 lines for a bug fix, 15-20 for a feature.
Do NOT include architecture, function signatures, or file-by-file instructions.
Qwen investigates the codebase and produces its own comprehensive plan.

DIVISION OF LABOR:
- You (Claude Code): task description, plan review, verify build/lint/type-check, final Playwright gate, frontend UI, security
- Qwen Agent: codebase investigation, planning, code building, first-pass mechanical checks (build/lint/type-check/Playwright, budget-capped), Playwright test writing
- Playwright: runs comprehensively when frontend changes detected. Unit/integration tests only for critical business domains (payments, auth, billing, data integrity, financial, security). Most code does NOT need tests.

DELEGATION PROTOCOL:
- Write the task description, then delegate via mcp__qwen-agent__run
- Use profile="default-delegation" — plan mode is enabled by default
- Qwen investigates the codebase with read-only tools and produces a comprehensive plan
- Returns state="awaiting_approval" — review the plan before any code is written
- Monitor with mcp__qwen-agent__poll

PLAN REVIEW (mandatory — before approving):
- plan(agent_id, "get") to inspect the plan
- Check codebase_analysis: did it read the right files? Do entity signatures match?
  READ THE FILES YOURSELF to verify claims.
- Check tool_calls_planned: do old_string values match actual file contents?
  READ THE FILES YOURSELF to verify edit strings.
- Check risk_assessment: are risks identified for each change?
- Red flags: editing a file not in files_read, empty old_string, no risk assessment
- plan(agent_id, "approve") / plan(agent_id, "edit", ...) / plan(agent_id, "reject", ...)

AFTER AGENT COMPLETES (mandatory — every time):
1. Read EVERY file the agent modified — line by line, not skimming
2. Check for: off-by-one errors, missing error handling, wrong variable names,
   hardcoded values, broken imports, security vulnerabilities, logic that
   doesn't match the plan
3. Re-run build + lint + type-check yourself (mandatory — should pass in seconds if agent passed)
4. Run Playwright yourself as the final E2E gate
5. Run any unit/integration tests the agent didn't cover
6. Start the app and exercise the happy path yourself
7. If you find ANY issue: fix it yourself OR send a specific follow-up task
8. Never say "output looks good" without citing specific evidence

TASKS YOU KEEP (do NOT delegate):
- Plan review and approval — investigate anything suspicious
- Test qualification — re-run build/lint/type-check, final Playwright gate, unit/integration tests
- ALL frontend UI work — use impeccable skills (Qwen writes Playwright tests for features it adds, not UI code)
- Questions, explanations, read-only reviews
- Git operations, security audits
- ALL security work — scanning, auditing, vulnerability review, hardening
- Stop authorization and verification

DELEGATION THRESHOLD:
- Only deploy Qwen for tasks touching ~5+ files
- Small tasks (~5 files or fewer): implement directly yourself
- Delegation overhead (run, poll, review, fix) exceeds direct implementation for small changes

FALLBACK: If Qwen is unavailable, implement directly yourself.

You are the architect and the quality gate. Every deliverable gets verified.
"""
            context_parts.insert(0, session_rules_qwen)  # Highest priority — must appear first
    except Exception:
        pass  # Graceful degradation

    # Load active specs from specs/ directory
    specs_context = load_active_specs(os.getcwd())
    if specs_context:
        context_parts.append(specs_context)

    # Add git information
    branch, changes = get_git_status()
    if branch:
        context_parts.append(f"Git branch: {branch}")
        if changes > 0:
            context_parts.append(f"Uncommitted changes: {changes} files")
    
    # Load project-specific context files if they exist
    context_files = [
        ".claude/CONTEXT.md",
        ".claude/TODO.md",
        "TODO.md",
        ".github/ISSUE_TEMPLATE.md"
    ]
    
    for file_path in context_files:
        if Path(file_path).exists():
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        context_parts.append(f"\n--- Content from {file_path} ---")
                        context_parts.append(content[:1000])  # Limit to first 1000 chars
            except Exception:
                pass
    
    # Add recent issues if available
    issues = get_recent_issues()
    if issues:
        context_parts.append("\n--- Recent GitHub Issues ---")
        context_parts.append(issues)

    # Detect project type and surface relevant plugins from New Tools
    try:
        from utils.plugin_resolver import get_plugins_for_project
        cwd = os.getcwd()
        plugin_ctx = get_plugins_for_project(cwd)
        if plugin_ctx:
            context_parts.append(f"\n{plugin_ctx}")
    except Exception:
        pass  # Graceful degradation

    return "\n".join(context_parts)


def _create_default_vr(session_id: str) -> None:
    """Create a default verification record with all checks pending.

    Ensures stop.py always has a well-formed VR to read, preventing
    the case where a missing file blocks stop forever.
    """
    from project_config import get_project_data_dir
    vr_file = get_project_data_dir() / f"verification_record_{session_id}.json"
    if vr_file.exists():
        return  # Don't overwrite existing
    check_keys = [
        "tests", "build", "lint", "typecheck", "app_starts", "execution",
        "frontend", "happy_path", "security", "commit_push", "upstream_sync",
    ]
    record = {
        "session_id": session_id,
        "reset_at": datetime.now().isoformat(),
        "checks": {
            key: {"status": "pending", "evidence": None, "timestamp": None, "skip_reason": None}
            for key in check_keys
        },
    }
    try:
        vr_file.parent.mkdir(parents=True, exist_ok=True)
        vr_file.write_text(json.dumps(record, indent=2))
    except Exception:
        pass  # Never block session start




def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--load-context', action='store_true',
                          help='Load development context at session start')
        parser.add_argument('--announce', action='store_true',
                          help='Announce session start via TTS')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract fields
        session_id = input_data.get('session_id', 'unknown')
        source = input_data.get('source', 'unknown')  # "startup", "resume", or "clear"

        # Reset verification record — prevent stale cross-session evidence
        reset_verification_record(session_id)

        # Create default VR so stop.py always has a well-formed file
        _create_default_vr(session_id)

        # Generate unique agent identity for this session (scopes Qwen state)
        agent_id = _generate_agent_identity(session_id)

        # Register this session in active_sessions.json for shell script lookups
        # Register both CWD and git root to handle cd-into-subdirectory lookups
        _register_active_session(session_id, os.getcwd())
        try:
            sys.path.insert(0, str(Path(__file__).parent / "utils"))
            from project_config import get_git_root
            git_root = get_git_root()
            if git_root != os.getcwd():
                _register_active_session(session_id, git_root)
        except Exception:
            pass

        # Ensure project .gitignore covers .claude/data/ .claude/artifacts/ .claude/reports/
        try:
            from project_config import ensure_project_gitignore
            ensure_project_gitignore()
        except Exception:
            pass

        # Log the session start event
        log_session_start(input_data)

        # Session key — the agent needs these in-context to declare scope
        # (see hooks/utils/session_scope.py; consumed by stop.py:_phase_1_implement).
        # Emitted on every session start, not just when --load-context is set,
        # because without the key the agent can't satisfy Phase 1.
        from project_config import get_project_data_dir
        scope_file = get_project_data_dir() / f"session_scope_{session_id}.json"
        key_context = (
            f"Session key: {session_id}\n"
            f"Agent id: {agent_id}\n\n"
            f"Before your first stop, declare this session's spec scope by writing\n"
            f"{scope_file} with one of:\n"
            f'  {{"specs": ["/absolute/path/to/project/specs/<name>.md", ...]}}  — specs this session is working on\n'
            f'  {{"no_spec": true, "reason": "<why>"}}  — trivial / no-spec work\n'
            f"The Stop hook (Phase 1) will not pass without this file."
        )
        if args.load_context:
            dev_context = load_development_context(source, agent_id=agent_id)
            additional_context = (
                f"{key_context}\n\n{dev_context}" if dev_context else key_context
            )
        else:
            additional_context = key_context
        _spawn_background_indexer(os.getcwd())
        try:
            if subprocess.run(['git', 'rev-parse', '--git-dir'], capture_output=True, timeout=3).returncode == 0:
                additional_context += '\nCode search: prefer `search_code` MCP tool for concept/semantic queries (e.g. "functions that handle auth"). Use grep/find only for exact string matches.'
        except Exception:
            pass
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": additional_context,
            }
        }))
        
        # Announce session start if requested
        if args.announce:
            try:
                # Try to use TTS to announce session start
                script_dir = Path(__file__).parent
                tts_script = script_dir / "utils" / "tts" / "pyttsx3_tts.py"
                
                if tts_script.exists():
                    messages = {
                        "startup": "Claude Code session started",
                        "resume": "Resuming previous session",
                        "clear": "Starting fresh session"
                    }
                    message = messages.get(source, "Session started")
                    
                    subprocess.run(
                        ["uv", "run", str(tts_script), message],
                        capture_output=True,
                        timeout=5
                    )
            except Exception:
                pass
        
        # Success
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == '__main__':
    main()