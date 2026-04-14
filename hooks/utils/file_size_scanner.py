"""File-size scanner — warns about oversized files.

Public interface:
    scan_oversized_files(project_root, threshold=400) -> list[tuple[str, int]]
        Returns [(relative_path, line_count), ...] sorted by line_count desc.
        Never raises — all errors result in an empty list.

    format_warning(oversized, threshold=400) -> str
        Formatted warning string for stderr output.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

# ── Configuration ───────────────────────────────────────────────────────

DEFAULT_THRESHOLD = 400
MAX_DISPLAY = 15

# Directory fragments to exclude (auto-generated / vendored / build output)
EXCLUDE_PATTERNS: set[str] = {
    "node_modules/",
    "vendor/",
    "__pycache__/",
    "coverage/",
    "build/",
    "dist/",
    ".next/",
    ".nuxt/",
    ".claude-flow/",
}

EXCLUDE_SUFFIXES: tuple[str, ...] = (
    ".min.js",
    ".min.css",
    ".map",
    ".pyc",
    ".pyo",
    ".bundle.js",
    ".bundle.css",
    ".chunk.js",
    ".chunk.css",
    ".json",
    ".jsonl",
    ".csv",
    ".xml",
    ".svg",
    ".lock",
)

EXCLUDE_FILENAMES: set[str] = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
    "Cargo.lock",
    "go.sum",
}


def _is_excluded(rel_path: str) -> bool:
    """Check if a relative path should be excluded from scanning."""
    for pattern in EXCLUDE_PATTERNS:
        if pattern in rel_path:
            return True
    filename = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
    if filename in EXCLUDE_FILENAMES:
        return True
    if rel_path.endswith(EXCLUDE_SUFFIXES):
        return True
    if "/migrations/" in rel_path and filename != "__init__.py":
        return True
    return False


def _count_lines(filepath: Path) -> int | None:
    """Count lines in a text file. Returns None for binary/unreadable."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="strict") as f:
            return sum(1 for _ in f)
    except (UnicodeDecodeError, OSError, PermissionError):
        return None


def scan_oversized_files(
    project_root: Path,
    threshold: int = DEFAULT_THRESHOLD,
) -> list[tuple[str, int]]:
    """Scan git-tracked files and return those exceeding *threshold* lines.

    Returns [(relative_path, line_count), ...] sorted by line_count desc.
    Never raises.
    """
    try:
        r = subprocess.run(
            ["git", "ls-files", "-z"],
            capture_output=True, text=True, timeout=10,
            cwd=str(project_root),
        )
        if r.returncode != 0:
            return []
        files = [f for f in r.stdout.split("\0") if f]
    except Exception:
        return []

    oversized: list[tuple[str, int]] = []
    for rel_path in files:
        if _is_excluded(rel_path):
            continue
        count = _count_lines(project_root / rel_path)
        if count is not None and count > threshold:
            oversized.append((rel_path, count))

    oversized.sort(key=lambda x: x[1], reverse=True)
    return oversized


def format_warning(
    oversized: list[tuple[str, int]],
    threshold: int = DEFAULT_THRESHOLD,
) -> str:
    """Format the oversized-files warning for stderr output."""
    if not oversized:
        return ""
    lines = [
        f"  [file-size] WARNING: {len(oversized)} file(s) exceed"
        f" {threshold} lines"
    ]
    for rel_path, count in oversized[:MAX_DISPLAY]:
        lines.append(f"    {rel_path:<60s} {count:>5d} lines")
    remainder = len(oversized) - MAX_DISPLAY
    if remainder > 0:
        lines.append(f"    ... and {remainder} more")
    return "\n".join(lines)
