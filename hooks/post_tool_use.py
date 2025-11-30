#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import subprocess
import sys
from pathlib import Path

# Linter commands by file extension
LINTER_MAP = {
    # Python
    '.py': ['ruff', 'check', '--output-format=concise'],

    # JavaScript/TypeScript
    '.js': ['eslint', '--format=compact'],
    '.ts': ['eslint', '--format=compact'],
    '.tsx': ['eslint', '--format=compact'],
    '.jsx': ['eslint', '--format=compact'],

    # Go
    '.go': ['go', 'vet'],

    # Rust
    '.rs': ['cargo', 'clippy', '--message-format=short', '--'],

    # C/C++
    '.c': ['clang-tidy'],
    '.cpp': ['clang-tidy'],
    '.cc': ['clang-tidy'],
    '.cxx': ['clang-tidy'],
    '.h': ['clang-tidy'],
    '.hpp': ['clang-tidy'],

    # C#
    '.cs': ['dotnet', 'format', '--verify-no-changes'],
}


def lint_file(file_path):
    """
    Run appropriate linter on file based on extension.
    Returns (has_errors, output) tuple.
    """
    ext = Path(file_path).suffix.lower()

    if ext not in LINTER_MAP:
        return False, None

    linter_cmd = LINTER_MAP[ext] + [file_path]

    try:
        result = subprocess.run(
            linter_cmd,
            capture_output=True,
            text=True,
            timeout=10
        )

        output = result.stdout.strip() or result.stderr.strip()
        has_errors = result.returncode != 0

        return has_errors, output if output else None

    except subprocess.TimeoutExpired:
        return False, None  # Timed out, don't block
    except FileNotFoundError:
        return False, None  # Linter not installed, skip gracefully
    except Exception:
        return False, None  # Any other error, skip gracefully


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})

        # Lint files after Write/Edit/MultiEdit
        if tool_name in ['Write', 'Edit', 'MultiEdit']:
            file_path = tool_input.get('file_path', '')

            if file_path:
                has_errors, lint_output = lint_file(file_path)

                if has_errors and lint_output:
                    # Block with lint errors
                    print(f"LINT ERRORS in {file_path}:", file=sys.stderr)
                    print(lint_output[:1000], file=sys.stderr)
                    sys.exit(2)  # Exit code 2 blocks the operation

        # Log to JSONL file (append-only, safe for concurrent access)
        log_dir = Path.home() / '.claude' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'post_tool_use.jsonl'

        with open(log_path, 'a') as f:
            f.write(json.dumps(input_data) + '\n')

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Exit cleanly on any other error
        sys.exit(0)

if __name__ == '__main__':
    main()
