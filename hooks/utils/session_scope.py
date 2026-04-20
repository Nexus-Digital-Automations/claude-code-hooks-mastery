"""Per-session scope declarations.

Owns: the on-disk format of ``~/.claude/data/session_scope_{sid}.json`` —
the file the agent writes to tell the Stop hook which specs this session
is working on.

Does NOT own: session-id resolution (see stop.py:_resolve_session_id),
spec completion counting (see stop.py:check_spec_completion), or the
decision about whether a missing scope file should fail Phase 1 (that
policy lives in stop.py:_phase_1_implement).

Called by: hooks/stop.py (reads).  Written by: the agent during a
session, per the Rule 2 workflow in CLAUDE.md.

Scope file schema (one of):
    {"specs": ["name.md", ...]}           # agent is working on these specs
    {"no_spec": true, "reason": "..."}    # session has no spec (trivial work)
"""

from __future__ import annotations

import json
from pathlib import Path


# @stable — path convention matches verification_record_{sid}.json etc.
def scope_path(session_id: str) -> Path:
    return Path.home() / f".claude/data/session_scope_{session_id}.json"


# @stable — returns None when the agent has not yet declared scope.
# Callers MUST treat None as "undeclared", not as "no specs".
def load_session_scope(session_id: str) -> dict | None:
    path = scope_path(session_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
