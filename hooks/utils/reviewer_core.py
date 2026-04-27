"""Re-export shim — delegates to the standalone claude-reviewer package.

The canonical implementation lives at:
  ~/Desktop/Claude Coding Projects/claude-reviewer/src/claude_reviewer/core.py

This file exists so existing callers (reviewer.py, claw_stop.py) can import
from reviewer_core without any changes to their import statements.
"""
import sys
from pathlib import Path

# Package is not globally installed — inject its src dir into sys.path.
# Idempotent: skip if already present from a prior import in this process.
_pkg_src = str(
    Path.home() / "Desktop" / "Claude Coding Projects" / "claude-reviewer" / "src"
)
if _pkg_src not in sys.path:
    sys.path.insert(0, _pkg_src)

from claude_reviewer.core import (  # noqa: F401, E402
    ReviewPacket,
    ReviewerConfig,
    SandboxResult,
    async_call_reviewer,
    call_reviewer,
    format_packet_for_prompt,
)
