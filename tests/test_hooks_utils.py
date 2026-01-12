#!/usr/bin/env python3
"""
Test Suite for Claude Code Hooks Utilities

Tests utility modules that actually exist:
- claude_flow.py - ReasoningBank integration
- claude_mem.py - Memory service client
- pattern_learner.py - EMA confidence scoring

Run with: python -m pytest tests/test_hooks_utils.py -v
"""

import sys
from pathlib import Path

# Add hooks directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'hooks'))


class TestClaudeFlowClient:
    """Tests for ClaudeFlowClient utility."""

    def test_create_client(self):
        from utils.claude_flow import ClaudeFlowClient
        client = ClaudeFlowClient()
        assert client.timeout == 10.0
        assert client.cli_prefix == ["npx", "claude-flow@alpha"]

    def test_create_client_custom_timeout(self):
        from utils.claude_flow import ClaudeFlowClient
        client = ClaudeFlowClient(timeout=5.0)
        assert client.timeout == 5.0

    def test_is_reasoningbank_available(self):
        from utils.claude_flow import ClaudeFlowClient
        client = ClaudeFlowClient()
        # Should return bool (True if DB exists or can init, False otherwise)
        result = client.is_reasoningbank_available()
        assert isinstance(result, bool)

    def test_memory_stats_returns_dict_or_none(self):
        from utils.claude_flow import ClaudeFlowClient
        client = ClaudeFlowClient()
        result = client.memory_stats()
        assert result is None or isinstance(result, dict)

    def test_memory_query_returns_string_or_none(self):
        from utils.claude_flow import ClaudeFlowClient
        client = ClaudeFlowClient()
        result = client.memory_query("test query")
        assert result is None or isinstance(result, str)

    def test_memory_store_returns_bool(self):
        from utils.claude_flow import ClaudeFlowClient
        client = ClaudeFlowClient()
        result = client.memory_store("test_key", {"test": "value"})
        assert isinstance(result, bool)


class TestClaudeFlowConvenienceFunctions:
    """Tests for Claude Flow convenience functions."""

    def test_query_reasoning_patterns(self):
        from utils.claude_flow import query_reasoning_patterns
        result = query_reasoning_patterns("test query")
        assert result is None or isinstance(result, str)

    def test_store_session_learning(self):
        from utils.claude_flow import store_session_learning
        result = store_session_learning("test_session", {"learned": "something"})
        assert isinstance(result, bool)

    def test_memory_search(self):
        from utils.claude_flow import memory_search
        result = memory_search("test pattern")
        assert result is None or isinstance(result, str)

    def test_get_tool_patterns(self):
        from utils.claude_flow import get_tool_patterns
        result = get_tool_patterns("Read")
        assert result is None or isinstance(result, str)


class TestPatternLearner:
    """Tests for PatternLearner utility."""

    def test_create_learner(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        assert learner is not None

    def test_learn_pattern(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.learn_pattern({'key': 'test', 'context': 'test context'})
        # Should not raise

    def test_get_confidence(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.learn_pattern({'key': 'test_conf', 'context': 'test'})
        conf = learner.get_confidence('test_conf')
        assert conf >= 0.0 and conf <= 1.0

    def test_update_confidence(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        learner.learn_pattern({'key': 'test_update', 'context': 'test'})
        old_conf = learner.get_confidence('test_update')
        # update_confidence takes (pattern_key, outcome) where outcome is 'success' or 'failure'
        learner.update_confidence('test_update', 'success')
        new_conf = learner.get_confidence('test_update')
        assert new_conf >= old_conf  # Success should increase or maintain confidence

    def test_get_recommended_strategies(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        strategies = learner.get_recommended_strategies(limit=3)
        assert isinstance(strategies, list)

    def test_get_high_confidence_patterns(self):
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        patterns = learner.get_high_confidence_patterns(threshold=0.5)
        assert isinstance(patterns, list)


class TestClaudeMemClient:
    """Tests for ClaudeMemClient utility."""

    def test_create_client(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        assert client is not None
        assert client.base_url == "http://localhost:37777"

    def test_health_check(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        # May return True (service running) or False (not running)
        result = client.health_check()
        assert isinstance(result, bool)

    def test_store_locally(self):
        from utils.claude_mem import ClaudeMemClient
        import uuid
        client = ClaudeMemClient()
        key = f"test_{uuid.uuid4().hex[:8]}"
        client._store_local(key, {"test": "data"})
        result = client._retrieve_local(key, default=None)
        assert result is not None
        assert result.get("test") == "data"

    def test_store_observation(self):
        from utils.claude_mem import ClaudeMemClient
        import uuid
        client = ClaudeMemClient()
        session_id = f"test_{uuid.uuid4().hex[:8]}"
        # Should not raise, graceful degradation
        client.store_observation(session_id, "Read", {"file": "test.py"}, "content")

    def test_search_solutions(self):
        from utils.claude_mem import ClaudeMemClient
        client = ClaudeMemClient()
        # Should return list (possibly empty)
        results = client.search_solutions("authentication", limit=3)
        assert isinstance(results, list)


class TestLoadRecentContext:
    """Tests for context loading functions."""

    def test_load_recent_context(self):
        from utils.claude_mem import load_recent_context
        # Should return string (possibly empty) or None
        result = load_recent_context()
        assert result is None or isinstance(result, str)

    def test_get_patterns_for_tool(self):
        from utils.claude_mem import get_patterns_for_tool
        result = get_patterns_for_tool("Read")
        assert result is None or isinstance(result, list)
