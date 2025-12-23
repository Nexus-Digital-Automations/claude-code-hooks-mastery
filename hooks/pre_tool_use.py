#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import os
import sys
import re
from pathlib import Path

# Add hooks directory to path for utils imports
sys.path.insert(0, str(Path(__file__).parent))

# Fix Python environment warnings
for var in ['PYTHONHOME', 'PYTHONPATH']:
    if var in os.environ:
        del os.environ[var]

def get_pattern_context():
    """
    Query patterns from Claude-Mem and PatternLearner.
    Returns context string or empty string if no patterns.
    """
    context_parts = []

    # 1. Query Claude-Mem for recent patterns
    try:
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        patterns = client.retrieve('recent_patterns', [])
        if patterns:
            context_parts.append("--- Recent Learned Patterns ---")
            for p in patterns[-3:]:
                context_parts.append(f"- {p.get('summary', 'Pattern')}")
    except Exception:
        pass  # Graceful degradation

    # 2. Query PatternLearner for strategies
    try:
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        strategies = learner.get_recommended_strategies(limit=2)
        if strategies:
            context_parts.append("--- Recommended Strategies ---")
            for s in strategies:
                desc = s.get('description', s.get('pattern_key', ''))
                if desc:
                    context_parts.append(f"- {desc}")
    except Exception:
        pass  # Graceful degradation

    return "\n".join(context_parts) if context_parts else ""


def get_current_focus(cwd):
    """
    Find the first unfinished task in FEATURES.md.
    Returns the task text or None if no unfinished tasks.
    """
    features_file = Path(cwd) / "docs" / "development" / "FEATURES.md"

    if not features_file.exists():
        return None

    try:
        content = features_file.read_text()
        # Find first unchecked item: - [ ] task description
        match = re.search(r'^- \[ \] (.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass

    return None  # All tasks complete or file unreadable


def get_context_injection(cwd, tool_name):
    """
    Build context injection from FEATURES.md and tool-specific files.
    """
    docs_dir = Path(cwd) / "docs" / "development"
    hooks_dir = docs_dir / "hooks"
    injections = []

    # 1. Auto-derive focus from first unfinished task in FEATURES.md
    current_task = get_current_focus(cwd)
    if current_task:
        injections.append(f"📌 CURRENT TASK: {current_task}")

    # 2. Security reminder for Write/Edit operations
    if tool_name in ['Write', 'Edit', 'MultiEdit']:
        injections.append("🔐 SECURITY: Never write secrets (API keys, passwords, tokens) outside of .env files or gitignored files")

    # 3. Inject tool-specific context if exists
    tool_map = {
        'Bash': 'bash.md',
        'Edit': 'edit.md',
        'Write': 'edit.md',
        'MultiEdit': 'edit.md',
    }

    if tool_name in tool_map:
        tool_file = hooks_dir / tool_map[tool_name]
        if tool_file.exists():
            try:
                content = tool_file.read_text().strip()
                if content:
                    injections.append(f"🔧 {tool_name}: {content[:150]}")
            except Exception:
                pass

    # 4. Query patterns from Claude-Mem and PatternLearner
    pattern_ctx = get_pattern_context()
    if pattern_ctx:
        injections.append(pattern_ctx)

    # 5. Query ReasoningBank via Claude Flow
    try:
        from utils.claude_flow import query_reasoning_patterns
        rb_patterns = query_reasoning_patterns(tool_name, namespace='debugging')
        if rb_patterns:
            injections.append(f"--- ReasoningBank ---\n{rb_patterns[:300]}")
    except Exception:
        pass  # Graceful degradation

    return "\n".join(injections) if injections else None


def is_env_file_write(tool_name, tool_input):
    """
    Check if any tool is trying to WRITE/EDIT .env files containing sensitive data.
    Reading .env files is allowed; only modifications are blocked.
    """
    # Only block write/edit operations, not reads
    if tool_name in ['Edit', 'MultiEdit', 'Write']:
        file_path = tool_input.get('file_path', '')
        if '.env' in file_path and not file_path.endswith('.env.sample'):
            return True

    # Check bash commands for .env file modifications (but allow cat/reading)
    elif tool_name == 'Bash':
        command = tool_input.get('command', '')
        # Pattern to detect .env file WRITE operations (not reads)
        env_write_patterns = [
            r'echo\s+.*>\s*\.env\b(?!\.sample)',  # echo > .env
            r'touch\s+.*\.env\b(?!\.sample)',  # touch .env
            r'cp\s+.*\.env\b(?!\.sample)',  # cp .env
            r'mv\s+.*\.env\b(?!\.sample)',  # mv .env
            r'>\s*\.env\b(?!\.sample)',  # redirect to .env
            r'>>\s*\.env\b(?!\.sample)',  # append to .env
            r'rm\s+.*\.env\b(?!\.sample)',  # rm .env
            r'sed\s+-i.*\.env\b(?!\.sample)',  # sed -i .env (in-place edit)
        ]

        for pattern in env_write_patterns:
            if re.search(pattern, command):
                return True

    return False

def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)
        
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        
        # Check for .env file writes (blocks modifications to sensitive environment files)
        if is_env_file_write(tool_name, tool_input):
            print("BLOCKED: Writing/editing .env files is prohibited", file=sys.stderr)
            print("Reading .env is allowed; use .env.sample for templates", file=sys.stderr)
            sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude

        # Inject context from FEATURES.md (current task reminder)
        cwd = input_data.get('cwd', os.getcwd())
        context = get_context_injection(cwd, tool_name)
        if context:
            output = {
                "hookSpecificOutput": {
                    "additionalContext": context
                }
            }
            print(json.dumps(output))

        # Log to JSONL file (append-only, safe for concurrent access)
        log_dir = Path.home() / '.claude' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'pre_tool_use.jsonl'

        with open(log_path, 'a') as f:
            f.write(json.dumps(input_data) + '\n')
        
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Gracefully handle JSON decode errors
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)

if __name__ == '__main__':
    main()