"""Per-session scope declarations.

Owns: the on-disk format of ``<project>/.claude/data/session_scope_{sid}.json``
— the file the agent writes to tell the Stop hook which specs this session
is working on.

Does NOT own: session-id resolution (see stop.py:_resolve_session_id),
spec completion counting (see stop.py:check_spec_completion), or the
decision about whether a missing scope file should fail Phase 1 (that
policy lives in stop.py:_phase_1_implement).

Path resolution: see ``project_config.get_project_data_dir`` — files live
under each project's git root, except the ~/.claude meta-repo, whose
scope files stay at ``~/.claude/data/``.

Called by: hooks/stop.py (reads).  Written by: the agent during a
session, per the Rule 2 workflow in CLAUDE.md.

Scope file schema (one of):
    {"specs": ["/abs/path/to/project/specs/name.md", ...]}  # agent is working on these specs
    {"no_spec": true, "reason": "..."}                      # session has no spec (trivial work)

Specs are identified by absolute path so the agent can declare specs in any
project directory without the Stop hook having to guess which cwd/specs/ to use.
"""

from __future__ import annotations

import json
from pathlib import Path

# Counterpart: get_project_data_dir owns the ~/.claude special case.
from project_config import get_project_data_dir


# @stable — path convention matches verification_record_{sid}.json etc.
def scope_path(session_id: str, cwd: str | None = None) -> Path:
    return get_project_data_dir(cwd) / f"session_scope_{session_id}.json"


# @stable — returns None when the agent has not yet declared scope.
# Callers MUST treat None as "undeclared", not as "no specs".
def load_session_scope(session_id: str, cwd: str | None = None) -> dict | None:
    path = scope_path(session_id, cwd)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
