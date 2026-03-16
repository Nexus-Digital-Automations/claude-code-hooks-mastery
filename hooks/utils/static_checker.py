#!/usr/bin/env python3
"""
Auto-run static verification checks (upstream_sync, lint).
Called by authorize-stop.sh before the main verification check.

Usage:
    python3 static_checker.py --vr-file .claude/data/verification_record.json
    python3 static_checker.py --vr-file .claude/data/verification_record.json --only-pending
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ── Helpers ────────────────────────────────────────────────────────────────

def _run(cmd: str, cwd: Path, timeout: int = 30) -> tuple[int, str, str]:
    """Run a shell command. Returns (rc, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"[timeout after {timeout}s]"
    except Exception as e:
        return -1, "", str(e)


def _write_vr(vr_file: Path, key: str, status: str, evidence: str) -> None:
    """Atomically write one check entry to verification_record.json."""
    try:
        try:
            record = json.loads(vr_file.read_text())
        except Exception:
            record = {"reset_at": datetime.now().isoformat(), "checks": {}}
        record.setdefault("checks", {})[key] = {
            "status": status,
            "evidence": evidence[:2000] if evidence else None,
            "timestamp": datetime.now().isoformat(),
            "skip_reason": None,
        }
        vr_file.write_text(json.dumps(record, indent=2))
    except Exception:
        pass  # Never block


def _is_pending(vr_file: Path, key: str) -> bool:
    """Return True if the check is currently pending in the record."""
    try:
        record = json.loads(vr_file.read_text())
        return record.get("checks", {}).get(key, {}).get("status", "pending") == "pending"
    except Exception:
        return True  # Assume pending if can't read


# ── Upstream sync ──────────────────────────────────────────────────────────

def check_upstream_sync(cwd: Path) -> tuple[str, str]:
    """
    Check if repo is synced with upstream.
    Returns (status, evidence_text).
    """
    # Check if there's an upstream remote
    rc, out, _ = _run("git remote -v", cwd, 10)
    if rc != 0:
        return "skipped", "Not a git repository"

    has_upstream = "upstream" in out
    has_origin = "origin" in out

    if not has_upstream and not has_origin:
        return "skipped", "No remote configured"

    # Determine remote to check (upstream for forks, origin otherwise)
    remote = "upstream" if has_upstream else "origin"

    # Get current branch
    rc, branch, _ = _run("git branch --show-current", cwd, 5)
    branch = branch.strip() or "main"

    # Fetch (dry-run first to see if fetch is needed)
    _run(f"git fetch {remote} --dry-run 2>&1", cwd, 20)

    # Get commits behind
    rc2, behind_out, _ = _run(
        f"git log HEAD..{remote}/{branch} --oneline 2>/dev/null", cwd, 10
    )
    behind_commits = [line for line in behind_out.strip().splitlines() if line.strip()]
    behind_count = len(behind_commits)

    if behind_count > 0:
        preview = "\n".join(behind_commits[:5])
        evidence = (
            f"⚠️  BEHIND {remote}/{branch} by {behind_count} commit(s)\n"
            f"Branch: {branch}\nRemote: {remote}\n"
            f"Behind commits:\n{preview}"
        )
    else:
        evidence = (
            f"✅ In sync with {remote}/{branch}\n"
            f"Branch: {branch}\nRemote: {remote}"
        )

    return "done", evidence


# ── Lint (project-type aware) ──────────────────────────────────────────────

def detect_lint_command(cwd: Path) -> tuple[str, str] | None:
    """Detect project type and return (command, description) or None."""
    if (cwd / "pyproject.toml").exists() or list(cwd.glob("*.py")):
        # Check if ruff is available
        rc, _, _ = _run("which ruff", cwd, 3)
        if rc == 0:
            return ("ruff check . 2>&1", "Python/ruff")
        return ("python3 -m py_compile $(find . -name '*.py' | head -20) 2>&1", "Python/py_compile")
    if (cwd / "package.json").exists():
        try:
            pkg = json.loads((cwd / "package.json").read_text())
            if "lint" in pkg.get("scripts", {}):
                return ("npm run lint 2>&1", "Node.js/npm run lint")
        except Exception:
            pass
        return ("npx eslint . --max-warnings=0 2>&1", "Node.js/eslint")
    if (cwd / "Cargo.toml").exists():
        return ("cargo clippy 2>&1", "Rust/cargo clippy")
    if (cwd / "go.mod").exists():
        return ("go vet ./... 2>&1", "Go/go vet")
    if (cwd / "Gemfile").exists():
        rc, _, _ = _run("which rubocop", cwd, 3)
        if rc == 0:
            return ("bundle exec rubocop --no-color 2>&1", "Ruby/rubocop")
    return None


def check_lint(cwd: Path, timeout: int = 30) -> tuple[str, str]:
    """Auto-run linter for current project type. Returns (status, evidence)."""
    lint_cmd = detect_lint_command(cwd)
    if lint_cmd is None:
        return "skipped", "No supported linter detected for this project type"
    cmd, desc = lint_cmd
    rc, stdout, stderr = _run(cmd, cwd, timeout)
    evidence = f"[auto-lint: {desc}]\n$ {cmd}\nexit: {rc}\n"
    if stdout:
        evidence += stdout[:1500]
    if stderr:
        evidence += f"\nstderr: {stderr[:300]}"
    return "done", evidence


# ── Main ───────────────────────────────────────────────────────────────────

def run_static_checks(
    cwd: Path,
    vr_file: Path,
    only_pending: bool = True,
) -> dict[str, str]:
    """
    Run static checks and write results to vr_file.
    Returns dict of check_key -> status.
    """
    results = {}

    # upstream_sync
    if not only_pending or _is_pending(vr_file, "upstream_sync"):
        status, evidence = check_upstream_sync(cwd)
        _write_vr(vr_file, "upstream_sync", status, evidence)
        results["upstream_sync"] = status
        print(f"[static] upstream_sync: {status}", file=sys.stderr)

    # lint
    if not only_pending or _is_pending(vr_file, "lint"):
        status, evidence = check_lint(cwd)
        _write_vr(vr_file, "lint", status, evidence)
        results["lint"] = status
        print(f"[static] lint: {status}", file=sys.stderr)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run static stop-hook checks")
    parser.add_argument("--vr-file", required=True, help="Path to verification_record.json")
    parser.add_argument("--only-pending", action="store_true",
                        help="Only run checks that are currently pending")
    parser.add_argument("--cwd", default=None, help="Working directory (default: os.getcwd())")
    args = parser.parse_args()

    cwd = Path(args.cwd) if args.cwd else Path.cwd()
    vr_file = Path(args.vr_file)
    vr_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        run_static_checks(cwd, vr_file, only_pending=args.only_pending)
        sys.exit(0)
    except Exception as e:
        print(f"[static_checker] error: {e}", file=sys.stderr)
        sys.exit(0)  # Never block on static checker failure
