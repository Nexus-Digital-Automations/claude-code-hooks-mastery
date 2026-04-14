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

# Only scan these source code extensions
CODE_EXTENSIONS: set[str] = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".go", ".rs", ".rb", ".java", ".kt",
    ".c", ".cpp", ".cc", ".h", ".hpp",
    ".cs", ".swift", ".m", ".mm",
    ".php", ".pl", ".pm", ".lua",
    ".sh", ".bash", ".zsh",
    ".ex", ".exs", ".erl",
    ".hs", ".ml", ".mli",
    ".r", ".R", ".jl",
    ".scala", ".clj", ".cljs",
    ".vue", ".svelte",
}


def _is_scannable(rel_path: str) -> bool:
    """Check if a file is source code worth scanning."""
    for pattern in EXCLUDE_PATTERNS:
        if pattern in rel_path:
            return False
    if "/migrations/" in rel_path:
        filename = rel_path.rsplit("/", 1)[-1] if "/" in rel_path else rel_path
        if filename != "__init__.py":
            return False
    dot = rel_path.rfind(".")
    if dot == -1:
        return False
    ext = rel_path[dot:]
    if ext not in CODE_EXTENSIONS:
        return False
    if ext in (".js", ".css") and (".min." in rel_path or ".bundle." in rel_path or ".chunk." in rel_path):
        return False
    return True


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
        if not _is_scannable(rel_path):
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
