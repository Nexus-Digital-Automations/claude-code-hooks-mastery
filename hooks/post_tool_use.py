#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Add hooks directory to path for utils imports
sys.path.insert(0, str(Path(__file__).parent))

# Fix Python environment warnings
for var in ['PYTHONHOME', 'PYTHONPATH']:
    if var in os.environ:
        del os.environ[var]

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


def observe_bash_check(session_id: str, tool_input: dict, tool_response) -> None:
    """Auto-record verification checks by observing Bash command outputs.

    Matches the command against the project's .claude-project.json config
    (or generic fallback patterns) and writes to the verification record.
    Never raises — observation is best-effort.
    """
    try:
        from utils.project_config import get_git_root, load_config, match_command, evaluate_output
        from utils.vr_utils import write_vr

        command = (tool_input.get("command") or "").strip()
        if not command:
            return

        # Extract stdout/stderr from tool_response (format varies)
        if isinstance(tool_response, dict):
            stdout = tool_response.get("stdout", "") or ""
            stderr = tool_response.get("stderr", "") or ""
        elif isinstance(tool_response, str):
            stdout = tool_response
            stderr = ""
        else:
            stdout = str(tool_response) if tool_response else ""
            stderr = ""

        project_root = Path(get_git_root())
        config = load_config(project_root)
        result = match_command(command, config)
        if not result:
            return

        check_key, check_conf = result
        vr_file = Path.home() / f".claude/data/verification_record_{session_id}.json"

        # commit_push needs both git commit + git push
        if check_key == "commit_push":
            _handle_commit_push(session_id, command, stdout, stderr, vr_file)
            return

        status = evaluate_output(stdout, stderr, check_conf)
        evidence = f"[auto] $ {command[:200]}\n{stdout[:1500]}"
        if stderr.strip():
            evidence += f"\nstderr: {stderr[:300]}"
        write_vr(vr_file, check_key, status, evidence, session_id=session_id)
    except Exception:
        pass  # Never block the hook


def _handle_commit_push(session_id: str, command: str, stdout: str, stderr: str, vr_file: Path) -> None:
    """Track git commit + git push as two sub-states for the commit_push check."""
    try:
        from utils.vr_utils import write_vr

        state_file = Path.home() / f".claude/data/commit_push_state_{session_id}.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)

        state = {}
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
            except Exception:
                state = {}

        cmd_lower = command.lower()
        combined = stdout + "\n" + stderr

        if "git commit" in cmd_lower and "git commit --amend" not in cmd_lower:
            # Check for actual commit (not just a failed one)
            if any(p in combined.lower() for p in ["files changed", "insertion", "create mode", "file changed"]):
                state["commit_observed"] = True
                state["commit_evidence"] = f"$ {command[:100]}\n{stdout[:300]}"

        if "git push" in cmd_lower and "--dry-run" not in cmd_lower:
            if "rejected" not in combined.lower() and "error" not in combined.lower():
                state["push_observed"] = True
                state["push_evidence"] = f"$ {command[:100]}\n{stdout[:300]}"

        state_file.write_text(json.dumps(state))

        # Write VR when both are observed
        if state.get("commit_observed") and state.get("push_observed"):
            evidence = f"[auto] commit: {state.get('commit_evidence', '')}\npush: {state.get('push_evidence', '')}"
            write_vr(vr_file, "commit_push", "passed", evidence, session_id=session_id)
    except Exception:
        pass


def update_tool_tracking(session_id: str, tool_name: str, tool_input: dict) -> None:
    """Atomic read-modify-write to ~/.claude/data/sessions/{session_id}_tools.json. Never raises."""
    try:
        tools_file = Path.home() / ".claude" / "data" / "sessions" / f"{session_id}_tools.json"
        data = {}
        if tools_file.exists():
            try:
                data = json.loads(tools_file.read_text())
            except Exception:
                data = {}
        if not data:
            data = {"session_id": session_id, "edit_extensions": {},
                    "write_extensions": {}, "bash_count": 0, "read_count": 0}

        if tool_name in ("Edit", "MultiEdit"):
            ext = Path(tool_input.get("file_path", "")).suffix.lower() or ".unknown"
            data["edit_extensions"][ext] = data["edit_extensions"].get(ext, 0) + 1
        elif tool_name == "Write":
            ext = Path(tool_input.get("file_path", "")).suffix.lower() or ".unknown"
            data["write_extensions"][ext] = data["write_extensions"].get(ext, 0) + 1
        elif tool_name == "Bash":
            data["bash_count"] = data.get("bash_count", 0) + 1
        elif tool_name == "Read":
            data["read_count"] = data.get("read_count", 0) + 1
        else:
            return  # Nothing to track

        data["last_updated"] = datetime.now().isoformat()
        tools_file.parent.mkdir(parents=True, exist_ok=True)
        tools_file.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _track_deepseek_result(session_id, tool_name, tool_input, tool_result):
    """Log DeepSeek MCP tool calls to a ring buffer (last 50 entries)."""
    ds_log = Path.home() / ".claude" / "data" / "deepseek_delegations.json"
    ds_log.parent.mkdir(parents=True, exist_ok=True)

    entries = []
    if ds_log.exists():
        try:
            entries = json.loads(ds_log.read_text())
        except Exception:
            entries = []

    # Extract action from tool name (e.g. mcp__deepseek-agent__run → run)
    action = tool_name.rsplit("__", 1)[-1] if "__" in tool_name else tool_name

    entry = {
        "timestamp": datetime.now().isoformat(),
        "session_id": session_id[:8],
        "action": action,
        "task_snippet": str(tool_input.get("task", tool_input.get("prompt", "")))[:200],
        "agent_id": tool_input.get("agent_id", ""),
        "state": str(tool_result)[:200] if tool_result else "",
    }
    entries.append(entry)

    # Keep last 50 entries
    entries = entries[-50:]

    ds_log.write_text(json.dumps(entries, indent=2))


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
        tool_result = input_data.get('tool_response', {})
        session_id = input_data.get('session_id', '')

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

        # Auto-observe Bash commands for verification checks
        if session_id and tool_name == "Bash":
            observe_bash_check(session_id, tool_input, tool_result)

        # Track tool usage for DeepSeek context enrichment
        if session_id and tool_name in ("Write", "Edit", "MultiEdit", "Bash", "Read"):
            update_tool_tracking(session_id, tool_name, tool_input)

        # Track DeepSeek MCP delegations
        if tool_name.startswith('mcp__deepseek-agent__'):
            try:
                _track_deepseek_result(session_id, tool_name, tool_input, tool_result)
            except Exception:
                pass

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
