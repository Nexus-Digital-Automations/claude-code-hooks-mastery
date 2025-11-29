#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Git Utilities for Claude Code Hooks

Helper functions for extracting git repository information:
- Current branch
- Uncommitted file count
- Recent commits
- Git status

These utilities support context-aware guidance generation by providing
information about the project's git state.
"""

import subprocess
from typing import Dict, Any, List, Optional
from pathlib import Path


def get_git_status(working_dir: Path = None) -> Dict[str, Any]:
    """
    Get comprehensive git status information.

    Args:
        working_dir: Working directory (defaults to current directory)

    Returns:
        Dictionary containing:
        - branch: Current branch name
        - uncommitted: Number of uncommitted files
        - untracked: Number of untracked files
        - ahead: Commits ahead of remote
        - behind: Commits behind remote
        - is_git_repo: Whether this is a git repository
    """
    if working_dir:
        cwd = str(working_dir)
    else:
        cwd = None

    try:
        # Check if this is a git repository
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode != 0:
            return {'is_git_repo': False}

        # Get current branch
        branch = get_current_branch(cwd)

        # Get uncommitted file count
        uncommitted = get_uncommitted_file_count(cwd)

        # Get untracked file count
        untracked = get_untracked_file_count(cwd)

        # Get ahead/behind counts
        ahead, behind = get_ahead_behind_counts(cwd)

        return {
            'is_git_repo': True,
            'branch': branch,
            'uncommitted': uncommitted,
            'untracked': untracked,
            'ahead': ahead,
            'behind': behind
        }

    except Exception:
        return {'is_git_repo': False}


def get_current_branch(cwd: str = None) -> str:
    """
    Get the current git branch name.

    Args:
        cwd: Working directory

    Returns:
        Branch name or 'unknown'
    """
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode == 0:
            return result.stdout.strip()

    except Exception:
        pass

    return 'unknown'


def get_uncommitted_file_count(cwd: str = None) -> int:
    """
    Get count of modified files (staged and unstaged).

    Args:
        cwd: Working directory

    Returns:
        Number of uncommitted files
    """
    try:
        # Get staged and unstaged files
        result = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode == 0:
            lines = [line for line in result.stdout.split('\n') if line.strip()]
            return len(lines)

    except Exception:
        pass

    return 0


def get_untracked_file_count(cwd: str = None) -> int:
    """
    Get count of untracked files.

    Args:
        cwd: Working directory

    Returns:
        Number of untracked files
    """
    try:
        result = subprocess.run(
            ['git', 'ls-files', '--others', '--exclude-standard'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode == 0:
            lines = [line for line in result.stdout.split('\n') if line.strip()]
            return len(lines)

    except Exception:
        pass

    return 0


def get_ahead_behind_counts(cwd: str = None) -> tuple[int, int]:
    """
    Get commits ahead/behind remote.

    Args:
        cwd: Working directory

    Returns:
        Tuple of (ahead_count, behind_count)
    """
    try:
        result = subprocess.run(
            ['git', 'rev-list', '--left-right', '--count', 'HEAD...@{upstream}'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode == 0:
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])
                return (ahead, behind)

    except Exception:
        pass

    return (0, 0)


def get_recent_commits(count: int = 5, cwd: str = None) -> List[str]:
    """
    Get recent commit messages.

    Args:
        count: Number of commits to retrieve
        cwd: Working directory

    Returns:
        List of commit messages
    """
    try:
        result = subprocess.run(
            ['git', 'log', f'-{count}', '--pretty=format:%s'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode == 0:
            lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            return lines

    except Exception:
        pass

    return []


def is_file_tracked(file_path: str, cwd: str = None) -> bool:
    """
    Check if a file is tracked by git.

    Args:
        file_path: Path to file
        cwd: Working directory

    Returns:
        True if file is tracked, False otherwise
    """
    try:
        result = subprocess.run(
            ['git', 'ls-files', '--error-unmatch', file_path],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        return result.returncode == 0

    except Exception:
        return False


def get_staged_files(cwd: str = None) -> List[str]:
    """
    Get list of staged files.

    Args:
        cwd: Working directory

    Returns:
        List of staged file paths
    """
    try:
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode == 0:
            return [line.strip() for line in result.stdout.split('\n') if line.strip()]

    except Exception:
        pass

    return []


def check_for_secrets_in_diff(cwd: str = None) -> bool:
    """
    Check if git diff contains potential secrets.

    Uses security patterns from infinite-continue-stop-hook.

    Args:
        cwd: Working directory

    Returns:
        True if secrets detected, False otherwise
    """
    import re

    secrets_patterns = [
        r'password', r'api[_-]?key', r'secret', r'token',
        r'AKIA', r'sk-', r'ghp_', r'glpat', r'xox[baprs]-',
        r'bearer', r'authorization:', r'private[_-]?key'
    ]

    try:
        # Check staged changes
        result = subprocess.run(
            ['git', 'diff', '--cached'],
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=2
        )

        if result.returncode == 0:
            diff_content = result.stdout

            for pattern in secrets_patterns:
                if re.search(pattern, diff_content, re.IGNORECASE):
                    return True

    except Exception:
        pass

    return False


if __name__ == '__main__':
    # Simple test
    status = get_git_status()
    print("Git Status:")
    print(f"  Is Git Repo: {status.get('is_git_repo')}")
    print(f"  Branch: {status.get('branch')}")
    print(f"  Uncommitted: {status.get('uncommitted')}")
    print(f"  Untracked: {status.get('untracked')}")
    print(f"  Ahead: {status.get('ahead')}")
    print(f"  Behind: {status.get('behind')}")

    print("\nRecent Commits:")
    for commit in get_recent_commits(3):
        print(f"  - {commit}")

    print("\nStaged Files:")
    for file in get_staged_files():
        print(f"  - {file}")

    secrets_detected = check_for_secrets_in_diff()
    print(f"\nSecrets in diff: {secrets_detected}")
