"""
Configuration loader for hooks MCP integration.
Provides unified access to feature toggles, server configs, and timeouts.
"""

import json
from pathlib import Path
from typing import Dict, Optional


class ConfigLoader:
    """Load and manage hook configuration with caching and defaults."""

    _instance = None
    _features_cache: Optional[Dict] = None
    _servers_cache: Optional[Dict] = None
    _mode_cache: Optional[Dict] = None

    def __new__(cls):
        """Singleton pattern for configuration."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.config_dir = Path.home() / '.claude' / 'hooks' / 'config'
        self.features_file = self.config_dir / 'features.json'
        self.servers_file = self.config_dir / 'mcp_servers.json'

    def _default_features(self) -> Dict:
        """Return default features configuration."""
        return {
            "version": "1.0.0",
            "features": {
                "neural": {"enabled": True, "timeout_ms": 30000},
                "swarm": {"enabled": True, "auto_init": True, "timeout_ms": 15000},
                "github": {"enabled": True, "timeout_ms": 20000},
                "workflow": {"enabled": True, "timeout_ms": 30000},
                "analytics": {"enabled": True, "timeout_ms": 15000},
                "memory": {"enabled": True, "timeout_ms": 5000},
                "ruv_swarm": {"enabled": True, "timeout_ms": 15000}
            },
            "fallbacks": {
                "use_local_json": True,
                "log_failures": True,
                "retry_count": 2
            }
        }

    def _default_servers(self) -> Dict:
        """Return default MCP servers configuration."""
        return {
            "version": "1.0.0",
            "servers": {
                "claude-flow": {
                    "enabled": True,
                    "prefix": "mcp__claude-flow_alpha__",
                    "priority": 1
                },
                "ruv-swarm": {
                    "enabled": True,
                    "prefix": "mcp__ruv-swarm__",
                    "priority": 2
                },

            }
        }

    def get_features(self, force_reload: bool = False) -> Dict:
        """Load features configuration with caching."""
        if ConfigLoader._features_cache and not force_reload:
            return ConfigLoader._features_cache

        try:
            if self.features_file.exists():
                with open(self.features_file, 'r') as f:
                    ConfigLoader._features_cache = json.load(f)
            else:
                ConfigLoader._features_cache = self._default_features()
        except Exception:
            ConfigLoader._features_cache = self._default_features()

        return ConfigLoader._features_cache

    def get_servers(self, force_reload: bool = False) -> Dict:
        """Load MCP servers configuration with caching."""
        if ConfigLoader._servers_cache and not force_reload:
            return ConfigLoader._servers_cache

        try:
            if self.servers_file.exists():
                with open(self.servers_file, 'r') as f:
                    ConfigLoader._servers_cache = json.load(f)
            else:
                ConfigLoader._servers_cache = self._default_servers()
        except Exception:
            ConfigLoader._servers_cache = self._default_servers()

        return ConfigLoader._servers_cache

    def is_feature_enabled(self, category: str, feature: Optional[str] = None) -> bool:
        """
        Check if a feature is enabled.

        Args:
            category: Feature category (neural, swarm, github, etc.)
            feature: Optional specific feature within category

        Returns:
            True if feature is enabled, False otherwise
        """
        features = self.get_features()
        cat_config = features.get('features', {}).get(category, {})

        if not cat_config.get('enabled', False):
            return False

        if feature:
            return cat_config.get(feature, False)

        return True

    def get_timeout(self, category: str) -> float:
        """
        Get timeout in seconds for a feature category.

        Args:
            category: Feature category

        Returns:
            Timeout in seconds (defaults to 10.0)
        """
        features = self.get_features()
        timeout_ms = features.get('features', {}).get(category, {}).get('timeout_ms', 10000)
        return timeout_ms / 1000.0

    def get_server_prefix(self, server: str) -> str:
        """
        Get MCP tool prefix for a server.

        Args:
            server: Server name (claude-flow, ruv-swarm)

        Returns:
            Tool prefix string
        """
        servers = self.get_servers()
        return servers.get('servers', {}).get(server, {}).get('prefix', '')

    def is_server_enabled(self, server: str) -> bool:
        """
        Check if an MCP server is enabled.

        Args:
            server: Server name

        Returns:
            True if server is enabled
        """
        servers = self.get_servers()
        return servers.get('servers', {}).get(server, {}).get('enabled', False)

    def get_server_tools(self, server: str, category: Optional[str] = None) -> list:
        """
        Get available tools for a server/category.

        Args:
            server: Server name
            category: Optional tool category

        Returns:
            List of tool names
        """
        servers = self.get_servers()
        server_config = servers.get('servers', {}).get(server, {})
        categories = server_config.get('categories', {})

        if category:
            return categories.get(category, [])

        # Return all tools across categories
        all_tools = []
        for cat_tools in categories.values():
            all_tools.extend(cat_tools)
        return all_tools

    def get_fallback_config(self) -> Dict:
        """Get fallback configuration."""
        features = self.get_features()
        return features.get('fallbacks', {
            'use_local_json': True,
            'log_failures': True,
            'retry_count': 2
        })

    def should_use_local_fallback(self) -> bool:
        """Check if local JSON fallback should be used."""
        return self.get_fallback_config().get('use_local_json', True)

    def get_retry_count(self) -> int:
        """Get number of retries for failed operations."""
        return self.get_fallback_config().get('retry_count', 2)

    def get_log_dir(self) -> Path:
        """Get logging directory path."""
        features = self.get_features()
        log_dir = features.get('logging', {}).get('log_dir', '.claude/logs')
        return Path.home() / log_dir

    def _default_mode(self) -> Dict:
        """Return default agent mode configuration."""
        return {
            "mode": "claude",
            "last_switched": None,
            "deepseek_profile": "standard",
            "deepseek_plan_mode": True,
            "delegation_policy": {
                "code_tasks": True,
                "research_tasks": False,
                "config_tasks": False,
                "docs_tasks": False,
            },
        }

    def get_agent_mode(self, force_reload: bool = False) -> Dict:
        """Load agent mode configuration with caching."""
        if ConfigLoader._mode_cache and not force_reload:
            return ConfigLoader._mode_cache

        mode_file = Path.home() / '.claude' / 'data' / 'agent_mode.json'
        try:
            if mode_file.exists():
                with open(mode_file, 'r') as f:
                    ConfigLoader._mode_cache = json.load(f)
            else:
                ConfigLoader._mode_cache = self._default_mode()
        except Exception:
            ConfigLoader._mode_cache = self._default_mode()

        return ConfigLoader._mode_cache

    def is_deepseek_mode(self) -> bool:
        """Check if the current agent mode is deepseek."""
        return self.get_agent_mode().get("mode") == "deepseek"


# Convenience function for quick access
def get_config() -> ConfigLoader:
    """Get the singleton ConfigLoader instance."""
    return ConfigLoader()
