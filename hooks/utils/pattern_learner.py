#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Pattern Learning System for Claude Code Prompt Hooks

This module tracks user responses to guidance over time and learns which
warnings to suppress based on user behavior. It implements intelligent
noise reduction while preserving critical security warnings.

Key Features:
- Pattern tracking (shown_count, ignored_count, acted_on_count)
- Context-specific learning (node_modules vs dist vs source files)
- Suppression score calculation with exponential dampening
- Critical warnings never suppressed (rm -rf /, rm -rf ~, etc.)
- Persistence across sessions via JSON storage

Research: Arize AI found 5-11% performance improvements through pattern learning.
"""

import json
import random
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class PatternLearner:
    """Tracks and learns from user responses to guidance over time."""

    def __init__(self, storage_path: Path = None):
        """
        Initialize the pattern learner.

        Args:
            storage_path: Path to prompt_patterns.json storage file
        """
        self.storage_path = storage_path or Path('.claude/data/prompt_patterns.json')
        self.patterns = self._load_patterns()

    def _load_patterns(self) -> Dict[str, Any]:
        """Load pattern data from storage."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass

        # Initialize empty pattern storage
        return {}

    def _save_patterns(self):
        """Save pattern data to storage."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.storage_path, 'w') as f:
                json.dump(self.patterns, f, indent=2)
        except Exception:
            # Fail silently - don't break hooks
            pass

    def should_suppress(self, category: str, context: Dict[str, Any]) -> bool:
        """
        Determine if guidance should be suppressed based on patterns.

        Args:
            category: Guidance category (rm_warnings, file_location_warnings, etc.)
            context: Current context (for critical warning detection)

        Returns:
            True if guidance should be suppressed, False otherwise
        """
        # CRITICAL: Never suppress critical warnings
        if self._is_critical_warning(category, context):
            return False

        # Get pattern data
        pattern = self.patterns.get(category)
        if not pattern:
            # No history - don't suppress
            return False

        # Check if we have enough samples
        shown_count = pattern.get('shown_count', 0)
        if shown_count < 3:  # Minimum samples before suppression
            return False

        # Get suppression score
        suppression_score = pattern.get('suppression_score', 0.0)

        # High suppression (>0.7) - only show occasionally
        if suppression_score > 0.7:
            # Show only 20% of the time
            return random.random() > 0.2

        # Medium suppression (>0.4) - show 50% of the time
        if suppression_score > 0.4:
            return random.random() > 0.5

        # Low suppression - show normally
        return False

    def record_shown(self, category: str, context: Dict[str, Any]):
        """
        Record that guidance was shown to the user.

        Args:
            category: Guidance category
            context: Current context (for context-specific tracking)
        """
        # Initialize category if not exists
        if category not in self.patterns:
            self.patterns[category] = {
                'shown_count': 0,
                'ignored_count': 0,
                'acted_on_count': 0,
                'last_shown': None,
                'suppression_score': 0.0,
                'context_specific': {}
            }

        pattern = self.patterns[category]

        # Increment shown count
        pattern['shown_count'] += 1
        pattern['last_shown'] = datetime.now().isoformat()

        # Context-specific tracking
        ctx_key = self._extract_context_key(context)
        if ctx_key:
            if ctx_key not in pattern['context_specific']:
                pattern['context_specific'][ctx_key] = {'ignored': 0, 'acted': 0}

        self._save_patterns()

    def record_response(self, category: str, response: str, context: Dict[str, Any] = None):
        """
        Record user response to guidance (ignored or acted upon).

        Args:
            category: Guidance category
            response: 'ignored' or 'acted_on'
            context: Optional context for context-specific tracking
        """
        if category not in self.patterns:
            return

        pattern = self.patterns[category]

        # Update counts
        if response == 'ignored':
            pattern['ignored_count'] += 1
        elif response == 'acted_on':
            pattern['acted_on_count'] += 1

        # Update context-specific tracking
        if context:
            ctx_key = self._extract_context_key(context)
            if ctx_key and ctx_key in pattern['context_specific']:
                if response == 'ignored':
                    pattern['context_specific'][ctx_key]['ignored'] += 1
                elif response == 'acted_on':
                    pattern['context_specific'][ctx_key]['acted'] += 1

        # Recalculate suppression score
        pattern['suppression_score'] = self._calculate_suppression_score(pattern)

        self._save_patterns()

    def _calculate_suppression_score(self, pattern: Dict[str, Any]) -> float:
        """
        Calculate suppression score (0.0 = never suppress, 1.0 = always suppress).

        Algorithm from research + infinite-continue-stop-hook patterns:
        - ignored_ratio with exponential dampening
        - Example: 80% ignored + 10+ instances = 0.8 suppression

        Args:
            pattern: Pattern data dictionary

        Returns:
            Suppression score between 0.0 and 1.0
        """
        shown_count = pattern.get('shown_count', 0)
        ignored_count = pattern.get('ignored_count', 0)

        if shown_count == 0:
            return 0.0

        ignored_ratio = ignored_count / shown_count

        # Exponential suppression after consistent ignoring
        if ignored_count > 5 and ignored_ratio > 0.7:
            # High ignore rate → high suppression
            return min(0.9, ignored_ratio)
        else:
            # Apply dampening factor (-0.3 to be more forgiving)
            return max(0.0, ignored_ratio - 0.3)

    def _is_critical_warning(self, category: str, context: Dict[str, Any]) -> bool:
        """
        Check if this is a critical warning that should NEVER be suppressed.

        Critical warnings:
        - rm -rf / (root directory)
        - rm -rf ~ (home directory)
        - rm -rf $HOME
        - .env file access
        - API key patterns in git-tracked files

        Args:
            category: Guidance category
            context: Current context

        Returns:
            True if critical warning, False otherwise
        """
        # Check for critical rm patterns
        command = context.get('tool_input', {}).get('command', '')

        critical_patterns = [
            r'rm\s+.*-[rf]+\s+/\s*$',     # rm -rf / (root directory only)
            r'rm\s+.*-[rf]+\s+~',          # rm -rf ~
            r'rm\s+.*-[rf]+\s+\$HOME',     # rm -rf $HOME
        ]

        import re
        for pattern in critical_patterns:
            if re.search(pattern, command):
                return True

        # Check for .env file access
        file_path = context.get('tool_input', {}).get('file_path', '')
        if '.env' in file_path and not file_path.endswith('.env.sample'):
            return True

        # Check for security category with high severity
        if category == 'security' and 'AKIA' in str(context):  # AWS keys
            return True

        return False

    def _extract_context_key(self, context: Dict[str, Any]) -> Optional[str]:
        """
        Extract a context key for context-specific tracking.

        Examples:
        - node_modules (for rm node_modules)
        - dist (for rm dist)
        - source_file (for editing .ts/.js files)

        Args:
            context: Current context

        Returns:
            Context key string or None
        """
        command = context.get('tool_input', {}).get('command', '')
        file_path = context.get('tool_input', {}).get('file_path', '')

        # For bash commands, extract target
        if 'node_modules' in command:
            return 'node_modules'
        elif 'dist' in command:
            return 'dist'
        elif 'build' in command:
            return 'build'

        # For file operations, extract file type
        if file_path:
            if file_path.endswith(('.ts', '.js', '.tsx', '.jsx')):
                return 'source_file'
            elif file_path.endswith('.json'):
                return 'config_file'
            elif file_path.endswith(('.md', '.txt')):
                return 'docs'

        return None

    def get_statistics(self, category: str = None) -> Dict[str, Any]:
        """
        Get pattern learning statistics.

        Args:
            category: Optional category to get stats for (None = all categories)

        Returns:
            Statistics dictionary
        """
        if category:
            return self.patterns.get(category, {})

        # Return all statistics
        stats = {
            'total_categories': len(self.patterns),
            'categories': {}
        }

        for cat, pattern in self.patterns.items():
            stats['categories'][cat] = {
                'shown_count': pattern.get('shown_count', 0),
                'ignored_count': pattern.get('ignored_count', 0),
                'acted_on_count': pattern.get('acted_on_count', 0),
                'suppression_score': pattern.get('suppression_score', 0.0),
                'last_shown': pattern.get('last_shown')
            }

        return stats

    # =========================================================================
    # ReasoningBank Extensions - Adaptive Learning from Sessions
    # =========================================================================

    def record_experience(self, tool: str, outcome: Dict[str, Any]):
        """
        Record a tool usage experience for learning.

        Args:
            tool: Tool name (Write, Edit, Bash, etc.)
            outcome: Outcome data including success status
        """
        # Initialize experiences storage if not exists
        if '_experiences' not in self.patterns:
            self.patterns['_experiences'] = []

        experience = {
            'tool': tool,
            'success': outcome.get('success', True),
            'context': outcome.get('context', {}),
            'timestamp': datetime.now().isoformat()
        }

        self.patterns['_experiences'].append(experience)

        # Keep last 500 experiences
        self.patterns['_experiences'] = self.patterns['_experiences'][-500:]

        self._save_patterns()

    def get_recommended_strategies(self, context: Dict[str, Any] = None,
                                   limit: int = 3) -> list:
        """
        Get recommended strategies based on past successes.

        Args:
            context: Current context for matching
            limit: Maximum number of strategies to return

        Returns:
            List of strategy recommendations
        """
        strategies = self.patterns.get('_strategies', [])

        if not strategies:
            return []

        # Sort by success rate
        sorted_strategies = sorted(
            strategies,
            key=lambda s: s.get('success_rate', 0),
            reverse=True
        )

        return sorted_strategies[:limit]

    def learn_pattern(self, pattern: Dict[str, Any]):
        """
        Learn a new pattern from successful session completion.

        Args:
            pattern: Pattern data to learn (tools used, task type, outcome)
        """
        # Initialize strategies storage if not exists
        if '_strategies' not in self.patterns:
            self.patterns['_strategies'] = []

        # Check if similar pattern exists
        pattern_key = pattern.get('pattern_key', '')
        existing = None
        for i, s in enumerate(self.patterns['_strategies']):
            if s.get('pattern_key') == pattern_key:
                existing = i
                break

        if existing is not None:
            # Update existing pattern
            strategy = self.patterns['_strategies'][existing]
            strategy['occurrences'] = strategy.get('occurrences', 1) + 1
            if pattern.get('success'):
                strategy['successes'] = strategy.get('successes', 0) + 1
            strategy['success_rate'] = (
                strategy['successes'] / strategy['occurrences']
            )
            strategy['last_seen'] = datetime.now().isoformat()
        else:
            # Add new pattern
            new_strategy = {
                'pattern_key': pattern_key,
                'description': pattern.get('description', ''),
                'tools_used': pattern.get('tools_used', []),
                'occurrences': 1,
                'successes': 1 if pattern.get('success') else 0,
                'success_rate': 1.0 if pattern.get('success') else 0.0,
                'learned_at': datetime.now().isoformat(),
                'last_seen': datetime.now().isoformat()
            }
            self.patterns['_strategies'].append(new_strategy)

            # Keep last 100 strategies
            self.patterns['_strategies'] = self.patterns['_strategies'][-100:]

        self._save_patterns()

    def get_experiences_summary(self) -> Dict[str, Any]:
        """
        Get summary of recorded experiences.

        Returns:
            Summary statistics of tool experiences
        """
        experiences = self.patterns.get('_experiences', [])

        if not experiences:
            return {'total': 0, 'by_tool': {}}

        # Count by tool
        by_tool = {}
        for exp in experiences:
            tool = exp.get('tool', 'unknown')
            if tool not in by_tool:
                by_tool[tool] = {'total': 0, 'success': 0}
            by_tool[tool]['total'] += 1
            if exp.get('success'):
                by_tool[tool]['success'] += 1

        # Calculate success rates
        for tool in by_tool:
            total = by_tool[tool]['total']
            success = by_tool[tool]['success']
            by_tool[tool]['success_rate'] = success / total if total > 0 else 0

        return {
            'total': len(experiences),
            'by_tool': by_tool
        }


if __name__ == '__main__':
    # Simple test
    learner = PatternLearner()

    # Simulate showing a warning
    test_context = {
        'tool_input': {'command': 'rm -rf node_modules/'}
    }

    learner.record_shown('rm_warnings', test_context)
    print("Recorded shown")

    # Simulate user ignoring it multiple times
    for _ in range(5):
        learner.record_response('rm_warnings', 'ignored', test_context)
    print("Recorded 5 ignores")

    # Check if should suppress
    should_suppress = learner.should_suppress('rm_warnings', test_context)
    print(f"Should suppress: {should_suppress}")

    # Print statistics
    stats = learner.get_statistics('rm_warnings')
    print(f"Statistics: {json.dumps(stats, indent=2)}")
