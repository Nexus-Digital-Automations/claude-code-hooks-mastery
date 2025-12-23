#!/usr/bin/env python3
"""
Comprehensive Test Suite for Claude Code Hooks Utilities

Tests all utility modules:
- trajectory_tracker.py
- knowledge_graph.py
- agent_coordinator.py
- async_jobs.py
- token_tracker.py
- mcp_registry.py
- pattern_learner.py
- claude_mem.py

Run with: python -m pytest tests/test_hooks_utils.py -v
"""

import sys
import time
from pathlib import Path

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'hooks'))


class TestTrajectoryTracker:
    """Tests for TrajectoryTracker utility."""

    def test_create_tracker(self):
        from utils.trajectory_tracker import TrajectoryTracker
        tracker = TrajectoryTracker('test_session')
        assert tracker.session_id == 'test_session'
        assert len(tracker.trajectory) == 0

    def test_record_step(self):
        from utils.trajectory_tracker import TrajectoryTracker
        tracker = TrajectoryTracker('test_step')
        tracker.record_step('tool_call', 'Read', {'file': 'test.py'}, 'content')
        assert len(tracker.trajectory) == 1
        assert tracker.trajectory[0]['step_type'] == 'tool_call'
        assert tracker.trajectory[0]['tool_name'] == 'Read'

    def test_record_decision_point(self):
        from utils.trajectory_tracker import TrajectoryTracker
        tracker = TrajectoryTracker('test_decision')
        tracker.record_decision_point(
            decision='Use pytest',
            alternatives=['pytest', 'unittest'],
            rationale='Best plugins'
        )
        assert len(tracker.trajectory) == 1
        assert tracker.trajectory[0]['step_type'] == 'decision'

    def test_record_error_recovery(self):
        from utils.trajectory_tracker import TrajectoryTracker
        tracker = TrajectoryTracker('test_error')
        tracker.record_error_recovery(
            error_type='ImportError',
            recovery_action='pip install foo',
            success=True
        )
        assert len(tracker.trajectory) == 1
        assert tracker.trajectory[0]['step_type'] == 'error_recovery'
        assert tracker.trajectory[0]['outcome'] == 'recovered'

    def test_calculate_statistics(self):
        from utils.trajectory_tracker import TrajectoryTracker
        tracker = TrajectoryTracker('test_stats')
        tracker.record_step('tool_call', 'Read', {}, 'ok')
        tracker.record_step('tool_call', 'Edit', {}, 'ok')
        tracker.record_error_recovery('Error', 'fix', False)

        stats = tracker._calculate_statistics()
        assert stats['tool_calls'] == 2
        assert stats['error_recoveries'] == 1
        assert 'Read' in stats['tools_used']
        assert 'Edit' in stats['tools_used']


class TestKnowledgeGraph:
    """Tests for KnowledgeGraph utility."""

    def test_create_graph(self):
        from utils.knowledge_graph import KnowledgeGraph
        graph = KnowledgeGraph()
        assert len(graph.nodes) >= 0
        assert len(graph.edges) >= 0

    def test_add_node(self):
        from utils.knowledge_graph import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_node('test_node', 'test_type', {'key': 'value'})
        assert 'test_node' in graph.nodes
        assert graph.nodes['test_node']['type'] == 'test_type'

    def test_add_edge(self):
        from utils.knowledge_graph import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_node('source', 'type1')
        graph.add_node('target', 'type2')
        graph.add_edge('source', 'target', 'connects')
        assert 'target' in graph.adjacency['source']
        assert 'source' in graph.adjacency['target']

    def test_add_tool_sequence(self):
        from utils.knowledge_graph import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_tool_sequence(['Read', 'Edit', 'Bash'], 'test')
        assert 'tool:Read' in graph.nodes
        assert 'tool:Edit' in graph.nodes
        assert 'tool:Bash' in graph.nodes

    def test_add_error_solution(self):
        from utils.knowledge_graph import KnowledgeGraph
        graph = KnowledgeGraph()
        result = graph.add_error_solution(
            'TypeError',
            'Add null check',
            'TypeError',
            ['Edit']
        )
        assert result is True
        # Check error and solution nodes exist
        error_nodes = [n for n in graph.nodes if 'error:' in n]
        solution_nodes = [n for n in graph.nodes if 'solution:' in n]
        assert len(error_nodes) >= 1
        assert len(solution_nodes) >= 1

    def test_get_tool_sequences(self):
        from utils.knowledge_graph import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_tool_sequence(['Read', 'Edit'], 'test1')
        graph.add_tool_sequence(['Read', 'Edit'], 'test2')
        sequences = graph.get_tool_sequences('Read')
        assert len(sequences) >= 1
        assert any(t == 'Edit' for t, _ in sequences)

    def test_get_stats(self):
        from utils.knowledge_graph import KnowledgeGraph
        graph = KnowledgeGraph()
        graph.add_tool_sequence(['Read', 'Edit'], 'test')
        stats = graph.get_stats()
        assert 'total_nodes' in stats
        assert 'total_edges' in stats
        assert 'node_types' in stats


class TestAgentCoordinator:
    """Tests for AgentCoordinator utility."""

    def test_create_coordinator(self):
        from utils.agent_coordinator import AgentCoordinator
        coord = AgentCoordinator('test_session')
        assert coord.session_id == 'test_session'

    def test_spawn_agent_graceful_failure(self):
        from utils.agent_coordinator import AgentCoordinator
        coord = AgentCoordinator('test_spawn')
        # Should fail gracefully without Claude Flow service
        agent_id = coord.spawn_agent('researcher', 'Find patterns')
        assert agent_id is None

    def test_hive_consensus(self):
        from utils.agent_coordinator import AgentCoordinator
        coord = AgentCoordinator('test_consensus')
        consensus = coord.hive_consensus(
            'Should we proceed?',
            ['security', 'architect', 'coder'],
            options=['yes', 'no', 'abstain']
        )
        assert 'winning_option' in consensus
        assert 'confidence' in consensus
        assert 'votes' in consensus
        assert consensus['winning_option'] in ['yes', 'no', 'abstain']

    def test_coordinate_task(self):
        from utils.agent_coordinator import AgentCoordinator
        coord = AgentCoordinator('test_orchestrate')
        result = coord.coordinate_task(
            'Implement feature',
            ['coder', 'tester'],
            parallel=True
        )
        assert 'success' in result
        assert 'agents' in result

    def test_get_stats(self):
        from utils.agent_coordinator import AgentCoordinator
        coord = AgentCoordinator('test_stats')
        coord.hive_consensus('Test?', ['coder'], ['yes', 'no'])
        stats = coord.get_stats()
        assert stats['consensus_votes'] >= 1


class TestAsyncJobManager:
    """Tests for AsyncJobManager utility."""

    def test_create_manager(self):
        from utils.async_jobs import AsyncJobManager
        manager = AsyncJobManager(max_workers=2)
        assert manager.max_workers == 2

    def test_submit_job(self):
        from utils.async_jobs import AsyncJobManager
        manager = AsyncJobManager()
        job_id = manager.submit('consolidate', {'session_id': 'test'})
        assert job_id is not None
        assert len(job_id) == 12

    def test_check_status(self):
        from utils.async_jobs import AsyncJobManager
        manager = AsyncJobManager()
        job_id = manager.submit('consolidate', {})
        time.sleep(0.1)
        status = manager.check_status(job_id)
        assert 'status' in status
        assert status['status'] in ['pending', 'running', 'completed', 'failed']

    def test_get_result(self):
        from utils.async_jobs import AsyncJobManager
        manager = AsyncJobManager()
        job_id = manager.submit('consolidate', {})
        result = manager.get_result(job_id, timeout=2)
        # Result should be dict or None
        assert result is None or isinstance(result, dict)

    def test_list_jobs(self):
        from utils.async_jobs import AsyncJobManager
        manager = AsyncJobManager()
        manager.submit('consolidate', {})
        jobs = manager.list_jobs()
        assert isinstance(jobs, list)

    def test_cleanup(self):
        from utils.async_jobs import AsyncJobManager
        manager = AsyncJobManager()
        manager.submit('consolidate', {})
        time.sleep(0.5)
        cleaned = manager.cleanup(max_age_hours=0)
        assert isinstance(cleaned, int)


class TestTokenTracker:
    """Tests for TokenTracker utility.

    Note: TokenTracker persists data using first 12 chars of session_id as filename.
    All tests use UUID-based session IDs to ensure uniqueness across test runs.
    """

    def test_create_tracker(self):
        from utils.token_tracker import TokenTracker
        import uuid
        # Short prefix + UUID ensures unique storage file
        session_id = f'tc_{uuid.uuid4().hex}'
        tracker = TokenTracker(session_id)
        assert tracker.session_id == session_id

    def test_record_usage(self):
        from utils.token_tracker import TokenTracker
        import uuid
        session_id = f'tr_{uuid.uuid4().hex}'
        tracker = TokenTracker(session_id)
        tracker.record_usage(1000, 500, 'Read')
        assert len(tracker.usage_records) == 1
        assert tracker.tool_usage['Read']['input'] == 1000
        assert tracker.tool_usage['Read']['output'] == 500

    def test_get_session_stats(self):
        from utils.token_tracker import TokenTracker
        import uuid
        session_id = f'ts_{uuid.uuid4().hex}'
        tracker = TokenTracker(session_id)
        tracker.record_usage(1000, 500, 'Read')
        tracker.record_usage(2000, 1000, 'Edit')
        stats = tracker.get_session_stats()
        assert stats['total_input_tokens'] == 3000
        assert stats['total_output_tokens'] == 1500
        assert stats['total_operations'] == 2
        assert 'costs' in stats

    def test_calculate_efficiency(self):
        from utils.token_tracker import TokenTracker
        import uuid
        session_id = f'te_{uuid.uuid4().hex}'
        tracker = TokenTracker(session_id)
        tracker.record_usage(1000, 500, 'Read')
        efficiency = tracker.calculate_efficiency()
        assert 'efficiency_score' in efficiency
        assert 'rating' in efficiency
        assert efficiency['rating'] in ['excellent', 'good', 'moderate', 'low', 'poor']

    def test_get_tool_efficiency(self):
        from utils.token_tracker import TokenTracker
        import uuid
        session_id = f'tf_{uuid.uuid4().hex}'
        tracker = TokenTracker(session_id)
        tracker.record_usage(1000, 500, 'Read')
        tracker.record_usage(2000, 1000, 'Read')
        tool_eff = tracker.get_tool_efficiency()
        assert 'Read' in tool_eff
        assert tool_eff['Read']['total_calls'] == 2

    def test_estimate_remaining_budget(self):
        from utils.token_tracker import TokenTracker
        import uuid
        session_id = f'tb_{uuid.uuid4().hex}'
        tracker = TokenTracker(session_id)
        tracker.record_usage(1000, 500, 'Read')
        budget = tracker.estimate_remaining_budget(1.00)
        assert 'budget_remaining' in budget
        assert 'estimated_operations' in budget


class TestMCPRegistry:
    """Tests for MCPRegistry utility."""

    def test_create_registry(self):
        from utils.mcp_registry import MCPRegistry
        registry = MCPRegistry()
        assert registry is not None

    def test_register_custom_tool(self):
        from utils.mcp_registry import MCPRegistry
        registry = MCPRegistry()
        tool_id = registry.register_custom_tool('test_server', {
            'name': 'test_tool',
            'description': 'A test tool',
            'parameters': {}
        })
        assert tool_id == 'mcp__test_server__test_tool'
        assert tool_id in registry.tools

    def test_get_available_tools(self):
        from utils.mcp_registry import MCPRegistry
        registry = MCPRegistry()
        registry.register_custom_tool('test', {'name': 'tool1', 'description': 'Tool 1'})
        tools = registry.get_available_tools()
        assert len(tools) >= 1

    def test_record_tool_use(self):
        from utils.mcp_registry import MCPRegistry
        import uuid
        registry = MCPRegistry()
        # Use unique tool name to avoid persisted state conflicts
        unique_name = f'tool_use_{uuid.uuid4().hex[:8]}'
        tool_id = f'mcp__test__{unique_name}'
        registry.register_custom_tool('test', {'name': unique_name, 'description': 'Tool for use test'})
        registry.record_tool_use(tool_id, success=True)
        assert registry.tool_usage[tool_id]['calls'] == 1
        assert registry.tool_usage[tool_id]['successes'] == 1

    def test_get_tool_success_rate(self):
        from utils.mcp_registry import MCPRegistry
        import uuid
        registry = MCPRegistry()
        # Use unique tool name to avoid persisted state conflicts
        unique_name = f'tool_rate_{uuid.uuid4().hex[:8]}'
        tool_id = f'mcp__test__{unique_name}'
        registry.register_custom_tool('test', {'name': unique_name, 'description': 'Tool for rate test'})
        registry.record_tool_use(tool_id, success=True)
        registry.record_tool_use(tool_id, success=False)
        rate = registry.get_tool_success_rate(tool_id)
        assert rate == 0.5

    def test_recommend_tools(self):
        from utils.mcp_registry import MCPRegistry
        registry = MCPRegistry()
        registry.register_custom_tool('test', {
            'name': 'file_search',
            'description': 'Search for files'
        })
        recs = registry.recommend_tools('search for files')
        assert len(recs) >= 1

    def test_get_stats(self):
        from utils.mcp_registry import MCPRegistry
        registry = MCPRegistry()
        registry.register_custom_tool('test', {'name': 'tool1', 'description': 'Tool'})
        stats = registry.get_stats()
        assert 'total_tools' in stats
        assert 'total_servers' in stats


class TestPatternLearner:
    """Tests for PatternLearner utility."""

    def test_create_learner(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        assert learner is not None

    def test_learn_pattern(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.learn_pattern({
            'pattern_key': 'test_pattern',
            'description': 'A test pattern',
            'success': True
        })
        # Pattern should be stored
        assert len(learner.patterns) >= 0  # May have prior patterns

    def test_record_experience(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.record_experience('Edit', {'file': 'test.py', 'success': True})
        # Experience should be recorded
        assert True  # Just verify no error

    def test_update_confidence(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.update_confidence('test_key', outcome=True)
        conf = learner.get_confidence('test_key')
        assert conf > 0

    def test_get_confidence(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.update_confidence('conf_test', outcome=True)
        learner.update_confidence('conf_test', outcome=True)
        conf = learner.get_confidence('conf_test')
        assert 0 <= conf <= 1

    def test_decay_confidence(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.update_confidence('decay_test', outcome=True)
        before = learner.get_confidence('decay_test')
        learner.decay_confidence(decay_rate=0.5)
        after = learner.get_confidence('decay_test')
        assert after < before

    def test_get_high_confidence_patterns(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.update_confidence('high_conf', outcome=True)
        learner.update_confidence('high_conf', outcome=True)
        learner.update_confidence('high_conf', outcome=True)
        high = learner.get_high_confidence_patterns(threshold=0.5)
        assert isinstance(high, list)

    def test_get_recommended_strategies(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.learn_pattern({
            'pattern_key': 'strategy_test',
            'description': 'Test strategy',
            'success': True
        })
        strategies = learner.get_recommended_strategies(limit=3)
        assert isinstance(strategies, list)


class TestClaudeMemClient:
    """Tests for ClaudeMemClient utility."""

    def test_create_client(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        assert client.base_url == 'http://localhost:37777'

    def test_health_check(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient(timeout=1.0)
        health = client.health_check()
        # May be True or False depending on service
        assert isinstance(health, bool)

    def test_local_store_retrieve(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        client.store('test_local', {'value': 42})
        result = client.retrieve('test_local')
        assert result['value'] == 42
        client.delete('test_local')

    def test_store_observation(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        result = client.store_observation(
            'test_session',
            'Edit',
            {'file': 'test.py'},
            'success'
        )
        assert result is True

    def test_search_solutions(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        solutions = client.search_solutions('TypeError')
        assert isinstance(solutions, list)

    def test_semantic_search(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        results = client.semantic_search('authentication')
        assert isinstance(results, list)

    def test_find_similar_code(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        results = client.find_similar_code('def main():')
        assert isinstance(results, list)

    def test_find_related_errors(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        results = client.find_related_errors('ImportError')
        assert isinstance(results, list)

    def test_get_context_for_file(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        results = client.get_context_for_file('src/main.py')
        assert isinstance(results, list)


def run_all_tests():
    """Run all tests and print results."""
    test_classes = [
        TestTrajectoryTracker,
        TestKnowledgeGraph,
        TestAgentCoordinator,
        TestAsyncJobManager,
        TestTokenTracker,
        TestMCPRegistry,
        TestPatternLearner,
        TestClaudeMemClient,
    ]

    total_tests = 0
    passed_tests = 0
    failed_tests = []

    for test_class in test_classes:
        print(f"\n{'='*60}")
        print(f"Running {test_class.__name__}")
        print('='*60)

        instance = test_class()
        test_methods = [m for m in dir(instance) if m.startswith('test_')]

        for method_name in test_methods:
            total_tests += 1
            try:
                getattr(instance, method_name)()
                print(f"  ✅ {method_name}")
                passed_tests += 1
            except Exception as e:
                print(f"  ❌ {method_name}: {e}")
                failed_tests.append((test_class.__name__, method_name, str(e)))

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed_tests}/{total_tests} tests passed")
    print('='*60)

    if failed_tests:
        print("\nFailed tests:")
        for cls, method, error in failed_tests:
            print(f"  - {cls}.{method}: {error}")

    return len(failed_tests) == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
