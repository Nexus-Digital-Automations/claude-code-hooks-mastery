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


def store_tool_observation(session_id, tool_name, tool_input, tool_result):
    """
    Store tool observation to Claude-Mem, ReasoningBank, PatternLearner,
    Neural, Analytics, and Swarm systems.

    All operations are non-blocking with graceful fallback.
    Enhanced with MCP tool integrations.
    """
    # Determine success based on tool result
    is_success = True
    result_str = str(tool_result)[:5000]
    if 'error' in result_str.lower() or 'failed' in result_str.lower():
        is_success = False

    # 1. Claude-Mem: Store observation via HTTP API (increased timeout)
    try:
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient(timeout=5.0)  # Increased from 2.0
        client.store_observation(
            session_id=session_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_response=result_str
        )
    except Exception:
        pass  # Graceful degradation

    # 2. ReasoningBank: Store patterns for code-modifying tools (with confidence)
    if tool_name in ['Write', 'Edit', 'MultiEdit', 'Bash', 'Read', 'Grep', 'Glob']:
        try:
            from utils.claude_flow import store_tool_pattern
            store_tool_pattern(
                tool_name,
                {
                    "tool": tool_name,
                    "file": tool_input.get("file_path", tool_input.get("command", ""))[:100],
                    "success": is_success,
                    "session": session_id[:8],
                    "result_preview": result_str[:200]
                },
                confidence=0.7 if is_success else 0.4
            )
        except Exception:
            pass  # Graceful degradation

    # 3. PatternLearner: Record experience for local learning
    try:
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.record_experience(tool_name, {
            "success": is_success,
            "file_path": tool_input.get("file_path", ""),
            "session": session_id[:8]
        })
    except Exception:
        pass  # Graceful degradation

    # 4. NEW: Neural pattern training for successful operations
    if is_success and tool_name in ['Write', 'Edit', 'MultiEdit', 'Bash']:
        try:
            from utils.neural_client import get_neural_client
            client = get_neural_client(timeout=3.0)

            # Train pattern for this successful operation
            client.analyze_patterns(
                action='learn',
                operation=f'tool:{tool_name}',
                outcome='success',
                metadata={
                    'session': session_id[:8],
                    'file': tool_input.get('file_path', '')[:100],
                    'confidence': 0.7
                }
            )
        except Exception:
            pass  # Graceful degradation

    # 5. NEW: Analytics tracking for performance monitoring
    try:
        from utils.analytics_client import get_analytics_client
        client = get_analytics_client(timeout=3.0)

        # Record metrics for this tool operation
        client.metrics_collect(components=[tool_name])
    except Exception:
        pass  # Graceful degradation

    # 7. NEW: Track plugin relevance for learning feedback
    if is_success:
        try:
            from utils.plugin_resolver import get_resolver
            resolver = get_resolver()
            relevant_plugins = resolver.resolve_by_tool(tool_name, tool_input)
            if relevant_plugins:
                # Record to PatternLearner so future recommendations improve
                try:
                    from utils.pattern_learner import PatternLearner
                    pl = PatternLearner()
                    for p in relevant_plugins[:2]:
                        pl.record_experience(
                            f"plugin:{p.get('name', 'unknown')}",
                            {
                                "tool": tool_name,
                                "plugin": p.get('name', ''),
                                "category": p.get('category', ''),
                                "success": True,
                                "session": session_id[:8]
                            }
                        )
                except Exception:
                    pass
        except Exception:
            pass  # Graceful degradation

    # 6. NEW: Swarm coordination update for agent tracking
    try:
        from utils.swarm_client import get_swarm_client
        client = get_swarm_client(timeout=3.0)

        # Update coordination if swarm is active
        status = client.swarm_status(verbose=False)
        if status and status.get('status') == 'active':
            # Store operation in swarm memory namespace
            from utils.mcp_client import get_mcp_client
            mcp = get_mcp_client(timeout=3.0)
            mcp.memory_store(
                key=f'tool_op/{session_id[:8]}/{tool_name}',
                value=json.dumps({
                    'tool': tool_name,
                    'success': is_success,
                    'timestamp': __import__('datetime').datetime.now().isoformat()
                }),
                namespace='swarm_coordination',
                ttl=3600  # 1 hour TTL
            )
    except Exception:
        pass  # Graceful degradation


def update_tool_tracking(session_id: str, tool_name: str, tool_input: dict) -> None:
    """Atomic read-modify-write to ~/.claude/data/sessions/{session_id}_tools.json. Never raises."""
    try:
        tools_file = Path.home() / ".claude" / "data" / "sessions" / f"{session_id}_tools.json"
        data = {}
        if tools_file.exists():
            try: data = json.loads(tools_file.read_text())
            except Exception: data = {}
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

        # Store observation to Claude-Mem, ReasoningBank, and PatternLearner
        if session_id:
            store_tool_observation(session_id, tool_name, tool_input, tool_result)

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
