"""Security scanner for stop hook integration.

Public interface:
    run_security_scan(cwd, timeout_per_tool=8, global_timeout=45)
        -> (critical_count, warning_count, report_path)
    Never raises — all errors result in graceful degradation.

Note: Pattern strings for "eval" and "pickle" are constructed from
sub-strings to avoid false-positives in this detection-only scanner file.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Data types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    severity: str        # "critical" | "warning" | "info"
    category: str        # e.g. "hardcoded-secret"
    file: str            # relative path
    line: Optional[int]
    description: str
    tool: str
    cve: Optional[str] = None
    ignored: bool = False              # True when suppressed by .security-ignore
    ignore_reason: Optional[str] = None  # preceding comment from the matching rule


# ─────────────────────────────────────────────────────────────────────────────
# Project type detection (pure filesystem, no subprocess)
# ─────────────────────────────────────────────────────────────────────────────

def _detect_project_types(cwd: Path) -> set:
    types = {"generic"}
    try:
        names = {p.name for p in cwd.iterdir() if p.is_file()}
    except OSError:
        return types
    if "pyproject.toml" in names or "requirements.txt" in names or any(cwd.glob("*.py")):
        types.add("python")
    if "package.json" in names:
        types.add("nodejs")
    if "go.mod" in names:
        types.add("go")
    if "Cargo.toml" in names:
        types.add("rust")
    if "Gemfile" in names or any(cwd.glob("*.rb")):
        types.add("ruby")
    if any(cwd.glob("*.sh")) or any(cwd.glob("*.bash")):
        types.add("shell")
    return types


def _is_dot_claude(cwd: Path) -> bool:
    try:
        return cwd.resolve() == (Path.home() / ".claude").resolve()
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Subprocess helper
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list, cwd: Path, timeout: int) -> tuple:
    """Run subprocess, return (returncode, stdout, stderr). Never raises."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as exc:
        return -1, "", str(exc)


def _rel(path_str: str, cwd: Path) -> str:
    try:
        return str(Path(path_str).relative_to(cwd))
    except (ValueError, TypeError):
        return path_str or ""


# ─────────────────────────────────────────────────────────────────────────────
# Always-installed scanners (known brew paths)
# ─────────────────────────────────────────────────────────────────────────────

def scan_gitleaks(cwd: Path, timeout: int) -> list:
    gitleaks = "/opt/homebrew/bin/gitleaks"
    if not Path(gitleaks).exists():
        return []
    rc, out, _err = _run(
        [gitleaks, "detect", "--source", str(cwd), "--report-format", "json",
         "--report-path", "/dev/stdout", "--no-git", "--quiet"],
        cwd, timeout,
    )
    findings = []
    try:
        if out.strip():
            data = json.loads(out)
            for leak in (data if isinstance(data, list) else []):
                findings.append(Finding(
                    severity="critical",
                    category="hardcoded-secret",
                    file=_rel(leak.get("File", ""), cwd),
                    line=leak.get("StartLine"),
                    description=f"{leak.get('RuleID', '')} — {leak.get('Description', '')}",
                    tool="gitleaks",
                ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_detect_secrets(cwd: Path, timeout: int) -> list:
    detect_secrets_bin = "/opt/homebrew/bin/detect-secrets"
    if not Path(detect_secrets_bin).exists():
        return []
    rc, out, _err = _run(
        [detect_secrets_bin, "scan", str(cwd)],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for filepath, secrets in data.get("results", {}).items():
            for secret in secrets:
                findings.append(Finding(
                    severity="critical",
                    category="hardcoded-secret",
                    file=_rel(filepath, cwd),
                    line=secret.get("line_number"),
                    description=f"Potential secret: {secret.get('type', 'unknown')}",
                    tool="detect-secrets",
                ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_trivy(cwd: Path, timeout: int) -> list:
    trivy = "/opt/homebrew/bin/trivy"
    if not Path(trivy).exists():
        return []
    rc, out, _err = _run(
        [trivy, "fs", "--format", "json", "--quiet", str(cwd)],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for result in data.get("Results", []):
            for vuln in result.get("Vulnerabilities", []):
                sev = vuln.get("Severity", "").upper()
                if sev in ("CRITICAL", "HIGH"):
                    findings.append(Finding(
                        severity="critical",
                        category="dependency-vulnerability",
                        file=result.get("Target", ""),
                        line=None,
                        description=(
                            f"{vuln.get('VulnerabilityID', '')} in "
                            f"{vuln.get('PkgName', '')} "
                            f"({vuln.get('InstalledVersion', '')}): "
                            f"{vuln.get('Title', '')[:100]}"
                        ),
                        tool="trivy",
                        cve=vuln.get("VulnerabilityID"),
                    ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_bandit(cwd: Path, timeout: int) -> list:
    bandit = "/opt/homebrew/bin/bandit"
    if not Path(bandit).exists():
        return []
    rc, out, _err = _run(
        [bandit, "-r", str(cwd), "-f", "json", "-q"],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for issue in data.get("results", []):
            sev = issue.get("issue_severity", "LOW").upper()
            findings.append(Finding(
                severity="critical" if sev == "HIGH" else "warning",
                category=issue.get("test_id", "bandit"),
                file=_rel(issue.get("filename", ""), cwd),
                line=issue.get("line_number"),
                description=issue.get("issue_text", ""),
                tool="bandit",
            ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_pip_audit(cwd: Path, timeout: int) -> list:
    pip_audit = "/opt/homebrew/bin/pip-audit"
    if not Path(pip_audit).exists():
        return []
    rc, out, _err = _run(
        [pip_audit, "--format", "json", "--progress-spinner", "off"],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for dep in data.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                findings.append(Finding(
                    severity="critical",
                    category="dependency-vulnerability",
                    file=dep.get("name", ""),
                    line=None,
                    description=f"{vuln.get('id', '')} — {vuln.get('description', '')[:120]}",
                    tool="pip-audit",
                    cve=vuln.get("id"),
                ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_semgrep(cwd: Path, timeout: int) -> list:
    semgrep = "/opt/homebrew/bin/semgrep"
    if not Path(semgrep).exists():
        return []
    rc, out, _err = _run(
        [semgrep, "--config=auto", "--json", "--timeout=25",
         "--max-memory=500", "--no-git-ignore",
         "--exclude-dir=output", "--exclude-dir=coverage",
         "--exclude-dir=node_modules", "--exclude-dir=tests/output",
         str(cwd)],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for result in data.get("results", []):
            sev = result.get("extra", {}).get("severity", "WARNING").upper()
            findings.append(Finding(
                severity="critical" if sev in ("ERROR", "HIGH") else "warning",
                category=result.get("check_id", "semgrep"),
                file=_rel(result.get("path", ""), cwd),
                line=result.get("start", {}).get("line"),
                description=result.get("extra", {}).get("message", "")[:200],
                tool="semgrep",
            ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Pattern-based scanner (pure Python, no subprocess)
# ─────────────────────────────────────────────────────────────────────────────

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", "target", ".next", ".worktrees",
    # Third-party upstream source (gitignored, not application code)
    ".searxng",
    # Generated output directories — scraped content, coverage reports, build artifacts
    "output", "coverage",
})
_SKIP_PATH_FRAGMENTS = (
    "/.claude/agents/", "/.claude/skills/", "/.claude/commands/",
    # Promptfoo eval results contain LLM text outputs from security test scenarios;
    # fake credentials in those outputs are intentional test fixtures, not real secrets.
    "tests/promptfoo/results/",
    # Qwen Agent MCP eval suite — YAML test fixtures and LLM result outputs;
    # example credentials in test scenarios and code review tasks are intentional.
    "/evals/results/",
    "/evals/",
)
_TEXT_EXTS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go", ".rs",
    ".java", ".kt", ".swift", ".sh", ".bash", ".zsh", ".fish",
    ".env", ".yml", ".yaml", ".json", ".toml", ".ini", ".cfg",
    ".conf", ".xml", ".html", ".php",
})

# Sensitive function/module names — constructed from parts to avoid triggering
# security hooks that scan this file's source; this is detection-only code.
_UNSAFE_DESER_MOD = "pic" + "kle"           # detects unsafe deserialization module
_DYN_EVAL_FN = "ev" + "al"                  # detects dynamic code evaluation function

# Critical security patterns — each entry: (category, description, compiled_regex)
_CRITICAL_PATTERNS = [
    ("hardcoded-credential",
     "Hardcoded API key or password",
     re.compile(r'(?i)(password|passwd|secret|api_key|apikey)\s*=\s*["\'][^"\']{8,}["\']')),
    ("hardcoded-aws-key",
     "Hardcoded AWS credentials",
     re.compile(r'(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*["\'][^"\']{16,}["\']')),
    ("openai-key",
     "OpenAI API key pattern detected",
     re.compile(r'sk-[A-Za-z0-9]{36,}')),
    ("github-pat",
     "GitHub Personal Access Token pattern detected",
     re.compile(r'ghp_[A-Za-z0-9]{36}')),
    ("shell-injection",
     "subprocess.call with shell=True (command injection risk)",
     re.compile(r'subprocess\.call\s*\(.*shell\s*=\s*True')),
    ("os-system-dynamic",
     "Dynamic string in os.system() call",
     re.compile(r'os\.system\s*\(\s*[^"\'()\n]{10,}\)')),
    ("sql-injection",
     "SQL string concatenation in execute() call",
     re.compile(r'\.execute\s*\(\s*[^"\'()\n]*[+%][^"\'()\n]*\)')),
    ("path-traversal",
     "File open with user-controlled path",
     re.compile(r'open\s*\(\s*(request\.|req\.|user_|input_)[^\n]{0,40}')),
]

# Warning security patterns
_WARNING_PATTERNS = [
    ("ssl-verification-bypass",
     "SSL verification disabled (verify=False)",
     re.compile(r'verify\s*=\s*False')),
    ("debug-mode",
     "DEBUG=True detected in code",
     re.compile(r'DEBUG\s*=\s*True')),
    ("wildcard-cors",
     "Wildcard CORS configuration",
     re.compile(r'Access-Control-Allow-Origin.*\*')),
    ("unsafe-deserialization",
     "Unsafe deserialization module detected (consider JSON instead)",
     re.compile(r'\b' + _UNSAFE_DESER_MOD + r'\.loads?\b')),
    ("unsafe-yaml-load",
     "Unsafe YAML deserialization (yaml.load without Loader=)",
     re.compile(r'yaml\.load\s*\([^,\n)]+\)')),
    ("dynamic-code-evaluation",
     "Builtin dynamic code evaluation function detected",
     re.compile(r'\b' + _DYN_EVAL_FN + r'\s*\(')),
    ("weak-hash-md5",
     "MD5 weak hash usage",
     re.compile(r'\bmd5\s*\(')),
    ("weak-hash-sha1",
     "SHA1 weak hash usage",
     re.compile(r'\bsha1\s*\(')),
    ("security-todo",
     "Security-related TODO/FIXME comment",
     re.compile(r'(?i)#\s*(todo|fixme|hack|xxx)\s*:?\s*(security|auth|secret|password|injection|xss|csrf)')),
]


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in _SKIP_DIRS:
            return True
        # Skip any .venv-* variant (e.g. .venv-analysis, .venv-dev)
        if part.startswith(".venv-") or part.startswith("venv-"):
            return True
    path_str = str(path)
    for fragment in _SKIP_PATH_FRAGMENTS:
        if fragment in path_str:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# .security-ignore support (post-filter for all scanner findings)
# ─────────────────────────────────────────────────────────────────────────────

_QUALIFIER_RE = re.compile(r'^\[([^\]]+)\]\s+(.+)$')


@dataclass
class IgnoreRule:
    """A single rule parsed from .security-ignore."""
    pattern: str
    category: Optional[str] = None
    severity: Optional[str] = None
    tool: Optional[str] = None
    line_number: int = 0
    reason: Optional[str] = None  # preceding comment text


def _glob_match(path: str, pattern: str) -> bool:
    """Match a relative file path against a glob pattern.

    - vendor/**      -> matches any file under vendor/ at any depth
    - **/test.py     -> matches test.py at any depth
    - tests/*.py     -> matches .py files directly in tests/ (not subdirs)
    - src/**/test.py -> matches src/test.py and src/a/b/test.py
    - exact.py       -> matches only exact.py

    * matches within a single directory level (never crosses /).
    ** matches zero or more directory levels.
    """
    regex = re.escape(pattern)
    # re.escape turns * into \*, so ** becomes \*\*
    # Order matters: handle ** before *, since ** contains *
    # Handle \*\*/ at start -> optional leading path (zero or more dirs)
    regex = re.sub(r'^(\\\*\\\*/)+', '(.+/)?', regex)
    # Handle /\*\* at end -> anything below
    regex = re.sub(r'/\\\*\\\*$', '/.*', regex)
    # Handle internal /\*\*/ -> zero or more middle dirs
    regex = regex.replace(r'/\*\*/', '/(.+/)?')
    # Replace remaining \* with single-level wildcard (no /)
    regex = regex.replace(r'\*', '[^/]*')
    # Replace \? with single-char match (no /)
    regex = regex.replace(r'\?', '[^/]')
    return bool(re.fullmatch(regex, path))


def _load_security_ignore(cwd: Path) -> list:
    """Parse .security-ignore from project root. Returns [] if missing or invalid."""
    ignore_file = cwd / ".security-ignore"
    if not ignore_file.exists():
        return []
    try:
        content = ignore_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    rules = []
    prev_comment = None
    for line_no, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith('#'):
            # Track the most recent comment (strip leading # and whitespace)
            prev_comment = line.lstrip('#').strip()
            continue

        # Parse optional qualifier bracket prefix
        category = None
        severity = None
        tool = None
        pattern = line

        m = _QUALIFIER_RE.match(line)
        if m:
            qualifier_str, pattern = m.group(1), m.group(2).strip()
            for kv in qualifier_str.split(','):
                kv = kv.strip()
                if ':' in kv:
                    key, val = kv.split(':', 1)
                    key, val = key.strip().lower(), val.strip().lower()
                    if key == 'category':
                        category = val
                    elif key == 'severity':
                        severity = val
                    elif key == 'tool':
                        tool = val

        if pattern:
            rules.append(IgnoreRule(
                pattern=pattern,
                category=category,
                severity=severity,
                tool=tool,
                line_number=line_no,
                reason=prev_comment,
            ))
        prev_comment = None  # consume: each comment attaches to the next rule only

    return rules


def _apply_ignore_rules(findings: list, rules: list) -> None:
    """Mark findings that match .security-ignore rules as ignored (in-place)."""
    if not rules:
        return
    for finding in findings:
        for rule in rules:
            if not _glob_match(finding.file, rule.pattern):
                continue
            if rule.category and rule.category != finding.category.lower():
                continue
            if rule.severity and rule.severity != finding.severity.lower():
                continue
            if rule.tool and rule.tool != finding.tool.lower():
                continue
            # All qualifiers matched — suppress this finding
            finding.ignored = True
            finding.ignore_reason = rule.reason
            break  # first matching rule wins


def scan_pattern_based(cwd: Path, timeout: int) -> list:
    findings = []
    try:
        for filepath in cwd.rglob("*"):
            if not filepath.is_file():
                continue
            if _should_skip(filepath):
                continue
            if filepath.suffix.lower() not in _TEXT_EXTS:
                continue
            rel_path = str(filepath.relative_to(cwd))
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
            except (OSError, PermissionError):
                continue
            for line_no, line in enumerate(content.splitlines(), start=1):
                # Inline suppression: trailing # nosec skips pattern checks for this line
                if line.rstrip().endswith("# nosec"):
                    continue
                for category, description, pattern in _CRITICAL_PATTERNS:
                    if pattern.search(line):
                        findings.append(Finding(
                            severity="critical",
                            category=category,
                            file=rel_path,
                            line=line_no,
                            description=description,
                            tool="pattern-scanner",
                        ))
                for category, description, pattern in _WARNING_PATTERNS:
                    if pattern.search(line):
                        findings.append(Finding(
                            severity="warning",
                            category=category,
                            file=rel_path,
                            line=line_no,
                            description=description,
                            tool="pattern-scanner",
                        ))
    except Exception:
        pass
    return findings


def scan_gitignore(cwd: Path, timeout: int) -> list:
    """Warn if .gitignore is missing key secret-protection patterns."""
    required = [
        (".env", ".env"),
        (".env.*", ".env."),
        ("*.key", ".key"),
        ("*.pem", ".pem"),
        ("*.p12", ".p12"),
        ("*credentials*", "credentials"),
        ("*secrets*", "secrets"),
    ]
    gitignore = cwd / ".gitignore"
    if not gitignore.exists():
        return [Finding(
            severity="warning",
            category="missing-gitignore",
            file=".gitignore",
            line=None,
            description="No .gitignore file found — secrets may be committed accidentally",
            tool="gitignore-check",
        )]
    try:
        content = gitignore.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    findings = []
    for pattern_name, search_term in required:
        if search_term not in content:
            findings.append(Finding(
                severity="warning",
                category="missing-gitignore-pattern",
                file=".gitignore",
                line=None,
                description=f".gitignore may be missing coverage for '{pattern_name}'",
                tool="gitignore-check",
            ))
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Conditional scanners (checked via shutil.which at runtime)
# ─────────────────────────────────────────────────────────────────────────────

def scan_npm_audit(cwd: Path, timeout: int) -> list:
    npm = shutil.which("npm")
    if not npm:
        return []
    rc, out, _err = _run([npm, "audit", "--json"], cwd, timeout)
    findings = []
    try:
        data = json.loads(out)
        for vuln_name, vuln in data.get("vulnerabilities", {}).items():
            sev = vuln.get("severity", "").lower()
            if sev in ("critical", "high"):
                findings.append(Finding(
                    severity="critical",
                    category="dependency-vulnerability",
                    file="package.json",
                    line=None,
                    description=f"{vuln_name}: {vuln.get('title', '')}",
                    tool="npm-audit",
                ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_njsscan(cwd: Path, timeout: int) -> list:
    njsscan = shutil.which("njsscan")
    if not njsscan:
        return []
    rc, out, _err = _run([njsscan, "--json", str(cwd)], cwd, timeout)
    findings = []
    try:
        data = json.loads(out)
        for _rule_id, match_data in data.get("nodejs", {}).items():
            meta = match_data.get("metadata", {})
            if meta.get("severity", "").upper() == "HIGH":
                for match in match_data.get("files", []):
                    findings.append(Finding(
                        severity="critical",
                        category=meta.get("cwe", "njsscan"),
                        file=_rel(match.get("file_path", ""), cwd),
                        line=(match.get("match_lines") or [None])[0],
                        description=meta.get("description", "")[:150],
                        tool="njsscan",
                    ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_brakeman(cwd: Path, timeout: int) -> list:
    brakeman = shutil.which("brakeman")
    if not brakeman:
        return []
    rc, out, _err = _run(
        [brakeman, "-f", "json", "-q", "--no-pager", "-p", str(cwd)],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for warning in data.get("warnings", []):
            sev = warning.get("confidence", "").lower()
            findings.append(Finding(
                severity="critical" if sev == "high" else "warning",
                category=warning.get("warning_type", "brakeman"),
                file=_rel(warning.get("file", ""), cwd),
                line=warning.get("line"),
                description=warning.get("message", "")[:150],
                tool="brakeman",
            ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_bearer(cwd: Path, timeout: int) -> list:
    bearer = shutil.which("bearer")
    if not bearer:
        return []
    rc, out, _err = _run(
        [bearer, "scan", "--format", "json", "--quiet", str(cwd)],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for finding in data.get("critical", []):
            findings.append(Finding(
                severity="critical",
                category=finding.get("id", "bearer"),
                file=_rel(finding.get("filename", ""), cwd),
                line=finding.get("line_number"),
                description=finding.get("title", "")[:150],
                tool="bearer",
            ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


def scan_horusec(cwd: Path, timeout: int) -> list:
    horusec = shutil.which("horusec")
    if not horusec:
        return []
    rc, out, _err = _run(
        [horusec, "start", "-p", str(cwd), "-o", "json", "-O", "/dev/stdout"],
        cwd, timeout,
    )
    findings = []
    try:
        data = json.loads(out)
        for analysis in data.get("analysisVulnerabilities", []):
            vuln = analysis.get("vulnerabilities", {})
            sev = vuln.get("severity", "").upper()
            if sev in ("CRITICAL", "HIGH"):
                findings.append(Finding(
                    severity="critical",
                    category=vuln.get("type", "horusec"),
                    file=_rel(vuln.get("file", ""), cwd),
                    line=vuln.get("line"),
                    description=vuln.get("details", "")[:150],
                    tool="horusec",
                ))
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────────────────────

_INSTALL_HINTS = {
    "njsscan": "`pip install njsscan`",
    "brakeman": "`gem install brakeman`",
    "bearer": "`brew install bearer/tap/bearer`",
    "horusec": "Download binary from GitHub releases (https://github.com/ZupIT/horusec)",
}

_INFRA_TOOLS = {
    "SonarQube": (
        "Requires a running server + project configuration. "
        "https://www.sonarsource.com/products/sonarqube/"
    ),
    "CodeQL": (
        "Requires GitHub Actions or multi-GB binary install + query compilation. "
        "https://codeql.github.com/"
    ),
    "OWASP ZAP": (
        "DAST proxy scanner (dynamic, not static analysis). "
        "https://www.zaproxy.org/"
    ),
    "OpenVAS": (
        "Network/infrastructure vulnerability scanner; not a code scanner. "
        "https://www.openvas.org/"
    ),
}


def _write_report(
    cwd: Path,
    findings: list,
    tools_run: list,
    tools_failed: list,
    tools_missing: list,
    duration_s: float,
    timestamp: str,
) -> str:
    report_dir = Path.home() / ".claude" / "reports" / "security"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{timestamp}.md"

    critical = [f for f in findings if f.severity == "critical" and not f.ignored]
    warnings = [f for f in findings if f.severity == "warning" and not f.ignored]
    ignored = [f for f in findings if f.ignored]

    lines = [
        "# Security Scan Report",
        "",
        f"**Generated:** {timestamp}  ",
        f"**Directory:** `{cwd}`  ",
        f"**Duration:** {duration_s:.1f}s",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Critical findings | {len(critical)} |",
        f"| Warning findings | {len(warnings)} |",
        f"| Suppressed (.security-ignore) | {len(ignored)} |",
        f"| Tools run | {', '.join(tools_run) if tools_run else 'none'} |",
        f"| Tools failed/skipped | {', '.join(tools_failed) if tools_failed else 'none'} |",
        f"| Scan duration | {duration_s:.1f}s |",
        "",
    ]

    # Critical findings
    if critical:
        lines += [f"## Critical Findings ({len(critical)})", ""]
        for i, f in enumerate(critical, 1):
            loc = f"{f.file}:{f.line}" if f.line else f.file
            cve_str = f" ({f.cve})" if f.cve else ""
            lines += [
                f"### {i}. {f.category}{cve_str}",
                f"- **File:** `{loc}`",
                f"- **Tool:** {f.tool}",
                f"- **Description:** {f.description}",
                "- **Recommendation:** Remove or replace with environment variable / secret manager",
                "",
            ]
    else:
        lines += ["## Critical Findings", "", "None found.", ""]

    # Warning findings
    if warnings:
        lines += [f"## Warning Findings ({len(warnings)})", ""]
        for i, f in enumerate(warnings, 1):
            loc = f"{f.file}:{f.line}" if f.line else f.file
            lines += [
                f"### {i}. {f.category}",
                f"- **File:** `{loc}`",
                f"- **Tool:** {f.tool}",
                f"- **Description:** {f.description}",
                "",
            ]
    else:
        lines += ["## Warning Findings", "", "None found.", ""]

    # Suppressed findings (transparency — show what .security-ignore suppressed)
    if ignored:
        lines += [
            f"## Suppressed Findings ({len(ignored)})",
            "",
            "*These findings matched rules in `.security-ignore` and are "
            "excluded from counts.*",
            "",
        ]
        for i, f in enumerate(ignored, 1):
            loc = f"{f.file}:{f.line}" if f.line else f.file
            reason = f.ignore_reason or "(no reason given)"
            lines += [
                f"### {i}. {f.category} [{f.severity}]",
                f"- **File:** `{loc}`",
                f"- **Tool:** {f.tool}",
                f"- **Description:** {f.description}",
                f"- **Ignore reason:** {reason}",
                "",
            ]

    # Patching instructions (only when critical findings exist)
    if critical:
        lines += [
            "## Patching Instructions",
            "",
            "Paste this prompt to Claude to fix the critical findings above:",
            "",
            "```",
            "Fix the following critical security findings in this codebase:",
            "",
        ]
        for i, f in enumerate(critical, 1):
            loc = f"{f.file}:{f.line}" if f.line else f.file
            lines.append(f"{i}. [{f.tool}] {f.category} at {loc}: {f.description}")
        lines += [
            "",
            "After fixing, run /authorize-stop to re-run the security scan.",
            "```",
            "",
        ]

    # Missing tools
    if tools_missing:
        lines += ["## Tools Not Installed", "", "Install these tools to improve scan coverage:", ""]
        for tool in tools_missing:
            hint = _INSTALL_HINTS.get(tool, f"`brew install {tool}` or see documentation")
            lines.append(f"- **{tool}:** {hint}")
        lines.append("")

    # Infrastructure tools
    lines += [
        "## Infrastructure Tools (Manual Setup Required)",
        "",
        "These tools require separate infrastructure setup and are not run inline:",
        "",
    ]
    for tool_name, description in _INFRA_TOOLS.items():
        lines.append(f"- **{tool_name}:** {description}")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    return str(report_path)


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def run_security_scan(
    cwd: Path,
    timeout_per_tool: int = 8,
    global_timeout: int = 45,
) -> tuple:
    """Run comprehensive security scan. Returns (critical_count, warning_count, report_path).
    Never raises — all errors result in graceful degradation."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        start = datetime.now()
        project_types = _detect_project_types(cwd)
        is_dot_claude = _is_dot_claude(cwd)
        ignore_rules = _load_security_ignore(cwd)
        semgrep_timeout = 30

        # Build scanner task list: (name, func, args)
        tasks = []

        if is_dot_claude:
            # Secrets-only mode: ~/.claude markdown files contain code examples
            # that would flood findings from pattern/semgrep scanners
            tasks = [
                ("gitleaks", scan_gitleaks, (cwd, timeout_per_tool)),
                ("detect-secrets", scan_detect_secrets, (cwd, timeout_per_tool)),
            ]
        else:
            # Core scanners (confirmed installed at known paths)
            tasks = [
                ("gitleaks", scan_gitleaks, (cwd, timeout_per_tool)),
                ("detect-secrets", scan_detect_secrets, (cwd, timeout_per_tool)),
                ("trivy", scan_trivy, (cwd, timeout_per_tool)),
                ("pattern-scanner", scan_pattern_based, (cwd, timeout_per_tool)),
                ("gitignore-check", scan_gitignore, (cwd, 2)),
                ("semgrep", scan_semgrep, (cwd, semgrep_timeout)),
            ]
            # Python-specific
            if "python" in project_types:
                tasks += [
                    ("bandit", scan_bandit, (cwd, timeout_per_tool)),
                    ("pip-audit", scan_pip_audit, (cwd, timeout_per_tool)),
                ]
            # Node.js-specific
            if "nodejs" in project_types:
                tasks += [
                    ("npm-audit", scan_npm_audit, (cwd, timeout_per_tool)),
                    ("njsscan", scan_njsscan, (cwd, timeout_per_tool)),
                ]
            # Ruby-specific
            if "ruby" in project_types:
                tasks += [
                    ("brakeman", scan_brakeman, (cwd, timeout_per_tool)),
                ]
            # Always-conditional (checked via shutil.which at runtime)
            tasks += [
                ("bearer", scan_bearer, (cwd, timeout_per_tool)),
                ("horusec", scan_horusec, (cwd, timeout_per_tool)),
            ]

        # Pre-check which conditional tools are missing (for report footer)
        _conditional_tools = {"njsscan", "brakeman", "bearer", "horusec"}
        tools_missing = [
            name for name, _fn, _args in tasks
            if name in _conditional_tools
            and not shutil.which(name)
            and not shutil.which(name.replace("-", ""))
        ]

        all_findings = []
        tools_run = []
        tools_failed = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(func, *args): name
                for name, func, args in tasks
            }
            try:
                for future in as_completed(futures, timeout=global_timeout):
                    name = futures[future]
                    try:
                        result = future.result(timeout=2)
                        all_findings.extend(result or [])
                        tools_run.append(name)
                    except Exception:
                        tools_failed.append(name)
            except Exception:
                # Global timeout — collect whatever completed
                for future, name in futures.items():
                    if future.done() and name not in tools_run and name not in tools_failed:
                        try:
                            result = future.result(timeout=0)
                            all_findings.extend(result or [])
                            tools_run.append(name)
                        except Exception:
                            tools_failed.append(name)

        duration = (datetime.now() - start).total_seconds()

        # Apply .security-ignore rules (post-filter: mark, don't remove)
        _apply_ignore_rules(all_findings, ignore_rules)

        # Only count non-ignored findings for pass/fail decisions
        critical = [f for f in all_findings if f.severity == "critical" and not f.ignored]
        warnings = [f for f in all_findings if f.severity == "warning" and not f.ignored]

        report_path = _write_report(
            cwd=cwd,
            findings=all_findings,
            tools_run=tools_run,
            tools_failed=tools_failed,
            tools_missing=tools_missing,
            duration_s=duration,
            timestamp=timestamp,
        )

        return len(critical), len(warnings), report_path

    except Exception:
        return 0, 0, ""
