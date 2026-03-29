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
        'output', 'reports', 'mcp_server',
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
    if (Path.home() / f".claude/data/verification_record_{session_id}.json").exists():
        return session_id
    try:
        sessions_file = Path.home() / ".claude/data/active_sessions.json"
        if sessions_file.exists():
            sessions = json.loads(sessions_file.read_text())
            # Try git root first, then CWD
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

        # 1. Rate limit bypass
        is_rate_limited, detail = detect_rate_limit(input_data)
        if is_rate_limited:
            print(f"\nSTOP ALLOWED — RATE LIMIT DETECTED\n{detail}\n", file=sys.stderr)
            sys.exit(0)

        # 2. Emergency mode detection
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

        # 3. Root cleanliness
        is_clean, violations = check_root_cleanliness()
        if not is_clean:
            print(
                "\nSTOP BLOCKED — ROOT FOLDER NOT CLEAN\n"
                + "\n".join(violations) + "\n"
                "\nMove/delete violations, then retry.\n",
                file=sys.stderr,
            )
            sys.exit(2)

        # Load project config (used by verification gate and security scan)
        try:
            sys.path.insert(0, str(Path(__file__).parent / "utils"))
            from project_config import get_git_root, load_config
            config = load_config(Path(get_git_root()))
        except Exception:
            config = {}

        # 4. Config-driven verification gate
        all_passed, done, missing = check_verification(session_id)
        if not all_passed:
            print(build_blocked_message(done, missing, config), file=sys.stderr)
            sys.exit(2)

        # 5. Show evidence summary
        evidence_display = build_evidence_display(done, session_id)
        print(evidence_display, file=sys.stderr)

        # 6. Authorization check
        if not check_stop_authorization(session_id):
            auth_script = Path(__file__).parent.parent / "commands" / "authorize-stop.sh"
            print(
                f"\nAll checks passed. Now authorize: bash {auth_script}\n",
                file=sys.stderr,
            )
            sys.exit(2)

        # 7. Final reset — one-time use
        resolved_sid = _resolve_session_id(session_id)
        auth_file = Path.home() / f".claude/data/stop_authorization_{resolved_sid}.json"
        try:
            auth_file.write_text(json.dumps({"authorized": False}))
        except Exception:
            pass

        # Reset VR for next task
        try:
            from datetime import datetime as _dt
            from utils.vr_utils import VR_CHECKS_ORDER
            vr_file = Path.home() / f".claude/data/verification_record_{resolved_sid}.json"
            all_pending = {
                k: {"status": "pending", "evidence": None, "timestamp": None, "skip_reason": None}
                for k, _ in VR_CHECKS_ORDER
            }
            vr_file.write_text(json.dumps({
                "reset_at": _dt.now().isoformat(),
                "checks": all_pending,
            }))
        except Exception:
            pass

        # 9. Logging
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
