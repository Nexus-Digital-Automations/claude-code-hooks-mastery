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


def load_development_context(source):
    """Load relevant development context based on session source."""
    context_parts = []

    # Add timestamp
    context_parts.append(f"Session started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    context_parts.append(f"Session source: {source}")

    # Add validation requirements
    validation_instructions = """
--- MANDATORY VALIDATION PROTOCOL ---
BEFORE completing ANY task, you MUST validate your work using one or more of these methods:

TESTING METHODS:
- Unit tests: `npm test`, `pytest`, `cargo test`, `go test`, `jest`, `mocha`
- Integration tests: Run API tests, database tests
- E2E tests: Puppeteer, Playwright, Cypress, Selenium
- Type checking: `tsc --noEmit`, `mypy`, `pyright`

BUILD VERIFICATION:
- Compile/build: `npm run build`, `tsc`, `cargo build`, `go build`
- Lint check: `eslint`, `flake8`, `pylint`, `clippy`
- No errors in build output

RUNTIME VERIFICATION:
- Add console.log/print statements to verify code paths execute
- Run the application and check it starts without errors
- Make API calls and verify responses
- Check browser console for errors

LOG ANALYSIS:
- Review application logs for errors/warnings
- Check server logs after making requests
- Analyze test output for failures
- Review build output for warnings

VISUAL VERIFICATION:
- Take screenshots of UI changes (if applicable)
- Use Puppeteer/Playwright to capture page state
- Verify visual elements render correctly

PROOF OF FUNCTIONALITY:
- Show command output proving tests pass
- Display log entries proving code executed
- Capture API responses showing correct behavior
- Screenshot showing expected UI state

VALIDATION REPORT REQUIRED:
Before stopping, you MUST present a report like this:

## Validation Report
**Command:** `[what you ran]`
**Result:** ✅ PASS or ❌ FAIL
**Output:** [actual output snippet]

Show proof. The user is a critical thinker - not empty claims.

YOU ARE NOT ALLOWED TO STOP until you have:
1. Executed at least one validation method
2. Confirmed the validation passed
3. Fixed any failures found
4. Presented a validation report with proof

This is not optional - it is a requirement. Run the validation commands yourself.
"""
    context_parts.append(validation_instructions)

    # Add autonomous execution guidance
    autonomous_execution = """
--- AUTONOMOUS EXECUTION ---
DO NOT ASK: "Should I fix this?" / "Should I continue?" / "Want me to proceed?"
Just fix it. Just continue. Just proceed.
Errors = fix immediately and continue.
Ambiguity = resolve UPFRONT ONLY, not mid-task.
KEEP WORKING until ALL requested features are complete.
"""
    context_parts.append(autonomous_execution)
    
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

    return "\n".join(context_parts)


def load_reasoning_context() -> str:
    """Load patterns and strategies from Claude-Mem, PatternLearner, and ReasoningBank."""
    context_parts = []

    # Try to load from Claude-Mem (port 37777)
    try:
        from utils.claude_mem import load_recent_context
        context_str = load_recent_context()
        if context_str:
            context_parts.append(context_str)
    except Exception:
        pass  # Graceful degradation

    # Try to load from PatternLearner
    try:
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        strategies = learner.get_recommended_strategies(limit=3)
        if strategies:
            context_parts.append("--- Recommended Strategies ---")
            for s in strategies:
                desc = s.get('description', s.get('pattern_key', 'Unknown'))
                rate = s.get('success_rate', 0)
                context_parts.append(f"- {desc} ({rate:.0%} success)")
    except Exception:
        pass  # Graceful degradation

    # Try to load from Claude Flow ReasoningBank
    try:
        from utils.claude_flow import ClaudeFlowClient
        cf = ClaudeFlowClient()
        rb_context = cf.memory_query("session patterns", namespace="sessions", limit=3)
        if rb_context:
            context_parts.append("--- ReasoningBank Patterns ---")
            context_parts.append(rb_context[:500])  # Limit output
    except Exception:
        pass  # Graceful degradation

    return "\n".join(context_parts) if context_parts else ""


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
        _session_id = input_data.get('session_id', 'unknown')  # Reserved for future use
        source = input_data.get('source', 'unknown')  # "startup", "resume", or "clear"

        # Log the session start event
        log_session_start(input_data)

        # Load development context if requested
        if args.load_context:
            context = load_development_context(source)
            # Add reasoning context (patterns, strategies)
            reasoning_ctx = load_reasoning_context()
            if reasoning_ctx:
                context = context + "\n\n" + reasoning_ctx if context else reasoning_ctx
            if context:
                # Using JSON output to add context
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": context
                    }
                }
                print(json.dumps(output))
                sys.exit(0)
        
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