"""
Swarm coordination client for multi-agent orchestration.
Supports Claude-Flow, Ruv-Swarm, and DAA (Decentralized Autonomous Agents).
"""

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import time

try:
    from .config_loader import get_config
except ImportError:
    from config_loader import get_config


class SwarmClient:
    """
    Client for swarm coordination and multi-agent orchestration.

    Supports:
    - Swarm lifecycle management
    - Agent spawning and coordination
    - Topology optimization
    - DAA (Decentralized Autonomous Agents) operations
    - Ruv-Swarm advanced features
    """

    def __init__(self, timeout: Optional[float] = None, prefer_ruv_swarm: bool = False):
        """
        Initialize swarm client.

        Args:
            timeout: Operation timeout in seconds
            prefer_ruv_swarm: Prefer ruv-swarm over claude-flow when available
        """
        self.config = get_config()
        self.timeout = timeout or self.config.get_timeout('swarm')
        self.prefer_ruv_swarm = prefer_ruv_swarm
        self.active_swarm_id: Optional[str] = None
        self.log_dir = self.config.get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'swarm_client.jsonl'

    def _log(self, operation: str, params: Dict, result: Any, success: bool, elapsed: float):
        """Log swarm operation."""
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'operation': operation,
                'swarm_id': self.active_swarm_id,
                'params': {k: str(v)[:100] for k, v in params.items()},
                'success': success,
                'elapsed_ms': round(elapsed * 1000, 2)
            }
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

    def _get_server(self) -> str:
        """Determine which server to use."""
        if self.prefer_ruv_swarm and self.config.is_server_enabled('ruv-swarm'):
            return 'ruv-swarm'
        return 'claude-flow'

    def _call_tool(self, tool_name: str, params: Dict, server: Optional[str] = None,
                   timeout: Optional[float] = None) -> Optional[Dict]:
        """Call MCP tool via subprocess."""
        if not self.config.is_feature_enabled('swarm'):
            return None

        use_server = server or self._get_server()
        use_timeout = timeout or self.timeout

        start_time = time.time()
        try:
            if use_server == 'ruv-swarm':
                cmd = ['npx', 'ruv-swarm', 'mcp', 'call', tool_name, json.dumps(params)]
            else:
                cmd = ['npx', 'claude-flow@alpha', 'mcp', 'call', tool_name, json.dumps(params)]

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
    # SWARM LIFECYCLE
    # =========================================================================

    def init_swarm(self, topology: str = 'adaptive', max_agents: int = 8,
                   strategy: str = 'balanced') -> Optional[Dict]:
        """
        Initialize a new swarm.

        Args:
            topology: Swarm topology (hierarchical, mesh, ring, star, adaptive)
            max_agents: Maximum number of agents
            strategy: Distribution strategy (balanced, specialized, adaptive)

        Returns:
            Swarm init result with swarm_id
        """
        result = self._call_tool('swarm_init', {
            'topology': topology,
            'maxAgents': max_agents,
            'strategy': strategy
        })
        if result and 'swarm_id' in result:
            self.active_swarm_id = result['swarm_id']
        return result

    def destroy_swarm(self, swarm_id: Optional[str] = None) -> bool:
        """
        Gracefully destroy a swarm.

        Args:
            swarm_id: Swarm ID (uses active if not specified)

        Returns:
            True if destroyed successfully
        """
        sid = swarm_id or self.active_swarm_id
        if not sid:
            return False
        result = self._call_tool('swarm_destroy', {'swarmId': sid})
        if result and sid == self.active_swarm_id:
            self.active_swarm_id = None
        return result is not None

    def scale_swarm(self, target_size: int, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """
        Scale swarm to target agent count.

        Args:
            target_size: Target number of agents
            swarm_id: Swarm ID

        Returns:
            Scale result
        """
        params = {'targetSize': target_size}
        if swarm_id or self.active_swarm_id:
            params['swarmId'] = swarm_id or self.active_swarm_id
        return self._call_tool('swarm_scale', params)

    def swarm_status(self, swarm_id: Optional[str] = None, verbose: bool = False) -> Optional[Dict]:
        """
        Get swarm status.

        Args:
            swarm_id: Swarm ID
            verbose: Include detailed agent info

        Returns:
            Swarm status
        """
        params = {'verbose': verbose}
        if swarm_id or self.active_swarm_id:
            params['swarmId'] = swarm_id or self.active_swarm_id
        return self._call_tool('swarm_status', params)

    def swarm_monitor(self, swarm_id: Optional[str] = None, interval: int = 1,
                      duration: int = 10) -> Optional[Dict]:
        """
        Monitor swarm activity in real-time.

        Args:
            swarm_id: Swarm ID
            interval: Update interval in seconds
            duration: Monitoring duration

        Returns:
            Monitoring results
        """
        params = {'interval': interval, 'duration': duration}
        if swarm_id or self.active_swarm_id:
            params['swarmId'] = swarm_id or self.active_swarm_id
        return self._call_tool('swarm_monitor', params)

    # =========================================================================
    # AGENT MANAGEMENT
    # =========================================================================

    def spawn_agent(self, agent_type: str, capabilities: Optional[List[str]] = None,
                    name: Optional[str] = None) -> Optional[Dict]:
        """
        Spawn a new agent.

        Args:
            agent_type: Agent type (researcher, coder, analyst, optimizer, coordinator)
            capabilities: Agent capabilities
            name: Custom agent name

        Returns:
            Agent spawn result with agent_id
        """
        params = {'type': agent_type}
        if capabilities:
            params['capabilities'] = capabilities
        if name:
            params['name'] = name
        if self.active_swarm_id:
            params['swarmId'] = self.active_swarm_id
        return self._call_tool('agent_spawn', params)

    def spawn_agents_parallel(self, agents: List[Dict], max_concurrency: int = 5,
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
        return self._call_tool('agents_spawn_parallel', {
            'agents': agents,
            'maxConcurrency': max_concurrency,
            'batchSize': batch_size
        }, server='claude-flow')

    def list_agents(self, swarm_id: Optional[str] = None,
                    filter_status: str = 'all') -> Optional[List]:
        """
        List agents in swarm.

        Args:
            swarm_id: Swarm ID
            filter_status: Status filter (all, active, idle, busy)

        Returns:
            List of agents
        """
        params = {'filter': filter_status}
        if swarm_id or self.active_swarm_id:
            params['swarmId'] = swarm_id or self.active_swarm_id
        result = self._call_tool('agent_list', params)
        return result.get('agents', []) if result else None

    def get_agent_metrics(self, agent_id: Optional[str] = None,
                          metric: str = 'all') -> Optional[Dict]:
        """
        Get agent performance metrics.

        Args:
            agent_id: Specific agent ID
            metric: Metric type (all, cpu, memory, tasks, performance)

        Returns:
            Agent metrics
        """
        params = {'metric': metric}
        if agent_id:
            params['agentId'] = agent_id
        return self._call_tool('agent_metrics', params)

    # =========================================================================
    # COORDINATION
    # =========================================================================

    def topology_optimize(self, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """
        Auto-optimize swarm topology.

        Args:
            swarm_id: Swarm ID

        Returns:
            Optimization result
        """
        params = {}
        if swarm_id or self.active_swarm_id:
            params['swarmId'] = swarm_id or self.active_swarm_id
        return self._call_tool('topology_optimize', params)

    def load_balance(self, tasks: List[str], swarm_id: Optional[str] = None) -> Optional[Dict]:
        """
        Distribute tasks efficiently across agents.

        Args:
            tasks: Tasks to distribute
            swarm_id: Swarm ID

        Returns:
            Load balance result
        """
        params = {'tasks': tasks}
        if swarm_id or self.active_swarm_id:
            params['swarmId'] = swarm_id or self.active_swarm_id
        return self._call_tool('load_balance', params)

    def coordination_sync(self, swarm_id: Optional[str] = None) -> Optional[Dict]:
        """
        Sync agent coordination state.

        Args:
            swarm_id: Swarm ID

        Returns:
            Sync result
        """
        params = {}
        if swarm_id or self.active_swarm_id:
            params['swarmId'] = swarm_id or self.active_swarm_id
        return self._call_tool('coordination_sync', params)

    # =========================================================================
    # DAA (Decentralized Autonomous Agents)
    # =========================================================================

    def daa_init(self, enable_coordination: bool = True, enable_learning: bool = True,
                 persistence_mode: str = 'auto') -> Optional[Dict]:
        """
        Initialize DAA service (Ruv-Swarm).

        Args:
            enable_coordination: Enable peer coordination
            enable_learning: Enable autonomous learning
            persistence_mode: Persistence mode (auto, memory, disk)

        Returns:
            DAA init result
        """
        return self._call_tool('daa_init', {
            'enableCoordination': enable_coordination,
            'enableLearning': enable_learning,
            'persistenceMode': persistence_mode
        }, server='ruv-swarm')

    def daa_agent_create(self, agent_type: str, capabilities: Optional[List[str]] = None,
                         cognitive_pattern: str = 'adaptive', learning_rate: float = 0.1,
                         enable_memory: bool = True) -> Optional[Dict]:
        """
        Create a DAA agent with autonomous capabilities.

        Args:
            agent_type: Agent type
            capabilities: Agent capabilities
            cognitive_pattern: Thinking pattern (convergent, divergent, lateral, systems, critical, adaptive)
            learning_rate: Learning rate (0-1)
            enable_memory: Enable persistent memory

        Returns:
            DAA agent creation result
        """
        params = {
            'agent_type': agent_type,
            'cognitivePattern': cognitive_pattern,
            'learningRate': learning_rate,
            'enableMemory': enable_memory
        }
        if capabilities:
            params['capabilities'] = capabilities
        return self._call_tool('daa_agent_create', params)

    def daa_capability_match(self, task_requirements: List[str],
                             available_agents: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Match capabilities to tasks.

        Args:
            task_requirements: Required capabilities
            available_agents: Optional list of agent IDs

        Returns:
            Capability match results
        """
        params = {'task_requirements': task_requirements}
        if available_agents:
            params['available_agents'] = available_agents
        return self._call_tool('daa_capability_match', params)

    def daa_consensus(self, agents: List[str], proposal: Dict) -> Optional[Dict]:
        """
        Run consensus mechanism across agents.

        Args:
            agents: Agent IDs to participate
            proposal: Proposal to vote on

        Returns:
            Consensus result
        """
        return self._call_tool('daa_consensus', {
            'agents': agents,
            'proposal': proposal
        })

    def daa_communication(self, from_agent: str, to_agents: List[str],
                          message: Dict) -> Optional[Dict]:
        """
        Inter-agent communication.

        Args:
            from_agent: Source agent ID
            to_agents: Target agent IDs
            message: Message object

        Returns:
            Communication result
        """
        return self._call_tool('daa_communication', {
            'from': from_agent,
            'to': ','.join(to_agents) if isinstance(to_agents, list) else to_agents,
            'message': message
        })

    def daa_fault_tolerance(self, agent_id: str, strategy: str = 'retry') -> Optional[Dict]:
        """
        Handle agent fault tolerance.

        Args:
            agent_id: Agent ID
            strategy: Recovery strategy

        Returns:
            Fault tolerance result
        """
        return self._call_tool('daa_fault_tolerance', {
            'agentId': agent_id,
            'strategy': strategy
        })

    def daa_knowledge_share(self, source_agent: str, target_agents: List[str],
                            knowledge_domain: str, knowledge_content: Dict) -> Optional[Dict]:
        """
        Share knowledge between agents (Ruv-Swarm).

        Args:
            source_agent: Source agent ID
            target_agents: Target agent IDs
            knowledge_domain: Knowledge domain
            knowledge_content: Knowledge to share

        Returns:
            Knowledge sharing result
        """
        return self._call_tool('daa_knowledge_share', {
            'sourceAgentId': source_agent,
            'targetAgentIds': target_agents,
            'knowledgeDomain': knowledge_domain,
            'knowledgeContent': knowledge_content
        }, server='ruv-swarm')

    def daa_agent_adapt(self, agent_id: str, feedback: str,
                        performance_score: float, suggestions: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Trigger agent adaptation based on feedback (Ruv-Swarm).

        Args:
            agent_id: Agent ID
            feedback: Feedback message
            performance_score: Performance score (0-1)
            suggestions: Improvement suggestions

        Returns:
            Adaptation result
        """
        params = {
            'agentId': agent_id,
            'feedback': feedback,
            'performanceScore': performance_score
        }
        if suggestions:
            params['suggestions'] = suggestions
        return self._call_tool('daa_agent_adapt', params, server='ruv-swarm')

    def daa_cognitive_pattern(self, agent_id: str, action: str = 'analyze',
                              pattern: Optional[str] = None) -> Optional[Dict]:
        """
        Analyze or change agent cognitive pattern (Ruv-Swarm).

        Args:
            agent_id: Agent ID
            action: Action (analyze, change)
            pattern: New pattern for change action

        Returns:
            Cognitive pattern result
        """
        params = {'agentId': agent_id, 'action': action}
        if pattern:
            params['pattern'] = pattern
        return self._call_tool('daa_cognitive_pattern', params, server='ruv-swarm')

    def daa_meta_learning(self, source_domain: str, target_domain: str,
                          transfer_mode: str = 'adaptive',
                          agent_ids: Optional[List[str]] = None) -> Optional[Dict]:
        """
        Enable meta-learning across domains (Ruv-Swarm).

        Args:
            source_domain: Source knowledge domain
            target_domain: Target knowledge domain
            transfer_mode: Transfer mode (adaptive, direct, gradual)
            agent_ids: Specific agents to update

        Returns:
            Meta-learning result
        """
        params = {
            'sourceDomain': source_domain,
            'targetDomain': target_domain,
            'transferMode': transfer_mode
        }
        if agent_ids:
            params['agentIds'] = agent_ids
        return self._call_tool('daa_meta_learning', params, server='ruv-swarm')

    def daa_performance_metrics(self, category: str = 'all',
                                time_range: str = '24h') -> Optional[Dict]:
        """
        Get DAA performance metrics (Ruv-Swarm).

        Args:
            category: Metrics category (all, system, performance, efficiency, neural)
            time_range: Time range (1h, 24h, 7d)

        Returns:
            Performance metrics
        """
        return self._call_tool('daa_performance_metrics', {
            'category': category,
            'timeRange': time_range
        }, server='ruv-swarm')

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def is_available(self) -> bool:
        """Check if swarm services are available."""
        try:
            result = self.swarm_status()
            return result is not None
        except Exception:
            return False

    def get_active_swarm_id(self) -> Optional[str]:
        """Get the currently active swarm ID."""
        return self.active_swarm_id

    def set_active_swarm(self, swarm_id: str):
        """Set the active swarm ID."""
        self.active_swarm_id = swarm_id


# Convenience function
def get_swarm_client(timeout: Optional[float] = None, prefer_ruv_swarm: bool = False) -> SwarmClient:
    """Get a swarm client instance."""
    return SwarmClient(timeout=timeout, prefer_ruv_swarm=prefer_ruv_swarm)
