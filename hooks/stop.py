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
import random
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


def get_completion_messages():
    """Return list of friendly completion messages."""
    return [
        "Work complete!",
        "All done!",
        "Task finished!",
        "Job complete!",
        "Ready for next task!"
    ]


def get_tts_script_path():
    """
    Determine which TTS script to use based on available API keys.
    Priority order: ElevenLabs > OpenAI > pyttsx3
    """
    # Get current script directory and construct utils/tts path
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"
    
    # Check for ElevenLabs API key (highest priority)
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)
    
    # Check for OpenAI API key (second priority)
    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)
    
    # Fall back to pyttsx3 (no API key required)
    pyttsx3_script = tts_dir / "pyttsx3_tts.py"
    if pyttsx3_script.exists():
        return str(pyttsx3_script)
    
    return None


def get_llm_completion_message():
    """
    Generate completion message using available LLM services.
    Priority order: OpenAI > Anthropic > Ollama > fallback to random message
    
    Returns:
        str: Generated or fallback completion message
    """
    # Get current script directory and construct utils/llm path
    script_dir = Path(__file__).parent
    llm_dir = script_dir / "utils" / "llm"
    
    # Try OpenAI first (highest priority)
    if os.getenv('OPENAI_API_KEY'):
        oai_script = llm_dir / "oai.py"
        if oai_script.exists():
            try:
                result = subprocess.run([
                    "uv", "run", str(oai_script), "--completion"
                ], 
                capture_output=True,
                text=True,
                timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass
    
    # Try Anthropic second
    if os.getenv('ANTHROPIC_API_KEY'):
        anth_script = llm_dir / "anth.py"
        if anth_script.exists():
            try:
                result = subprocess.run([
                    "uv", "run", str(anth_script), "--completion"
                ], 
                capture_output=True,
                text=True,
                timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass
    
    # Try Ollama third (local LLM)
    ollama_script = llm_dir / "ollama.py"
    if ollama_script.exists():
        try:
            result = subprocess.run([
                "uv", "run", str(ollama_script), "--completion"
            ], 
            capture_output=True,
            text=True,
            timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass
    
    # Fallback to random predefined message
    messages = get_completion_messages()
    return random.choice(messages)

def announce_completion():
    """Announce completion using the best available TTS service."""
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return  # No TTS scripts available
        
        # Get completion message (LLM-generated or fallback)
        completion_message = get_llm_completion_message()
        
        # Call the TTS script with the completion message
        subprocess.run([
            "uv", "run", tts_script, completion_message
        ], 
        capture_output=True,  # Suppress output
        timeout=10  # 10-second timeout
        )
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Fail silently if TTS encounters issues
        pass
    except Exception:
        # Fail silently for any other errors
        pass


def get_stop_attempts_path():
    """Return path to stop attempts tracking file."""
    return Path(__file__).parent.parent / "data" / "stop_attempts.json"


def record_stop_attempt():
    """Record a stop attempt timestamp. Keeps last 10 attempts."""
    attempts_file = get_stop_attempts_path()
    attempts_file.parent.mkdir(parents=True, exist_ok=True)

    attempts = []
    if attempts_file.exists():
        try:
            with open(attempts_file, 'r') as f:
                data = json.load(f)
                attempts = data.get("attempts", [])
        except (json.JSONDecodeError, IOError):
            attempts = []

    attempts.append({"ts": time.time()})
    # Keep only last 10
    attempts = attempts[-10:]

    try:
        with open(attempts_file, 'w') as f:
            json.dump({"attempts": attempts}, f)
    except IOError:
        pass

    return attempts


def detect_emergency_mode(attempts):
    """
    Detect if the agent is in a rapid-fire stop loop.
    Returns (is_emergency, count_in_window, window_seconds) if 3+ attempts in 30s.
    """
    now = time.time()
    window = 30.0
    recent = [a for a in attempts if now - a.get("ts", 0) <= window]
    count = len(recent)

    if count >= 3:
        earliest = min(a["ts"] for a in recent)
        span = round(now - earliest, 1)
        return (True, count, span)

    return (False, count, 0)


def check_root_cleanliness():
    """
    Check if project root folder is clean (no temporary/generated files).
    Returns (is_clean: bool, violations: list).
    """
    # Allowed files/dirs at root (essential configs and docs only)
    allowed_patterns = {
        # Config files
        'package.json', 'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
        'pyproject.toml', 'poetry.lock', 'Pipfile', 'Pipfile.lock',
        'Cargo.toml', 'Cargo.lock', 'go.mod', 'go.sum',
        'tsconfig.json', 'tsconfig.*.json', 'jsconfig.json',
        'webpack.config.js', 'vite.config.js', 'rollup.config.js',
        'jest.config.js', 'vitest.config.js', 'playwright.config.js',
        '.eslintrc.js', '.eslintrc.json', 'eslint.config.mjs', 'eslint.config.js',
        '.prettierrc', '.prettierrc.json', '.prettierrc.js',
        '.editorconfig', '.nvmrc', '.node-version', '.python-version',
        'babel.config.js', '.babelrc', '.babelrc.json',
        # Docs
        'README.md', 'README.txt', 'README.rst', 'CLAUDE.md',
        'LICENSE', 'LICENSE.md', 'LICENSE.txt', 'NOTICE', 'CONTRIBUTING.md',
        'CHANGELOG.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md', 'RELEASE_PROCESS.md',
        # Build/CI/CD
        'Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
        'Makefile', 'makefile', 'CMakeLists.txt',
        # Dotfiles/dirs
        '.gitignore', '.gitattributes', '.dockerignore',
        '.github', '.gitlab', '.vscode', '.idea',
        '.git', '.svn', '.hg',
        # Entry points (for single-file projects)
        'main.py', 'app.py', 'index.js', 'index.ts', 'main.go', 'main.rs',
        # Directories
        'src', 'tests', 'test', 'docs', 'scripts', 'config',
        'public', 'static', 'assets', 'lib',
        'node_modules', '__pycache__', '.cache', 'venv', '.venv',
        # Project-specific data/output directories (often gitignored)
        'output', 'reports', 'mcp_server',
        # Hidden hook configs
        '.pre-commit-config.yaml', '.husky',
        # Claude Code operational directories (from .gitignore)
        '.claude', 'data', 'plans', 'projects', 'todos', 'statsig',
        'shell-snapshots', 'session-env', 'file-history', 'paste-cache',
        'claude-mem', 'cache', 'checkpoints', 'telemetry', 'tasks',
        'plugins', 'helpers', 'status_lines', 'debug', 'logs',
        # Claude Code files
        'history.jsonl', 'stats-cache.json', 'architectural_decisions.json',
        'lessons.json', 'statusline-command.sh',
        'package.json', 'package-lock.json', 'settings.local.json',
        'settings copy.json',
        # Project-specific directories
        'python-scripts', 'commands', 'agents', 'skills', 'hooks',
        '.validation-artifacts', '.swarm', '.claude-flow', '.ruff_cache',
        'New Tools',
        # Rust/Cargo build output (always gitignored, required at root by Cargo)
        'target',
        # Next.js build output (always gitignored, required at root by Next.js)
        '.next',
    }

    # Forbidden extensions (files only — directories are never flagged)
    forbidden_extensions = {
        # Logs and temp files
        '.log', '.tmp', '.bak', '.swp', '.swo',
        # Data/output files
        '.csv', '.xlsx', '.xls', '.tsv',
        '.pdf', '.docx', '.doc',
        # Images/media
        '.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.mp3',
        # Archives
        '.zip', '.tar', '.gz', '.tgz', '.rar',
        # Compiled/binary
        '.exe', '.o', '.so', '.dylib', '.dll',
        # Text docs (standard ones like README.txt already in allowed_patterns)
        '.txt',
        # Markdown (standard ones like README.md, CLAUDE.md already in allowed_patterns)
        '.md',
        # Compiled output and test output
        '.out', '.xml',
    }

    violations = []
    cwd = Path.cwd()

    # Skip cleanliness check when CWD is ~/.claude or any subdirectory
    # (e.g. if session cd'd into agents/, hooks/, etc.)
    if cwd.name == '.claude' or any(p.name == '.claude' for p in cwd.parents):
        return (True, [])

    try:
        # List all items in root
        for item in cwd.iterdir():
            name = item.name

            # Skip allowed items (fast path)
            if name in allowed_patterns:
                continue

            # Only flag files, not directories
            if item.is_file():
                ext = item.suffix.lower()
                if ext in forbidden_extensions:
                    violations.append(f"  ❌ {name} (file)")

        return (len(violations) == 0, violations)
    except Exception:
        # If we can't check, assume clean (fail-safe)
        return (True, [])


def check_codebase_organization():
    """
    Check if codebase follows organization best practices.
    Returns (is_organized: bool, suggestions: list, warnings: list).
    """
    suggestions = []
    warnings = []
    cwd = Path.cwd()

    # Skip checks if this is the .claude directory itself
    if cwd.name == '.claude':
        return (True, [], [])

    try:
        # Check 1: Source code files at root (should be in src/)
        source_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.go', '.rs', '.java', '.cpp', '.c', '.rb'}
        allowed_root_files = {'main.py', 'app.py', 'index.js', 'index.ts', 'main.go', 'main.rs',
                             'setup.py', '__init__.py', '__main__.py'}

        for item in cwd.iterdir():
            if item.is_file() and item.suffix in source_extensions:
                if item.name not in allowed_root_files and not item.name.startswith('.'):
                    warnings.append(f"  ⚠️  {item.name} at root → should be in src/ directory")

        # Check 2: Recommend directory structure if missing
        has_src = (cwd / 'src').exists()
        has_tests = (cwd / 'tests').exists() or (cwd / 'test').exists()

        # Count source files to determine if this is a real project
        source_files = [f for f in cwd.rglob('*') if f.is_file() and f.suffix in source_extensions]
        is_real_project = len(source_files) > 3

        if is_real_project:
            if not has_src:
                # Check if there are source files that should be in src/
                root_source_files = [f for f in cwd.iterdir()
                                   if f.is_file() and f.suffix in source_extensions
                                   and f.name not in allowed_root_files]
                if root_source_files:
                    suggestions.append("  💡 Consider creating src/ directory for source code")

            if not has_tests:
                # Check if there are any test files scattered around
                test_files = [f for f in cwd.rglob('*test*.py') if f.is_file()]
                test_files += [f for f in cwd.rglob('*.test.js') if f.is_file()]
                test_files += [f for f in cwd.rglob('*.test.ts') if f.is_file()]
                if test_files:
                    suggestions.append("  💡 Consider creating tests/ directory (mirror src/ structure)")

        # Check 3: Multiple test directories (inconsistency)
        test_dirs = []
        if (cwd / 'tests').exists():
            test_dirs.append('tests/')
        if (cwd / 'test').exists():
            test_dirs.append('test/')
        if (cwd / '__tests__').exists():
            test_dirs.append('__tests__/')
        if (cwd / 'spec').exists():
            test_dirs.append('spec/')

        if len(test_dirs) > 1:
            warnings.append(f"  ⚠️  Multiple test directories found: {', '.join(test_dirs)} → consolidate into tests/")

        # Check 4: Documentation organization
        has_docs = (cwd / 'docs').exists()
        doc_files_at_root = [f for f in cwd.iterdir()
                            if f.is_file() and f.suffix == '.md'
                            and f.name not in {'README.md', 'CLAUDE.md', 'LICENSE.md', 'CONTRIBUTING.md',
                                              'CHANGELOG.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md'}]

        if len(doc_files_at_root) > 3 and not has_docs:
            suggestions.append(f"  💡 {len(doc_files_at_root)} .md files at root → consider docs/ directory")

        # Check 5: Scripts organization
        has_scripts = (cwd / 'scripts').exists()
        script_files_at_root = [f for f in cwd.iterdir()
                               if f.is_file() and f.suffix in {'.sh', '.bash', '.zsh'}
                               and not f.name.startswith('.')]

        if len(script_files_at_root) > 2 and not has_scripts:
            suggestions.append(f"  💡 {len(script_files_at_root)} script files at root → consider scripts/ directory")

        # Determine if organized
        is_organized = len(warnings) == 0

        return (is_organized, suggestions, warnings)

    except Exception:
        # If we can't check, assume organized (fail-safe)
        return (True, [], [])


def check_upstream_sync(cwd=None):
    """Check if repo is a fork (has 'upstream' remote) and if it's synced.

    Returns:
        None  — not a fork, or git not available
        dict  — {'behind': int, 'branch': str, 'fetch_ok': bool}
    """
    try:
        import subprocess
        kw = dict(capture_output=True, text=True, cwd=cwd)

        # Check for upstream remote
        r = subprocess.run(['git', 'remote'], **kw)
        if r.returncode != 0 or 'upstream' not in r.stdout.split():
            return None  # Not a fork

        # Get current branch
        branch_r = subprocess.run(['git', 'branch', '--show-current'], **kw)
        branch = branch_r.stdout.strip() or 'main'

        # Fetch upstream (quiet, with timeout — non-fatal if it fails)
        fetch_r = subprocess.run(
            ['git', 'fetch', 'upstream', '--quiet'],
            capture_output=True, cwd=cwd, timeout=15
        )
        fetch_ok = fetch_r.returncode == 0

        if not fetch_ok:
            return {'behind': None, 'branch': branch, 'fetch_ok': False}

        # Count commits behind upstream/<branch>
        behind_r = subprocess.run(
            ['git', 'rev-list', '--count', f'HEAD..upstream/{branch}'],
            **kw
        )
        if behind_r.returncode != 0:
            return {'behind': None, 'branch': branch, 'fetch_ok': True}

        behind = int(behind_r.stdout.strip() or '0')
        return {'behind': behind, 'branch': branch, 'fetch_ok': True}

    except Exception:
        return None


def _extract_transcript_context(input_data):
    """Extract files_modified, bash_commands, and last_user_prompt from transcript JSONL.

    Only processes entries written AFTER the current task's verification reset_at
    timestamp. This prevents tool calls from previous tasks in the same session
    from contaminating the DeepSeek reviewer's ground truth context.

    Returns (files_modified: list[str], bash_commands: list[str], last_user_prompt: str).
    All fields are always returned; empty when transcript is unavailable.
    """
    transcript_path = input_data.get('transcript_path', '')
    files_modified = []
    bash_commands = []
    last_user_prompt = ""

    if not transcript_path or not Path(transcript_path).exists():
        return files_modified, bash_commands, last_user_prompt

    # Determine task start time from verification record (reset_at field).
    # Entries before this time belong to previous tasks — skip them.
    task_start_ts = ""
    try:
        vr_data = json.loads((Path.home() / ".claude/data/verification_record.json").read_text())
        task_start_ts = vr_data.get("reset_at", "")
    except Exception:
        pass  # If VR unreadable, fall back to reading full transcript (old behavior)

    try:
        with open(transcript_path, 'r') as _tf:
            for _line in _tf:
                _line = _line.strip()
                if not _line:
                    continue
                try:
                    _entry = json.loads(_line)
                except json.JSONDecodeError:
                    continue

                # Skip entries from before the current task started
                if task_start_ts:
                    entry_ts = _entry.get("timestamp", "")
                    if entry_ts and entry_ts < task_start_ts:
                        continue

                _msg = _entry.get("message", {})
                _content = _msg.get("content", [])
                _role = _msg.get("role", "")

                if _role == "assistant" and isinstance(_content, list):
                    for _block in _content:
                        if not isinstance(_block, dict):
                            continue
                        if _block.get("type") == "tool_use":
                            _name = _block.get("name", "")
                            _inp = _block.get("input", {}) or {}
                            if _name in ("Edit", "Write", "MultiEdit"):
                                _fp = _inp.get("file_path", "")
                                if _fp and _fp not in files_modified:
                                    files_modified.append(_fp)
                            elif _name == "Bash":
                                _cmd = (_inp.get("command") or "").strip()
                                if _cmd:
                                    bash_commands.append(_cmd[:200])
                elif _role == "user":
                    if isinstance(_content, list):
                        # Real user messages have type="text" blocks (not tool_result)
                        for _block in _content:
                            if isinstance(_block, dict) and _block.get("type") == "text":
                                _text = (_block.get("text") or "").strip()
                                if _text:
                                    last_user_prompt = _text
                    elif isinstance(_content, str) and _content.strip():
                        last_user_prompt = _content.strip()
    except Exception:
        pass

    # Keep only last 15 bash commands to stay within context budget
    bash_commands = bash_commands[-30:]
    return files_modified, bash_commands, last_user_prompt


def _get_session_task_type(session_id: str) -> str:
    """Get task_type from session data file. Returns 'unknown' on any error."""
    try:
        _sf = Path(f".claude/data/sessions/{session_id}.json")
        if _sf.exists():
            return json.loads(_sf.read_text()).get("task_type", "unknown")
    except Exception:
        pass
    return "unknown"


def detect_rate_limit(input_data):
    """
    Detect if the session is stopping due to a rate limit or API overload error.
    Checks last_assistant_message and the tail of the transcript file.
    Returns (is_rate_limited: bool, detail: str).
    """
    # Patterns checked against the last_assistant_message (human-readable text).
    # Must be distinctive enough to avoid false positives in normal responses.
    last_msg_patterns = [
        'rate limit', 'rate_limit', 'ratelimit',
        'too many requests', 'too_many_requests',
        'RateLimitError', 'OverloadedError',
        'resource_exhausted',
        'server is overloaded',
        'rate limit exceeded',
        'api rate limit',
        'quota exceeded',
        'anthropic.rate_limit',
    ]

    # Broader patterns for raw transcript/error entries where 429 status codes appear literally.
    rate_limit_patterns = last_msg_patterns + [
        'http 429', 'status: 429', '" 429"', "'429'",
        'overloaded', 'overload',
        'throttl',
        'retry after', 'retry_after',
        'request limit',
    ]

    def check_text(text):
        """Check if text contains any rate limit pattern."""
        if not text:
            return None
        text_lower = text.lower()
        for pattern in rate_limit_patterns:
            if pattern.lower() in text_lower:
                return pattern
        return None

    # Check 1: last_assistant_message — use stricter pattern set only
    def check_text_strict(text):
        if not text:
            return None
        text_lower = text.lower()
        for pattern in last_msg_patterns:
            if pattern.lower() in text_lower:
                return pattern
        return None

    last_msg = input_data.get('last_assistant_message', '')
    match = check_text_strict(last_msg)
    if match:
        return (True, f"Rate limit detected in last message (matched: '{match}')")

    # Check 2: Tail of transcript file for error entries
    transcript_path = input_data.get('transcript_path', '')
    if transcript_path and Path(transcript_path).exists():
        try:
            # Read last 10 lines of transcript
            with open(transcript_path, 'r') as f:
                lines = f.readlines()
            tail_lines = lines[-10:] if len(lines) >= 10 else lines

            for line in tail_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Check message content for rate limit errors
                    msg = entry.get('message', {})
                    content = msg.get('content', '')

                    # Handle string content
                    if isinstance(content, str):
                        match = check_text(content)
                        if match:
                            return (True, f"Rate limit detected in transcript (matched: '{match}')")

                    # Handle list content (content blocks)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict):
                                block_text = block.get('text', '') or block.get('content', '') or ''
                                match = check_text(block_text)
                                if match:
                                    return (True, f"Rate limit detected in transcript (matched: '{match}')")

                    # Check for error type entries
                    entry_type = entry.get('type', '')
                    if entry_type == 'error':
                        error_text = json.dumps(entry)
                        match = check_text(error_text)
                        if match:
                            return (True, f"Rate limit error entry in transcript (matched: '{match}')")

                except (json.JSONDecodeError, TypeError, AttributeError):
                    # Check raw line as fallback
                    match = check_text(line)
                    if match:
                        return (True, f"Rate limit detected in raw transcript (matched: '{match}')")

        except (IOError, OSError):
            pass  # Can't read transcript, skip this check

    return (False, '')


def detect_hedging_language(input_data):
    """
    Detect speculative/hedging language OR user-delegation phrases in the last assistant message.
    Agents must verify things themselves — never speculate and never offload verification to the user.
    Returns (has_hedging: bool, matched_phrase: str, snippet: str, category: str).
    category is 'hedging', 'delegation', or 'lazy_execution'.
    """
    HEDGING_PHRASES = [
        'should be working',
        'should be fixed',
        'should work now',
        'should now work',
        'should be live',
        'should be running',
        'should be up',
        'should be functional',
        'should be operational',
        'should be accessible',
        'should be able to',
        'this should fix',
        'this should work',
        'this should resolve',
        'that should fix',
        'that should work',
        'that should resolve',
        'ought to work',
        'ought to fix',
        'hopefully',
        'probably works',
        'likely works',
        'might work now',
        'should be working now',
        'should be',
    ]

    # Phrases that offload verification responsibility to the user.
    # The ONLY allowed form is "to repeat the verification I did yourself" — which
    # presupposes the agent already verified and merely offers the user a way to reproduce it.
    # Note: "to verify" does NOT substring-match "verification" (chars diverge at index 5).
    DELEGATION_PHRASES = [
        'to verify',
        'to check for yourself',
        'to see for yourself',
        'check for yourself',
        'see for yourself',
    ]

    last_msg = input_data.get('last_assistant_message', '')
    if not last_msg:
        return (False, '', '', '')

    # Strip code blocks, inline code, and double-quoted strings — quoted/example phrases are not claims
    import re
    scannable = re.sub(r'```.*?```', '', last_msg, flags=re.DOTALL)
    scannable = re.sub(r'`[^`]*`', '', scannable)
    scannable = re.sub(r'"[^"\n]{3,100}"', '', scannable)

    msg_lower = scannable.lower()

    # Check hedging phrases first (more specific before catch-all 'should be')
    for phrase in HEDGING_PHRASES:
        if phrase in msg_lower:
            idx = msg_lower.find(phrase)
            start = max(0, idx - 40)
            end = min(len(scannable), idx + len(phrase) + 60)
            snippet = scannable[start:end].replace('\n', ' ').strip()
            return (True, phrase, snippet, 'hedging')

    # Check delegation phrases
    for phrase in DELEGATION_PHRASES:
        if phrase in msg_lower:
            idx = msg_lower.find(phrase)
            start = max(0, idx - 40)
            end = min(len(scannable), idx + len(phrase) + 60)
            snippet = scannable[start:end].replace('\n', ' ').strip()
            return (True, phrase, snippet, 'delegation')

    # Patterns where agent instructs user to run a command the agent should run itself.
    # "Execute, Don't Recommend" (CLAUDE.md Principle #4).
    LAZY_EXECUTION_PHRASES = [
        'try the command',
        'try running',
        'you should run',
        "you'll need to run",
        "you'll want to run",
        'you need to run',
        'you can run',
    ]

    for phrase in LAZY_EXECUTION_PHRASES:
        if phrase in msg_lower:
            idx = msg_lower.find(phrase)
            start = max(0, idx - 40)
            end = min(len(scannable), idx + len(phrase) + 80)
            snippet = scannable[start:end].replace('\n', ' ').strip()
            return (True, phrase, snippet, 'lazy_execution')

    return (False, '', '', '')


def check_stop_authorization():
    """
    Check if stop is authorized via file-based configuration.
    Returns True if authorized, False otherwise.
    """
    auth_file = Path(".claude/data/stop_authorization.json")

    # If file doesn't exist, default to NOT authorized (blocked)
    if not auth_file.exists():
        return False

    try:
        with open(auth_file, 'r') as f:
            auth_data = json.load(f)
            return auth_data.get("authorized", False)
    except (json.JSONDecodeError, IOError, KeyError):
        # Any error reading file = NOT authorized (fail-safe)
        return False


# ── Verification record helpers ────────────────────────────────────────────

_VR_CHECKS_ORDER = [
    ("tests",         "TESTS              "),
    ("build",         "BUILD              "),
    ("lint",          "LINT               "),
    ("app_starts",    "APP STARTS         "),
    ("api",           "CODE/SCRIPT/API EXECUTION"),
    ("frontend",      "FRONTEND VALIDATION"),
    ("happy_path",    "HAPPY PATH         "),
    ("error_cases",   "ERROR CASES        "),
    ("commit_push",   "COMMIT & PUSH      "),
    ("upstream_sync", "UPSTREAM SYNC      "),
]

_VR_RUN_CMDS = {
    "tests":
        "pytest 2>&1 | bash ~/.claude/commands/check-tests.sh\n"
        "  npm test 2>&1 | bash ~/.claude/commands/check-tests.sh",
    "build":
        "npm run build 2>&1 | bash ~/.claude/commands/check-build.sh\n"
        "  tsc --noEmit 2>&1 | bash ~/.claude/commands/check-build.sh\n"
        "  cargo build 2>&1 | bash ~/.claude/commands/check-build.sh",
    "lint":
        "npm run lint 2>&1 | bash ~/.claude/commands/check-lint.sh\n"
        "  ruff check . 2>&1 | bash ~/.claude/commands/check-lint.sh\n"
        "  cargo clippy 2>&1 | bash ~/.claude/commands/check-lint.sh",
    "app_starts":
        "# ⚠️  If you created/modified startup scripts or package.json scripts:\n"
        "#     bash -n script.sh or shellcheck = syntax check ONLY. Must run the full command.\n"
        "# Check if already running first:\n"
        "  PORT=3000  # or 8000, 8080 — use the project's actual port\n"
        "  # If running: kill it, restart, and record:\n"
        "  (lsof -ti:$PORT | xargs kill -9 2>/dev/null; sleep 1; npm start 2>&1 | head -30) | bash ~/.claude/commands/check-app-starts.sh\n"
        "  # If not running: start normally:\n"
        "  npm start 2>&1 | head -30 | bash ~/.claude/commands/check-app-starts.sh\n"
        "  python main.py 2>&1 | head -30 | bash ~/.claude/commands/check-app-starts.sh",
    "api":
        "# ⚠️  bash -n SCRIPT.sh = syntax check ONLY — the script was NOT run.\n"
        "# ⚠️  shellcheck = static analysis — the script was NOT run.\n"
        "# If you created/modified startup scripts or package.json, run the actual command:\n"
        "  bash scripts/dev.sh 2>&1 | head -20 | bash ~/.claude/commands/check-api.sh\n"
        "  yarn dev 2>&1 | head -20 | bash ~/.claude/commands/check-api.sh\n"
        "# Run WHATEVER CODE WAS CHANGED — scripts, functions, CLI tools, APIs.\n"
        "# Use REAL-WORLD inputs that replicate how the code is actually used.\n"
        "# If you can execute it, you must. Only skip if execution is impossible.\n"
        "  bash SCRIPT.sh --args 2>&1 | bash ~/.claude/commands/check-api.sh\n"
        "  curl http://localhost:PORT/api/ENDPOINT 2>&1 | bash ~/.claude/commands/check-api.sh\n"
        '  python -c "from app import fn; print(fn(real_args))" 2>&1 | bash ~/.claude/commands/check-api.sh\n'
        '  bash ~/.claude/commands/check-api.sh "ran X with real input Y, got output Z, exit N (min 50 chars)"',
    "frontend":
        "npx playwright test 2>&1 | bash ~/.claude/commands/check-frontend.sh\n"
        "  npm run test:e2e 2>&1 | bash ~/.claude/commands/check-frontend.sh\n"
        '  bash ~/.claude/commands/check-frontend.sh "opened http://..., verified X, clicked Y, saw Z, console: zero errors (min 50 chars)"',
    "happy_path":
        'bash ~/.claude/commands/check-happy-path.sh "I did X with input Y and saw result Z"',
    "error_cases":
        'bash ~/.claude/commands/check-error-cases.sh "I tested X error by doing Y and saw Z"',
    "commit_push":
        'git add -p && git commit -m "msg" && git push\n'
        '  bash ~/.claude/commands/check-commit-push.sh "committed N files on branch X, pushed to origin"',
    "upstream_sync":
        "# Auto-runs via static_checker.py on authorize-stop.\n"
        "# To skip manually:\n"
        'bash ~/.claude/commands/check-upstream-sync.sh --skip "not a fork — no upstream remote"',
}

_VR_SKIP_CMDS = {
    "tests":        'bash ~/.claude/commands/check-tests.sh --skip "reason (min 10 chars)"',
    "build":        'bash ~/.claude/commands/check-build.sh --skip "reason (min 10 chars)"',
    "lint":         'bash ~/.claude/commands/check-lint.sh --skip "reason (min 10 chars)"',
    "app_starts":   'bash ~/.claude/commands/check-app-starts.sh --skip "reason (min 10 chars)"',
    "api":          'bash ~/.claude/commands/check-api.sh --skip "reason (min 10 chars)"',
    "frontend":     'bash ~/.claude/commands/check-frontend.sh --skip "reason (min 10 chars)"',
    "happy_path":   'bash ~/.claude/commands/check-happy-path.sh --skip "reason (min 10 chars)"',
    "error_cases":  'bash ~/.claude/commands/check-error-cases.sh --skip "reason (min 10 chars)"',
    "commit_push":  'bash ~/.claude/commands/check-commit-push.sh --skip "reason (min 10 chars)"',
    "upstream_sync": 'bash ~/.claude/commands/check-upstream-sync.sh --skip "not a fork — no upstream remote"',
}


def read_verification_record() -> dict:
    """Read .claude/data/verification_record.json.
    Returns all-pending default if missing or unreadable."""
    vr_file = Path.home() / ".claude/data/verification_record.json"
    all_pending = {
        k: {"status": "pending", "evidence": None, "timestamp": None, "skip_reason": None}
        for k, _ in _VR_CHECKS_ORDER
    }
    default = {"reset_at": None, "checks": all_pending}
    try:
        with open(vr_file, 'r') as f:
            data = json.load(f)
        # Ensure all keys are present
        checks = data.get("checks", {})
        for k, _ in _VR_CHECKS_ORDER:
            if k not in checks:
                checks[k] = all_pending[k]
        data["checks"] = checks
        return data
    except Exception:
        return default


def check_verification_complete(record: dict):
    """Returns (is_complete, done_items, pending_items).
    done_items and pending_items are lists of (key, label, status, ts_short, ev_short).
    """
    checks = record.get("checks", {})
    done_items = []
    pending_items = []
    for key, label in _VR_CHECKS_ORDER:
        item = checks.get(key, {})
        status = item.get("status", "pending")
        if status == "pending":
            pending_items.append((key, label, "pending", None, None))
        else:
            ts = item.get("timestamp") or ""
            ts_short = ts[11:16] if len(ts) >= 16 else (ts or "?")
            ev = item.get("evidence") or item.get("skip_reason") or ""
            ev_short = ev[:70].replace("\n", " ") if ev else ""
            done_items.append((key, label, status, ts_short, ev_short))
    is_complete = len(pending_items) == 0
    return (is_complete, done_items, pending_items)


def build_checklist_message(done_items: list, pending_items: list) -> str:
    """Build the STOP BLOCKED — VERIFICATION REQUIRED message."""
    SEP = "━" * 68
    lines = [
        "",
        "=" * 70,
        "STOP BLOCKED — VERIFICATION REQUIRED",
        "=" * 70,
        "",
        "YOU MUST RUN EACH COMMAND BELOW AND RECORD EVIDENCE.",
        "Reading code is not verification. Running commands is.",
        "Every item below requires a SPECIFIC action. No shortcuts.",
    ]

    step = 0
    for key, label, status, ts_short, ev_short in done_items:
        step += 1
        mark = "✅" if status == "done" else "⏭ "
        ev_display = f' — "{ev_short}"' if ev_short else ""
        lines += [
            "",
            SEP,
            f"{mark} STEP {step}: {label.strip()}  (done @ {ts_short}{ev_display})",
            SEP,
        ]

    for key, label, status, ts_short, ev_short in pending_items:
        step += 1
        lines += [
            "",
            SEP,
            f"❌ STEP {step}: {label.strip()}  (not done)",
            SEP,
        ]
        # Per-check instructions
        if key in ("happy_path", "error_cases"):
            lines.append("Describe exactly what you tested (min 30 chars). Be specific:")
            lines.append(f"  {_VR_RUN_CMDS[key]}")
            lines.append("No applicable scenario? Skip with a reason (min 10 chars):")
            lines.append(f"  {_VR_SKIP_CMDS[key]}")
        else:
            lines.append("Run the command and pipe the output:")
            for cmd_line in _VR_RUN_CMDS[key].split("\n"):
                lines.append(f"  {cmd_line}")
            lines.append("Not applicable? Skip with a reason (min 10 chars):")
            lines.append(f"  {_VR_SKIP_CMDS[key]}")

    lines += [
        "",
        "Complete ALL pending items, then run:",
        "  bash ~/.claude/commands/authorize-stop.sh",
        "=" * 70,
        "",
    ]
    return "\n".join(lines)


def format_evidence_display(done_items: list, checks: dict) -> str:
    """Show full evidence for all completed verification checks."""
    EVIDENCE_TRUNCATE = 500
    SEP = "─" * 68
    lines = [
        "",
        "=" * 70,
        "VERIFICATION EVIDENCE SUMMARY",
        "=" * 70,
        "",
    ]
    for i, (key, label, status, ts_short, _ev_short) in enumerate(done_items, 1):
        check_data = checks.get(key, {})
        if status == "skipped":
            full_ev = check_data.get("skip_reason") or ""
            ev_label = "Skip reason"
        else:
            full_ev = check_data.get("evidence") or ""
            ev_label = "Command output"
        mark = "✅" if status == "done" else "⏭ "
        lines.append(f"{mark} Step {i}: {label.strip()}  [{status} @ {ts_short}]")
        lines.append(SEP)
        if full_ev:
            display_ev = full_ev[:EVIDENCE_TRUNCATE]
            truncated = len(full_ev) > EVIDENCE_TRUNCATE
            lines.append(f"{ev_label}:")
            for ev_line in display_ev.split("\n"):
                lines.append(f"  {ev_line}")
            if truncated:
                lines.append(f"  ... [{len(full_ev) - EVIDENCE_TRUNCATE} more chars truncated]")
        else:
            lines.append(f"{ev_label}: (none recorded)")
        lines.append("")
    lines.append("=" * 70)
    return "\n".join(lines)


def main():
    try:
        # Read JSON input from stdin EARLY so we can use it for rate limit detection
        # Store in a variable for later use (stdin can only be read once)
        try:
            raw_stdin = sys.stdin.read()
            input_data = json.loads(raw_stdin) if raw_stdin.strip() else {}
        except (json.JSONDecodeError, ValueError):
            input_data = {}

        # RATE LIMIT DETECTION - auto-allow stop if rate limited
        is_rate_limited, rate_limit_detail = detect_rate_limit(input_data)
        if is_rate_limited:
            rate_limit_msg = f"""
======================================================================
STOP ALLOWED - RATE LIMIT DETECTED
======================================================================

{rate_limit_detail}

Bypassing validation requirements — rate limit errors are not
something the agent can fix. Session will stop gracefully.
======================================================================
"""
            print(rate_limit_msg, file=sys.stderr)
            # Still log the stop event
            try:
                log_dir = os.path.join(os.getcwd(), "logs")
                os.makedirs(log_dir, exist_ok=True)
                log_path = os.path.join(log_dir, "stop.json")
                if os.path.exists(log_path):
                    with open(log_path, 'r') as f:
                        try:
                            log_data = json.load(f)
                        except (json.JSONDecodeError, ValueError):
                            log_data = []
                else:
                    log_data = []
                input_data['_rate_limited'] = True
                input_data['_rate_limit_detail'] = rate_limit_detail
                log_data.append(input_data)
                with open(log_path, 'w') as f:
                    json.dump(log_data, f, indent=2)
            except Exception:
                pass
            sys.exit(0)  # Allow stop immediately

        # EMERGENCY MODE DETECTION - detect rapid-fire stop loops
        # (only matters if not already authorized)
        attempts = record_stop_attempt()
        is_emergency, attempt_count, span = detect_emergency_mode(attempts)

        if is_emergency and not check_stop_authorization():
            auth_script = Path(__file__).parent.parent / "commands" / "authorize-stop.sh"
            emergency_msg = f"""
╔══════════════════════════════════════════════════════════════╗
║  🚨 EMERGENCY: YOU ARE STUCK IN A STOP LOOP 🚨              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  You have attempted to stop {attempt_count} times in {span}s.{' ' * max(0, 17 - len(str(attempt_count)) - len(str(span)))}║
║  Responding with "." or short text will NOT let you stop.    ║
║                                                              ║
║  THE USER REQUIRES THOROUGH VALIDATION BEFORE STOPPING.      ║
║                                                              ║
║  TO ACTUALLY STOP, YOU MUST:                                 ║
║                                                              ║
║  1. STOP trying to stop. Do the work first.                  ║
║  2. Complete all requested tasks                             ║
║  3. Run validation (tests, build, lint — 3+ methods)         ║
║  4. Present a validation report with ACTUAL OUTPUT            ║
║  5. Run this exact command:                                  ║
║     bash {auth_script}  ║
║  6. THEN you may stop (the hook will allow it)               ║
║                                                              ║
║  The authorize-stop command sets a one-time flag that        ║
║  lets the stop hook pass. Without it, stopping is blocked.   ║
║                                                              ║
║  DO NOT respond with "." or minimal text.                    ║
║  DO NOT try to stop again without completing steps above.    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
            print(emergency_msg, file=sys.stderr)
            sys.exit(2)

        # ROOT CLEANLINESS CHECK - blocks stop if violations found
        is_clean, violations = check_root_cleanliness()

        # CODEBASE ORGANIZATION CHECK - informational feedback
        is_organized, suggestions, org_warnings = check_codebase_organization()

        if not is_clean:
            violation_list = "\n".join(violations)
            root_blocked_msg = f"""
======================================================================
STOP BLOCKED - ROOT FOLDER NOT CLEAN
======================================================================

🚨 ROOT FOLDER VIOLATIONS DETECTED:
{violation_list}

ROOT MUST BE CLEAN BEFORE STOPPING:
✅ Move temp files to appropriate directories
✅ Move logs to logs/ directory (and gitignore)
✅ Move outputs to output/ directory (and gitignore)
✅ Move test results to tests/ or output/ directory
✅ Delete scratch/debug files OR move to scripts/
✅ Ensure .gitignore covers all generated files

Run 'ls -la' to verify, then fix violations before proceeding.

ONLY THESE BELONG AT ROOT:
• Core configs (package.json, pyproject.toml, etc.)
• Essential docs (README.md, LICENSE, etc.)
• Build specs (.github/, Dockerfile, etc.)
• Essential dotfiles (.gitignore, .editorconfig, etc.)

See CLAUDE.md Core Principle #7 for details.
======================================================================
"""
            print(root_blocked_msg, file=sys.stderr)
            sys.exit(2)  # Exit code 2 blocks stop

        # HEDGING LANGUAGE CHECK — blocks stop if last message contains speculative or delegation phrases
        _has_hedging, _hedging_phrase, _hedging_snippet, _hedging_category = detect_hedging_language(input_data)
        if _has_hedging:
            if _hedging_category == 'delegation':
                hedging_msg = f"""
======================================================================
STOP BLOCKED — DELEGATION PHRASE DETECTED
======================================================================

🚫 Your last message contains "{_hedging_phrase}" — offloading verification to the user.

  Context: "...{_hedging_snippet}..."

Agents must verify things themselves. Never tell the user to "run X to verify" —
that means YOU haven't verified it yet.

REQUIRED — actually verify it yourself:
  • Run the code / start the service / hit the endpoint
  • Observe the actual output / response / behavior
  • Record evidence with definitive language: "Verification: exit 0, 9/9 passed"
  • You MAY say "to repeat the verification I did yourself, run..." (agent already verified)

Verify it yourself, then stop.
======================================================================
"""
            elif _hedging_category == 'lazy_execution':
                hedging_msg = f"""
======================================================================
STOP BLOCKED — EXECUTE, DON'T RECOMMEND VIOLATION
======================================================================

🚫 Your last message contains "{_hedging_phrase}" — you told the user to run a command
   instead of running it yourself.

  Context: "...{_hedging_snippet}..."

CLAUDE.md Principle #4: "NEVER say 'You should run Y' for actions the agent can execute."
The agent must run commands itself, not delegate to the user.

REQUIRED:
  • Run the command yourself right now
  • Capture the output / error
  • Report the result definitively ("Ran X — output: ...")
  • If the command is risky/destructive, confirm with user FIRST, then run it

Run it, then stop.
======================================================================
"""
            else:
                hedging_msg = f"""
======================================================================
STOP BLOCKED — SPECULATIVE LANGUAGE DETECTED
======================================================================

🚫 Your last message contains "{_hedging_phrase}" — a speculative phrase.

  Context: "...{_hedging_snippet}..."

"Should be" is not verification. Speculation is not proof.
You must PROVE the thing works before stopping.

REQUIRED — actually verify it:
  • Run the code / start the service / hit the endpoint
  • Observe the actual output / response / behavior
  • Record evidence with the check commands
  • Use definitive language: "it works" not "should be working"

Verify it, then stop.
======================================================================
"""
            print(hedging_msg, file=sys.stderr)
            sys.exit(2)

        # Write DeepSeek review context early (before any blocking checks) so
        # authorize-stop.sh always has fresh context even if agent runs it directly.
        try:
            _files_mod, _bash_cmds, _last_prompt = _extract_transcript_context(input_data)
            _ds_ctx = {
                "last_user_prompt": _last_prompt or input_data.get("last_user_prompt", ""),
                "last_assistant_message": input_data.get("last_assistant_message", ""),
                "task_type": _get_session_task_type(input_data.get("session_id", "")),
                "files_modified": _files_mod,
                "bash_commands": _bash_cmds,
                "transcript_path": input_data.get("transcript_path", ""),
                "session_id": input_data.get("session_id", ""),
            }
            Path(".claude/data").mkdir(parents=True, exist_ok=True)
            Path(".claude/data/deepseek_context.json").write_text(
                json.dumps(_ds_ctx, indent=2)
            )
        except Exception:
            pass

        # VERIFICATION CHECKLIST CHECK — blocks stop if any of 8 items are pending
        _vr = read_verification_record()
        _vr_complete, _vr_done, _vr_pending = check_verification_complete(_vr)
        if not _vr_complete:
            print(build_checklist_message(_vr_done, _vr_pending), file=sys.stderr)
            sys.exit(2)

        # EVIDENCE DISPLAY — show full command output for all completed steps
        _evidence_display = format_evidence_display(_vr_done, _vr.get("checks", {}))
        print(_evidence_display, file=sys.stderr)

        # AUTHORIZATION CHECK - blocks stop if not authorized
        if not check_stop_authorization():
            # Get absolute path to authorize-stop.sh script
            script_dir = Path(__file__).parent
            auth_script = script_dir.parent / "commands" / "authorize-stop.sh"

            # Check upstream sync for forks
            upstream_sync = check_upstream_sync()
            upstream_line = ""
            if upstream_sync is not None:
                if not upstream_sync['fetch_ok']:
                    upstream_line = "⚠️  Fork upstream fetch failed — verify sync manually\n"
                elif upstream_sync['behind'] and upstream_sync['behind'] > 0:
                    n = upstream_sync['behind']
                    b = upstream_sync['branch']
                    upstream_line = (
                        f"⚠️  FORK OUT OF SYNC — {n} commit(s) behind upstream/{b}\n"
                        f"   Sync before stopping: git fetch upstream && "
                        f"git merge upstream/{b} && git push\n"
                    )
                else:
                    upstream_line = f"✅ Fork is in sync with upstream/{upstream_sync['branch']}\n"

            # Build organization feedback section
            org_feedback = ""
            if org_warnings or suggestions:
                org_feedback = "\n📁 CODEBASE ORGANIZATION FEEDBACK:\n"
                if org_warnings:
                    org_feedback += "\nWarnings (consider fixing):\n"
                    org_feedback += "\n".join(org_warnings) + "\n"
                if suggestions:
                    org_feedback += "\nSuggestions (optional improvements):\n"
                    org_feedback += "\n".join(suggestions) + "\n"
                org_feedback += "\nSee CLAUDE.md 'Codebase Organization' section for guidelines.\n"

            # Build dynamic auth-required message showing all 6 verified items
            _blocked_lines = [
                "",
                "=" * 70,
                "STOP BLOCKED - AUTHORIZATION REQUIRED",
                "=" * 70,
                "",
                "✅ Root folder is clean.",
                "✅ All 8 verification checks completed.",
                "",
            ]
            if upstream_line:
                _blocked_lines.append(upstream_line.rstrip())
                _blocked_lines.append("")
            if org_feedback:
                _blocked_lines.append(org_feedback.strip())
                _blocked_lines.append("")
            # Show each verified item with evidence
            for _vr_key, _vr_label, _vr_status, _vr_ts, _vr_ev in _vr_done:
                _mark = "✅" if _vr_status == "done" else "⏭ "
                _ev_display = f' — "{_vr_ev}"' if _vr_ev else ""
                _blocked_lines.append(
                    f"  {_mark} {_vr_label}  [{_vr_status} @ {_vr_ts}]{_ev_display}"
                )
            _blocked_lines += [
                "",
                "Now authorize the stop:",
                f"  bash {auth_script}",
                "=" * 70,
                "",
            ]
            blocked_msg = "\n".join(_blocked_lines)
            print(blocked_msg, file=sys.stderr)
            sys.exit(2)  # Exit code 2 blocks stop

        # ── Two-phase security scan gate ──────────────────────────────────────
        _auth_file = Path(".claude/data/stop_authorization.json")
        _scan_complete = False
        _prior_report = None
        try:
            with open(_auth_file, 'r') as _f:
                _auth_state = json.load(_f)
            _scan_complete = _auth_state.get("security_scan_complete", False)
            _prior_report = _auth_state.get("security_report_path")
        except Exception:
            pass  # Treat as scan not yet run

        if not _scan_complete:
            # Phase 1: run the security scan
            print("\n🔐 Running security scan...", file=sys.stderr, flush=True)
            _critical_count = 0
            _warning_count = 0
            _report_path = ""
            try:
                from utils.security_scanner import run_security_scan
                _critical_count, _warning_count, _report_path = run_security_scan(
                    Path.cwd(), timeout_per_tool=8, global_timeout=45
                )
            except Exception:
                pass  # Graceful degradation — scanner errors never block stop

            # Save scan state, clear authorization
            try:
                with open(_auth_file, 'w') as _f:
                    json.dump({
                        "authorized": False,
                        "security_scan_complete": True,
                        "security_report_path": _report_path,
                    }, _f)
            except Exception:
                pass

            if _critical_count > 0:
                _sec_blocked = (
                    "\n======================================================================"
                    "\nSTOP BLOCKED — SECURITY SCAN FOUND CRITICAL ISSUES"
                    "\n======================================================================"
                    f"\n\n🔴 Critical findings: {_critical_count}"
                    f"\n⚠️  Warnings:          {_warning_count}"
                    f"\n📄 Full report:       {_report_path}"
                    "\n\nFix the critical issues, then run /authorize-stop to re-scan."
                    "\n======================================================================\n"
                )
                print(_sec_blocked, file=sys.stderr)
                sys.exit(2)  # Block stop
            else:
                # Scan passed — show summary and require one more authorization
                # (so the user actually sees the result; silent allows are invisible)
                _sec_ok_msg = (
                    "\n======================================================================"
                    "\nSECURITY SCAN PASSED ✅"
                    "\n======================================================================"
                    f"\n\n🔴 Critical findings: 0"
                    f"\n⚠️  Warnings:          {_warning_count}"
                    f"\n📄 Report:            {_report_path}"
                    "\n\nRun /authorize-stop once more to complete the stop."
                    "\n======================================================================\n"
                )
                print(_sec_ok_msg, file=sys.stderr)
                sys.exit(2)  # Show the summary; next authorize skips re-scan
        else:
            # Phase 2: scan already ran and passed; user re-authorized — allow stop
            _prior = f" Report: {_prior_report}" if _prior_report else ""
            _phase2_msg = (
                "\n======================================================================"
                "\nSECURITY SCAN PREVIOUSLY PASSED ✅ — Proceeding with stop"
                "\n======================================================================"
                f"\n{_prior}"
                "\n======================================================================\n"
            )
            print(_phase2_msg, file=sys.stderr)
            # Fall through — allow stop

        # Final reset — always one-time use; clears both auth and scan state
        try:
            with open(_auth_file, 'w') as _f:
                json.dump({
                    "authorized": False,
                    "security_scan_complete": False,
                    "security_report_path": None,
                }, _f)
        except Exception:
            pass

        # Reset verification record for next task — all items back to pending
        try:
            from datetime import datetime as _dt
            _vr_file = Path.home() / ".claude/data/verification_record.json"
            _all_pending = {
                k: {"status": "pending", "evidence": None, "timestamp": None, "skip_reason": None}
                for k, _ in _VR_CHECKS_ORDER
            }
            with open(_vr_file, 'w') as _f:
                json.dump({"reset_at": _dt.now().isoformat(), "checks": _all_pending}, _f)
        except Exception:
            pass

        # Reset dynamic checks alongside verification record
        try:
            _dc_file = Path(".claude/data/dynamic_checks.json")
            if _dc_file.exists():
                _dc_file.write_text(json.dumps({
                    "project_root": str(Path.cwd()),
                    "registered_at": None,
                    "checks": {},
                }, indent=2))
        except Exception:
            pass

        # Reset DeepSeek review state for next task
        try:
            for _ds_file in [
                Path(".claude/data/deepseek_review_state.json"),
                Path(".claude/data/deepseek_context.json"),
            ]:
                if _ds_file.exists():
                    _ds_file.unlink()
        except Exception:
            pass

        # Informational DeepSeek delegation summary (non-blocking)
        try:
            from utils.config_loader import get_config
            if get_config().is_deepseek_mode():
                _ds_log = Path.home() / ".claude" / "data" / "deepseek_delegations.json"
                if _ds_log.exists():
                    _ds_entries = json.loads(_ds_log.read_text())
                    # Filter to current session (match on first 8 chars)
                    _sid_prefix = input_data.get("session_id", "")[:8]
                    _session_ds = [d for d in _ds_entries if d.get("session_id") == _sid_prefix]
                    if _session_ds:
                        print(f"\xf0\x9f\x93\x8b DeepSeek delegations in this session: {len(_session_ds)}", file=sys.stderr)
        except Exception:
            pass

        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        parser.add_argument('--notify', action='store_true', help='Enable TTS completion announcement')
        args = parser.parse_args()

        # input_data was already read from stdin at the top of main()

        # Extract required fields
        session_id = input_data.get("session_id", "")
        _stop_hook_active = input_data.get("stop_hook_active", False)  # Reserved

        # Persist session learnings to Claude-Mem (non-blocking)
        try:
            from utils.claude_mem import persist_session_learnings
            persist_session_learnings(session_id, input_data)
        except Exception:
            pass  # Graceful degradation - never block stop

        # Persist session learnings to ReasoningBank via Claude Flow (non-blocking)
        try:
            from utils.claude_flow import store_session_learning
            store_session_learning(session_id, {
                "completed_at": input_data.get("timestamp", ""),
                "tool_count": len(input_data.get("tool_calls", [])),
                "summary": f"Session {session_id[:8]}... completed"
            })
        except Exception:
            pass  # Graceful degradation - never block stop

        # NEW: Run quality assessment via Analytics (non-blocking)
        quality_result = None
        try:
            from utils.analytics_client import get_analytics_client
            analytics = get_analytics_client(timeout=5.0)

            # Run quality assessment on session
            quality_result = analytics.quality_assess(
                target='session',
                criteria=['completion', 'validation', 'testing']
            )

            # Store quality result if available
            if quality_result and quality_result.get('score', 0) > 0:
                from utils.mcp_client import get_mcp_client
                mcp = get_mcp_client(timeout=3.0)
                mcp.memory_store(
                    key=f'quality/{session_id[:8]}',
                    value=json.dumps(quality_result),
                    namespace='quality_assessments',
                    ttl=604800  # 7 day TTL
                )
        except Exception:
            pass  # Graceful degradation - never block stop

        # NEW: Workflow validation check (non-blocking)
        try:
            from utils.workflow_client import get_workflow_client
            workflow = get_workflow_client(timeout=5.0)

            # Check for any active workflows that should complete
            workflows = workflow.workflow_list(status='active', limit=5)
            if workflows:
                # Log active workflows but don't block
                print(f"Note: {len(workflows)} active workflows detected", file=sys.stderr)
        except Exception:
            pass  # Graceful degradation - never block stop

        # NEW: Neural pattern learning from session outcome (non-blocking)
        try:
            from utils.neural_client import get_neural_client
            neural = get_neural_client(timeout=5.0)

            # Learn from completed session
            neural.analyze_patterns(
                action='learn',
                operation='session_complete',
                outcome='success',
                metadata={
                    'session': session_id[:8],
                    'quality_score': quality_result.get('score', 0) if quality_result else 0
                }
            )
        except Exception:
            pass  # Graceful degradation - never block stop

        # Ensure log directory exists
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "stop.json")

        # Read existing log data or initialize empty list
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []
        
        # Append new data
        log_data.append(input_data)
        
        # Write back to file with formatting
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        # Handle --chat switch
        if args.chat and 'transcript_path' in input_data:
            transcript_path = input_data['transcript_path']
            if os.path.exists(transcript_path):
                # Read .jsonl file and convert to JSON array
                chat_data = []
                try:
                    with open(transcript_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # Skip invalid lines
                    
                    # Write to logs/chat.json
                    chat_file = os.path.join(log_dir, 'chat.json')
                    with open(chat_file, 'w') as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass  # Fail silently

        # Announce completion via TTS (only if --notify flag is set)
        if args.notify:
            announce_completion()

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
