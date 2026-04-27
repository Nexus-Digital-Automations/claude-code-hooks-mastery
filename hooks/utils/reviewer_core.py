"""Re-export shim — delegates to the standalone claude-reviewer package.

The canonical implementation lives at:
  ~/Desktop/Claude Coding Projects/claude-reviewer/src/claude_reviewer/core.py

This file exists so existing callers (reviewer.py, claw_stop.py) can import
from reviewer_core without any changes to their import statements.
"""
import os
import sys
from pathlib import Path

# Load ~/.claude/.env into os.environ before the package imports so
# DEEPSEEK_API_KEY (and others) don't need to live in ~/.zshrc.
# Shell-env vars take precedence — existing values are never overwritten.
_dotenv = Path.home() / ".claude" / ".env"
if _dotenv.is_file():
    for _line in _dotenv.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            _k = _k.strip()
            if _k and _k not in os.environ:
                os.environ[_k] = _v.strip().strip('"').strip("'")

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
