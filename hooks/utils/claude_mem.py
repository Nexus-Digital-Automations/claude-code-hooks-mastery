#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Claude-Mem HTTP Client - Persistent Memory Integration

Provides interface to Claude-Mem service (port 37777) with
graceful fallback to local JSON storage when service unavailable.

Usage:
    client = ClaudeMemClient()
    client.store("key", {"data": "value"})
    data = client.retrieve("key")
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Any


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

    def store(self, key: str, value: Any) -> bool:
        """
        Store value in memory.

        Args:
            key: Storage key
            value: Any JSON-serializable value

        Returns:
            True on success, False on failure
        """
        # Try HTTP API first
        try:
            data = json.dumps({'key': key, 'value': value}).encode('utf-8')
            request = urllib.request.Request(
                f"{self.base_url}/store",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass  # Fall through to local storage

        # Fallback to local JSON
        return self._store_local(key, value)

    def retrieve(self, key: str, default: Any = None) -> Any:
        """
        Retrieve value from memory.

        Args:
            key: Storage key
            default: Default value if key not found

        Returns:
            Stored value or default
        """
        # Try HTTP API first
        try:
            url = f"{self.base_url}/retrieve?key={urllib.parse.quote(key)}"
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('value', default)
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass  # Fall through to local storage
        except Exception:
            pass

        # Fallback to local JSON
        return self._retrieve_local(key, default)

    def delete(self, key: str) -> bool:
        """
        Delete value from memory.

        Args:
            key: Storage key

        Returns:
            True on success, False on failure
        """
        # Try HTTP API first
        try:
            url = f"{self.base_url}/delete?key={urllib.parse.quote(key)}"
            request = urllib.request.Request(url, method='DELETE')
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                if response.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass

        return self._delete_local(key)

    def list_keys(self) -> list:
        """
        List all stored keys.

        Returns:
            List of key names
        """
        # Try HTTP API first
        try:
            url = f"{self.base_url}/keys"
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('keys', [])
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            pass

        # Fallback to local files
        return self._list_local_keys()

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

    def _sanitize_key(self, key: str) -> str:
        """Sanitize key for use as filename."""
        # Replace unsafe characters
        safe_key = key.replace('/', '_').replace('\\', '_')
        safe_key = safe_key.replace(':', '_').replace('*', '_')
        safe_key = safe_key.replace('?', '_').replace('"', '_')
        safe_key = safe_key.replace('<', '_').replace('>', '_')
        safe_key = safe_key.replace('|', '_')
        return safe_key[:100]  # Limit length


# Convenience functions for hook integration

def persist_session_learnings(session_id: str, input_data: dict, port: int = 37777):
    """
    Persist session learnings to Claude-Mem.

    Called from stop.py after authorization passes.
    """
    client = ClaudeMemClient(port=port)

    # Store session summary
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

    # Keep last 50 patterns
    patterns = patterns[-50:]
    client.store('recent_patterns', patterns)


def load_recent_patterns(port: int = 37777, limit: int = 5) -> list:
    """
    Load recent patterns from Claude-Mem.

    Called from session_start.py for context loading.
    """
    client = ClaudeMemClient(port=port)
    patterns = client.retrieve('recent_patterns', [])
    return patterns[-limit:] if patterns else []


if __name__ == '__main__':
    # Simple test
    print("Testing Claude-Mem client...")

    client = ClaudeMemClient()

    # Test store
    result = client.store("test_key", {"message": "Hello from test"})
    print(f"Store result: {result}")

    # Test retrieve
    value = client.retrieve("test_key")
    print(f"Retrieved: {value}")

    # Test list
    keys = client.list_keys()
    print(f"Keys: {keys}")

    # Cleanup
    client.delete("test_key")
    print("Test complete")
