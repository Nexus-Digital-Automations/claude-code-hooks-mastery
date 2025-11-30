#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import os
import sys
import re
from pathlib import Path

# Fix Python environment warnings
for var in ['PYTHONHOME', 'PYTHONPATH']:
    if var in os.environ:
        del os.environ[var]

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

    # 2. Inject tool-specific context if exists
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

    return "\n".join(injections) if injections else None


def is_env_file_access(tool_name, tool_input):
    """
    Check if any tool is trying to access .env files containing sensitive data.
    """
    if tool_name in ['Read', 'Edit', 'MultiEdit', 'Write', 'Bash']:
        # Check file paths for file-based tools
        if tool_name in ['Read', 'Edit', 'MultiEdit', 'Write']:
            file_path = tool_input.get('file_path', '')
            if '.env' in file_path and not file_path.endswith('.env.sample'):
                return True
        
        # Check bash commands for .env file access
        elif tool_name == 'Bash':
            command = tool_input.get('command', '')
            # Pattern to detect .env file access (but allow .env.sample)
            env_patterns = [
                r'\b\.env\b(?!\.sample)',  # .env but not .env.sample
                r'cat\s+.*\.env\b(?!\.sample)',  # cat .env
                r'echo\s+.*>\s*\.env\b(?!\.sample)',  # echo > .env
                r'touch\s+.*\.env\b(?!\.sample)',  # touch .env
                r'cp\s+.*\.env\b(?!\.sample)',  # cp .env
                r'mv\s+.*\.env\b(?!\.sample)',  # mv .env
            ]
            
            for pattern in env_patterns:
                if re.search(pattern, command):
                    return True
    
    return False

def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)
        
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        
        # Check for .env file access (blocks access to sensitive environment files)
        if is_env_file_access(tool_name, tool_input):
            print("BLOCKED: Access to .env files containing sensitive data is prohibited", file=sys.stderr)
            print("Use .env.sample for template files instead", file=sys.stderr)
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

        # Ensure log directory exists
        log_dir = Path.cwd() / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'pre_tool_use.json'
        
        # Read existing log data or initialize empty list
        if log_path.exists():
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
        
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Gracefully handle JSON decode errors
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)

if __name__ == '__main__':
    main()