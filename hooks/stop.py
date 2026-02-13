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
        'CHANGELOG.md', 'CODE_OF_CONDUCT.md', 'SECURITY.md',
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
        'New Tools'
    }

    # Forbidden patterns (will trigger violations)
    forbidden_patterns = [
        '.log', '.tmp', '.bak', '.swp', '.swo',
        'test-results', 'coverage', '.pytest_cache',
        'dist', 'build', 'target', '.next', 'out',
        '.exe', '.o', '.so', '.dylib',
        'scratch', 'temp', 'debug', 'output.csv', 'output.json',
        '.generated.', 'chart.', 'report.'
    ]

    violations = []
    cwd = Path.cwd()

    try:
        # List all items in root
        for item in cwd.iterdir():
            name = item.name

            # Skip allowed items
            if name in allowed_patterns:
                continue

            # Check for forbidden patterns
            is_violation = False
            for pattern in forbidden_patterns:
                if pattern in name.lower():
                    is_violation = True
                    break

            if is_violation:
                item_type = "dir" if item.is_dir() else "file"
                violations.append(f"  ❌ {name} ({item_type})")

        return (len(violations) == 0, violations)
    except Exception:
        # If we can't check, assume clean (fail-safe)
        return (True, [])


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


def main():
    try:
        # ROOT CLEANLINESS CHECK - blocks stop if violations found
        is_clean, violations = check_root_cleanliness()
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

        # AUTHORIZATION CHECK - blocks stop if not authorized
        if not check_stop_authorization():
            # Get absolute path to authorize-stop.sh script
            script_dir = Path(__file__).parent
            auth_script = script_dir.parent / "commands" / "authorize-stop.sh"

            blocked_msg = f"""
======================================================================
STOP BLOCKED - VALIDATION REQUIRED
======================================================================

✅ Root folder is clean!

VALIDATION METHODS (execute 3+):
□ Unit tests: npm test, pytest, cargo test, go test
□ Build/compile: npm run build, tsc --noEmit, cargo build
□ Lint check: eslint, flake8, mypy, clippy
□ Console.log: add logs, run app, verify output
□ App logs: review logs/ for errors/warnings
□ Puppeteer: screenshot UI, test interactions
□ API tests: curl endpoints, verify responses
□ Runtime: start app, confirm no crashes

BEFORE STOPPING:
1. ✅ Root is clean (verified automatically)
2. Complete ALL user requests
3. Execute 3+ validation methods above
4. Present validation report with ACTUAL OUTPUT
5. Commit completed work: git add . && git commit -m "..."
6. Push to remote: git push

To authorize stop, run: bash {auth_script}
======================================================================
"""
            print(blocked_msg, file=sys.stderr)
            sys.exit(2)  # Exit code 2 blocks stop

        # Stop is authorized - reset authorization for next time (one-time use)
        try:
            auth_file = Path(".claude/data/stop_authorization.json")
            with open(auth_file, 'w') as f:
                json.dump({"authorized": False}, f)
        except Exception:
            pass  # Fail silently if can't reset

        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        parser.add_argument('--notify', action='store_true', help='Enable TTS completion announcement')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

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
