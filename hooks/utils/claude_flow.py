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
    """Client for Claude Flow CLI operations."""

    def __init__(self, timeout: float = 3.0):
        """
        Initialize the client.

        Args:
            timeout: Command timeout in seconds (keep short for non-blocking)
        """
        self.timeout = timeout
        self.cli_prefix = ["npx", "claude-flow@alpha"]

    def _run_command(self, args: list, input_data: str = None) -> Optional[str]:
        """
        Run a Claude Flow CLI command.

        Args:
            args: Command arguments
            input_data: Optional stdin input

        Returns:
            Command output or None on failure
        """
        try:
            result = subprocess.run(
                self.cli_prefix + args,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                input=input_data
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
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
