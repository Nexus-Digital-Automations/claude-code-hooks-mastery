#!/usr/bin/env python3
"""
Project Name Utility

Extracts project name from git repository or falls back to directory name.
Used by TTS system to include project name in completion messages.
"""

import os
import re
import subprocess
from pathlib import Path


def get_project_name():
    """
    Get the project name using the following priority:
    1. Environment variable PROJECT_NAME (if set)
    2. Git repository name from remote URL
    3. Git repository name from .git/config
    4. Current directory name (fallback)

    Returns:
        str: Sanitized project name (lowercase, alphanumeric + hyphens)
    """
    # Priority 1: Check environment variable override
    env_name = os.getenv('PROJECT_NAME')
    if env_name:
        return sanitize_project_name(env_name)

    # Priority 2: Try git remote URL
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.getcwd()
        )
        if result.returncode == 0 and result.stdout.strip():
            repo_url = result.stdout.strip()
            name = extract_repo_name_from_url(repo_url)
            if name:
                return sanitize_project_name(name)
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        pass

    # Priority 3: Try .git/config file parsing
    try:
        git_config = Path('.git/config')
        if git_config.exists():
            with open(git_config, 'r') as f:
                content = f.read()
                # Look for [remote "origin"] url line
                match = re.search(r'\[remote "origin"\].*?url\s*=\s*(.+?)(?:\n|$)', content, re.DOTALL)
                if match:
                    repo_url = match.group(1).strip()
                    name = extract_repo_name_from_url(repo_url)
                    if name:
                        return sanitize_project_name(name)
    except (IOError, OSError):
        pass

    # Priority 4: Fallback to directory name
    current_dir = Path.cwd()
    return sanitize_project_name(current_dir.name)


def extract_repo_name_from_url(url):
    """
    Extract repository name from git URL.

    Handles formats:
    - https://github.com/user/repo.git
    - git@github.com:user/repo.git
    - https://github.com/user/repo
    - /path/to/repo.git

    Args:
        url (str): Git repository URL

    Returns:
        str: Repository name without .git suffix, or None if extraction fails
    """
    if not url:
        return None

    # Remove .git suffix if present
    if url.endswith('.git'):
        url = url[:-4]

    # Extract the last path component
    # Handle both https://github.com/user/repo and git@github.com:user/repo
    if '/' in url:
        repo_name = url.split('/')[-1]
    elif ':' in url:
        # git@github.com:user/repo format
        repo_name = url.split(':')[-1].split('/')[-1]
    else:
        repo_name = url

    return repo_name.strip()


def sanitize_project_name(name):
    """
    Sanitize project name for use in TTS messages.

    - Convert to lowercase
    - Replace underscores with hyphens
    - Remove special characters except hyphens
    - Remove leading/trailing hyphens
    - Collapse multiple hyphens

    Args:
        name (str): Raw project name

    Returns:
        str: Sanitized project name suitable for speech
    """
    if not name:
        return "project"

    # Convert to lowercase
    name = name.lower()

    # Replace underscores with hyphens
    name = name.replace('_', '-')

    # Remove all characters except alphanumeric and hyphens
    name = re.sub(r'[^a-z0-9-]', '', name)

    # Collapse multiple hyphens
    name = re.sub(r'-+', '-', name)

    # Remove leading/trailing hyphens
    name = name.strip('-')

    # If empty after sanitization, return default
    if not name:
        return "project"

    return name


def main():
    """Command-line interface for testing."""
    project_name = get_project_name()
    print(project_name)


if __name__ == '__main__':
    main()
