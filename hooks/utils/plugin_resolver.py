"""
Plugin Resolver - Indexes the 67 New Tools plugins for fast context-aware resolution.

Loads marketplace.json once, caches for 5 minutes, builds keyword/category/extension
reverse indices. Provides methods for matching plugins by file, tool, task, or keywords.

Singleton pattern with module-level caching. Graceful degradation on any error.
"""

import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Module-level cache
_resolver_instance = None
_resolver_timestamp = 0.0
_CACHE_TTL = 300  # 5 minutes

MARKETPLACE_PATH = Path.home() / ".claude" / "New Tools" / "agents" / ".claude-plugin" / "marketplace.json"

# File extension to language/category mapping
EXTENSION_MAP = {
    '.py': ['python', 'django', 'fastapi', 'backend'],
    '.js': ['javascript', 'nodejs', 'react', 'frontend'],
    '.ts': ['typescript', 'nodejs', 'react', 'frontend'],
    '.tsx': ['typescript', 'react', 'frontend'],
    '.jsx': ['javascript', 'react', 'frontend'],
    '.rs': ['rust', 'systems-programming'],
    '.go': ['golang', 'backend'],
    '.java': ['java', 'jvm', 'enterprise'],
    '.scala': ['scala', 'jvm'],
    '.cs': ['csharp', 'dotnet', 'jvm'],
    '.rb': ['ruby', 'rails'],
    '.php': ['php', 'web-scripting'],
    '.ex': ['elixir', 'functional', 'phoenix'],
    '.exs': ['elixir', 'functional'],
    '.jl': ['julia', 'scientific-computing'],
    '.sol': ['solidity', 'blockchain', 'web3'],
    '.sh': ['bash', 'shell', 'scripting'],
    '.bash': ['bash', 'shell', 'scripting'],
    '.tf': ['terraform', 'infrastructure'],
    '.yml': ['ci-cd', 'kubernetes', 'deployment'],
    '.yaml': ['ci-cd', 'kubernetes', 'deployment'],
    '.dockerfile': ['deployment', 'containers', 'kubernetes'],
    '.sql': ['database-design', 'sql', 'data-modeling'],
    '.graphql': ['graphql', 'api'],
    '.proto': ['api', 'backend'],
    '.md': ['documentation', 'technical-writing'],
    '.c': ['c', 'systems-programming'],
    '.cpp': ['cpp', 'systems-programming'],
    '.h': ['c', 'cpp', 'systems-programming'],
    '.hpp': ['cpp', 'systems-programming'],
    '.swift': ['mobile', 'ios'],
    '.kt': ['mobile', 'android', 'jvm'],
    '.dart': ['flutter', 'mobile', 'cross-platform'],
}


class PluginResolver:
    """Indexes and resolves plugins from marketplace.json."""

    def __init__(self):
        self.plugins: List[dict] = []
        self.keyword_index: Dict[str, List[dict]] = {}
        self.category_index: Dict[str, List[dict]] = {}
        self.extension_index: Dict[str, List[dict]] = {}
        self._loaded = False

    def load(self) -> bool:
        """Load and index marketplace.json. Returns True on success."""
        try:
            if not MARKETPLACE_PATH.exists():
                return False

            with open(MARKETPLACE_PATH, 'r') as f:
                data = json.load(f)

            self.plugins = data.get('plugins', [])
            self._build_indices()
            self._loaded = True
            return True
        except Exception:
            return False

    def _build_indices(self):
        """Build reverse indices for fast lookup."""
        self.keyword_index.clear()
        self.category_index.clear()
        self.extension_index.clear()

        for plugin in self.plugins:
            # Keyword index
            keywords = plugin.get('keywords', [])
            for kw in keywords:
                kw_lower = kw.lower()
                self.keyword_index.setdefault(kw_lower, []).append(plugin)

            # Also index plugin name words
            for word in plugin.get('name', '').split('-'):
                if len(word) > 2:
                    self.keyword_index.setdefault(word.lower(), []).append(plugin)

            # Category index
            category = plugin.get('category', 'unknown')
            self.category_index.setdefault(category, []).append(plugin)

            # Extension index: map file extensions to plugins via keywords
            for ext, ext_keywords in EXTENSION_MAP.items():
                for ek in ext_keywords:
                    if ek in keywords or ek in plugin.get('name', ''):
                        self.extension_index.setdefault(ext, []).append(plugin)
                        break

    def resolve_by_file(self, file_path: str) -> List[dict]:
        """Match plugins by file extension."""
        if not self._loaded:
            return []

        ext = Path(file_path).suffix.lower()
        if not ext:
            return []

        # Direct extension match
        matches = self.extension_index.get(ext, [])
        if matches:
            return _dedupe_plugins(matches)

        # Fallback: check extension keywords against keyword index
        ext_keywords = EXTENSION_MAP.get(ext, [])
        results = []
        for kw in ext_keywords:
            results.extend(self.keyword_index.get(kw, []))
        return _dedupe_plugins(results)

    def resolve_by_tool(self, tool_name: str, tool_input: dict = None) -> List[dict]:
        """Match plugins based on tool context."""
        if not self._loaded:
            return []

        tool_input = tool_input or {}
        results = []

        # For file-based tools, resolve by file extension
        file_path = tool_input.get('file_path', '')
        if file_path:
            results.extend(self.resolve_by_file(file_path))

        # For Bash commands, look for tool-specific keywords
        if tool_name == 'Bash':
            command = tool_input.get('command', '')
            cmd_keywords = _extract_command_keywords(command)
            for kw in cmd_keywords:
                results.extend(self.keyword_index.get(kw, []))

        # For Task tools, check subagent_type
        if tool_name == 'Task':
            subagent = tool_input.get('subagent_type', '')
            if subagent:
                for word in subagent.lower().replace('-', ' ').split():
                    results.extend(self.keyword_index.get(word, []))

        return _dedupe_plugins(results)[:3]

    def resolve_by_task(self, description: str) -> List[dict]:
        """Match plugins by extracting keywords from task description."""
        if not self._loaded:
            return []

        keywords = _extract_task_keywords(description)
        return self.resolve_by_keywords(keywords)

    def resolve_by_keywords(self, keywords: List[str]) -> List[dict]:
        """Direct keyword lookup across the index."""
        if not self._loaded:
            return []

        results = []
        for kw in keywords:
            kw_lower = kw.lower()
            results.extend(self.keyword_index.get(kw_lower, []))
        return _dedupe_plugins(results)[:5]

    def resolve_by_category(self, category: str) -> List[dict]:
        """Get all plugins in a category."""
        if not self._loaded:
            return []
        return self.category_index.get(category, [])

    def get_recommended_agents(self, plugin_name: str) -> List[str]:
        """Get agent names from a plugin."""
        for p in self.plugins:
            if p.get('name') == plugin_name:
                return [os.path.basename(a).replace('.md', '') for a in p.get('agents', [])]
        return []

    def get_recommended_skills(self, plugin_name: str) -> List[str]:
        """Get skill names from a plugin."""
        for p in self.plugins:
            if p.get('name') == plugin_name:
                return [os.path.basename(s) for s in p.get('skills', [])]
        return []

    def get_all_categories(self) -> Dict[str, int]:
        """Get category counts."""
        return {cat: len(plugins) for cat, plugins in self.category_index.items()}

    def format_recommendation(self, plugins: List[dict], max_plugins: int = 2) -> str:
        """Format plugin recommendations as compact context injection string."""
        if not plugins:
            return ""

        lines = ["--- Plugin Recommendations ---"]
        for p in plugins[:max_plugins]:
            name = p.get('name', 'unknown')
            desc = p.get('description', '')[:80]
            agents = [os.path.basename(a).replace('.md', '') for a in p.get('agents', [])]
            agent_str = ', '.join(agents[:3])
            lines.append(f"- {name}: {desc}")
            if agent_str:
                lines.append(f"  Agents: {agent_str}")

        return "\n".join(lines)


def get_resolver() -> PluginResolver:
    """Get or create the singleton PluginResolver with TTL caching."""
    global _resolver_instance, _resolver_timestamp

    now = time.time()
    if _resolver_instance is not None and (now - _resolver_timestamp) < _CACHE_TTL:
        return _resolver_instance

    resolver = PluginResolver()
    resolver.load()
    _resolver_instance = resolver
    _resolver_timestamp = now
    return resolver


def _dedupe_plugins(plugins: List[dict]) -> List[dict]:
    """Remove duplicate plugins from list, preserving order."""
    seen = set()
    result = []
    for p in plugins:
        name = p.get('name', '')
        if name not in seen:
            seen.add(name)
            result.append(p)
    return result


def _extract_command_keywords(command: str) -> List[str]:
    """Extract relevant keywords from a bash command."""
    keywords = []
    cmd_lower = command.lower()

    keyword_map = {
        'docker': ['deployment', 'containers'],
        'kubectl': ['kubernetes', 'k8s'],
        'terraform': ['terraform', 'infrastructure'],
        'npm': ['javascript', 'nodejs'],
        'pip': ['python'],
        'cargo': ['rust'],
        'go ': ['golang'],
        'git': ['git'],
        'pytest': ['testing', 'python'],
        'jest': ['testing', 'javascript'],
        'eslint': ['javascript', 'quality'],
        'ruff': ['python', 'quality'],
        'helm': ['kubernetes', 'helm'],
        'aws': ['cloud', 'aws'],
        'gcloud': ['cloud', 'gcp'],
        'az ': ['cloud', 'azure'],
        'psql': ['database-design', 'sql'],
        'mysql': ['database-design', 'sql'],
        'redis': ['database-operations'],
        'curl': ['api'],
    }

    for cmd_prefix, kws in keyword_map.items():
        if cmd_prefix in cmd_lower:
            keywords.extend(kws)

    return keywords


def _extract_task_keywords(description: str) -> List[str]:
    """Extract relevant keywords from a task/prompt description."""
    desc_lower = description.lower()
    keywords = []

    # Technology keywords
    tech_keywords = [
        'python', 'javascript', 'typescript', 'react', 'django', 'fastapi',
        'rust', 'golang', 'java', 'scala', 'ruby', 'rails', 'php',
        'elixir', 'julia', 'solidity', 'blockchain', 'web3',
        'kubernetes', 'k8s', 'docker', 'terraform', 'aws', 'gcp', 'azure',
        'graphql', 'rest', 'api', 'database', 'sql', 'mongodb', 'postgres',
        'redis', 'kafka', 'nginx', 'ci-cd', 'github-actions',
        'react-native', 'flutter', 'ios', 'android', 'mobile',
        'security', 'sast', 'owasp', 'authentication', 'authorization',
        'testing', 'tdd', 'unit-test', 'e2e', 'performance', 'monitoring',
        'observability', 'logging', 'metrics', 'tracing',
        'documentation', 'seo', 'deployment', 'migration', 'refactoring',
        'debugging', 'mlops', 'machine-learning', 'llm', 'prompt',
    ]

    for kw in tech_keywords:
        if kw in desc_lower:
            keywords.append(kw)

    # Multi-word patterns
    multi_patterns = {
        'pull request': 'pull-request',
        'code review': 'code-review',
        'data pipeline': 'data-pipeline',
        'data engineering': 'data-engineering',
        'incident response': 'incident-response',
        'technical debt': 'technical-debt',
        'full stack': 'full-stack',
    }

    for pattern, kw in multi_patterns.items():
        if pattern in desc_lower:
            keywords.append(kw)

    return keywords


# Convenience functions for hook integration

def get_plugin_context_for_file(file_path: str) -> str:
    """Get plugin context string for a file being edited."""
    try:
        resolver = get_resolver()
        plugins = resolver.resolve_by_file(file_path)
        return resolver.format_recommendation(plugins, max_plugins=2)
    except Exception:
        return ""


def get_plugin_context_for_tool(tool_name: str, tool_input: dict = None) -> str:
    """Get plugin context string for a tool operation."""
    try:
        resolver = get_resolver()
        plugins = resolver.resolve_by_tool(tool_name, tool_input)
        return resolver.format_recommendation(plugins, max_plugins=2)
    except Exception:
        return ""


def get_plugin_suggestions_for_prompt(prompt: str) -> str:
    """Get plugin suggestions for a user prompt."""
    try:
        resolver = get_resolver()
        plugins = resolver.resolve_by_task(prompt)
        return resolver.format_recommendation(plugins, max_plugins=2)
    except Exception:
        return ""


def get_plugins_for_project(cwd: str) -> str:
    """Detect project type from common files and return relevant plugins."""
    try:
        resolver = get_resolver()
        cwd_path = Path(cwd)
        keywords = []

        # Detect project type from common files
        project_signals = {
            'pyproject.toml': ['python', 'backend'],
            'setup.py': ['python', 'backend'],
            'requirements.txt': ['python', 'backend'],
            'package.json': ['javascript', 'nodejs'],
            'tsconfig.json': ['typescript', 'nodejs'],
            'Cargo.toml': ['rust', 'systems-programming'],
            'go.mod': ['golang', 'backend'],
            'build.gradle': ['java', 'jvm'],
            'pom.xml': ['java', 'jvm'],
            'build.sbt': ['scala', 'jvm'],
            'Gemfile': ['ruby', 'rails'],
            'composer.json': ['php'],
            'mix.exs': ['elixir', 'functional'],
            'Project.toml': ['julia'],
            'hardhat.config.js': ['solidity', 'blockchain', 'web3'],
            'truffle-config.js': ['solidity', 'blockchain'],
            'Dockerfile': ['deployment', 'containers'],
            'docker-compose.yml': ['deployment', 'containers'],
            'terraform.tf': ['terraform', 'infrastructure'],
            'k8s/': ['kubernetes', 'k8s'],
            '.github/workflows/': ['ci-cd', 'github-actions'],
            '.gitlab-ci.yml': ['ci-cd', 'gitlab-ci'],
            'next.config.js': ['react', 'frontend'],
            'next.config.ts': ['react', 'frontend', 'typescript'],
            'nuxt.config.ts': ['frontend'],
            'angular.json': ['frontend', 'angular'],
            'pubspec.yaml': ['flutter', 'mobile'],
        }

        for filename, kws in project_signals.items():
            if (cwd_path / filename).exists():
                keywords.extend(kws)

        if not keywords:
            return ""

        plugins = resolver.resolve_by_keywords(list(set(keywords)))
        if not plugins:
            return ""

        lines = ["--- Project-Relevant Plugins ---"]
        for p in plugins[:5]:
            name = p.get('name', 'unknown')
            cat = p.get('category', '')
            agents = [os.path.basename(a).replace('.md', '') for a in p.get('agents', [])[:3]]
            agent_str = ', '.join(agents)
            lines.append(f"- {name} [{cat}]: {agent_str}")

        return "\n".join(lines)
    except Exception:
        return ""
