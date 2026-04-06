#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
#     "openai",
# ]
# ///

import argparse
import json
import os
import sys
import subprocess
import time
from pathlib import Path

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


# ── TTS ──────────────────────────────────────────────────────────────────

def get_tts_script_path():
    """Determine which TTS script to use based on available API keys."""
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"
    if os.getenv('ELEVENLABS_API_KEY'):
        p = tts_dir / "elevenlabs_tts.py"
        if p.exists():
            return str(p)
    if os.getenv('OPENAI_API_KEY'):
        p = tts_dir / "openai_tts.py"
        if p.exists():
            return str(p)
    p = tts_dir / "pyttsx3_tts.py"
    return str(p) if p.exists() else None


def announce_completion():
    """Announce completion using the best available TTS service."""
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return
        subprocess.run(
            ["uv", "run", tts_script, "Task complete"],
            capture_output=True, timeout=10,
        )
    except Exception:
        pass


# ── Stop attempt tracking ────────────────────────────────────────────────

def get_stop_attempts_path():
    return Path(__file__).parent.parent / "data" / "stop_attempts.json"


def record_stop_attempt():
    attempts_file = get_stop_attempts_path()
    attempts_file.parent.mkdir(parents=True, exist_ok=True)
    attempts = []
    if attempts_file.exists():
        try:
            attempts = json.loads(attempts_file.read_text()).get("attempts", [])
        except Exception:
            attempts = []
    attempts.append({"ts": time.time()})
    attempts = attempts[-10:]
    try:
        attempts_file.write_text(json.dumps({"attempts": attempts}))
    except IOError:
        pass
    return attempts


def detect_emergency_mode(attempts):
    now = time.time()
    recent = [a for a in attempts if now - a.get("ts", 0) <= 30.0]
    count = len(recent)
    if count >= 3:
        earliest = min(a["ts"] for a in recent)
        return (True, count, round(now - earliest, 1))
    return (False, count, 0)


# ── Spec acceptance criteria validation ──────────────────────────────────

def check_spec_completion(cwd=None):
    """Check active spec files for uncompleted acceptance criteria.

    Returns (all_done, summary_lines) where summary_lines is a list of
    human-readable strings describing spec completion status.
    Never raises — informational only.
    """
    try:
        specs_dir = Path(cwd or os.getcwd()) / "specs"
        if not specs_dir.is_dir():
            return (True, [])

        results = []
        all_done = True
        for spec_file in sorted(specs_dir.glob("*.md")):
            try:
                content = spec_file.read_text(errors='replace')
                if not content.startswith("---"):
                    continue
                parts = content.split("---", 2)
                if len(parts) < 3:
                    continue
                fm = parts[1]
                status = ""
                title = ""
                for line in fm.split("\n"):
                    line = line.strip()
                    if line.startswith("status:"):
                        status = line[7:].strip()
                    elif line.startswith("title:"):
                        title = line[6:].strip().strip("'\"")
                if status not in ("active", "in-progress"):
                    continue
                body = parts[2]
                unchecked = body.count("- [ ]")
                checked = body.count("- [x]")
                total = unchecked + checked
                if total == 0:
                    continue
                if unchecked > 0:
                    all_done = False
                    results.append(
                        f"  \u26a0  {spec_file.name}: {title} — "
                        f"{checked}/{total} criteria met, {unchecked} remaining"
                    )
                else:
                    results.append(
                        f"  \u2705 {spec_file.name}: {title} — "
                        f"{total}/{total} criteria met"
                    )
            except Exception:
                continue
        return (all_done, results)
    except Exception:
        return (True, [])


# ── Root cleanliness ─────────────────────────────────────────────────────

def check_root_cleanliness():
    allowed_patterns = {
        'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
        'pyproject.toml', 'poetry.lock', 'Pipfile', 'Pipfile.lock',
        'Cargo.toml', 'Cargo.lock', 'go.mod', 'go.sum',
        'tsconfig.json', 'jsconfig.json',
        'webpack.config.js', 'vite.config.js', 'rollup.config.js',
        'jest.config.js', 'vitest.config.js', 'playwright.config.js',
        '.eslintrc.js', '.eslintrc.json', 'eslint.config.mjs', 'eslint.config.js',
        '.prettierrc', '.prettierrc.json', '.prettierrc.js',
        '.editorconfig', '.nvmrc', '.node-version', '.python-version',
        'babel.config.js', '.babelrc', '.babelrc.json',
        'README.md', 'README.txt', 'README.rst', 'CLAUDE.md',
        'LICENSE', 'LICENSE.md', 'LICENSE.txt', 'NOTICE', 'CONTRIBUTING.md',
        'CHANGELOG.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'RELEASE_PROCESS.md',
        'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
        'Makefile', 'makefile', 'CMakeLists.txt',
        '.gitignore', '.gitattributes', '.dockerignore',
        '.github', '.gitlab', '.vscode', '.idea',
        '.git', '.svn', '.hg',
        'main.py', 'app.py', 'index.js', 'index.ts', 'main.go', 'main.rs',
        'src', 'tests', 'test', 'docs', 'scripts', 'config',
        'public', 'static', 'assets', 'lib',
        'node_modules', '__pycache__', '.cache', 'venv', '.venv',
        'output', 'reports', 'mcp_server', 'specs',
        '.pre-commit-config.yaml', '.husky',
        '.claude', 'data', 'plans', 'projects', 'todos', 'statsig',
        'shell-snapshots', 'session-env', 'file-history', 'paste-cache',
        'claude-mem', 'cache', 'checkpoints', 'telemetry', 'tasks',
        'plugins', 'helpers', 'status_lines', 'debug', 'logs',
        'history.jsonl', 'stats-cache.json', 'architectural_decisions.json',
        'lessons.json', 'statusline-command.sh',
        'settings.local.json', 'settings copy.json',
        'python-scripts', 'commands', 'agents', 'skills', 'hooks',
        '.validation-artifacts', '.swarm', '.claude-flow', '.ruff_cache',
        'New Tools', 'target', '.next',
        '.claude-project.json',
    }
    forbidden_extensions = {
        '.log', '.tmp', '.bak', '.swp', '.swo',
        '.csv', '.xlsx', '.xls', '.tsv',
        '.pdf', '.docx', '.doc',
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mp3',
        '.zip', '.tar', '.gz', '.tgz', '.rar',
        '.exe', '.o', '.so', '.dylib', '.dll',
        '.txt', '.md', '.out', '.xml',
    }
    violations = []
    cwd = Path.cwd()
    if cwd.name == '.claude' or any(p.name == '.claude' for p in cwd.parents):
        return (True, [])
    try:
        for item in cwd.iterdir():
            name = item.name
            if name in allowed_patterns:
                continue
            if item.is_file():
                ext = item.suffix.lower()
                if ext in forbidden_extensions:
                    violations.append(f"  {name} (file)")
        return (len(violations) == 0, violations)
    except Exception:
        return (True, [])


# ── Upstream sync ────────────────────────────────────────────────────────

def check_upstream_sync(cwd=None):
    try:
        kw = dict(capture_output=True, text=True, cwd=cwd)
        r = subprocess.run(['git', 'remote'], timeout=5, **kw)
        if r.returncode != 0 or 'upstream' not in r.stdout.split():
            return None
        branch_r = subprocess.run(['git', 'branch', '--show-current'], timeout=5, **kw)
        branch = branch_r.stdout.strip() or 'main'
        fetch_r = subprocess.run(
            ['git', 'fetch', 'upstream', '--quiet'],
            capture_output=True, cwd=cwd, timeout=15,
        )
        if fetch_r.returncode != 0:
            return {'behind': None, 'branch': branch, 'fetch_ok': False}
        behind_r = subprocess.run(
            ['git', 'rev-list', '--count', f'HEAD..upstream/{branch}'], timeout=5, **kw,
        )
        behind = int(behind_r.stdout.strip() or '0') if behind_r.returncode == 0 else None
        return {'behind': behind, 'branch': branch, 'fetch_ok': True}
    except Exception:
        return None


# ── Rate limit detection ─────────────────────────────────────────────────

def detect_rate_limit(input_data):
    last_msg_patterns = [
        'rate limit', 'rate_limit', 'ratelimit',
        'too many requests', 'too_many_requests',
        'RateLimitError', 'OverloadedError',
        'resource_exhausted', 'server is overloaded',
        'rate limit exceeded', 'api rate limit',
        'quota exceeded', 'anthropic.rate_limit',
    ]
    rate_limit_patterns = last_msg_patterns + [
        'http 429', 'status: 429', '" 429"', "'429'",
        'overloaded', 'overload', 'throttl',
        'retry after', 'retry_after', 'request limit',
    ]

    def check_text(text, patterns):
        if not text:
            return None
        text_lower = text.lower()
        for p in patterns:
            if p.lower() in text_lower:
                return p
        return None

    last_msg = input_data.get('last_assistant_message', '')
    match = check_text(last_msg, last_msg_patterns)
    if match:
        return (True, f"Rate limit detected in last message (matched: '{match}')")

    transcript_path = input_data.get('transcript_path', '')
    if transcript_path and Path(transcript_path).exists():
        try:
            with open(transcript_path) as f:
                lines = f.readlines()
            for line in lines[-10:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    msg = entry.get('message', {})
                    content = msg.get('content', '')
                    if isinstance(content, str):
                        match = check_text(content, rate_limit_patterns)
                        if match:
                            return (True, f"Rate limit in transcript (matched: '{match}')")
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                block_text = block.get('text', '') or block.get('content', '') or ''
                                match = check_text(block_text, rate_limit_patterns)
                                if match:
                                    return (True, f"Rate limit in transcript (matched: '{match}')")
                    if entry.get('type') == 'error':
                        match = check_text(json.dumps(entry), rate_limit_patterns)
                        if match:
                            return (True, f"Rate limit error entry (matched: '{match}')")
                except Exception:
                    match = check_text(line, rate_limit_patterns)
                    if match:
                        return (True, f"Rate limit in raw transcript (matched: '{match}')")
        except Exception:
            pass
    return (False, '')


# ── Session ID resolution ────────────────────────────────────────────────

def _resolve_session_id(session_id: str) -> str:
    """Resolve the canonical session ID for VR/auth file lookups.

    Prefers active_sessions.json (authoritative for the current session) over
    stale VR files from prior sessions. Old VR files persist after session
    restarts, causing the harness-provided session_id to resolve to a stale
    session while authorize-stop.sh writes auth for the current one.
    """
    # 1. Check active_sessions.json first — most authoritative for current session
    try:
        sessions_file = Path.home() / ".claude/data/active_sessions.json"
        if sessions_file.exists():
            sessions = json.loads(sessions_file.read_text())
            try:
                sys.path.insert(0, str(Path(__file__).parent / "utils"))
                from project_config import get_git_root
                git_root = get_git_root()
                for lookup_dir in [git_root, os.getcwd()]:
                    resolved = sessions.get(lookup_dir, "")
                    if resolved and (Path.home() / f".claude/data/verification_record_{resolved}.json").exists():
                        return resolved
            except Exception:
                cwd = os.getcwd()
                resolved = sessions.get(cwd, "")
                if resolved and (Path.home() / f".claude/data/verification_record_{resolved}.json").exists():
                    return resolved
    except Exception:
        pass
    # 2. Fall back to harness-provided session_id if its VR file exists
    if (Path.home() / f".claude/data/verification_record_{session_id}.json").exists():
        return session_id
    return session_id


def check_stop_authorization(session_id: str = "default"):
    session_id = _resolve_session_id(session_id)
    auth_file = Path.home() / f".claude/data/stop_authorization_{session_id}.json"
    if not auth_file.exists():
        return False
    try:
        return json.loads(auth_file.read_text()).get("authorized", False)
    except Exception:
        return False


# ── Config-driven verification gate ──────────────────────────────────────

def check_verification(session_id: str) -> tuple[bool, list, list]:
    """Check required verification items against the project config.

    Returns (all_passed, done_items, missing_items).
    Each item is (key, label, status, ts_short, evidence_short).
    """
    try:
        sys.path.insert(0, str(Path(__file__).parent / "utils"))
        from project_config import get_git_root, load_config, get_required_checks
        from vr_utils import VR_CHECKS_ORDER
    except ImportError:
        # Fallback: allow stop if config system unavailable
        return (True, [], [])

    session_id = _resolve_session_id(session_id)
    vr_file = Path.home() / f".claude/data/verification_record_{session_id}.json"

    try:
        record = json.loads(vr_file.read_text())
        checks = record.get("checks", {})
    except Exception:
        checks = {}

    project_root = Path(get_git_root())
    config = load_config(project_root)

    # Determine if files were modified (heuristic: any non-pending check)
    files_modified = any(
        checks.get(k, {}).get("status") not in ("pending", None)
        for k in ("tests", "build", "lint")
    )
    required = get_required_checks(config, files_modified=files_modified)
    label_map = {k: label for k, label in VR_CHECKS_ORDER}

    done = []
    missing = []
    for key in required:
        label = label_map.get(key, key.upper())
        item = checks.get(key, {})
        status = item.get("status", "pending")
        if status == "pending":
            run_cmd = config.get("checks", {}).get(key, {})
            if isinstance(run_cmd, dict):
                run_cmd = run_cmd.get("run_command", "")
            else:
                run_cmd = ""
            missing.append((key, label, "pending", None, run_cmd or None))
        else:
            ts = item.get("timestamp", "")
            ts_short = ts[11:16] if ts else "?"
            ev = (item.get("evidence") or item.get("skip_reason") or "")[:60].replace("\n", " ")
            done.append((key, label, status, ts_short, ev))

    return (len(missing) == 0, done, missing)


def build_blocked_message(done: list, missing: list, config: dict) -> str:
    ptype = config.get("project_type", "unknown")
    lines = [
        "",
        "=" * 60,
        "STOP BLOCKED — VERIFICATION INCOMPLETE",
        "=" * 60,
        "",
        f"Project type: {ptype}",
        "",
    ]
    for key, label, status, ts_short, ev in done:
        mark = "\u2705" if status in ("done", "passed") else "\u23ed "
        ev_display = f' — "{ev}"' if ev else ""
        lines.append(f"  {mark} {label:<18} [{status} @ {ts_short}]{ev_display}")
    lines.append("")
    for key, label, _status, _ts, run_cmd in missing:
        hint = f" — run: {run_cmd}" if run_cmd else ""
        lines.append(f"  \u274c {label:<18} not observed{hint}")
    lines += [
        "",
        "Run the missing checks, then: bash ~/.claude/commands/authorize-stop.sh",
        "=" * 60,
        "",
    ]
    return "\n".join(lines)


def build_evidence_display(done: list, session_id: str) -> str:
    """Show evidence summary for all completed checks."""
    session_id = _resolve_session_id(session_id)
    vr_file = Path.home() / f".claude/data/verification_record_{session_id}.json"
    try:
        checks = json.loads(vr_file.read_text()).get("checks", {})
    except Exception:
        checks = {}

    lines = [
        "",
        "=" * 60,
        "VERIFICATION EVIDENCE SUMMARY",
        "=" * 60,
        "",
    ]
    sep = "\u2500" * 60
    for i, (key, label, status, ts_short, _ev_short) in enumerate(done, 1):
        check_data = checks.get(key, {})
        if status == "skipped":
            full_ev = check_data.get("skip_reason") or ""
            ev_label = "Skip reason"
        else:
            full_ev = check_data.get("evidence") or ""
            ev_label = "Command output"
        mark = "\u2705" if status in ("done", "passed") else "\u23ed "
        lines.append(f"{mark} Step {i}: {label.strip()}  [{status} @ {ts_short}]")
        lines.append(sep)
        if full_ev:
            display_ev = full_ev[:500]
            lines.append(f"{ev_label}:")
            for ev_line in display_ev.split("\n"):
                lines.append(f"  {ev_line}")
            if len(full_ev) > 500:
                lines.append(f"  ... [{len(full_ev) - 500} more chars truncated]")
        else:
            lines.append(f"{ev_label}: (none recorded)")
        lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# ── Phase handlers ──────────────────────────────────────────────────────
# Each returns (passed: bool, message: str). Message is shown only on failure.

def _phase_1_implement(session_id: str, config: dict) -> tuple[bool, str]:
    """Phase 1: Implementation complete — spec criteria + root cleanliness."""
    issues = []

    # Root cleanliness
    is_clean, violations = check_root_cleanliness()
    if not is_clean:
        issues.append("Root folder not clean:")
        issues.extend(violations)
        issues.append("")
        issues.append("Move/delete violations, then retry.")

    # Spec acceptance criteria
    spec_done, spec_summary = check_spec_completion()
    if not spec_done:
        issues.append("Spec acceptance criteria incomplete:")
        issues.extend(spec_summary)
        issues.append("")
        issues.append("Complete all acceptance criteria before proceeding.")

    if issues:
        return (False, "\n".join(issues))
    return (True, "")


def _phase_2_static_analysis(session_id: str, config: dict) -> tuple[bool, str]:
    """Phase 2: Lint + typecheck must pass (zero errors)."""
    resolved_sid = _resolve_session_id(session_id)
    vr_file = Path.home() / f".claude/data/verification_record_{resolved_sid}.json"

    try:
        sys.path.insert(0, str(Path(__file__).parent / "utils"))
        from project_config import get_git_root, auto_run_missing
        from vr_utils import write_vr as _write_vr

        project_root = Path(get_git_root())

        # Force fresh lint — never trust cached partial results
        _write_vr(vr_file, "lint", "pending", "", session_id=None)
        auto_run_missing(resolved_sid, config, vr_file, project_root)
    except Exception:
        pass

    try:
        record = json.loads(vr_file.read_text())
        checks = record.get("checks", {})
    except Exception:
        checks = {}

    from project_config import get_required_checks
    required = get_required_checks(config)

    issues = []
    phase_checks = ["lint", "typecheck"]

    for key in phase_checks:
        if key not in required:
            continue
        item = checks.get(key, {})
        status = item.get("status", "pending")
        if status == "pending":
            run_cmd = config.get("checks", {}).get(key, {})
            if isinstance(run_cmd, dict):
                run_cmd = run_cmd.get("run_command", "")
            else:
                run_cmd = ""
            hint = f" — run: {run_cmd}" if run_cmd else ""
            issues.append(f"  \u274c {key.upper():<18} not observed{hint}")
        elif status == "failed":
            ev = (item.get("evidence") or "")[:400]
            issues.append(f"  \u274c {key.upper():<18} FAILED")
            if ev:
                for ev_line in ev.split("\n")[:10]:
                    issues.append(f"     {ev_line}")

    if issues:
        msg = "\n".join(issues)
        msg += "\n\nFix all errors, then retry."
        return (False, msg)
    return (True, "")


def _phase_3_tests(session_id: str, config: dict) -> tuple[bool, str]:
    """Phase 3: Tests — required only for stable, important features."""
    resolved_sid = _resolve_session_id(session_id)
    vr_file = Path.home() / f".claude/data/verification_record_{resolved_sid}.json"

    from project_config import get_required_checks

    required = get_required_checks(config)
    if "tests" not in required:
        return (True, "")

    # Apply test necessity heuristic
    try:
        from project_config import should_require_tests
        from vr_utils import parse_transcript

        # Get modified files from VR or transcript
        task_file = Path.home() / f".claude/data/current_task_{resolved_sid}.json"
        task_start = None
        transcript_path = None
        if task_file.exists():
            try:
                task_data = json.loads(task_file.read_text())
                task_start = task_data.get("started_at")
                transcript_path = task_data.get("transcript_path")
            except Exception:
                pass

        modified_files = []
        if transcript_path:
            modified_files, _, _ = parse_transcript(transcript_path, task_start)

        # Check for active spec
        has_active_spec = False
        specs_dir = Path.cwd() / "specs"
        if specs_dir.is_dir():
            for sf in specs_dir.glob("*.md"):
                try:
                    content = sf.read_text(errors="replace")
                    if "status: active" in content or "status: in-progress" in content:
                        has_active_spec = True
                        break
                except Exception:
                    continue

        if not should_require_tests(config, modified_files, has_active_spec):
            return (True, "")
    except Exception:
        pass  # If heuristic fails, fall through to normal check

    try:
        record = json.loads(vr_file.read_text())
        checks = record.get("checks", {})
    except Exception:
        checks = {}

    item = checks.get("tests", {})
    status = item.get("status", "pending")

    if status == "pending":
        run_cmd = config.get("checks", {}).get("tests", {})
        if isinstance(run_cmd, dict):
            run_cmd = run_cmd.get("run_command", "")
        else:
            run_cmd = ""
        hint = f"\n\nRun: {run_cmd}" if run_cmd else ""
        return (False, f"  \u274c TESTS not run yet.{hint}")
    elif status == "failed":
        ev = (item.get("evidence") or "")[:500]
        msg = "  \u274c TESTS FAILED\n"
        if ev:
            for ev_line in ev.split("\n")[:15]:
                msg += f"     {ev_line}\n"
        msg += "\nFix failing tests, then retry."
        return (False, msg)

    return (True, "")


def _phase_4_build(session_id: str, config: dict) -> tuple[bool, str]:
    """Phase 4: Build verification + app startup."""
    resolved_sid = _resolve_session_id(session_id)
    vr_file = Path.home() / f".claude/data/verification_record_{resolved_sid}.json"

    from project_config import get_required_checks
    required = get_required_checks(config)

    try:
        record = json.loads(vr_file.read_text())
        checks = record.get("checks", {})
    except Exception:
        checks = {}

    phase_checks = ["build", "app_starts"]
    issues = []

    for key in phase_checks:
        if key not in required:
            continue
        item = checks.get(key, {})
        status = item.get("status", "pending")
        label = "BUILD" if key == "build" else "APP STARTS"

        if status == "pending":
            run_cmd = config.get("checks", {}).get(key, {})
            if isinstance(run_cmd, dict):
                run_cmd = run_cmd.get("run_command", "")
            else:
                run_cmd = ""
            hint = f" — run: {run_cmd}" if run_cmd else ""
            issues.append(f"  \u274c {label:<18} not observed{hint}")
        elif status == "failed":
            ev = (item.get("evidence") or "")[:400]
            issues.append(f"  \u274c {label:<18} FAILED")
            if ev:
                for ev_line in ev.split("\n")[:10]:
                    issues.append(f"     {ev_line}")

    if issues:
        msg = "\n".join(issues)
        msg += "\n\nFix build/startup failures, then retry."
        return (False, msg)
    return (True, "")


def _phase_5_frontend(session_id: str, config: dict) -> tuple[bool, str]:
    """Phase 5: Frontend validation via Playwright/Cypress."""
    if not config.get("has_frontend", False):
        return (True, "")

    try:
        sys.path.insert(0, str(Path(__file__).parent / "utils"))
        from project_config import get_git_root
        project_root = Path(get_git_root())
    except Exception:
        project_root = Path.cwd()

    # Check E2E framework exists
    _pw_configs = ("playwright.config.ts", "playwright.config.js",
                   "playwright.config.mjs", "playwright.config.cjs")
    _cy_configs = ("cypress.config.ts", "cypress.config.js",
                   "cypress.config.mjs", "cypress.config.cjs")
    _has_e2e = (any((project_root / f).exists() for f in _pw_configs) or
                any((project_root / f).exists() for f in _cy_configs))

    if not _has_e2e:
        return (False,
            "Frontend detected but no E2E test framework configured.\n"
            "Set up Playwright: npx playwright init\n"
            "Write and pass ALL E2E tests before stopping."
        )

    resolved_sid = _resolve_session_id(session_id)
    vr_file = Path.home() / f".claude/data/verification_record_{resolved_sid}.json"

    from project_config import get_required_checks
    required = get_required_checks(config)

    try:
        record = json.loads(vr_file.read_text())
        checks = record.get("checks", {})
    except Exception:
        checks = {}

    phase_checks = ["frontend", "happy_path"]
    issues = []

    for key in phase_checks:
        if key not in required:
            continue
        item = checks.get(key, {})
        status = item.get("status", "pending")
        label = "FRONTEND" if key == "frontend" else "HAPPY PATH"

        if status == "pending":
            run_cmd = config.get("checks", {}).get(key, {})
            if isinstance(run_cmd, dict):
                run_cmd = run_cmd.get("run_command", "")
            else:
                run_cmd = ""
            hint = f" — run: {run_cmd}" if run_cmd else ""
            issues.append(f"  \u274c {label:<18} not observed{hint}")
        elif status == "failed":
            ev = (item.get("evidence") or "")[:500]
            issues.append(f"  \u274c {label:<18} FAILED")
            if ev:
                for ev_line in ev.split("\n")[:10]:
                    issues.append(f"     {ev_line}")

    if issues:
        msg = "\n".join(issues)
        msg += "\n\nFix frontend failures. All E2E tests must pass."
        return (False, msg)

    # Belt-and-suspenders: verify Playwright evidence has zero failures
    import re as _re
    fe_check = checks.get("frontend", {})
    fe_evidence = fe_check.get("evidence", "")
    if fe_evidence:
        fail_match = _re.search(r'(\d+)\s+failed', fe_evidence)
        if fail_match and int(fail_match.group(1)) > 0:
            return (False,
                f"{fail_match.group(1)} Playwright test(s) failed.\n"
                "ALL tests must pass. Zero failures tolerated.\n"
                "Fix and re-run: npx playwright test"
            )

    return (True, "")


def _phase_6_ship(session_id: str, config: dict) -> tuple[bool, str]:
    """Phase 6: Security scan, commit, push, upstream sync."""
    resolved_sid = _resolve_session_id(session_id)
    vr_file = Path.home() / f".claude/data/verification_record_{resolved_sid}.json"

    try:
        sys.path.insert(0, str(Path(__file__).parent / "utils"))
        from project_config import get_git_root, auto_run_missing
        project_root = Path(get_git_root())

        # Auto-run security and upstream_sync
        auto_run_missing(resolved_sid, config, vr_file, project_root)
    except Exception:
        pass

    # Detect if there are actual uncommitted or unpushed changes
    has_changes = False
    try:
        from project_config import get_git_root
        _root = get_git_root()
        _kw = dict(capture_output=True, text=True, timeout=5, cwd=_root)
        # Uncommitted tracked changes?
        _diff = subprocess.run(["git", "diff", "HEAD", "--name-only"], **_kw)
        if _diff.stdout.strip():
            has_changes = True
        # Staged but uncommitted?
        if not has_changes:
            _staged = subprocess.run(["git", "diff", "--cached", "--name-only"], **_kw)
            if _staged.stdout.strip():
                has_changes = True
        # Unpushed commits?
        if not has_changes:
            _branch = subprocess.run(["git", "branch", "--show-current"], **_kw)
            _b = _branch.stdout.strip() or "main"
            _rev = subprocess.run(
                ["git", "rev-list", f"origin/{_b}...HEAD", "--count"], **_kw,
            )
            if _rev.returncode == 0 and int(_rev.stdout.strip() or "0") > 0:
                has_changes = True
    except Exception:
        has_changes = True  # Assume changes if detection fails

    # Detect if upstream remote exists (fork scenario)
    has_upstream = False
    try:
        _remotes = subprocess.run(
            ["git", "remote"], capture_output=True, text=True, timeout=5,
            cwd=get_git_root(),
        )
        has_upstream = "upstream" in _remotes.stdout.split()
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"  [phase6] upstream remote detection failed ({exc}), skipping sync", file=sys.stderr)

    from project_config import get_required_checks
    required = get_required_checks(config, files_modified=has_changes)

    # Remove upstream_sync if no upstream remote exists
    if not has_upstream and "upstream_sync" in required:
        required = [r for r in required if r != "upstream_sync"]

    try:
        record = json.loads(vr_file.read_text())
        checks = record.get("checks", {})
    except Exception:
        checks = {}

    phase_checks = ["security", "commit_push", "upstream_sync", "execution"]
    label_map = {
        "security": "SECURITY",
        "commit_push": "COMMIT & PUSH",
        "upstream_sync": "UPSTREAM SYNC",
        "execution": "EXECUTION",
    }
    issues = []

    for key in phase_checks:
        if key not in required:
            continue
        item = checks.get(key, {})
        status = item.get("status", "pending")
        label = label_map.get(key, key.upper())

        if status == "pending":
            if key == "commit_push":
                issues.append(f"  \u274c {label:<18} — commit and push your changes")
            elif key == "security":
                issues.append(f"  \u274c {label:<18} — security scan not run")
            else:
                issues.append(f"  \u274c {label:<18} — not verified")
        elif status == "failed":
            ev = (item.get("evidence") or "")[:300]
            issues.append(f"  \u274c {label:<18} FAILED")
            if ev:
                for ev_line in ev.split("\n")[:8]:
                    issues.append(f"     {ev_line}")

    if issues:
        msg = "\n".join(issues)
        msg += "\n\nFix issues, commit, push, then retry."
        return (False, msg)
    return (True, "")


def _phase_7_reviewer(session_id: str, config: dict, input_data: dict) -> tuple[bool, str]:
    """Phase 7: GPT-5 Mini protocol compliance review.

    IMPORTANT: stop.py runs under bare python3 (not uv run --script),
    so openai/dotenv are NOT importable. The reviewer runs as a subprocess.
    """
    resolved_sid = _resolve_session_id(session_id)

    try:
        _reviewer_script = Path(__file__).parent / "utils" / "reviewer.py"
        _data_dir = Path.home() / ".claude" / "data"

        # Check if reviewer is enabled
        _rev_enabled = True
        _rev_max_rounds = 5
        _rev_config_file = _data_dir / "reviewer_config.json"
        if _rev_config_file.exists():
            try:
                _rev_conf = json.loads(_rev_config_file.read_text())
                _rev_enabled = _rev_conf.get("enabled", True)
                _rev_max_rounds = _rev_conf.get("max_rounds", 5)
            except Exception:
                pass

        if not _rev_enabled:
            print("  [reviewer] Disabled in config \u2014 skipping", file=sys.stderr)
            return (True, "")
        if not _reviewer_script.exists():
            print("  [reviewer] reviewer.py not found \u2014 skipping", file=sys.stderr)
            return (True, "")

        # Check for existing approval
        _approval_file = _data_dir / f"reviewer_approval_{resolved_sid}.json"
        if _approval_file.exists():
            try:
                if json.loads(_approval_file.read_text()).get("approved", False):
                    return (True, "")
            except Exception:
                pass

        # Check OPENAI_API_KEY
        _has_api_key = bool(os.getenv("OPENAI_API_KEY"))
        if not _has_api_key:
            _env_file = Path.home() / ".claude" / ".env"
            if _env_file.exists():
                try:
                    for _line in _env_file.read_text().splitlines():
                        _line = _line.strip()
                        if _line.startswith("OPENAI_API_KEY=") and len(_line) > 15:
                            _has_api_key = True
                            break
                except Exception:
                    pass

        if not _has_api_key:
            print("  [reviewer] OPENAI_API_KEY not set \u2014 skipping (non-blocking)", file=sys.stderr)
            return (True, "")

        # Call reviewer
        print("\n  Running GPT-5 Mini protocol review (Phase 7)...\n", file=sys.stderr)
        _last_msg = input_data.get("last_assistant_message", "")
        _rev_cmd = [
            "uv", "run", "--script", str(_reviewer_script),
            resolved_sid, "--json",
        ]
        if _last_msg:
            _rev_cmd.extend(["--last-message", _last_msg])

        _rev_proc = subprocess.run(
            _rev_cmd,
            capture_output=True, text=True, timeout=180,
            cwd=os.getcwd(),
        )

        if _rev_proc.returncode == 1:
            # FINDINGS
            lines = []
            try:
                _rev_data = json.loads(_rev_proc.stdout)
                _round = _rev_data.get("round_count", "?")
                lines.append(f"Round {_round} of {_rev_max_rounds}")
                lines.append("")
                for _finding in _rev_data.get("findings", []):
                    _sev_icon = (
                        "\U0001f6ab"
                        if _finding.get("severity") == "blocking"
                        else "\u26a0\ufe0f"
                    )
                    _cat = _finding.get("category", "?")
                    _desc = _finding.get("description", "")
                    lines.append(f"  {_sev_icon} [{_cat}] {_desc}")
                    if _finding.get("evidence_needed"):
                        lines.append(f"     \u2192 {_finding['evidence_needed']}")
                    lines.append("")
                lines.append(f"Summary: {_rev_data.get('summary', '')}")
            except Exception:
                lines.append("  (Could not parse reviewer output)")
                if _rev_proc.stdout:
                    lines.append(f"  stdout: {_rev_proc.stdout[:500]}")
            lines.append("")
            lines.append("Address the findings, then retry stop.")
            return (False, "\n".join(lines))

        elif _rev_proc.returncode == 0:
            try:
                _rev_data = json.loads(_rev_proc.stdout)
                _summary = _rev_data.get("summary", "Approved")
                print(f"  [reviewer] APPROVED: {_summary}", file=sys.stderr)
            except Exception:
                print("  [reviewer] APPROVED", file=sys.stderr)
            return (True, "")
        else:
            _err = (_rev_proc.stderr or _rev_proc.stdout or "")[:300]
            print(f"  [reviewer] Error (non-blocking, exit {_rev_proc.returncode}): {_err}", file=sys.stderr)
            return (True, "")

    except subprocess.TimeoutExpired:
        print("  [reviewer] Timed out after 180s (non-blocking)", file=sys.stderr)
        return (True, "")
    except FileNotFoundError:
        print("  [reviewer] uv not found \u2014 skipping (non-blocking)", file=sys.stderr)
        return (True, "")
    except Exception as _rev_exc:
        print(
            f"  [reviewer] Error (non-blocking): {type(_rev_exc).__name__}: "
            f"{str(_rev_exc)[:200]}",
            file=sys.stderr,
        )
        return (True, "")


# ── Phase dispatcher ────────────────────────────────────────────────────

PHASE_HANDLERS = {
    1: ("IMPLEMENT",        _phase_1_implement),
    2: ("STATIC ANALYSIS",  _phase_2_static_analysis),
    3: ("TESTS",            _phase_3_tests),
    4: ("BUILD",            _phase_4_build),
    5: ("FRONTEND",         _phase_5_frontend),
    6: ("SHIP",             _phase_6_ship),
    # Phase 7 (reviewer) handled specially — needs input_data
}

PHASE_COUNT = 7


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    try:
        # Read stdin early
        try:
            raw_stdin = sys.stdin.read()
            input_data = json.loads(raw_stdin) if raw_stdin.strip() else {}
        except (json.JSONDecodeError, ValueError):
            input_data = {}

        session_id = input_data.get("session_id", "default")

        # ── Phase 0: Bypass gates (rate limit + emergency) ──────────────
        is_rate_limited, detail = detect_rate_limit(input_data)
        if is_rate_limited:
            print(f"\nSTOP ALLOWED \u2014 RATE LIMIT DETECTED\n{detail}\n", file=sys.stderr)
            sys.exit(0)

        attempts = record_stop_attempt()
        is_emergency, attempt_count, span = detect_emergency_mode(attempts)
        if is_emergency and not check_stop_authorization(session_id):
            auth_script = Path(__file__).parent.parent / "commands" / "authorize-stop.sh"
            print(
                f"\n  EMERGENCY: {attempt_count} stop attempts in {span}s.\n"
                f"  Complete your work, then run: bash {auth_script}\n",
                file=sys.stderr,
            )
            sys.exit(2)

        # ── Load project config ─────────────────────────────────────────
        try:
            sys.path.insert(0, str(Path(__file__).parent / "utils"))
            from project_config import get_git_root, load_config
            config = load_config(Path(get_git_root()))
        except Exception:
            config = {}

        # ── Resolve session and VR ──────────────────────────────────────
        resolved_sid = _resolve_session_id(session_id)
        vr_file = Path.home() / f".claude/data/verification_record_{resolved_sid}.json"

        # Read current phase from VR (defaults to 1)
        try:
            from vr_utils import get_current_phase, advance_phase
            current_phase, current_phase_name = get_current_phase(vr_file)
        except Exception:
            current_phase = 1

        # ── Phase loop: auto-advance through passing phases ─────────────
        for phase_num in range(current_phase, PHASE_COUNT + 1):
            if phase_num in PHASE_HANDLERS:
                phase_label, handler = PHASE_HANDLERS[phase_num]
                passed, message = handler(session_id, config)
            elif phase_num == 7:
                # Phase 7: Reviewer (needs authorization first)
                if not check_stop_authorization(session_id):
                    auth_script = Path(__file__).parent.parent / "commands" / "authorize-stop.sh"
                    # Show evidence summary before asking for auth
                    all_passed, done, missing = check_verification(session_id)
                    if done:
                        evidence_display = build_evidence_display(done, session_id)
                        print(evidence_display, file=sys.stderr)
                    print(
                        f"\n\u2705 Phases 1-6 passed. Now authorize: bash {auth_script}\n",
                        file=sys.stderr,
                    )
                    sys.exit(2)
                phase_label = "REVIEW"
                passed, message = _phase_7_reviewer(session_id, config, input_data)
            else:
                continue

            if not passed:
                # Show focused failure message for this phase only
                lines = [
                    "",
                    "=" * 60,
                    f"PHASE {phase_num}/{PHASE_COUNT} \u2014 {phase_label}",
                    "=" * 60,
                    "",
                    message,
                    "",
                    "=" * 60,
                    "",
                ]
                print("\n".join(lines), file=sys.stderr)
                sys.exit(2)

            # Phase passed — advance
            try:
                if phase_num < PHASE_COUNT:
                    advance_phase(vr_file, phase_num + 1)
            except Exception:
                pass

        # ── All phases passed — final reset ─────────────────────────────
        auth_file = Path.home() / f".claude/data/stop_authorization_{resolved_sid}.json"
        try:
            auth_file.write_text(json.dumps({"authorized": False}))
        except Exception:
            pass

        # Reset reviewer approval for next task
        try:
            from utils.reviewer import reset_approval, clear_conversation
            reset_approval(resolved_sid)
            clear_conversation(resolved_sid)
        except Exception:
            pass

        # Reset VR for next task (all checks pending, phase 1)
        try:
            from datetime import datetime as _dt
            from utils.vr_utils import VR_CHECKS_ORDER
            all_pending = {
                k: {"status": "pending", "evidence": None, "timestamp": None, "skip_reason": None}
                for k, _ in VR_CHECKS_ORDER
            }
            vr_file.write_text(json.dumps({
                "reset_at": _dt.now().isoformat(),
                "phase": 1,
                "phase_name": "implement",
                "phase_history": [],
                "checks": all_pending,
            }))
        except Exception:
            pass

        # ── Logging ─────────────────────────────────────────────────────
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true')
        parser.add_argument('--notify', action='store_true')
        args = parser.parse_args()

        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "stop.json")
        log_data = []
        if os.path.exists(log_path):
            try:
                log_data = json.loads(Path(log_path).read_text())
            except Exception:
                log_data = []
        log_data.append(input_data)
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

        if args.chat and 'transcript_path' in input_data:
            tp = input_data['transcript_path']
            if os.path.exists(tp):
                try:
                    chat_data = []
                    with open(tp) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    with open(os.path.join(log_dir, 'chat.json'), 'w') as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass

        if args.notify:
            announce_completion()

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
