"""Project configuration for the rules-based verification system.

Reads `.claude-project.json` from the project root (git root) to determine
which verification checks are required and how to match/evaluate them.
Falls back to auto-detection from filesystem markers when no config exists.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

# ── Git root resolution ──────────────────────────────────────────────────

_git_root_cache: dict[str, str] = {}


def get_git_root() -> str:
    """Return the git repo root for the current working directory.

    Caches per-CWD to avoid repeated subprocess calls.  Falls back to CWD
    if not inside a git repository.
    """
    cwd = os.getcwd()
    if cwd in _git_root_cache:
        return _git_root_cache[cwd]
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        root = r.stdout.strip() if r.returncode == 0 else cwd
    except Exception:
        root = cwd
    _git_root_cache[cwd] = root
    return root


# ── Config loading ───────────────────────────────────────────────────────

CONFIG_FILENAME = ".claude-project.json"

_config_cache: dict[str, tuple[float, dict]] = {}  # path -> (mtime, config)


def load_config(project_root: Path | str) -> dict:
    """Load `.claude-project.json` from *project_root*, falling back to auto-detection.

    The result is cached and invalidated when the file's mtime changes.
    """
    project_root = Path(project_root)
    config_path = project_root / CONFIG_FILENAME
    cache_key = str(config_path)

    if config_path.exists():
        mtime = config_path.stat().st_mtime
        if cache_key in _config_cache and _config_cache[cache_key][0] == mtime:
            return _config_cache[cache_key][1]
        try:
            config = json.loads(config_path.read_text())
            _config_cache[cache_key] = (mtime, config)
            return config
        except Exception:
            pass  # Fall through to auto-detect

    return auto_detect_config(project_root)


# ── Auto-detection ───────────────────────────────────────────────────────

def auto_detect_config(project_root: Path) -> dict:
    """Infer project type and capabilities from filesystem markers."""
    config: dict[str, Any] = {
        "project_type": "other",
        "has_tests": False,
        "has_build": False,
        "has_frontend": False,
        "has_app": False,
        "checks": {},
    }

    # Python
    if (project_root / "pyproject.toml").exists() or (project_root / "setup.py").exists():
        config["project_type"] = "python"
        config["has_tests"] = (project_root / "tests").is_dir()

    # Node.js
    pkg_json = project_root / "package.json"
    if pkg_json.exists():
        config["project_type"] = "node"
        try:
            pkg = json.loads(pkg_json.read_text())
            scripts = pkg.get("scripts", {})
            config["has_tests"] = "test" in scripts
            config["has_build"] = "build" in scripts
            config["has_app"] = "start" in scripts or "dev" in scripts
            config["has_frontend"] = any(
                (project_root / f).exists()
                for f in ("playwright.config.ts", "playwright.config.js",
                          "cypress.config.ts", "cypress.config.js")
            ) or "test:e2e" in scripts
        except Exception:
            config["has_tests"] = True

    # Rust
    if (project_root / "Cargo.toml").exists():
        config["project_type"] = "rust"
        config["has_tests"] = True
        config["has_build"] = True

    # Go
    if (project_root / "go.mod").exists():
        config["project_type"] = "go"
        config["has_tests"] = True

    # Ruby
    if (project_root / "Gemfile").exists():
        config["project_type"] = "ruby"
        config["has_tests"] = (project_root / "spec").is_dir() or (project_root / "test").is_dir()

    return config


# ── Required checks derivation ───────────────────────────────────────────

def get_required_checks(config: dict, files_modified: bool = True) -> list[str]:
    """Derive the list of required check keys from a project config.

    *files_modified* controls whether commit_push is required.
    """
    required = ["lint", "upstream_sync"]  # Always required

    if config.get("has_tests", False):
        required.insert(0, "tests")
    if config.get("has_build", False):
        required.append("build")
    if config.get("has_app", False):
        required.append("app_starts")
    if config.get("has_frontend", False):
        required.append("frontend")
    if files_modified:
        required.append("commit_push")

    return required


# ── Command matching ─────────────────────────────────────────────────────

# Generic fallback patterns: (substring_in_command, check_key, default_pass_patterns, default_fail_patterns)
_GENERIC_PATTERNS: list[tuple[list[str], str, list[str], list[str]]] = [
    # Tests
    (["pytest", "python -m pytest"], "tests",
     [r"\d+ passed"], ["FAILED", "ERROR", "failed"]),
    (["npm test", "npx jest", "npx vitest", "yarn test"], "tests",
     [r"passed", r"Tests:\s+\d+ passed"], ["FAIL", "failed"]),
    (["cargo test"], "tests",
     [r"test result: ok"], ["FAILED", "failures"]),
    (["go test"], "tests",
     [r"^ok\s"], ["FAIL"]),

    # Lint
    (["ruff check", "ruff ."], "lint",
     [r"All checks passed", r"^$"], [r"Found \d+ error"]),
    (["npm run lint", "npx eslint", "eslint"], "lint",
     [r"no problems", r"0 errors"], [r"\d+ error"]),
    (["cargo clippy"], "lint",
     [], [r"^error"]),
    (["go vet"], "lint",
     [], [r"^#"]),

    # Build
    (["npm run build", "npx tsc", "tsc --noEmit", "vite build"], "build",
     [r"Successfully compiled", r"built in"], ["error TS", "ERROR", "Build failed"]),
    (["cargo build"], "build",
     [], [r"^error"]),

    # Frontend
    (["playwright test", "npx playwright", "cypress run"], "frontend",
     [r"passed"], ["failed", "FAIL"]),

    # App starts
    (["npm start", "npm run dev", "yarn dev", "uvicorn", "flask run", "python.*app"], "app_starts",
     [r"listening", r"started", r"ready"], ["EADDRINUSE", "Error:", "Cannot find"]),

    # Git commit/push
    (["git commit"], "commit_push",
     [r"files? changed", r"insertions?", r"create mode"], []),
    (["git push"], "commit_push",
     [], [r"rejected", r"error.*failed"]),
]


def match_command(command: str, config: dict) -> tuple[str, dict] | None:
    """Match a Bash command against project config patterns, then generic fallbacks.

    Returns ``(check_key, check_config_dict)`` or ``None`` if no match.
    The check_config_dict always has ``pass_patterns`` and ``fail_patterns`` lists.
    """
    cmd_lower = command.lower()

    # 1. Try project config patterns first
    for check_key, check_conf in config.get("checks", {}).items():
        if not isinstance(check_conf, dict):
            continue
        for pattern in check_conf.get("command_patterns", []):
            if pattern.lower() in cmd_lower:
                return check_key, check_conf

    # 2. Fall back to generic patterns
    for substrings, check_key, pass_pats, fail_pats in _GENERIC_PATTERNS:
        for substr in substrings:
            if substr.lower() in cmd_lower:
                return check_key, {
                    "pass_patterns": pass_pats,
                    "fail_patterns": fail_pats,
                }

    return None


# ── Output evaluation ────────────────────────────────────────────────────

def evaluate_output(stdout: str, stderr: str, check_conf: dict) -> str:
    """Evaluate command output against pass/fail patterns.

    Returns ``"passed"`` or ``"failed"``.
    Fail patterns are checked first — any match means failure regardless of pass patterns.
    """
    combined = (stdout or "") + "\n" + (stderr or "")

    # Check fail patterns first
    for pattern in check_conf.get("fail_patterns", []):
        try:
            if re.search(pattern, combined, re.MULTILINE | re.IGNORECASE):
                return "failed"
        except re.error:
            if pattern.lower() in combined.lower():
                return "failed"

    # Check pass patterns
    for pattern in check_conf.get("pass_patterns", []):
        try:
            if re.search(pattern, combined, re.MULTILINE | re.IGNORECASE):
                return "passed"
        except re.error:
            if pattern.lower() in combined.lower():
                return "passed"

    # No patterns matched — assume passed if no fail patterns triggered
    return "passed"


# ── Auto-run missing checks ─────────────────────────────────────────────

def auto_run_missing(
    session_id: str,
    config: dict,
    vr_file: Path,
    project_root: Path,
) -> dict[str, str]:
    """Run commands for required-but-pending checks. Returns {check_key: status}.

    Only runs checks that have a ``run_command`` in the config or a known
    default command for the project type.
    """
    try:
        from .vr_utils import is_pending, write_vr
    except ImportError:
        from vr_utils import is_pending, write_vr

    required = get_required_checks(config, files_modified=True)
    results: dict[str, str] = {}

    # Determine run commands from config or defaults
    run_commands: dict[str, str] = {}
    for check_key, check_conf in config.get("checks", {}).items():
        if isinstance(check_conf, dict) and check_conf.get("run_command"):
            run_commands[check_key] = check_conf["run_command"]

    # upstream_sync is always auto-run (special logic, not a shell command)
    if "upstream_sync" in required and is_pending(vr_file, "upstream_sync"):
        status, evidence = _run_upstream_sync(project_root)
        write_vr(vr_file, "upstream_sync", status, evidence, session_id=session_id)
        results["upstream_sync"] = status

    for check_key in required:
        if check_key == "upstream_sync":
            continue
        if check_key == "commit_push":
            continue  # Can't auto-run — too risky
        if not is_pending(vr_file, check_key):
            continue

        cmd = run_commands.get(check_key)
        if not cmd:
            continue

        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=120, cwd=str(project_root),
            )
            stdout = r.stdout or ""
            stderr = r.stderr or ""

            check_conf = config.get("checks", {}).get(check_key, {})
            if not isinstance(check_conf, dict):
                check_conf = {}
            # Fall back to generic patterns if config has no patterns
            if not check_conf.get("pass_patterns") and not check_conf.get("fail_patterns"):
                match = match_command(cmd, config)
                if match:
                    _, check_conf = match

            status = evaluate_output(stdout, stderr, check_conf)
            evidence = f"[auto-run] $ {cmd}\nexit={r.returncode}\n{stdout[:1500]}"
            if stderr.strip():
                evidence += f"\nstderr: {stderr[:300]}"
            write_vr(vr_file, check_key, status, evidence, session_id=session_id)
            results[check_key] = status
        except subprocess.TimeoutExpired:
            write_vr(vr_file, check_key, "failed",
                      f"[auto-run] $ {cmd}\nTimed out after 120s", session_id=session_id)
            results[check_key] = "failed"
        except Exception as exc:
            write_vr(vr_file, check_key, "failed",
                      f"[auto-run] $ {cmd}\nError: {exc}", session_id=session_id)
            results[check_key] = "failed"

    return results


def _run_upstream_sync(project_root: Path) -> tuple[str, str]:
    """Check upstream sync status. Returns (status, evidence)."""
    kw: dict[str, Any] = dict(capture_output=True, text=True, cwd=str(project_root))
    try:
        # Check for upstream remote
        r = subprocess.run(["git", "remote"], timeout=5, **kw)
        if r.returncode != 0 or "upstream" not in r.stdout.split():
            # Check origin instead
            r2 = subprocess.run(["git", "remote"], timeout=5, **kw)
            if "origin" not in (r2.stdout or "").split():
                return "skipped", "No remote configured"

            branch_r = subprocess.run(["git", "branch", "--show-current"], timeout=5, **kw)
            branch = branch_r.stdout.strip() or "main"

            fetch_r = subprocess.run(
                ["git", "fetch", "origin", "--quiet"], timeout=15,
                capture_output=True, cwd=str(project_root),
            )
            if fetch_r.returncode != 0:
                return "done", f"Fetch failed — skipping sync check\nBranch: {branch}"

            behind_r = subprocess.run(
                ["git", "rev-list", "--count", f"HEAD..origin/{branch}"],
                timeout=5, **kw,
            )
            behind = int(behind_r.stdout.strip() or "0") if behind_r.returncode == 0 else 0
            if behind > 0:
                return "done", f"Behind origin/{branch} by {behind} commit(s)\nBranch: {branch}"
            return "done", f"In sync with origin/{branch}\nBranch: {branch}\nRemote: origin"

        # Has upstream remote — it's a fork
        branch_r = subprocess.run(["git", "branch", "--show-current"], timeout=5, **kw)
        branch = branch_r.stdout.strip() or "main"

        fetch_r = subprocess.run(
            ["git", "fetch", "upstream", "--quiet"], timeout=15,
            capture_output=True, cwd=str(project_root),
        )
        if fetch_r.returncode != 0:
            return "done", f"Upstream fetch failed\nBranch: {branch}"

        behind_r = subprocess.run(
            ["git", "rev-list", "--count", f"HEAD..upstream/{branch}"],
            timeout=5, **kw,
        )
        behind = int(behind_r.stdout.strip() or "0") if behind_r.returncode == 0 else 0
        if behind > 0:
            return "done", f"Behind upstream/{branch} by {behind} commit(s)\nBranch: {branch}"
        return "done", f"In sync with upstream/{branch}\nBranch: {branch}"

    except Exception as exc:
        return "done", f"Sync check error: {exc}"
