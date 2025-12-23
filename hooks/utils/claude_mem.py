#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Claude-Mem HTTP Client - Full API Integration

Provides interface to Claude-Mem service (port 37777) for:
- Observation storage and retrieval
- Session summaries
- Full-text search (FTS5)
- Context injection

Falls back to local JSON storage when service unavailable.

Usage:
    client = ClaudeMemClient()
    client.store_observation(session_id, tool_name, tool_input, tool_response)
    context = client.get_recent_context(project="my-project")
    results = client.search("authentication bugs")
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, List, Dict


class ClaudeMemClient:
    """Client for Claude-Mem persistent memory service."""

    def __init__(self, port: int = 37777, timeout: float = 2.0):
        """
        Initialize the client.

        Args:
            port: Port where Claude-Mem service is running
            timeout: Request timeout in seconds (keep short for non-blocking)
        """
        self.base_url = f"http://localhost:{port}"
        self.timeout = timeout
        self.fallback_path = Path('.claude/data/memory')
        self.fallback_path.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # Core API Methods
    # =========================================================================

    def health_check(self) -> bool:
        """Check if Claude-Mem service is running."""
        try:
            url = f"{self.base_url}/health"
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return response.status == 200
        except Exception:
            return False

    def get_recent_context(self, project: str = None,
                           limit: int = 50) -> Optional[Dict]:
        """
        Get recent context for injection at session start.

        Args:
            project: Optional project filter
            limit: Maximum observations to return

        Returns:
            Context dict or None
        """
        try:
            params = {"limit": str(limit)}
            if project:
                params["project"] = project
            query = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/context/recent?{query}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
        except Exception:
            pass
        return None

    def store_observation(self, session_id: str, tool_name: str,
                          tool_input: dict, tool_response: str) -> bool:
        """
        Store a tool observation.

        Args:
            session_id: Claude session ID
            tool_name: Name of the tool used
            tool_input: Tool input parameters
            tool_response: Tool response/output

        Returns:
            True on success, False on failure
        """
        try:
            data = json.dumps({
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_response": tool_response[:5000]  # Limit response size
            }).encode('utf-8')

            request = urllib.request.Request(
                f"{self.base_url}/api/sessions/observations",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status == 200
        except Exception:
            pass

        # Fallback to local storage
        return self._store_local_observation(session_id, tool_name, tool_input)

    def generate_summary(self, session_id: str,
                         last_user_message: str,
                         last_assistant_message: str) -> bool:
        """
        Request session summary generation.

        Args:
            session_id: Claude session ID
            last_user_message: Last user message in session
            last_assistant_message: Last assistant message

        Returns:
            True on success, False on failure
        """
        try:
            data = json.dumps({
                "session_id": session_id,
                "last_user_message": last_user_message[:2000],
                "last_assistant_message": last_assistant_message[:2000]
            }).encode('utf-8')

            request = urllib.request.Request(
                f"{self.base_url}/api/sessions/summarize",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status == 200
        except Exception:
            return False

    def search(self, query: str, search_type: str = None,
               limit: int = 10) -> Optional[List[Dict]]:
        """
        Search observations using FTS5 full-text search.

        Args:
            query: Search query (supports boolean operators)
            search_type: Optional type filter (bugfix, feature, refactor, etc.)
            limit: Maximum results

        Returns:
            List of search results or None
        """
        try:
            params = {"query": query, "limit": str(limit)}
            if search_type:
                params["type"] = search_type
            query_str = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/search?{query_str}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('results', [])
        except Exception:
            pass
        return None

    def get_stats(self, project: str = None) -> Optional[Dict]:
        """
        Get database statistics.

        Args:
            project: Optional project filter

        Returns:
            Stats dict or None
        """
        try:
            url = f"{self.base_url}/api/stats"
            if project:
                url += f"?project={urllib.parse.quote(project)}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    return json.loads(response.read().decode('utf-8'))
        except Exception:
            pass
        return None

    def complete_session(self, session_id: str) -> bool:
        """
        Mark session as complete.

        Args:
            session_id: Claude session ID

        Returns:
            True on success, False on failure
        """
        try:
            data = json.dumps({"session_id": session_id}).encode('utf-8')
            request = urllib.request.Request(
                f"{self.base_url}/api/sessions/complete",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.status == 200
        except Exception:
            return False

    # =========================================================================
    # Legacy API Methods (for backward compatibility)
    # =========================================================================

    def store(self, key: str, value: Any) -> bool:
        """
        Store value (legacy method - uses observation storage).

        Args:
            key: Storage key
            value: Value to store

        Returns:
            True on success
        """
        return self._store_local(key, value)

    def retrieve(self, key: str, default: Any = None) -> Any:
        """
        Retrieve value (legacy method - uses local fallback).

        Args:
            key: Storage key
            default: Default value if not found

        Returns:
            Stored value or default
        """
        return self._retrieve_local(key, default)

    def delete(self, key: str) -> bool:
        """Delete value from local storage."""
        return self._delete_local(key)

    def list_keys(self) -> list:
        """List all locally stored keys."""
        return self._list_local_keys()

    # =========================================================================
    # Local Fallback Methods
    # =========================================================================

    def _store_local(self, key: str, value: Any) -> bool:
        """Store value in local JSON fallback."""
        try:
            file_path = self.fallback_path / f"{self._sanitize_key(key)}.json"
            with open(file_path, 'w') as f:
                json.dump({
                    'value': value,
                    'stored_at': datetime.now().isoformat()
                }, f, indent=2)
            return True
        except Exception:
            return False

    def _retrieve_local(self, key: str, default: Any) -> Any:
        """Retrieve value from local JSON fallback."""
        try:
            file_path = self.fallback_path / f"{self._sanitize_key(key)}.json"
            if file_path.exists():
                with open(file_path, 'r') as f:
                    return json.load(f).get('value', default)
        except Exception:
            pass
        return default

    def _delete_local(self, key: str) -> bool:
        """Delete value from local JSON fallback."""
        try:
            file_path = self.fallback_path / f"{self._sanitize_key(key)}.json"
            if file_path.exists():
                file_path.unlink()
                return True
        except Exception:
            pass
        return False

    def _list_local_keys(self) -> list:
        """List keys from local JSON fallback."""
        try:
            return [f.stem for f in self.fallback_path.glob('*.json')]
        except Exception:
            return []

    def _store_local_observation(self, session_id: str,
                                  tool_name: str, tool_input: dict) -> bool:
        """Store observation to local fallback."""
        try:
            obs_dir = self.fallback_path / "observations"
            obs_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_path = obs_dir / f"{session_id}_{timestamp}.json"

            with open(file_path, 'w') as f:
                json.dump({
                    'session_id': session_id,
                    'tool_name': tool_name,
                    'tool_input': tool_input,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
            return True
        except Exception:
            return False

    def _sanitize_key(self, key: str) -> str:
        """Sanitize key for use as filename."""
        safe_key = key.replace('/', '_').replace('\\', '_')
        safe_key = safe_key.replace(':', '_').replace('*', '_')
        safe_key = safe_key.replace('?', '_').replace('"', '_')
        safe_key = safe_key.replace('<', '_').replace('>', '_')
        safe_key = safe_key.replace('|', '_')
        return safe_key[:100]


# Convenience functions for hook integration

def persist_session_learnings(session_id: str, input_data: dict,
                               port: int = 37777):
    """
    Persist session learnings to Claude-Mem.

    Called from stop.py after authorization passes.
    """
    client = ClaudeMemClient(port=port)

    # Try to generate summary via API
    client.generate_summary(
        session_id,
        input_data.get('last_user_message', ''),
        input_data.get('last_assistant_message', '')
    )

    # Complete the session
    client.complete_session(session_id)

    # Also store to local for legacy compatibility
    client.store(f"session_{session_id}", {
        'session_id': session_id,
        'data': input_data,
        'persisted_at': datetime.now().isoformat()
    })

    # Update recent patterns list
    patterns = client.retrieve('recent_patterns', [])
    patterns.append({
        'session_id': session_id,
        'summary': f"Session {session_id[:8]}... completed",
        'timestamp': datetime.now().isoformat()
    })
    patterns = patterns[-50:]
    client.store('recent_patterns', patterns)


def load_recent_context(project: str = None, port: int = 37777) -> Optional[str]:
    """
    Load recent context from Claude-Mem.

    Called from session_start.py for context injection.
    """
    client = ClaudeMemClient(port=port)

    # Try Claude-Mem API first
    context = client.get_recent_context(project=project, limit=10)
    if context and context.get('observations'):
        lines = ["--- Claude-Mem Recent Context ---"]
        for obs in context['observations'][:5]:
            title = obs.get('title', 'Observation')
            lines.append(f"- {title}")
        return "\n".join(lines)

    # Fallback to local patterns
    patterns = client.retrieve('recent_patterns', [])
    if patterns:
        lines = ["--- Recent Patterns ---"]
        for p in patterns[-3:]:
            lines.append(f"- {p.get('summary', 'Pattern')}")
        return "\n".join(lines)

    return None


def search_memory(query: str, port: int = 37777) -> Optional[List[Dict]]:
    """
    Search Claude-Mem for relevant information.

    Args:
        query: Search query
        port: Claude-Mem port

    Returns:
        List of search results or None
    """
    client = ClaudeMemClient(port=port)
    return client.search(query)


if __name__ == '__main__':
    # Simple test
    print("Testing Claude-Mem client...")

    client = ClaudeMemClient()

    # Test health check
    healthy = client.health_check()
    print(f"Health check: {healthy}")

    # Test local storage (always works)
    result = client.store("test_key", {"message": "Hello from test"})
    print(f"Store result: {result}")

    value = client.retrieve("test_key")
    print(f"Retrieved: {value}")

    # Cleanup
    client.delete("test_key")
    print("Test complete")
