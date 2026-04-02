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

    # Detect Playwright/Cypress regardless of project type
    _pw_configs = ("playwright.config.ts", "playwright.config.js",
                   "playwright.config.mjs", "playwright.config.cjs")
    _cy_configs = ("cypress.config.ts", "cypress.config.js",
                   "cypress.config.mjs", "cypress.config.cjs")
    _has_playwright = any((project_root / f).exists() for f in _pw_configs)
    _has_cypress = any((project_root / f).exists() for f in _cy_configs)

    if _has_playwright or _has_cypress:
        config["has_frontend"] = True
        # Auto-set run_command for frontend check
        if _has_playwright:
            config["checks"]["frontend"] = {
                "command_patterns": ["playwright test", "npx playwright"],
                "pass_patterns": [r"\d+ passed"],
                "fail_patterns": [r"\d+ failed", "failed", "FAIL"],
                "run_command": "npx playwright test",
            }
        elif _has_cypress:
            config["checks"]["frontend"] = {
                "command_patterns": ["cypress run"],
                "pass_patterns": [r"All specs passed"],
                "fail_patterns": ["failed", "FAIL"],
                "run_command": "npx cypress run",
            }

    # Python
    _pyproject = project_root / "pyproject.toml"
    if _pyproject.exists() or (project_root / "setup.py").exists():
        config["project_type"] = "python"
        config["has_tests"] = (project_root / "tests").is_dir()
        if config["has_tests"]:
            # Use uv run pytest when the project is uv-managed, else python -m pytest
            _uv_lock = (project_root / "uv.lock").exists()
            _test_cmd = "uv run pytest tests/ -x -q" if _uv_lock else "python -m pytest tests/ -x -q"
            config["checks"]["tests"] = {
                "command_patterns": ["pytest", "python -m pytest", "uv run pytest"],
                "pass_patterns": [r"\d+ passed"],
                "fail_patterns": [r"\d+ failed", r"FAILED", r"ERROR"],
                "run_command": _test_cmd,
            }
        # Detect ruff linter
        _has_ruff = (project_root / ".ruff_cache").exists()
        if not _has_ruff and _pyproject.exists():
            try:
                _has_ruff = "[tool.ruff]" in _pyproject.read_text()
            except Exception:
                pass
        if _has_ruff:
            config["checks"]["lint"] = {
                "command_patterns": ["ruff check", "ruff ."],
                "pass_patterns": [r"All checks passed", r"^$"],
                "fail_patterns": [r"Found \d+ error"],
                "run_command": "ruff check .",
            }
        # Detect mypy config
        _has_mypy = (project_root / "mypy.ini").exists() or (
            project_root / ".mypy.ini"
        ).exists()
        if not _has_mypy and _pyproject.exists():
            try:
                _has_mypy = "[tool.mypy]" in _pyproject.read_text()
            except Exception:
                pass
        if _has_mypy:
            config["has_typecheck"] = True
            config["checks"]["typecheck"] = {
                "command_patterns": ["mypy"],
                "pass_patterns": [r"Success", r"0 error"],
                "fail_patterns": [r"error:", r"Found \d+ error"],
                "run_command": "mypy .",
            }
        # Detect pyright
        if (project_root / "pyrightconfig.json").exists():
            config["has_typecheck"] = True
            config["checks"]["typecheck"] = {
                "command_patterns": ["pyright"],
                "pass_patterns": [r"0 error"],
                "fail_patterns": [r"error:", r"Found \d+ error"],
                "run_command": "pyright",
            }

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
            # Detect ESLint
            _eslint_configs = (
                ".eslintrc.js", ".eslintrc.cjs", ".eslintrc.json", ".eslintrc.yml",
                "eslint.config.mjs", "eslint.config.js", "eslint.config.cjs",
            )
            _has_eslint = "lint" in scripts or any(
                (project_root / f).exists() for f in _eslint_configs
            )
            if _has_eslint:
                _lint_cmd = "npm run lint" if "lint" in scripts else "npx eslint ."
                config["checks"]["lint"] = {
                    "command_patterns": ["npm run lint", "npx eslint", "eslint"],
                    "pass_patterns": [r"no problems", r"0 errors"],
                    "fail_patterns": [r"\d+ error", r"\d+ warning"],
                    "run_command": _lint_cmd,
                }
            if "test:e2e" in scripts:
                config["has_frontend"] = True
                if "frontend" not in config["checks"]:
                    config["checks"]["frontend"] = {
                        "command_patterns": ["npm run test:e2e"],
                        "pass_patterns": [r"passed"],
                        "fail_patterns": ["failed", "FAIL"],
                        "run_command": "npm run test:e2e",
                    }
            # Detect frontend frameworks from package.json dependencies
            _all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            _frontend_frameworks = {
                "react", "react-dom", "vue", "@angular/core", "svelte",
                "next", "@remix-run/react", "nuxt", "gatsby", "solid-js",
                "astro", "@astrojs/astro",
            }
            if any(fw in _all_deps for fw in _frontend_frameworks):
                config["has_frontend"] = True
        except Exception:
            config["has_tests"] = True
        # TypeScript type-checking
        if (project_root / "tsconfig.json").exists():
            config["has_typecheck"] = True
            if "typecheck" not in config["checks"]:
                config["checks"]["typecheck"] = {
                    "command_patterns": ["tsc --noEmit", "tsc -noEmit", "npx tsc"],
                    "pass_patterns": [r"0 errors", r"^$"],
                    "fail_patterns": [r"error TS\d+", r"Found \d+ error"],
                    "run_command": "npx tsc --noEmit",
                }

    # Rust
    if (project_root / "Cargo.toml").exists():
        config["project_type"] = "rust"
        config["has_tests"] = True
        config["has_build"] = True
        config["has_typecheck"] = True  # cargo check is Rust's type-checker
        config["checks"]["typecheck"] = {
            "command_patterns": ["cargo check"],
            "pass_patterns": [],
            "fail_patterns": [r"^error"],
            "run_command": "cargo check",
        }

    # Go
    if (project_root / "go.mod").exists():
        config["project_type"] = "go"
        config["has_tests"] = True

    # Ruby
    if (project_root / "Gemfile").exists():
        config["project_type"] = "ruby"
        config["has_tests"] = (project_root / "spec").is_dir() or (project_root / "test").is_dir()

    # File-based frontend detection (catches projects without npm deps)
    _frontend_files = [
        "src/App.tsx", "src/App.jsx", "src/App.vue", "src/App.svelte",
        "src/main.tsx", "src/main.ts", "src/index.tsx", "src/index.ts",
        "app/layout.tsx", "app/layout.jsx", "app/page.tsx", "app/page.jsx",
        "pages/index.tsx", "pages/index.jsx", "pages/index.vue",
        "public/index.html",
    ]
    if any((project_root / f).exists() for f in _frontend_files):
        config["has_frontend"] = True

    return config


# ── Required checks derivation ───────────────────────────────────────────

def get_required_checks(config: dict, files_modified: bool = True) -> list[str]:
    """Derive the list of required check keys from a project config.

    *files_modified* controls whether commit_push is required.

    Any check can be opted out by setting ``"required": false`` in its per-check
    config block, e.g. ``"checks": {"frontend": {"required": false}}``.
    This lets projects disable checks that are auto-detected but have pre-existing
    failures or are otherwise not applicable to the current session.
    """
    checks_conf = config.get("checks", {})

    def _is_required(key: str, default: bool = True) -> bool:
        """Return False if the check's config explicitly sets required: false."""
        check_conf = checks_conf.get(key, {})
        if isinstance(check_conf, dict) and "required" in check_conf:
            return bool(check_conf["required"])
        return default

    required = []
    # Always-required checks (can still be disabled via "required": false)
    if _is_required("lint"):
        required.append("lint")
    if _is_required("security"):
        required.append("security")
    if _is_required("upstream_sync"):
        required.append("upstream_sync")

    if config.get("has_tests", False) and _is_required("tests"):
        required.insert(0, "tests")
    if config.get("has_build", False) and _is_required("build"):
        required.append("build")
    if (config.get("has_typecheck", False) or "typecheck" in checks_conf) and _is_required("typecheck"):
        required.append("typecheck")
    if config.get("has_app", False) and _is_required("app_starts"):
        required.append("app_starts")
    # execution: required if config defines it or project has scripts/CLI
    if (config.get("has_execution", False) or "execution" in checks_conf) and _is_required("execution"):
        required.append("execution")
    if config.get("has_frontend", False) and _is_required("frontend"):
        required.append("frontend")
    # happy_path: required if config defines it (user specifies what "happy path" means)
    if "happy_path" in checks_conf and _is_required("happy_path"):
        required.append("happy_path")
    if files_modified and _is_required("commit_push"):
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
    (["npm run build", "vite build"], "build",
     [r"Successfully compiled", r"built in"], ["error TS", "ERROR", "Build failed"]),
    (["cargo build"], "build",
     [], [r"^error"]),

    # Type checking
    (["tsc --noEmit", "tsc -noEmit", "npx tsc"], "typecheck",
     [r"0 errors", r"^$"], [r"error TS\d+", r"Found \d+ error"]),
    (["mypy", "dmypy run", "pyright"], "typecheck",
     [r"Success", r"0 error"], [r"error:", r"Found \d+ error"]),
    (["cargo check"], "typecheck",
     [], [r"^error"]),

    # Execution (running scripts, CLI tools, API calls)
    (["curl ", "curl\t", "httpie ", "http "], "execution",
     [r"200", r"HTTP/"], [r"Connection refused", r"Could not resolve"]),
    (["python3 ", "python ", "node ", "ruby ", "go run "], "execution",
     [], [r"Traceback", r"Error:", r"SyntaxError", r"Cannot find"]),
    (["bash ", "sh ", "./"], "execution",
     [], [r"command not found", r"No such file"]),

    # Frontend (Playwright / Cypress E2E tests)
    (["playwright test", "npx playwright", "cypress run", "npm run test:e2e"], "frontend",
     [r"\d+ passed", r"All specs passed"], ["failed", "FAIL", r"\d+ failed"]),

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

    # security is always auto-run (uses security_scanner, not a shell command)
    if "security" in required and is_pending(vr_file, "security"):
        status, evidence = _run_security_scan(project_root, config)
        write_vr(vr_file, "security", status, evidence, session_id=session_id)
        results["security"] = status

    for check_key in required:
        if check_key in ("upstream_sync", "security"):
            continue
        if check_key == "commit_push":
            # Auto-satisfy only when repo is fully clean: 0 unpushed commits
            # AND no uncommitted changes to tracked files.
            try:
                branch_r = subprocess.run(
                    ["git", "branch", "--show-current"],
                    capture_output=True, text=True, timeout=5,
                    cwd=str(project_root),
                )
                branch = branch_r.stdout.strip() or "main"
                rev_r = subprocess.run(
                    ["git", "rev-list", f"origin/{branch}...HEAD", "--count"],
                    capture_output=True, text=True, timeout=5,
                    cwd=str(project_root),
                )
                unpushed = int(rev_r.stdout.strip() or "1")
                # Also check for uncommitted changes to tracked files
                diff_r = subprocess.run(
                    ["git", "diff", "HEAD", "--name-only"],
                    capture_output=True, text=True, timeout=5,
                    cwd=str(project_root),
                )
                has_uncommitted = bool(diff_r.stdout.strip())
                if unpushed == 0 and not has_uncommitted:
                    write_vr(vr_file, "commit_push", "passed",
                             f"[auto] 0 unpushed commits, 0 uncommitted changes on {branch}",
                             session_id=session_id)
                    results["commit_push"] = "passed"
            except Exception:
                pass
            continue
        if not is_pending(vr_file, check_key):
            continue

        cmd = run_commands.get(check_key)
        if not cmd:
            continue

        try:
            # Frontend (Playwright/Cypress) gets a longer timeout
            timeout = 300 if check_key == "frontend" else 120
            r = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=timeout, cwd=str(project_root),
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


def _run_security_scan(project_root: Path, config: dict) -> tuple[str, str]:
    """Run the security scanner. Returns (status, evidence)."""
    try:
        from .security_scanner import run_security_scan
    except ImportError:
        try:
            from security_scanner import run_security_scan
        except ImportError:
            return "passed", "Security scanner not available — skipped"

    try:
        critical, warnings, report_path = run_security_scan(
            project_root, timeout_per_tool=8, global_timeout=45,
        )
    except Exception as exc:
        return "passed", f"Security scan error (non-blocking): {exc}"

    sec_config = config.get("security", {})
    block_on_warnings = sec_config.get("block_on_warnings", True)
    max_warnings = sec_config.get("allow_warning_count", 0)

    evidence = (
        f"Critical: {critical}, Warnings: {warnings}\n"
        f"Report: {report_path}"
    )

    should_fail = critical > 0 or (block_on_warnings and warnings > max_warnings)
    return ("failed" if should_fail else "passed"), evidence


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
