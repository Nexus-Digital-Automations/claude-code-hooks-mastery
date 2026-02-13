"""
Unified MCP client for Claude-Flow, Ruv-Swarm, and Flow-Nexus tools.
Provides a consistent interface with graceful degradation and timeout handling.
"""

import json
import subprocess
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import time

try:
    from .config_loader import get_config
except ImportError:
    from config_loader import get_config


class MCPClient:
    """
    Unified MCP client supporting Claude-Flow, Ruv-Swarm, and Flow-Nexus.

    All operations are non-blocking with configurable timeouts and graceful fallbacks.
    """

    def __init__(self, timeout: Optional[float] = None, server: str = 'claude-flow'):
        """
        Initialize MCP client.

        Args:
            timeout: Default timeout in seconds (uses config if not specified)
            server: Default server to use (claude-flow, ruv-swarm, flow-nexus)
        """
        self.config = get_config()
        self.server = server
        self.timeout = timeout or self.config.get_timeout('swarm')
        self.log_dir = self.config.get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'mcp_client.jsonl'

    def _log(self, operation: str, params: Dict, result: Any, success: bool, elapsed: float):
        """Log MCP operation for debugging."""
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'server': self.server,
                'operation': operation,
                'params': params,
                'success': success,
                'elapsed_ms': round(elapsed * 1000, 2),
                'result_preview': str(result)[:200] if result else None
            }
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass  # Never fail on logging

    def _call_mcp(self, tool_name: str, params: Dict, timeout: Optional[float] = None) -> Optional[Dict]:
        """
        Call an MCP tool via subprocess.

        Args:
            tool_name: MCP tool name (without prefix)
            params: Tool parameters
            timeout: Optional override timeout

        Returns:
            Tool result dict or None on failure
        """
        if not self.config.is_server_enabled(self.server):
            return None

        prefix = self.config.get_server_prefix(self.server)
        full_tool = f"{prefix}{tool_name}"
        use_timeout = timeout or self.timeout

        start_time = time.time()
        try:
            # Build npx command for MCP tool invocation
            if self.server == 'claude-flow':
                cmd = ['npx', 'claude-flow@alpha', 'mcp', 'call', tool_name, json.dumps(params)]
            elif self.server == 'ruv-swarm':
                cmd = ['npx', 'ruv-swarm', 'mcp', 'call', tool_name, json.dumps(params)]
            else:
                # For flow-nexus, use direct CLI
                cmd = ['npx', 'flow-nexus@latest', 'mcp', 'call', tool_name, json.dumps(params)]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=use_timeout,
                cwd=str(Path.home())
            )

            elapsed = time.time() - start_time

            if result.returncode == 0 and result.stdout.strip():
                try:
                    parsed = json.loads(result.stdout.strip())
                    self._log(tool_name, params, parsed, True, elapsed)
                    return parsed
                except json.JSONDecodeError:
                    # Return raw output if not JSON
                    self._log(tool_name, params, result.stdout.strip(), True, elapsed)
                    return {'raw_output': result.stdout.strip()}
            else:
                self._log(tool_name, params, result.stderr, False, elapsed)
                return None

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            self._log(tool_name, params, 'TIMEOUT', False, elapsed)
            return None
        except Exception as e:
            elapsed = time.time() - start_time
            self._log(tool_name, params, str(e), False, elapsed)
            return None

    # =========================================================================
    # SWARM COORDINATION
    # =========================================================================

    def swarm_init(self, topology: str = 'adaptive', max_agents: int = 8,
                   strategy: str = 'balanced') -> Optional[Dict]:
        """
        Initialize a new swarm with specified topology.

        Args:
            topology: Swarm topology (hierarchical, mesh, ring, star, adaptive)
            max_agents: Maximum number of agents
            strategy: Distribution strategy (balanced, specialized, adaptive)

        Returns:
            Swarm initialization result with swarm_id
        """
        return self._call_mcp('swarm_init', {
            'topology': topology,
            'maxAgents': max_agents,
            'strategy': strategy
        })

    def swarm_status(self, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """Get current swarm status."""
        params = {}
        if swarm_id:
            params['swarmId'] = swarm_id
        return self._call_mcp('swarm_status', params)

    def swarm_scale(self, target_size: int, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """Scale swarm to target size."""
        params = {'targetSize': target_size}
        if swarm_id:
            params['swarmId'] = swarm_id
        return self._call_mcp('swarm_scale', params)

    def swarm_destroy(self, swarm_id: str) -> bool:
        """Gracefully destroy a swarm."""
        result = self._call_mcp('swarm_destroy', {'swarmId': swarm_id})
        return result is not None

    def swarm_monitor(self, swarm_id: Optional[str] = None, interval: int = 1) -> Optional[Dict]:
        """Monitor swarm activity."""
        params = {'interval': interval}
        if swarm_id:
            params['swarmId'] = swarm_id
        return self._call_mcp('swarm_monitor', params)

    # =========================================================================
    # AGENT MANAGEMENT
    # =========================================================================

    def agent_spawn(self, agent_type: str, capabilities: Optional[List[str]] = None,
                    name: Optional[str] = None, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """
        Spawn a new agent in the swarm.

        Args:
            agent_type: Agent type (researcher, coder, analyst, optimizer, coordinator)
            capabilities: Optional list of capabilities
            name: Optional custom name
            swarm_id: Optional swarm to join

        Returns:
            Agent spawn result with agent_id
        """
        params = {'type': agent_type}
        if capabilities:
            params['capabilities'] = capabilities
        if name:
            params['name'] = name
        if swarm_id:
            params['swarmId'] = swarm_id
        return self._call_mcp('agent_spawn', params)

    def agents_spawn_parallel(self, agents: List[Dict], max_concurrency: int = 5,
                              batch_size: int = 3) -> Optional[Dict]:
        """
        Spawn multiple agents in parallel (10-20x faster).

        Args:
            agents: List of agent configs [{type, name, capabilities, priority}]
            max_concurrency: Maximum concurrent spawns
            batch_size: Agents per batch

        Returns:
            Parallel spawn results
        """
        return self._call_mcp('agents_spawn_parallel', {
            'agents': agents,
            'maxConcurrency': max_concurrency,
            'batchSize': batch_size
        })

    def agent_list(self, swarm_id: Optional[str] = None, filter_status: str = 'all') -> Optional[List]:
        """List active agents."""
        params = {'filter': filter_status}
        if swarm_id:
            params['swarmId'] = swarm_id
        result = self._call_mcp('agent_list', params)
        return result.get('agents', []) if result else None

    def agent_metrics(self, agent_id: Optional[str] = None) -> Optional[Dict]:
        """Get agent performance metrics."""
        params = {}
        if agent_id:
            params['agentId'] = agent_id
        return self._call_mcp('agent_metrics', params)

    # =========================================================================
    # TASK ORCHESTRATION
    # =========================================================================

    def task_orchestrate(self, task: str, strategy: str = 'adaptive',
                         priority: str = 'medium', max_agents: Optional[int] = None) -> Optional[Dict]:
        """
        Orchestrate a task across the swarm.

        Args:
            task: Task description
            strategy: Execution strategy (parallel, sequential, adaptive)
            priority: Task priority (low, medium, high, critical)
            max_agents: Maximum agents to use

        Returns:
            Task orchestration result with task_id
        """
        params = {
            'task': task,
            'strategy': strategy,
            'priority': priority
        }
        if max_agents:
            params['maxAgents'] = max_agents
        return self._call_mcp('task_orchestrate', params)

    def task_status(self, task_id: str) -> Optional[Dict]:
        """Check task execution status."""
        return self._call_mcp('task_status', {'taskId': task_id})

    def task_results(self, task_id: str) -> Optional[Dict]:
        """Get task completion results."""
        return self._call_mcp('task_results', {'taskId': task_id})

    # =========================================================================
    # COORDINATION
    # =========================================================================

    def topology_optimize(self, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """Auto-optimize swarm topology."""
        params = {}
        if swarm_id:
            params['swarmId'] = swarm_id
        return self._call_mcp('topology_optimize', params)

    def load_balance(self, tasks: List[str], swarm_id: Optional[str] = None) -> Optional[Dict]:
        """Distribute tasks efficiently."""
        params = {'tasks': tasks}
        if swarm_id:
            params['swarmId'] = swarm_id
        return self._call_mcp('load_balance', params)

    def coordination_sync(self, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """Sync agent coordination."""
        params = {}
        if swarm_id:
            params['swarmId'] = swarm_id
        return self._call_mcp('coordination_sync', params)

    # =========================================================================
    # MEMORY OPERATIONS
    # =========================================================================

    def memory_store(self, key: str, value: Any, namespace: str = 'default',
                     ttl: Optional[int] = None) -> bool:
        """
        Store a value in persistent memory.

        Args:
            key: Memory key
            value: Value to store (will be JSON serialized)
            namespace: Memory namespace
            ttl: Optional TTL in seconds

        Returns:
            True if stored successfully
        """
        params = {
            'action': 'store',
            'key': key,
            'value': json.dumps(value) if not isinstance(value, str) else value,
            'namespace': namespace
        }
        if ttl:
            params['ttl'] = ttl
        result = self._call_mcp('memory_usage', params)
        return result is not None

    def memory_retrieve(self, key: str, namespace: str = 'default') -> Optional[Any]:
        """Retrieve a value from persistent memory."""
        result = self._call_mcp('memory_usage', {
            'action': 'retrieve',
            'key': key,
            'namespace': namespace
        })
        if result and 'value' in result:
            try:
                return json.loads(result['value'])
            except (json.JSONDecodeError, TypeError):
                return result['value']
        return None

    def memory_search(self, pattern: str, namespace: Optional[str] = None,
                      limit: int = 10) -> Optional[List]:
        """Search memory with pattern."""
        params = {'pattern': pattern, 'limit': limit}
        if namespace:
            params['namespace'] = namespace
        result = self._call_mcp('memory_search', params)
        return result.get('results', []) if result else None

    def memory_list(self, namespace: str = 'default') -> Optional[List]:
        """List all keys in namespace."""
        result = self._call_mcp('memory_usage', {
            'action': 'list',
            'namespace': namespace
        })
        return result.get('keys', []) if result else None

    def memory_delete(self, key: str, namespace: str = 'default') -> bool:
        """Delete a key from memory."""
        result = self._call_mcp('memory_usage', {
            'action': 'delete',
            'key': key,
            'namespace': namespace
        })
        return result is not None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def health_check(self, components: Optional[List[str]] = None) -> Optional[Dict]:
        """Check system health."""
        params = {}
        if components:
            params['components'] = components
        return self._call_mcp('health_check', params)

    def is_available(self) -> bool:
        """Check if MCP server is available."""
        try:
            result = self.health_check()
            return result is not None
        except Exception:
            return False

    def with_server(self, server: str) -> 'MCPClient':
        """Return a new client configured for a different server."""
        return MCPClient(timeout=self.timeout, server=server)


# Convenience functions for quick access
def get_mcp_client(server: str = 'claude-flow', timeout: Optional[float] = None) -> MCPClient:
    """Get an MCP client instance."""
    return MCPClient(timeout=timeout, server=server)


def get_claude_flow_client(timeout: Optional[float] = None) -> MCPClient:
    """Get a Claude Flow MCP client."""
    return MCPClient(timeout=timeout, server='claude-flow')


def get_ruv_swarm_client(timeout: Optional[float] = None) -> MCPClient:
    """Get a Ruv-Swarm MCP client."""
    return MCPClient(timeout=timeout, server='ruv-swarm')


def get_flow_nexus_client(timeout: Optional[float] = None) -> MCPClient:
    """Get a Flow-Nexus MCP client."""
    return MCPClient(timeout=timeout, server='flow-nexus')
