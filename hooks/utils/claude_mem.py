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
- Full-text search (FTS5) with boolean operators
- Semantic search (ChromaDB)
- SSE streaming for real-time updates
- Multilingual mode support
- Private tag filtering
- Context injection

Falls back to local JSON storage when service unavailable.

Usage:
    client = ClaudeMemClient()
    client.store_observation(session_id, tool_name, tool_input, tool_response)
    context = client.get_recent_context(project="my-project")
    results = client.search("authentication bugs")
    results = client.boolean_search("authentication AND (login OR oauth)")
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, List, Dict

# Try to load config_loader for unified configuration
try:
    from .config_loader import get_config
    _config = get_config()
except ImportError:
    try:
        from config_loader import get_config
        _config = get_config()
    except ImportError:
        _config = None


class ClaudeMemClient:
    """Client for Claude-Mem persistent memory service with enhanced integration."""

    def __init__(self, port: int = 37777, timeout: float = None,
                 language: str = 'en', use_private_tags: bool = False):
        """
        Initialize the client.

        Args:
            port: Port where Claude-Mem service is running
            timeout: Request timeout in seconds (uses config if not specified)
            language: Language mode for multilingual support (en, es, fr, de, ja, zh)
            use_private_tags: Enable private tag filtering
        """
        self.base_url = f"http://localhost:{port}"

        # Get timeout from config or use default
        if timeout is not None:
            self.timeout = timeout
        elif _config is not None:
            self.timeout = _config.get_timeout('memory') / 1000  # Convert ms to seconds
        else:
            self.timeout = 5.0

        # Multilingual support
        self.language = language
        self.use_private_tags = use_private_tags

        self.fallback_path = Path('.claude/data/memory')
        self.fallback_path.mkdir(parents=True, exist_ok=True)

        # Get retry count from config or use default
        if _config is not None:
            self._retry_count = _config.get_fallback_config().get('retry_count', 2)
        else:
            self._retry_count = 2

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
               limit: int = 10, private_only: bool = False) -> Optional[List[Dict]]:
        """
        Search observations using FTS5 full-text search.

        Args:
            query: Search query (supports boolean operators)
            search_type: Optional type filter (bugfix, feature, refactor, etc.)
            limit: Maximum results
            private_only: Only return results with private tags

        Returns:
            List of search results or None
        """
        try:
            params = {"query": query, "limit": str(limit)}
            if search_type:
                params["type"] = search_type
            if self.language != 'en':
                params["lang"] = self.language
            if private_only or self.use_private_tags:
                params["private"] = "true"
            query_str = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/search?{query_str}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('results', [])
        except Exception:
            pass
        return None

    # =========================================================================
    # Boolean Search Helpers (FTS5 Enhanced)
    # =========================================================================

    def boolean_search(self, query: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Perform boolean search using FTS5 operators.

        Supports:
        - AND: both terms must match (authentication AND oauth)
        - OR: either term matches (login OR signin)
        - NOT: exclude term (error NOT warning)
        - Phrases: "exact phrase"
        - Prefix: term* (auth* matches auth, authentication, authorized)
        - Grouping: (term1 OR term2) AND term3

        Args:
            query: Boolean search query
            limit: Maximum results

        Returns:
            List of search results
        """
        return self.search(query, limit=limit)

    def phrase_search(self, phrase: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Search for exact phrase match.

        Args:
            phrase: Exact phrase to search for
            limit: Maximum results

        Returns:
            List of results containing exact phrase
        """
        # Wrap in quotes for exact match
        query = f'"{phrase}"'
        return self.search(query, limit=limit)

    def prefix_search(self, prefix: str, limit: int = 10) -> Optional[List[Dict]]:
        """
        Search for terms starting with prefix.

        Args:
            prefix: Term prefix (e.g., "auth" matches authentication, authorize)
            limit: Maximum results

        Returns:
            List of results matching prefix
        """
        query = f'{prefix}*'
        return self.search(query, limit=limit)

    def exclude_search(self, include_term: str, exclude_term: str,
                       limit: int = 10) -> Optional[List[Dict]]:
        """
        Search including one term while excluding another.

        Args:
            include_term: Term to include
            exclude_term: Term to exclude
            limit: Maximum results

        Returns:
            List of results with include_term but not exclude_term
        """
        query = f'{include_term} NOT {exclude_term}'
        return self.search(query, limit=limit)

    def combined_search(self, must_have: List[str] = None,
                        should_have: List[str] = None,
                        must_not: List[str] = None,
                        limit: int = 10) -> Optional[List[Dict]]:
        """
        Advanced combined boolean search.

        Args:
            must_have: All these terms must be present (AND)
            should_have: At least one of these should be present (OR)
            must_not: None of these should be present (NOT)
            limit: Maximum results

        Returns:
            List of search results
        """
        parts = []

        if must_have:
            parts.append(' AND '.join(must_have))

        if should_have:
            parts.append(f"({' OR '.join(should_have)})")

        if must_not:
            for term in must_not:
                parts.append(f"NOT {term}")

        query = ' AND '.join(parts) if parts else '*'
        return self.search(query, limit=limit)

    # =========================================================================
    # Private Tag Management
    # =========================================================================

    def store_with_tags(self, session_id: str, tool_name: str,
                        tool_input: dict, tool_response: str,
                        tags: List[str] = None, private: bool = False) -> bool:
        """
        Store observation with tags and optional private flag.

        Args:
            session_id: Claude session ID
            tool_name: Name of the tool used
            tool_input: Tool input parameters
            tool_response: Tool response/output
            tags: List of tags for categorization
            private: Mark as private (not shared in public searches)

        Returns:
            True on success, False on failure
        """
        try:
            data = json.dumps({
                "session_id": session_id,
                "tool_name": tool_name,
                "tool_input": tool_input,
                "tool_response": tool_response[:5000],
                "tags": tags or [],
                "private": private,
                "language": self.language
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

    def search_by_tag(self, tag: str, limit: int = 10,
                      private_only: bool = False) -> Optional[List[Dict]]:
        """
        Search observations by tag.

        Args:
            tag: Tag to search for
            limit: Maximum results
            private_only: Only return private observations

        Returns:
            List of matching observations
        """
        try:
            params = {"tag": tag, "limit": str(limit)}
            if private_only:
                params["private"] = "true"
            query = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/search/by-tag?{query}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('results', [])
        except Exception:
            pass
        return None

    def get_all_tags(self) -> Optional[List[str]]:
        """
        Get all unique tags in the database.

        Returns:
            List of unique tags
        """
        try:
            url = f"{self.base_url}/api/tags"
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('tags', [])
        except Exception:
            pass
        return None

    # =========================================================================
    # Multilingual Support
    # =========================================================================

    def set_language(self, language: str):
        """
        Set the language mode for searches and storage.

        Supported languages: en, es, fr, de, ja, zh, ko, pt, it, ru

        Args:
            language: ISO 639-1 language code
        """
        self.language = language

    def search_multilingual(self, query: str, languages: List[str] = None,
                            limit: int = 10) -> Optional[List[Dict]]:
        """
        Search across multiple languages.

        Args:
            query: Search query
            languages: List of language codes to search (defaults to all)
            limit: Maximum results

        Returns:
            List of results from all specified languages
        """
        try:
            params = {"query": query, "limit": str(limit)}
            if languages:
                params["langs"] = ",".join(languages)
            query_str = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/search/multilingual?{query_str}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('results', [])
        except Exception:
            pass

        # Fallback to standard search
        return self.search(query, limit=limit)

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
    # Enhanced FTS5 Search Methods
    # =========================================================================

    def search_solutions(self, error_signature: str, limit: int = 5) -> List[Dict]:
        """
        Search for solutions to similar errors.

        Uses FTS5 full-text search to find observations where errors
        were resolved, extracting solution patterns.

        Args:
            error_signature: Key part of error message to match
            limit: Maximum number of solutions to return

        Returns:
            List of solution dicts with keys: solution, tools_used, confidence
        """
        solutions = []

        # Build query to find error resolution patterns
        # Search for error + fix/resolved/solution keywords
        query = f'"{error_signature[:50]}" AND (fix OR resolved OR solution OR fixed)'

        try:
            results = self.search(query, search_type="bugfix", limit=limit * 2)
            if results:
                for result in results:
                    tool_response = result.get('tool_response', '')
                    tool_name = result.get('tool_name', '')

                    # Extract solution from tool response
                    if tool_response and len(tool_response) > 20:
                        solutions.append({
                            'solution': tool_response[:500],
                            'tools_used': [tool_name] if tool_name else [],
                            'confidence': min(result.get('relevance', 0.5), 0.9),
                            'session_id': result.get('session_id', ''),
                            'timestamp': result.get('timestamp', '')
                        })
        except Exception:
            pass

        # Also search local knowledge graph for solutions
        try:
            from knowledge_graph import find_similar_solutions
            kg_solutions = find_similar_solutions(error_signature)
            for sol in kg_solutions[:limit]:
                solutions.append({
                    'solution': sol.get('description', ''),
                    'tools_used': sol.get('tools_used', []),
                    'confidence': min(sol.get('weight', 1) / 10, 0.9),
                    'source': 'knowledge_graph'
                })
        except Exception:
            pass

        # Deduplicate and sort by confidence
        seen = set()
        unique_solutions = []
        for sol in solutions:
            key = sol.get('solution', '')[:100]
            if key not in seen:
                seen.add(key)
                unique_solutions.append(sol)

        unique_solutions.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        return unique_solutions[:limit]

    def search_by_tool(self, tool_name: str, file_extension: str = None,
                       limit: int = 10) -> List[Dict]:
        """
        Search for observations involving a specific tool.

        Args:
            tool_name: Tool name to search for
            file_extension: Optional file extension filter (e.g., ".py", ".ts")
            limit: Maximum results

        Returns:
            List of observation dicts
        """
        query = f'tool:{tool_name}'
        if file_extension:
            query += f' AND file:*{file_extension}'

        return self.search(query, limit=limit) or []

    def inject_relevant_context(self, tool_name: str, tool_input: dict,
                                 max_context_len: int = 2000) -> Optional[str]:
        """
        Build context injection for a tool call based on similar past operations.

        Searches memory for similar tool usages and extracts patterns
        that might be helpful for the current operation.

        Args:
            tool_name: Tool about to be used
            tool_input: Tool input parameters
            max_context_len: Maximum context string length

        Returns:
            Context string for injection, or None if no relevant context
        """
        context_parts = []

        # Extract file info from tool input
        file_path = tool_input.get('file_path', '') or tool_input.get('path', '')
        if file_path:
            ext = Path(file_path).suffix
            file_name = Path(file_path).name
        else:
            ext = None
            file_name = None

        # Search for similar tool operations
        try:
            if file_name:
                query = f'{tool_name} AND {file_name}'
            elif ext:
                query = f'{tool_name} AND *{ext}'
            else:
                query = tool_name

            results = self.search(query, limit=5)
            if results:
                context_parts.append(f"--- Similar {tool_name} operations ---")
                for result in results[:3]:
                    response_preview = result.get('tool_response', '')[:200]
                    if response_preview:
                        context_parts.append(f"• {response_preview}")
        except Exception:
            pass

        # Search for errors in similar files
        if ext:
            try:
                error_results = self.search(f'error AND *{ext}', limit=3)
                if error_results:
                    context_parts.append(f"--- Common errors in {ext} files ---")
                    for result in error_results[:2]:
                        error_preview = result.get('tool_response', '')[:150]
                        if 'error' in error_preview.lower():
                            context_parts.append(f"⚠ {error_preview}")
            except Exception:
                pass

        # Get tool sequence suggestions
        try:
            from knowledge_graph import suggest_next_tool
            next_tools = suggest_next_tool(tool_name)
            if next_tools:
                tool_suggestions = [f"{t}({w})" for t, w in next_tools[:3]]
                context_parts.append(f"--- Common next tools: {', '.join(tool_suggestions)} ---")
        except Exception:
            pass

        if not context_parts:
            return None

        context = "\n".join(context_parts)
        if len(context) > max_context_len:
            context = context[:max_context_len] + "..."

        return context

    def get_session_observations(self, session_id: str,
                                  limit: int = 50) -> List[Dict]:
        """
        Get all observations for a specific session.

        Args:
            session_id: Session ID to get observations for
            limit: Maximum observations to return

        Returns:
            List of observation dicts
        """
        try:
            params = {"session_id": session_id, "limit": str(limit)}
            query = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/sessions/observations?{query}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return data.get('observations', [])
        except Exception:
            pass

        # Fallback to local observations
        return self._get_local_observations(session_id)

    def _get_local_observations(self, session_id: str) -> List[Dict]:
        """Get observations from local fallback storage."""
        observations = []
        try:
            obs_dir = self.fallback_path / "observations"
            if obs_dir.exists():
                for obs_file in obs_dir.glob(f"{session_id}*.json"):
                    with open(obs_file, 'r') as f:
                        observations.append(json.load(f))
        except Exception:
            pass
        return observations

    # =========================================================================
    # Semantic Search Methods (ChromaDB Integration)
    # =========================================================================

    def semantic_search(self, query: str, limit: int = 10,
                        collection: str = "observations") -> List[Dict]:
        """
        Perform semantic similarity search using ChromaDB.

        Falls back to FTS5 text search if ChromaDB is unavailable.

        Args:
            query: Natural language query
            limit: Maximum results
            collection: Collection to search

        Returns:
            List of semantically similar results
        """
        results = []

        # Try ChromaDB endpoint first
        try:
            params = {
                "query": query,
                "limit": str(limit),
                "collection": collection,
                "search_type": "semantic"
            }
            query_str = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/semantic-search?{query_str}"

            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    results = data.get('results', [])
                    # Add similarity scores
                    for r in results:
                        r['search_type'] = 'semantic'
                    return results
        except Exception:
            pass

        # Fallback to FTS5 search
        fts_results = self.search(query, limit=limit)
        if fts_results:
            for r in fts_results:
                r['search_type'] = 'fts5_fallback'
            return fts_results

        return results

    def find_similar_code(self, code_snippet: str, limit: int = 5) -> List[Dict]:
        """
        Find similar code patterns in stored observations.

        Args:
            code_snippet: Code to find similar patterns for
            limit: Maximum results

        Returns:
            List of similar code observations
        """
        # Extract key identifiers from code
        keywords = []
        for word in code_snippet.split():
            # Keep function/variable-like words
            clean = word.strip('(){}[],:;')
            if clean and len(clean) > 2 and clean.isidentifier():
                keywords.append(clean)

        if not keywords:
            return []

        # Build query from top keywords
        query = ' OR '.join(keywords[:10])
        return self.semantic_search(query, limit=limit)

    def find_related_errors(self, error_message: str, limit: int = 5) -> List[Dict]:
        """
        Find related error patterns and their solutions.

        Args:
            error_message: Error message to match
            limit: Maximum results

        Returns:
            List of related error observations with potential solutions
        """
        # Clean error message for better matching
        clean_error = error_message.replace('\n', ' ').strip()

        # Try semantic search first
        results = self.semantic_search(
            f"error: {clean_error[:200]}",
            limit=limit * 2
        )

        # Filter to error-related results
        error_results = []
        for r in results:
            response = r.get('tool_response', '').lower()
            tool = r.get('tool_name', '').lower()
            if 'error' in response or 'fix' in response or tool in ['bash', 'edit']:
                error_results.append(r)

        return error_results[:limit]

    def get_context_for_file(self, file_path: str, limit: int = 5) -> List[Dict]:
        """
        Get historical context for a specific file.

        Args:
            file_path: Path to file
            limit: Maximum results

        Returns:
            List of observations related to this file
        """
        file_name = Path(file_path).name
        ext = Path(file_path).suffix

        # Search for file-specific history
        results = self.semantic_search(
            f"file:{file_name} OR *{ext}",
            limit=limit
        )

        return results

    # =========================================================================
    # SSE Streaming Methods
    # =========================================================================

    def stream_observations(self, session_id: Optional[str] = None,
                            callback: Optional[callable] = None,
                            timeout: float = 30.0) -> List[Dict]:
        """
        Stream observations in real-time via Server-Sent Events.

        Connects to SSE endpoint for real-time observation updates.
        Falls back to polling if SSE is unavailable.

        Args:
            session_id: Optional session filter
            callback: Optional callback for each observation
            timeout: Connection timeout

        Returns:
            List of received observations (if no callback provided)
        """
        observations = []

        try:
            params = {}
            if session_id:
                params['session_id'] = session_id
            query = urllib.parse.urlencode(params) if params else ''
            url = f"{self.base_url}/api/stream/observations"
            if query:
                url += f"?{query}"

            request = urllib.request.Request(url)
            request.add_header('Accept', 'text/event-stream')

            with urllib.request.urlopen(request, timeout=timeout) as response:
                buffer = ""
                start_time = datetime.now()
                max_duration = timeout

                while (datetime.now() - start_time).total_seconds() < max_duration:
                    chunk = response.read(1024)
                    if not chunk:
                        break

                    buffer += chunk.decode('utf-8')

                    # Parse SSE events
                    while '\n\n' in buffer:
                        event, buffer = buffer.split('\n\n', 1)
                        if event.startswith('data: '):
                            data = event[6:]
                            try:
                                obs = json.loads(data)
                                if callback:
                                    callback(obs)
                                else:
                                    observations.append(obs)
                            except json.JSONDecodeError:
                                pass

        except Exception:
            # Fallback to polling
            if session_id:
                observations = self.get_session_observations(session_id)

        return observations

    def subscribe_to_updates(self, event_types: List[str],
                              callback: callable,
                              duration: float = 60.0) -> bool:
        """
        Subscribe to specific event types via SSE.

        Args:
            event_types: List of event types to subscribe to
                        (observation, summary, search, error)
            callback: Callback function for each event
            duration: Subscription duration in seconds

        Returns:
            True if subscription was successful
        """
        try:
            params = {'events': ','.join(event_types)}
            query = urllib.parse.urlencode(params)
            url = f"{self.base_url}/api/stream/events?{query}"

            request = urllib.request.Request(url)
            request.add_header('Accept', 'text/event-stream')

            with urllib.request.urlopen(request, timeout=duration) as response:
                buffer = ""
                start_time = datetime.now()

                while (datetime.now() - start_time).total_seconds() < duration:
                    chunk = response.read(512)
                    if not chunk:
                        break

                    buffer += chunk.decode('utf-8')

                    while '\n\n' in buffer:
                        event_block, buffer = buffer.split('\n\n', 1)
                        event_type = None
                        event_data = None

                        for line in event_block.split('\n'):
                            if line.startswith('event: '):
                                event_type = line[7:]
                            elif line.startswith('data: '):
                                try:
                                    event_data = json.loads(line[6:])
                                except json.JSONDecodeError:
                                    event_data = line[6:]

                        if event_type and event_data:
                            callback(event_type, event_data)

            return True

        except Exception:
            return False

    def watch_session(self, session_id: str,
                      on_observation: Optional[callable] = None,
                      on_summary: Optional[callable] = None,
                      timeout: float = 30.0) -> Dict[str, Any]:
        """
        Watch a session for real-time updates.

        Convenience method that sets up SSE subscription for a session.

        Args:
            session_id: Session to watch
            on_observation: Callback for new observations
            on_summary: Callback for summary updates
            timeout: Watch duration

        Returns:
            Summary of watched events
        """
        events_received = {'observations': 0, 'summaries': 0, 'errors': 0}

        def handle_event(event_type: str, event_data: Dict):
            if event_type == 'observation':
                events_received['observations'] += 1
                if on_observation:
                    on_observation(event_data)
            elif event_type == 'summary':
                events_received['summaries'] += 1
                if on_summary:
                    on_summary(event_data)
            elif event_type == 'error':
                events_received['errors'] += 1

        self.subscribe_to_updates(
            ['observation', 'summary', 'error'],
            handle_event,
            duration=timeout
        )

        return events_received

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


def search_by_concept(concept: str, port: int = 37777, limit: int = 5) -> Optional[List[Dict]]:
    """
    Search Claude-Mem for observations by concept tag.

    Args:
        concept: Concept to search (e.g., 'authentication', 'debugging', 'refactoring')
        port: Claude-Mem port
        limit: Maximum results

    Returns:
        List of matching observations or None
    """
    client = ClaudeMemClient(port=port)
    try:
        params = {"concept": concept, "limit": str(limit)}
        query = urllib.parse.urlencode(params)
        url = f"{client.base_url}/api/search/by-concept?{query}"

        with urllib.request.urlopen(url, timeout=client.timeout) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                return data.get('results', [])
    except Exception:
        pass
    return None


def get_patterns_for_tool(tool_name: str, port: int = 37777) -> Optional[List[Dict]]:
    """
    Get stored patterns for a specific tool from Claude-Mem.

    Args:
        tool_name: Tool name (e.g., 'Edit', 'Bash', 'Write')
        port: Claude-Mem port

    Returns:
        List of patterns or None
    """
    client = ClaudeMemClient(port=port)
    return client.search_by_tool(tool_name, limit=5)


def store_batch_observations(observations: List[Dict], port: int = 37777) -> bool:
    """
    Store multiple observations in a single request.

    Args:
        observations: List of observation dicts with session_id, tool_name, etc.
        port: Claude-Mem port

    Returns:
        True on success
    """
    client = ClaudeMemClient(port=port)
    try:
        data = json.dumps({"observations": observations}).encode('utf-8')
        request = urllib.request.Request(
            f"{client.base_url}/api/sessions/observations/batch",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(request, timeout=client.timeout) as response:
            return response.status == 200
    except Exception:
        # Fallback: store individually
        success = True
        for obs in observations:
            if not client.store_observation(
                obs.get('session_id', ''),
                obs.get('tool_name', ''),
                obs.get('tool_input', {}),
                obs.get('tool_response', '')
            ):
                success = False
        return success


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
