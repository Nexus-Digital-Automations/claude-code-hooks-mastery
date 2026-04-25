"""Canonical validation-artifacts directory accessor.

Session telemetry (summaries, lessons, task metrics, architectural decisions,
error catalogs, etc.) lives at ``<project>/.claude/artifacts/`` — a
project-scoped path so each project owns its own telemetry.

Counterpart: ``project_config.get_project_data_dir`` (the per-project state
directory; this module owns the sibling ``artifacts/`` directory).

All producers and consumers MUST go through :func:`get_validation_artifacts_dir`
so writers and readers stay in sync.
"""

from __future__ import annotations

from pathlib import Path


def get_validation_artifacts_dir(cwd: str | None = None) -> Path:
    """Return the validation-artifacts directory for the project at *cwd*.

    Never writes to the global ``~/.claude/`` namespace (historical bug).
    For the ``~/.claude`` meta-repo: returns ``~/.claude/artifacts/``.
    For every other project: returns ``<git_root>/.claude/artifacts/``.
    """
    from project_config import get_project_data_dir
    proj_data = get_project_data_dir(cwd)
    # sibiling of .claude/data/ → .claude/artifacts/
    artifacts_dir = proj_data.parent / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir
