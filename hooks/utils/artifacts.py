"""Canonical validation-artifacts directory accessor.

Session telemetry (summaries, lessons, task metrics, architectural decisions,
error catalogs, etc.) lives at ``~/.claude/.validation-artifacts/`` — an
absolute path that does NOT depend on the current working directory. This
prevents hooks from dirtying whichever project repo Claude Code was invoked in.

Historical bug: hooks used ``Path(".validation-artifacts")`` which resolved
against cwd. When cwd was a project repo that didn't gitignore the path, the
write polluted the project tree after every session end and created a chronic
commit loop (see PR #1 — "fix: session_end telemetry writes must use absolute
paths").

All producers and consumers MUST go through :func:`get_validation_artifacts_dir`
so writers and readers stay in sync. Direct ``Path(".validation-artifacts")``
uses in hook code are a regression of the same bug.
"""

from __future__ import annotations

from pathlib import Path


def get_validation_artifacts_dir() -> Path:
    """Return the canonical validation-artifacts directory, creating it if missing.

    Always returns an absolute path rooted at ``~/.claude/.validation-artifacts``.
    The return value is independent of cwd — safe to call from any hook
    regardless of which project Claude Code was invoked in.
    """
    artifacts_dir = Path.home() / ".claude" / ".validation-artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir
