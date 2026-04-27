"""File-size justification registry.

Owns: persistent record of agent-acknowledged oversized files and their
reasons. When a loud-tier file (>800 lines) has a registered entry, stop.py
Phase 1 treats it as acknowledged and does not block.

Does NOT own: the scanning itself (file_size_scanner.py) or the blocking
decision logic (stop.py Phase 1 calls unjustified_loud()).

Called by: stop.py (Phase 1 gate) and reviewer.py (packet population).
Counterpart: file_size_scanner.py provides LOUD_THRESHOLD and scan results.

State file: <project_data_dir>/file_size_justifications.json
Schema: {rel_path: {reason, tier, line_count_at_registration, registered_at}}

CLI (run from project root):
    python3 hooks/utils/file_size_registry.py register <rel_path> "<reason>"
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _registry_path(project_root: Path) -> Path:
    sys.path.insert(0, str(Path(__file__).parent))
    from project_config import get_project_data_dir
    return Path(get_project_data_dir(str(project_root))) / "file_size_justifications.json"


class FileSizeRegistry:
    """Registry of developer-acknowledged oversized files.

    # States: unloaded → loaded (after .load())
    # load() is idempotent; missing file → empty registry (not an error).
    """

    def __init__(self, project_root: Path) -> None:
        self._path = _registry_path(project_root)
        self._data: dict[str, Any] = {}

    def load(self) -> FileSizeRegistry:
        try:
            self._data = json.loads(self._path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}
        return self

    def is_justified(self, rel_path: str) -> bool:
        return rel_path in self._data

    def register(self, rel_path: str, reason: str, line_count: int, tier: str) -> None:
        self._data[rel_path] = {
            "reason": reason,
            "tier": tier,
            "line_count_at_registration": line_count,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))

    def unjustified_loud(self, oversized: list[tuple[str, int]]) -> list[tuple[str, int]]:
        """Return loud-tier files that have no registered justification."""
        from file_size_scanner import LOUD_THRESHOLD
        return [(p, c) for p, c in oversized if c > LOUD_THRESHOLD and not self.is_justified(p)]

    def as_review_dict(self) -> dict[str, Any]:
        return dict(self._data)


def _cli_register(rel_path: str, reason: str) -> None:
    project_root = Path.cwd()
    try:
        line_count = sum(1 for _ in open(project_root / rel_path, encoding="utf-8", errors="replace"))
    except OSError:
        line_count = 0
    from file_size_scanner import LOUD_THRESHOLD
    tier = "800+" if line_count > LOUD_THRESHOLD else "400-799"
    FileSizeRegistry(project_root).load().register(rel_path, reason, line_count, tier)
    print(f"✅ Registered: {rel_path} ({line_count} lines, {tier}) — {reason}")


if __name__ == "__main__":
    if len(sys.argv) < 4 or sys.argv[1] != "register":
        print(
            'Usage: python3 file_size_registry.py register <rel_path> "<reason>"',
            file=sys.stderr,
        )
        sys.exit(1)
    _cli_register(sys.argv[2], sys.argv[3])
