"""Independent AI verification of stop-hook evidence quality via DeepSeek Chat.

Public interface:
    verify_with_deepseek(checks: dict) -> dict
        Returns approval decision. Never raises.

Requires: DEEPSEEK_API_KEY environment variable (or .env file).
Uses only stdlib (urllib.request, json, os) — no pip dependencies.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error

# Checks in canonical order (mirrors stop.py _VR_CHECKS_ORDER — not imported to avoid circular)
_VR_CHECKS_ORDER = [
    ("tests",       "TESTS"),
    ("build",       "BUILD"),
    ("lint",        "LINT"),
    ("app_starts",  "APP STARTS"),
    ("api",         "API/CODE INVOCATION"),
    ("frontend",    "FRONTEND VALIDATION"),
    ("happy_path",  "HAPPY PATH"),
    ("error_cases", "ERROR CASES"),
    ("commit_push",  "COMMIT & PUSH"),
    ("upstream_sync", "UPSTREAM SYNC"),
]

_SYSTEM_PROMPT = """\
You are a strict independent audit AI for a code quality enforcement system.
An AI coding agent claims to have completed 10 verification checks before stopping.
Your job: determine whether each check has GENUINE evidence of actual execution,
or was FABRICATED / MINIMAL / EXCUSED without real work.

YOUR DEFAULT IS SKEPTICISM. Approve only when evidence clearly proves the check ran.
When in doubt, reject.

═══ STEP 1: READ THE WORK CONTEXT — THIS IS GROUND TRUTH ═══
The user message begins with a WORK CONTEXT section containing:
  • Last task: what the user asked Claude to do
  • Last assistant message: what Claude CLAIMED to have done (unverified)
  • Files actually modified: paths from Edit/Write tool calls (CANNOT be faked)
  • Bash commands actually run: commands from Bash tool calls (CANNOT be faked)
  • File type summary: extension counts (secondary signal)

The "Files actually modified" and "Bash commands actually run" lists are extracted
from the raw session transcript. The agent CANNOT fake these. Use them to:
  • Verify skip reasons: "no frontend" + no .tsx/.jsx in files modified → credible
  • Detect lies: "ran pytest" but no pytest command appears in bash history → suspicious
  • Detect source-reading disguised as validation: grep/cat/read commands ≠ running tests
  • Identify project type from actual file paths (e.g., hooks/stop.py → Python hook project)

Cross-reference the agent's CLAIMS (in evidence and skip reasons) against the FACTS
(files modified, bash commands). Contradictions must be flagged.

If files_modified and bash_commands are both empty: either no tools were used (chat
session) or tracking failed. Fall back to skip reasons and evidence text, but apply
extra skepticism since no ground truth exists.

═══ STEP 2: EVALUATE SKIPPED CHECKS ═══
A skip is valid ONLY when the check genuinely does not apply to this project.
Cross-reference the skip reason against the actual files modified and bash commands.

Valid skip patterns:
  • "No test suite exists" + no test files in files_modified + no pytest/jest in bash
  • "No server — Python CLI tool" + only .py/.sh files modified
  • "No frontend" + no .tsx/.jsx/.html/.vue/.svelte in files_modified
  • "No API endpoints" + no curl/fetch/http in bash commands

Suspicious skip patterns — flag these:
  • "N/A" with no explanation
  • "Not applicable" with no project type context
  • "No frontend" when .tsx/.jsx/.html files appear in files_modified
  • "No runnable app" when server-framework imports or start scripts appear in files_modified
  • HAPPY PATH or ERROR CASES skipped with "not applicable" — these nearly always apply;
    even hook/config edits have a happy path (the hook ran correctly)
  • Same generic excuse repeated for 5+ checks → agent is dodging

═══ STEP 3: PER-CHECK EVIDENCE STANDARDS ═══
Each check has its own definition of genuine evidence. Do NOT apply a generic
"has specifics = genuine" rule. Apply the correct standard for each check.

── TESTS ────────────────────────────────────────────────────────────────────────
Bash commands must show a test runner (pytest, jest, npm test, cargo test).
Grep/cat/read of test files is NOT running tests.

GENUINE: Test runner output with pass/fail counts.
  "pytest: 12 passed, 0 failed in 1.3s"
  "npm test: ✓ 5 suites, 23 tests passed"
NOT GENUINE: "tests pass" with no output; py_compile (syntax check ≠ test runner);
  reading test files; no test runner visible in bash commands but claims "tests pass"

── BUILD ─────────────────────────────────────────────────────────────────────────
GENUINE: Compiler/bundler output with error counts.
  "tsc --noEmit: exit 0"  |  "cargo build: Finished in 4.5s"
NOT GENUINE: "build works" with no command or output; no build command in bash history

── LINT ──────────────────────────────────────────────────────────────────────────
GENUINE: Linter output with specific issue counts.
  "ruff check .: 2 warnings, 0 errors"  |  "eslint: 0 problems"
NOT GENUINE: "lint passes" with no output; no lint command in bash history

── APP STARTS ────────────────────────────────────────────────────────────────────
GENUINE: Server startup logs from an actual process.
  "Server listening on port 3000"  |  "uvicorn running on http://0.0.0.0:8000"
NOT GENUINE: "app starts" with no logs; syntax check output; no start command in bash

── API / CODE INVOCATION ─────────────────────────────────────────────────────────
GENUINE: Actual HTTP response or function return value with status code and body.
  curl with HTTP status + body  |  Python call with specific return value
NOT GENUINE: "API works"; "endpoint exists in source"; source code reading

── FRONTEND VALIDATION ───────────────────────────────────────────────────────────
STRICT. This check verifies the UI works in a browser. Reading source is NOT validation.

Check the bash commands: was playwright, test:e2e, or a browser tool actually run?
Check files_modified: if .tsx/.jsx/.html were edited, frontend validation is REQUIRED
unless those files have no UI (e.g., pure utility functions).

DOES NOT COUNT — reject even with specific file names and values:
  • "Source verification: confirmed in registry.ts / Sidebar.tsx / …"
  • "Code review of X.tsx shows setInterval removed"
  • "grep/cat confirms Cache-Control header in route.ts"
  • "tsc exit 0" / "TypeScript compiled" / "0 TS errors" (compile ≠ renders)
  • Any evidence phrased as: "source confirms", "verified in source files",
    "file inspection confirms", "code review shows"

DOES COUNT:
  • E2E output: "playwright test: 3 passed" with test names and duration
  • npm run test:e2e / npx playwright test with actual results
  • Manual browser evidence: URL + specific actions + what was SEEN
    ("opened http://localhost:3000, clicked Submit, saw success toast, 0 console errors")

SKIP VALID ONLY IF: no .tsx/.jsx/.html/.vue/.svelte in files_modified AND skip reason
names the project type ("Python hook script", "CLI tool", "backend API only").

── HAPPY PATH ────────────────────────────────────────────────────────────────────
Requires the agent to have EXECUTED something and observed the result.
Check bash commands: was the code actually run? Or only read/grepped?

GENUINE: Execution with observable outcome.
  "ran python3 -c '...', got expected output X"
  "ran pytest tests/test_x.py, 3 assertions passed — output: [...]"
  "called fn(args), returned expected_result"
NOT GENUINE:
  • "source code confirms the feature works" — inspection, not execution
  • "code review of X.py shows the logic is correct" — inspection
  • "verified implementation in source files" — inspection
  • Claims about what code SHOULD do, not what it DID when run

── ERROR CASES ───────────────────────────────────────────────────────────────────
Requires the agent to have TRIGGERED an error and OBSERVED the response.
Check bash commands: did the agent run something to provoke an error?

GENUINE: Error triggered + error response observed.
  "passed invalid input, got ValueError: expected X got Y"
  "curl /api/bad-endpoint → HTTP 404 + JSON error body"
NOT GENUINE:
  • "error handling code is present in source"
  • "try/except block exists in the file"
  • "reviewed error handling logic"
  • No bash commands that could produce errors

═══ STEP 4: EXCUSE DETECTION ═══
These agent patterns are attempts to avoid real verification. Reject them:

"Source verification confirms…" / "verified in source files" for frontend/happy/errors
  → Reject. Reading source ≠ runtime validation. Flag and require actual execution.

"Code review of [file] shows [feature] is implemented"
  → For frontend/happy_path/error_cases: Reject. Implemented ≠ working.

"Config-only change / hook edit" to bulk-skip TESTS + BUILD + APP STARTS
  → Suspicious. Even hook/config edits need syntax checked. Cross-check bash commands:
    did py_compile or equivalent actually run? If so, say that explicitly.

"No runnable app" + no bash commands → credible skip.
"No runnable app" + many bash commands → suspicious. What were those commands doing?

5+ checks skipped with generic reasons → flag as systematic dodging.

"Ran X which verifies X" with no output (circular claim) → reject.

═══ STEP 5: DISPLAY ARTIFACTS — DO NOT PENALIZE ═══
  • "[N more chars truncated]" — evidence cut for display; more real content exists.
  • "printf '{...}'" — formatting shorthand; if output follows, command ran.

Respond ONLY with valid JSON:
{
  "approved": true|false,
  "verdict": "one sentence summary",
  "suspicious_steps": ["step_key_names"],
  "instructions": "If rejected: specific corrective steps per suspicious item. If approved: empty string."
}"""

_EVIDENCE_TRUNCATE = 800
_API_URL = "https://api.deepseek.com/chat/completions"
_MODEL = "deepseek-chat"
_TIMEOUT = 20


def _build_user_message(checks: dict, context: dict | None = None) -> str:
    """Build the evidence review prompt from recorded check data."""
    lines = []

    if context:
        last_prompt  = (context.get("last_user_prompt") or "unknown")[:400]
        last_msg     = (context.get("last_assistant_message") or "")[:1000]
        task_type    = (context.get("task_type") or "unknown")
        tool_summary = context.get("tool_summary") or {}

        lines += [
            "=== WORK CONTEXT ===",
            f"Last task: {last_prompt}",
            f"Task type (classified at submit): {task_type}",
            "",
            "Last assistant message (what Claude told the user it did):",
            f"  {last_msg}",
            "",
        ]

        # Actual files modified this session (ground truth from transcript)
        files_modified = context.get("files_modified") or []
        if files_modified:
            lines.append("Files actually modified this session (from Edit/Write tool calls):")
            for f in files_modified[:30]:
                lines.append(f"  {f}")
        else:
            lines.append("Files actually modified: (none recorded)")
        lines.append("")

        # Bash commands run this session (ground truth from transcript)
        bash_cmds = context.get("bash_commands") or []
        if bash_cmds:
            lines.append("Bash commands actually run this session (last 15):")
            for cmd in bash_cmds:
                lines.append(f"  $ {cmd}")
        else:
            lines.append("Bash commands run: (none recorded)")
        lines.append("")

        # Legacy extension-count summary (if available)
        if tool_summary:
            edit_ext  = tool_summary.get("edit_extensions", {})
            write_ext = tool_summary.get("write_extensions", {})
            lines.append("File type summary:")
            lines.append("  Edited:  " + (
                ", ".join(f"{e}\u00d7{n}" for e, n in sorted(edit_ext.items())) if edit_ext else "(none)"))
            lines.append("  Written: " + (
                ", ".join(f"{e}\u00d7{n}" for e, n in sorted(write_ext.items())) if write_ext else "(none)"))
            lines.append(f"  Bash count: {tool_summary.get('bash_count', 0)}, "
                         f"Read count: {tool_summary.get('read_count', 0)}")
            lines.append("")

        lines += ["====================", ""]

    lines += [
        "Please review the following 8 verification steps and determine if the evidence is genuine.",
        "",
    ]
    for i, (key, label) in enumerate(_VR_CHECKS_ORDER, 1):
        check_data = checks.get(key, {})
        status = check_data.get("status", "pending")
        evidence = check_data.get("evidence") or ""
        skip_reason = check_data.get("skip_reason") or ""

        lines.append(f"--- Step {i}: {label} ---")
        lines.append(f"Status: {status}")
        if status == "skipped":
            display = skip_reason[:_EVIDENCE_TRUNCATE]
            lines.append(f"Skip reason: {display!r}")
        elif status == "done":
            display = evidence[:_EVIDENCE_TRUNCATE]
            lines.append(f"Evidence: {display!r}")
        else:
            lines.append("Evidence: (none — check was never completed)")
        lines.append("")

    return "\n".join(lines)


def _skipped(reason: str) -> dict:
    return {
        "approved": True,
        "verdict": "",
        "suspicious_steps": [],
        "instructions": "",
        "skipped": True,
        "skip_reason": reason,
    }


def verify_with_deepseek(checks: dict, context: dict | None = None) -> dict:
    """Review verification evidence with DeepSeek Chat.

    Args:
        checks  - Verification check data from the stop hook
        context - Optional dict with 'last_user_prompt' and 'last_assistant_message'
                  so DeepSeek can calibrate expectations to the actual work done.

    Returns:
        approved      - True if evidence looks genuine (or verifier was skipped)
        verdict       - One-sentence summary from DeepSeek
        suspicious_steps - Keys of suspicious checks
        instructions  - What the agent must do (empty string if approved)
        skipped       - True when verifier did not run (key missing, timeout, error)
        skip_reason   - Why it was skipped (empty string when ran successfully)

    Never raises.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return _skipped("DEEPSEEK_API_KEY not set")

    try:
        user_message = _build_user_message(checks, context)
        payload = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": 500,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        req = urllib.request.Request(_API_URL, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8")

        response_data = json.loads(raw)
        content = response_data["choices"][0]["message"]["content"]

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Keyword fallback: if response text signals rejection, treat as rejected
            lower = content.lower()
            if any(kw in lower for kw in ("suspicious", "false", "rejected", "fabricated")):
                return {
                    "approved": False,
                    "verdict": "Evidence quality rejected (raw response, JSON parse failed)",
                    "suspicious_steps": [],
                    "instructions": content[:1000],
                    "skipped": False,
                    "skip_reason": "",
                }
            return _skipped("JSON parse failure on API response")

        approved = bool(result.get("approved", True))
        return {
            "approved": approved,
            "verdict": str(result.get("verdict", "")),
            "suspicious_steps": list(result.get("suspicious_steps", [])),
            "instructions": str(result.get("instructions", "")),
            "skipped": False,
            "skip_reason": "",
        }

    except urllib.error.HTTPError as exc:
        return _skipped(f"API error: {exc.code}")
    except urllib.error.URLError as exc:
        reason = str(exc.reason)
        if "timed out" in reason.lower() or "timeout" in reason.lower():
            return _skipped("API timeout")
        return _skipped(f"API error: {reason}")
    except TimeoutError:
        return _skipped("API timeout")
    except Exception as exc:
        return _skipped(f"verifier error: {type(exc).__name__}")
