#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import json
import os
import sys
import re
from pathlib import Path

# Add hooks directory to path for utils imports
sys.path.insert(0, str(Path(__file__).parent))

# Fix Python environment warnings
for var in ['PYTHONHOME', 'PYTHONPATH']:
    if var in os.environ:
        del os.environ[var]

def get_current_focus(cwd):
    """
    Find the first unfinished task in FEATURES.md.
    Returns the task text or None if no unfinished tasks.
    """
    features_file = Path(cwd) / "docs" / "development" / "FEATURES.md"

    if not features_file.exists():
        return None

    try:
        content = features_file.read_text()
        match = re.search(r'^- \[ \] (.+)$', content, re.MULTILINE)
        if match:
            return match.group(1).strip()
    except Exception:
        pass

    return None


_CODING_STANDARDS = """\
CODE STANDARDS (enforced at every Write/Edit):
SIMPLICITY: No abstractions for single-use code. No "flexibility" or "configurability" not requested. If 200 lines could be 50, rewrite. Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.
SURGICAL: Every changed line must trace to the user's request. Match existing style (quotes, spacing, patterns). Remove only orphans YOUR changes created. Unrelated dead code: mention it, don't delete it.
ARCHITECTURE: Dependencies point inward — UI/DB depend on business logic, never reverse. Cross boundaries with DTOs, not entities. Strip all logic out of UI/DB classes (Humble Objects). No pass-through layers that only delegate.
FUNCTIONS: One thing, one abstraction level. ~40 lines max. No bool flag params (proves two responsibilities). Commands change state OR return data, never both (CQS). Prefer data-transformation pipelines over stateful class hierarchies.
NAMES: Precise nouns (classes), strong verbs (methods). Generic names forbidden: data, manager, processor, handler, helper, util as the full identifier. One concept = one name everywhere — never use synonyms for the same domain entity.
COMMENTS: Explain WHY (business rule, algorithm choice). Never explain WHAT mechanically — delete those. No encoded/abbreviated names.
ERRORS: Throw exceptions, not error codes. Never swallow exceptions silently. Crash early and loudly on invalid state. Never return null/None as an error signal — use Optional, empty collection, or Special Case.
LOGGING: Every new function that can fail must log the error before raising/re-raising. New API handlers log: method, path, status code, and duration. Auth/security events always logged: login, logout, permission denied, token invalid/expired. Background tasks/workers log start, completion, and every failure path. Never log PII (emails, passwords, tokens, session keys) — sanitize before logging. Use structured key=value or JSON fields for machine-parseable entries, not unstructured f-strings. Use the project's existing logger, not print().
CONCURRENCY: No shared mutable state. Use actor models, immutable structures, or pure transformations. Sporadic failures indicate threading defects — fix root cause, never retry-loop.
TESTING: Only write tests for critical business domains (payments, auth, billing, data integrity, financial, security). Most code does NOT need tests. When tests ARE needed, they must be Fast, Independent, Repeatable, Self-Validating. Cover boundary conditions and data states. See ~/.claude/data/critical-paths.json.
DOCUMENTATION (AI-agent legibility — future agents must be able to navigate this codebase):
  • Every new file: opening docstring stating what it owns, what it explicitly does NOT own, and what calls it vs. what it calls.
  • Every public function with non-obvious failure modes: document raises, never-returns-null guarantees, and what callers must NOT assume.
  • Every stateful class: comment diagram of valid states and transitions (even 3 lines of ASCII is enough).
  • Inline decision records for non-obvious choices: WHY this approach, what was rejected, what would invalidate the decision.
  • Cross-reference comments when one side of a contract is elsewhere: '# Counterpart: see X' or '# Also updates Y'.
  • Extension points: mark with '# EXTENSION POINT' so agents know where to add vs. where not to modify.
  • Stability signals: '# @stable' (external callers depend on this), '# @internal' (safe to refactor), '# @deprecated prefer X'.
  • Test names must read as specifications: test_raises_when_order_is_not_pending, not test_apply_discount.\
"""


def get_context_injection(cwd, tool_name, tool_input=None):
    """
    Build lightweight context injection: current task, security reminder,
    coding standards, and tool-specific docs only.
    """
    docs_dir = Path(cwd) / "docs" / "development"
    hooks_dir = docs_dir / "hooks"
    injections = []

    # 1. Auto-derive focus from first unfinished task in FEATURES.md
    current_task = get_current_focus(cwd)
    if current_task:
        injections.append(f"CURRENT TASK: {current_task}")

    # 2. Security reminder + coding standards for Write/Edit operations
    if tool_name in ['Write', 'Edit', 'MultiEdit']:
        injections.append("SECURITY: Never write secrets (API keys, passwords, tokens) outside of .env files or gitignored files")
        injections.append(_CODING_STANDARDS)

        # 2b. Warn when modifying .security-ignore (reviewer will audit this)
        file_path = (tool_input or {}).get('file_path', '')
        if file_path.endswith('.security-ignore'):
            injections.append(
                "WARNING: You are modifying .security-ignore. The reviewer "
                "(Phase 8) will audit this change. Every rule MUST have a "
                "preceding comment explaining WHY the suppression is justified. "
                "Do NOT add broad patterns (src/**, *.py, [severity:critical]). "
                "Do NOT suppress credential categories (hardcoded-secret, "
                "hardcoded-aws-key, github-pat, openai-key). Suppressions must "
                "be file-specific and narrow."
            )

    # 3. Inject tool-specific context if exists
    tool_map = {
        'Bash': 'bash.md',
        'Edit': 'edit.md',
        'Write': 'edit.md',
        'MultiEdit': 'edit.md',
    }

    if tool_name in tool_map:
        tool_file = hooks_dir / tool_map[tool_name]
        if tool_file.exists():
            try:
                content = tool_file.read_text().strip()
                if content:
                    injections.append(f"{tool_name}: {content[:150]}")
            except Exception:
                pass

    return "\n".join(injections) if injections else None


# IMP-9: Read from the same env var that the Qwen server uses so the two
# systems never drift apart.  Falls back to the historical default.
QWEN_BASE_PATH = os.environ.get(
    "QWEN_PROJECTS_ROOT",
    "/Users/jeremyparker/Desktop/Claude Coding Projects",
)


def _path_within_base(path_str: str, base: str) -> bool:
    """Return True iff path_str is strictly inside base (not equal to base)."""
    resolved = str(Path(path_str).resolve())
    return resolved != base and resolved.startswith(base + "/")


def check_qwen_working_dir(tool_name, tool_input):
    """
    Block mcp__qwen-agent__run calls whose working_dir (or allowed_dirs)
    fall outside QWEN_BASE_PATH.

    Allowed without working_dir:
      - agent_id is set (reusing an existing agent — working_dir already locked in)
      - config.scope.allowed_dirs is non-empty and all entries are within base path

    Returns (blocked: bool, reason: str | None).
    """
    if tool_name != "mcp__qwen-agent__run":
        return False, None

    base = str(Path(QWEN_BASE_PATH).resolve())

    # IMP-10: Reusing an existing agent — working_dir was validated at creation.
    if tool_input.get("agent_id"):
        return False, None

    working_dir = (tool_input.get("working_dir") or "").strip()

    if not working_dir:
        # IMP-10: Allow if config.scope.allowed_dirs is set and all entries are in base.
        allowed_dirs = (
            tool_input.get("config", {})
            .get("scope", {})
            .get("allowed_dirs", [])
        )
        if allowed_dirs and all(_path_within_base(d, base) for d in allowed_dirs):
            return False, None

        return True, (
            "BLOCKED: mcp__qwen-agent__run requires a working_dir "
            "(or agent_id to reuse an existing agent).\n"
            f"working_dir must be a subdirectory of: {QWEN_BASE_PATH}\n"
            "Example: working_dir=\"/Users/jeremyparker/Desktop/Claude Coding Projects/my-project\"\n"
            "Tip: set QWEN_PROJECTS_ROOT env var to change the allowed root."
        )

    # Validate working_dir is strictly inside base
    if not _path_within_base(working_dir, base):
        return True, (
            f"BLOCKED: working_dir '{working_dir}' is outside the allowed workspace.\n"
            f"Allowed: subdirectories of {QWEN_BASE_PATH}\n"
            "The base path itself is not a valid working directory — specify a named subproject.\n"
            "Tip: set QWEN_PROJECTS_ROOT env var to change the allowed root."
        )

    return False, None


def is_env_file_write(tool_name, tool_input):
    """
    Check if any tool is trying to WRITE/EDIT .env files containing sensitive data.
    Reading .env files is allowed; only modifications are blocked.
    """
    # Only block write/edit operations, not reads
    if tool_name in ['Edit', 'MultiEdit', 'Write']:
        file_path = tool_input.get('file_path', '')
        if '.env' in file_path and not file_path.endswith('.env.sample'):
            return True

    # Check bash commands for .env file modifications (but allow cat/reading)
    elif tool_name == 'Bash':
        command = tool_input.get('command', '')
        # Pattern to detect .env file WRITE operations (not reads)
        env_write_patterns = [
            r'echo\s+.*>\s*\.env\b(?!\.sample)',  # echo > .env
            r'touch\s+.*\.env\b(?!\.sample)',  # touch .env
            r'cp\s+.*\.env\b(?!\.sample)',  # cp .env
            r'mv\s+.*\.env\b(?!\.sample)',  # mv .env
            r'>\s*\.env\b(?!\.sample)',  # redirect to .env
            r'>>\s*\.env\b(?!\.sample)',  # append to .env
            r'rm\s+.*\.env\b(?!\.sample)',  # rm .env
            r'sed\s+-i.*\.env\b(?!\.sample)',  # sed -i .env (in-place edit)
        ]

        for pattern in env_write_patterns:
            if re.search(pattern, command):
                return True

    return False

def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)
        
        tool_name = input_data.get('tool_name', '')
        tool_input = input_data.get('tool_input', {})
        
        # Check for .env file writes (blocks modifications to sensitive environment files)
        if is_env_file_write(tool_name, tool_input):
            print("BLOCKED: Writing/editing .env files is prohibited", file=sys.stderr)
            print("Reading .env is allowed; use .env.sample for templates", file=sys.stderr)
            sys.exit(2)  # Exit code 2 blocks tool call and shows error to Claude

        # Enforce Qwen working_dir confinement
        ds_blocked, ds_reason = check_qwen_working_dir(tool_name, tool_input)
        if ds_blocked:
            print(ds_reason, file=sys.stderr)
            sys.exit(2)

        # Inject context from FEATURES.md, MCP tools (neural, swarm, github)
        cwd = input_data.get('cwd', os.getcwd())
        context = get_context_injection(cwd, tool_name, tool_input)
        if context:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "additionalContext": context
                }
            }
            print(json.dumps(output))

        # Log to JSONL file (append-only, safe for concurrent access)
        log_dir = Path.home() / '.claude' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'pre_tool_use.jsonl'

        with open(log_path, 'a') as f:
            f.write(json.dumps(input_data) + '\n')
        
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Gracefully handle JSON decode errors
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)

if __name__ == '__main__':
    main()