#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Claude Flow CLI Wrapper - Swarm Orchestration & ReasoningBank Integration

Provides interface to Claude Flow CLI commands for:
- Swarm coordination (hierarchical, mesh, adaptive topologies)
- ReasoningBank memory operations (query, store, consolidate)
- Agent spawning and task orchestration

Usage:
    from utils.claude_flow import ClaudeFlowClient
    cf = ClaudeFlowClient()
    patterns = cf.memory_query("authentication patterns")
    cf.memory_store("session_123", {"learned": "..."})
"""

import subprocess
import json
from typing import Any, Optional


class ClaudeFlowClient:
    """Client for Claude Flow CLI operations with MCP fallback."""

    def __init__(self, timeout: float = 10.0):
        """
        Initialize the client.

        Args:
            timeout: Command timeout in seconds (increased to 10s for reliability)
        """
        self.timeout = timeout
        self.cli_prefix = ["npx", "claude-flow@alpha"]
        self._log_enabled = True

    def _log(self, level: str, message: str, **kwargs):
        """Log messages to .claude/logs/claude_flow.json if enabled."""
        if not self._log_enabled:
            return
        try:
            import os
            from datetime import datetime
            log_dir = os.path.join(os.path.expanduser("~"), ".claude", "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "claude_flow.json")

            entry = {
                "timestamp": datetime.now().isoformat(),
                "level": level,
                "message": message,
                **kwargs
            }

            logs = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        logs = json.load(f)
                except (json.JSONDecodeError, IOError):
                    logs = []

            logs.append(entry)
            logs = logs[-100:]  # Keep last 100 entries

            with open(log_file, 'w') as f:
                json.dump(logs, f, indent=2)
        except (IOError, OSError):
            pass  # Silent failure for logging

    def _run_command(self, args: list, input_data: str = None) -> Optional[str]:
        """
        Run a Claude Flow CLI command with error logging.

        Args:
            args: Command arguments
            input_data: Optional stdin input

        Returns:
            Command output or None on failure
        """
        cmd_str = " ".join(self.cli_prefix + args)
        try:
            result = subprocess.run(
                self.cli_prefix + args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                input=input_data
            )
            if result.returncode == 0:
                self._log("debug", f"Command succeeded: {args[0]}", command=cmd_str)
                return result.stdout.strip()
            else:
                self._log("warning", f"Command failed: {args[0]}",
                         command=cmd_str, stderr=result.stderr[:200])
            return None
        except subprocess.TimeoutExpired:
            self._log("error", f"Command timed out after {self.timeout}s", command=cmd_str)
            return None
        except FileNotFoundError:
            self._log("error", "npx not found - Claude Flow CLI unavailable", command=cmd_str)
            return None
        except Exception as e:
            self._log("error", f"Command error: {str(e)[:100]}", command=cmd_str)
            return None

    # =========================================================================
    # ReasoningBank Health & Initialization
    # =========================================================================

    def is_reasoningbank_available(self) -> bool:
        """
        Check if ReasoningBank is available and initialized.

        Returns:
            True if ReasoningBank database exists or can be initialized
        """
        import os
        from pathlib import Path

        # Check if database file exists
        db_paths = [
            Path('.swarm/memory.db'),
            Path(os.path.expanduser('~/.swarm/memory.db')),
            Path(os.path.expanduser('~/.claude/.swarm/memory.db'))
        ]

        for db_path in db_paths:
            if db_path.exists():
                self._log("debug", f"ReasoningBank DB found at {db_path}")
                return True

        # Try to initialize via stats command (will create DB if needed)
        result = self._run_command(['memory', 'stats'])
        if result is not None:
            self._log("info", "ReasoningBank initialized successfully")
            return True

        self._log("warning", "ReasoningBank not available")
        return False

    def initialize_reasoningbank(self) -> bool:
        """
        Explicitly initialize ReasoningBank database.

        Returns:
            True if initialization succeeded
        """
        # Use longer timeout for initial setup
        old_timeout = self.timeout
        self.timeout = 30.0

        try:
            # Run memory stats which triggers initialization
            result = self._run_command(['memory', 'stats'])
            if result is not None:
                self._log("info", "ReasoningBank initialized", output=result[:200])
                return True

            # Fallback: try memory query which also initializes
            result = self._run_command(['memory', 'query', 'init', '--reasoningbank'])
            return result is not None
        finally:
            self.timeout = old_timeout

    def memory_stats(self) -> Optional[dict]:
        """
        Get ReasoningBank statistics.

        Returns:
            Stats dict with total_memories, namespaces, etc. or None
        """
        result = self._run_command(['memory', 'stats', '--json'])
        if result:
            try:
                return json.loads(result)
            except json.JSONDecodeError:
                return {'raw': result}
        return None

    # =========================================================================
    # ReasoningBank Memory Operations
    # =========================================================================

    def memory_query(self, query: str, namespace: str = None,
                     limit: int = 3) -> Optional[str]:
        """
        Query ReasoningBank for relevant patterns.

        Args:
            query: Search query
            namespace: Optional namespace filter (debugging, architecture, etc.)
            limit: Maximum results to return

        Returns:
            Query results or None
        """
        args = ["memory", "query", query, "--reasoningbank", "--limit", str(limit)]
        if namespace:
            args.extend(["--namespace", namespace])
        return self._run_command(args)

    def memory_store(self, key: str, value: Any,
                     namespace: str = None,
                     confidence: float = 0.5) -> bool:
        """
        Store pattern to ReasoningBank.

        Args:
            key: Storage key
            value: Value to store (will be JSON-serialized if dict)
            namespace: Optional namespace
            confidence: Initial confidence score (0.0-1.0)

        Returns:
            True on success, False on failure
        """
        value_str = json.dumps(value) if isinstance(value, dict) else str(value)
        args = [
            "memory", "store", key, value_str,
            "--reasoningbank",
            "--confidence", str(confidence)
        ]
        if namespace:
            args.extend(["--namespace", namespace])
        result = self._run_command(args)
        return result is not None

    def memory_consolidate(self) -> bool:
        """
        Consolidate ReasoningBank memories (remove duplicates, prune low-confidence).

        Returns:
            True on success, False on failure
        """
        result = self._run_command(["memory", "consolidate", "--reasoningbank"])
        return result is not None

    # =========================================================================
    # Swarm Coordination Operations
    # =========================================================================

    def swarm_init(self, topology: str = "hierarchical") -> bool:
        """
        Initialize swarm coordination.

        Args:
            topology: Swarm topology (hierarchical, mesh, adaptive, collective)

        Returns:
            True on success, False on failure
        """
        result = self._run_command([
            "coordination", "swarm-init",
            "--topology", topology
        ])
        return result is not None

    def agent_spawn(self, agent_type: str, task: str = None) -> Optional[str]:
        """
        Spawn a specialized agent.

        Args:
            agent_type: Type of agent (coder, reviewer, tester, etc.)
            task: Optional task description

        Returns:
            Agent ID or None on failure
        """
        args = ["coordination", "agent-spawn", "--type", agent_type]
        if task:
            args.extend(["--task", task])
        return self._run_command(args)

    def task_orchestrate(self, task: str, agents: list = None) -> Optional[str]:
        """
        Orchestrate a task across agents.

        Args:
            task: Task description
            agents: Optional list of agent types to use

        Returns:
            Orchestration result or None
        """
        args = ["coordination", "task-orchestrate", "--task", task]
        if agents:
            args.extend(["--agents", ",".join(agents)])
        return self._run_command(args)

    # =========================================================================
    # SPARC Development Operations
    # =========================================================================

    def sparc_tdd(self, feature: str) -> Optional[str]:
        """
        Run SPARC TDD workflow for a feature.

        Args:
            feature: Feature description

        Returns:
            Workflow result or None
        """
        return self._run_command(["sparc", "tdd", feature])

    def sparc_analyze(self, target: str) -> Optional[str]:
        """
        Run SPARC analysis on a target.

        Args:
            target: Analysis target (file, directory, or description)

        Returns:
            Analysis result or None
        """
        return self._run_command(["sparc", "analyze", target])

    # =========================================================================
    # GitHub Integration Operations
    # =========================================================================

    def github_pr_manager(self) -> Optional[str]:
        """
        Run GitHub PR manager.

        Returns:
            PR manager result or None
        """
        return self._run_command(["github", "pr-manager"])

    def github_issue_tracker(self) -> Optional[str]:
        """
        Run GitHub issue tracker.

        Returns:
            Issue tracker result or None
        """
        return self._run_command(["github", "issue-tracker"])


# Convenience functions for hook integration

def query_reasoning_patterns(query: str, namespace: str = None) -> Optional[str]:
    """
    Query ReasoningBank for patterns (convenience function).

    Called from pre_tool_use.py for context injection.
    """
    client = ClaudeFlowClient()
    return client.memory_query(query, namespace=namespace)


def store_session_learning(session_id: str, data: dict) -> bool:
    """
    Store session learning to ReasoningBank (convenience function).

    Called from stop.py for persistence.
    """
    client = ClaudeFlowClient()
    return client.memory_store(
        f"session_{session_id}",
        data,
        namespace="sessions"
    )


def consolidate_memories() -> bool:
    """
    Consolidate ReasoningBank memories (convenience function).

    Called from stop.py or session_end.py for cleanup.
    """
    client = ClaudeFlowClient()
    return client.memory_consolidate()


def memory_search(pattern: str, namespace: str = None, limit: int = 5) -> Optional[str]:
    """
    Search ReasoningBank for patterns (convenience function).

    Args:
        pattern: Search pattern (regex supported)
        namespace: Optional namespace filter
        limit: Maximum results

    Returns:
        Search results or None
    """
    client = ClaudeFlowClient()
    args = ["memory", "search", pattern, "--reasoningbank", "--limit", str(limit)]
    if namespace:
        args.extend(["--namespace", namespace])
    return client._run_command(args)


def get_tool_patterns(tool_name: str) -> Optional[str]:
    """
    Get patterns for a specific tool from ReasoningBank.

    Args:
        tool_name: Name of tool (e.g., 'Bash', 'Edit', 'Write')

    Returns:
        Tool-specific patterns or None
    """
    client = ClaudeFlowClient()
    return client.memory_query(
        f"tool:{tool_name} patterns best practices",
        namespace="tools",
        limit=3
    )


def store_tool_pattern(tool_name: str, pattern: dict, confidence: float = 0.6) -> bool:
    """
    Store a tool usage pattern to ReasoningBank.

    Args:
        tool_name: Name of tool
        pattern: Pattern data (success/failure, context, etc.)
        confidence: Initial confidence score

    Returns:
        True on success
    """
    from datetime import datetime
    client = ClaudeFlowClient()
    key = f"tool_{tool_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return client.memory_store(key, pattern, namespace="tools", confidence=confidence)


def assess_task_complexity(task_description: str) -> Optional[str]:
    """
    Assess task complexity for swarm topology selection.

    Returns assessment string or None.
    """
    client = ClaudeFlowClient()
    # Use memory to find similar past tasks
    similar = client.memory_query(task_description[:100], namespace="tasks", limit=2)
    if similar:
        return f"Found similar tasks: {similar[:200]}"
    return None


if __name__ == '__main__':
    # Simple test
    print("Testing Claude Flow client...")

    client = ClaudeFlowClient()

    # Test memory query (will fail gracefully if CLI not available)
    result = client.memory_query("test patterns")
    print(f"Memory query result: {result}")

    # Test memory store
    success = client.memory_store("test_key", {"test": "value"})
    print(f"Memory store success: {success}")

    print("Test complete")
