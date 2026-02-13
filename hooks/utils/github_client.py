"""
GitHub integration client for repository analysis, PR management, and code review.
Supports both Claude-Flow and Flow-Nexus GitHub tools.
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


class GitHubClient:
    """
    Client for GitHub integration via MCP tools.

    Supports:
    - Repository analysis
    - Pull request management
    - Automated code review
    - Issue tracking
    - Release coordination
    - Workflow automation
    """

    def __init__(self, timeout: Optional[float] = None, use_flow_nexus: bool = False):
        """
        Initialize GitHub client.

        Args:
            timeout: Operation timeout in seconds
            use_flow_nexus: Use Flow-Nexus for enhanced GitHub features
        """
        self.config = get_config()
        self.timeout = timeout or self.config.get_timeout('github')
        self.use_flow_nexus = use_flow_nexus and self.config.is_server_enabled('flow-nexus')
        self.log_dir = self.config.get_log_dir()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / 'github_client.jsonl'

    def _log(self, operation: str, params: Dict, result: Any, success: bool, elapsed: float):
        """Log GitHub operation."""
        try:
            entry = {
                'timestamp': datetime.now().isoformat(),
                'operation': operation,
                'params': {k: str(v)[:100] for k, v in params.items()},
                'success': success,
                'elapsed_ms': round(elapsed * 1000, 2)
            }
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

    def _call_tool(self, tool_name: str, params: Dict, timeout: Optional[float] = None) -> Optional[Dict]:
        """Call MCP tool via subprocess."""
        if not self.config.is_feature_enabled('github'):
            return None

        use_timeout = timeout or self.timeout
        server = 'flow-nexus' if self.use_flow_nexus else 'claude-flow'

        start_time = time.time()
        try:
            if server == 'flow-nexus':
                cmd = ['npx', 'flow-nexus@latest', 'mcp', 'call', tool_name, json.dumps(params)]
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
    # REPOSITORY ANALYSIS
    # =========================================================================

    def repo_analyze(self, repo: str, analysis_type: str = 'code_quality') -> Optional[Dict]:
        """
        Analyze a GitHub repository.

        Args:
            repo: Repository name (owner/repo) or '.' for current
            analysis_type: Analysis type (code_quality, performance, security)

        Returns:
            Repository analysis result
        """
        return self._call_tool('github_repo_analyze', {
            'repo': repo,
            'analysis_type': analysis_type
        })

    def repo_metrics(self, repo: str) -> Optional[Dict]:
        """
        Get repository metrics.

        Args:
            repo: Repository name (owner/repo)

        Returns:
            Repository metrics
        """
        return self._call_tool('github_metrics', {'repo': repo})

    # =========================================================================
    # PULL REQUEST MANAGEMENT
    # =========================================================================

    def pr_manage(self, repo: str, action: str, pr_number: Optional[int] = None) -> Optional[Dict]:
        """
        Manage pull requests.

        Args:
            repo: Repository name
            action: Action (review, merge, close, list)
            pr_number: PR number (required for review, merge, close)

        Returns:
            PR management result
        """
        params = {'repo': repo, 'action': action}
        if pr_number:
            params['pr_number'] = pr_number
        return self._call_tool('github_pr_manage', params)

    def pr_review(self, repo: str, pr_number: int) -> Optional[Dict]:
        """Review a pull request."""
        return self.pr_manage(repo, 'review', pr_number)

    def pr_merge(self, repo: str, pr_number: int) -> Optional[Dict]:
        """Merge a pull request."""
        return self.pr_manage(repo, 'merge', pr_number)

    def pr_close(self, repo: str, pr_number: int) -> Optional[Dict]:
        """Close a pull request."""
        return self.pr_manage(repo, 'close', pr_number)

    def pr_list(self, repo: str) -> Optional[List]:
        """List open pull requests."""
        result = self.pr_manage(repo, 'list')
        return result.get('pull_requests', []) if result else None

    # =========================================================================
    # CODE REVIEW
    # =========================================================================

    def code_review(self, repo: str, pr: int) -> Optional[Dict]:
        """
        Perform automated code review.

        Args:
            repo: Repository name
            pr: Pull request number

        Returns:
            Code review result
        """
        return self._call_tool('github_code_review', {
            'repo': repo,
            'pr': pr
        })

    # =========================================================================
    # ISSUE TRACKING
    # =========================================================================

    def issue_track(self, repo: str, action: str, issue_number: Optional[int] = None,
                    data: Optional[Dict] = None) -> Optional[Dict]:
        """
        Track and manage issues.

        Args:
            repo: Repository name
            action: Action (list, get, create, update, close, triage)
            issue_number: Issue number (for get, update, close)
            data: Issue data (for create, update)

        Returns:
            Issue tracking result
        """
        params = {'repo': repo, 'action': action}
        if issue_number:
            params['issue_number'] = issue_number
        if data:
            params['data'] = data
        return self._call_tool('github_issue_track', params)

    def issue_list(self, repo: str) -> Optional[List]:
        """List open issues."""
        result = self.issue_track(repo, 'list')
        return result.get('issues', []) if result else None

    def issue_triage(self, repo: str) -> Optional[Dict]:
        """Triage repository issues."""
        return self.issue_track(repo, 'triage')

    # =========================================================================
    # RELEASE COORDINATION
    # =========================================================================

    def release_coord(self, repo: str, version: str, options: Optional[Dict] = None) -> Optional[Dict]:
        """
        Coordinate a release.

        Args:
            repo: Repository name
            version: Release version
            options: Release options

        Returns:
            Release coordination result
        """
        params = {'repo': repo, 'version': version}
        if options:
            params.update(options)
        return self._call_tool('github_release_coord', params)

    # =========================================================================
    # WORKFLOW AUTOMATION
    # =========================================================================

    def workflow_auto(self, repo: str, workflow: Dict) -> Optional[Dict]:
        """
        Automate GitHub workflows.

        Args:
            repo: Repository name
            workflow: Workflow configuration

        Returns:
            Workflow automation result
        """
        return self._call_tool('github_workflow_auto', {
            'repo': repo,
            'workflow': workflow
        })

    # =========================================================================
    # MULTI-REPO SYNC
    # =========================================================================

    def sync_coord(self, repos: List[str]) -> Optional[Dict]:
        """
        Coordinate synchronization across multiple repositories.

        Args:
            repos: List of repository names

        Returns:
            Sync coordination result
        """
        return self._call_tool('github_sync_coord', {'repos': repos})

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def is_available(self) -> bool:
        """Check if GitHub services are available."""
        try:
            # Try a lightweight operation
            result = self.repo_metrics('.')
            return result is not None
        except Exception:
            return False

    def get_current_repo(self) -> Optional[str]:
        """Get the current repository name from git."""
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                url = result.stdout.strip()
                # Extract owner/repo from URL
                if 'github.com' in url:
                    # Handle both HTTPS and SSH URLs
                    if url.startswith('git@'):
                        # git@github.com:owner/repo.git
                        parts = url.split(':')[1].replace('.git', '')
                    else:
                        # https://github.com/owner/repo.git
                        parts = url.split('github.com/')[1].replace('.git', '')
                    return parts
        except Exception:
            pass
        return None


# Convenience function
def get_github_client(timeout: Optional[float] = None, use_flow_nexus: bool = False) -> GitHubClient:
    """Get a GitHub client instance."""
    return GitHubClient(timeout=timeout, use_flow_nexus=use_flow_nexus)
