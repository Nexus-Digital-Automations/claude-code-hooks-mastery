#!/usr/bin/env python3
"""
Dynamic check registration and execution for stop-hook validation.

Two modes:
  --pre-review   DeepSeek-review a command before registering it. Writes to
                 dynamic_checks.json if approved.
  --run          Execute all registered commands and record results in
                 verification_record.json.

Usage:
  python3 dynamic_validator.py --pre-review --check tests \
      --command "pytest tests/ -v" --pattern "passed" \
      --description "Runs pytest suite"

  python3 dynamic_validator.py --run \
      --dc-file .claude/data/dynamic_checks.json \
      --vr-file .claude/data/verification_record.json \
      --only-pending
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error


DYNAMIC_CHECK_KEYS = {"tests", "build", "app_starts", "api", "frontend"}

# Commands that trivially always succeed (local blocklist, pre-DeepSeek)
_TRIVIAL_COMMANDS = {
    "true", "false", "exit 0", "exit 1", "pwd", "ls", "ls -la", "ls -l",
    "echo", "printf", "date", "whoami", "hostname", ":", "[ true ]",
    "test 1 -eq 1", "cat /dev/null",
}

_TRIVIAL_PATTERNS = {".*", ".", "", " "}


# ── Local validation (before DeepSeek) ────────────────────────────────────

def local_validate(check_key: str, command: str, pattern: str, description: str) -> tuple[bool, str]:
    """Quick local checks before calling DeepSeek. Returns (ok, reason)."""
    if check_key not in DYNAMIC_CHECK_KEYS:
        return False, f"'{check_key}' is not a dynamic check key. Valid: {sorted(DYNAMIC_CHECK_KEYS)}"
    cmd_stripped = command.strip().lower()
    if cmd_stripped in _TRIVIAL_COMMANDS:
        return False, f"Command '{command}' is trivially simple — not valid evidence"
    if len(command.strip()) < 5:
        return False, "Command too short (< 5 chars)"
    if cmd_stripped.startswith("echo ") or cmd_stripped.startswith("printf "):
        return False, "echo/printf commands produce fabricated output, not real evidence"
    if pattern.strip() in _TRIVIAL_PATTERNS:
        return False, f"Pattern '{pattern}' is too permissive — provide a specific expected string"
    if len(description.strip()) < 20:
        return False, "Description too short (min 20 chars) — explain what this validates"
    # Detect self-referential commands
    for forbidden in ["check-tests.sh", "check-build.sh", "authorize-stop.sh",
                      "verification_record.json", "dynamic_checks.json"]:
        if forbidden in command:
            return False, f"Command must not reference hook internals ({forbidden})"
    return True, ""


# ── DeepSeek pre-review ────────────────────────────────────────────────────

_PRE_REVIEW_SYSTEM = """\
You are a strict security auditor for a code quality enforcement system.
An AI coding agent wants to register a shell command that will be automatically
executed by the stop-hook validation system as evidence that their work is done.

YOUR DEFAULT IS SUSPICION. Approve only when the command clearly validates
the stated check type with real execution.

═══ AUTOMATIC REJECTION ═══
Trivial/always-succeed: true, false, exit 0, echo anything, pwd, ls, date
Trivially permissive pattern: empty, ".*", single char
Type mismatch: test check with ls/grep/cat; build check with echo; api check without HTTP/fn call
Self-referential: writes to JSON files, calls check-*.sh or authorize-stop.sh
Escape hatches: || true, || exit 0, 2>/dev/null combined with ".*" pattern
Too vague description vs. specific command

═══ VALID EXAMPLES ═══
tests:       "pytest tests/ -v --tb=short"  pattern: "passed"
tests:       "npm test 2>&1"                pattern: "passing"
tests:       "cargo test 2>&1"              pattern: "test result: ok"
build:       "npm run build 2>&1"           pattern: "compiled successfully"
build:       "tsc --noEmit 2>&1"            pattern: "Found 0 errors"
build:       "cargo build 2>&1"             pattern: "Finished"
app_starts:  "timeout 8 npm start 2>&1"    pattern: "listening"
app_starts:  "timeout 8 python main.py"    pattern: "running on"
api:         "curl -s http://localhost:3000/api/health" pattern: "ok"
api:         "python -c 'from app import fn; print(fn({}))'  " pattern: "expected_value"
frontend:    "npx playwright test 2>&1"     pattern: "passed"
frontend:    "npm run test:e2e 2>&1"        pattern: "pass"

═══ INVALID EXAMPLES ═══
tests:    "echo 'all tests pass'"  — fabricated
build:    "ls dist/"               — doesn't run compiler
app_starts: "grep 'port' config.json" — doesn't start app
api:      "cat src/routes.js"      — doesn't call API
frontend: "echo 'looks good'"     — fabricated

Cross-check: does description match what the command actually does?

Respond ONLY with valid JSON (no markdown, no explanation outside JSON):
{"approved": true|false, "verdict": "one sentence", "rejection_reason": "if rejected: specific reason; if approved: empty string"}
"""


def deepseek_review(
    check_key: str,
    command: str,
    pattern: str,
    description: str,
    project_context: str,
    timeout: int = 20,
) -> dict:
    """
    Call DeepSeek to review a dynamic command before registration.
    Returns {"approved": bool, "verdict": str, "rejection_reason": str,
             "skipped": bool, "skip_reason": str}.
    Never raises.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    if not api_key:
        return {
            "approved": True, "verdict": "DEEPSEEK_API_KEY not set — skipping review",
            "rejection_reason": "", "skipped": True,
            "skip_reason": "DEEPSEEK_API_KEY not set",
        }

    user_msg = (
        f"Check type: {check_key}\n"
        f"Command: {command}\n"
        f"Expected pattern: {pattern}\n"
        f"Description: {description}\n"
        f"Project context: {project_context}\n"
    )

    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": _PRE_REVIEW_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 200,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }).encode()

    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
        content = body["choices"][0]["message"]["content"]
        result = json.loads(content)
        return {
            "approved": bool(result.get("approved", False)),
            "verdict": result.get("verdict", ""),
            "rejection_reason": result.get("rejection_reason", ""),
            "skipped": False,
            "skip_reason": "",
        }
    except Exception as e:
        # API error — fail open (allow registration but mark as unreviewed)
        return {
            "approved": True,
            "verdict": f"DeepSeek review failed: {e} — allowing with warning",
            "rejection_reason": "",
            "skipped": True,
            "skip_reason": str(e),
        }


# ── Registration (--pre-review mode) ──────────────────────────────────────

def pre_review_and_register(
    check_key: str,
    command: str,
    pattern: str,
    description: str,
    dc_file: Path,
    cwd: Path,
) -> int:
    """
    Validate, DeepSeek-review, and register a dynamic check.
    Returns 0 on success, 1 on rejection.
    """
    # Local validation first
    ok, reason = local_validate(check_key, command, pattern, description)
    if not ok:
        print(f"❌ Rejected (local validation): {reason}", file=sys.stderr)
        return 1

    # DeepSeek review
    project_files = ", ".join(
        f.name for f in sorted(cwd.iterdir())[:10]
        if f.is_file()
    ) if cwd.exists() else "unknown"
    project_context = f"CWD: {cwd}\nProject files: {project_files}"

    print("Sending command to DeepSeek for review...", file=sys.stderr)
    review = deepseek_review(check_key, command, pattern, description, project_context)

    if not review["approved"]:
        print(f"❌ Rejected by DeepSeek: {review['rejection_reason']}", file=sys.stderr)
        print(f"   Verdict: {review['verdict']}", file=sys.stderr)
        return 1

    if review.get("skipped"):
        print(f"⚠️  DeepSeek review skipped: {review['skip_reason']}", file=sys.stderr)
    else:
        print(f"✅ DeepSeek approved: {review['verdict']}", file=sys.stderr)

    # Write to dynamic_checks.json
    try:
        dc_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            dc = json.loads(dc_file.read_text())
        except Exception:
            dc = {"project_root": str(cwd), "registered_at": datetime.now().isoformat(), "checks": {}}

        dc["checks"][check_key] = {
            "command": command,
            "expected_pattern": pattern,
            "description": description,
            "registered_at": datetime.now().isoformat(),
            "deepseek_reviewed": not review.get("skipped", False),
            "deepseek_approved": review["approved"],
            "deepseek_verdict": review["verdict"],
            "deepseek_rejection_reason": review["rejection_reason"],
            "run_result": None,
        }
        dc_file.write_text(json.dumps(dc, indent=2))
        print(f"✅ Registered dynamic check '{check_key}': {command}", file=sys.stderr)
        return 0
    except Exception as e:
        print(f"❌ Failed to write dynamic_checks.json: {e}", file=sys.stderr)
        return 1


# ── Execution (--run mode) ─────────────────────────────────────────────────

def _run_cmd(command: str, cwd: Path, timeout: int = 60) -> tuple[int, str, str]:
    """Run a shell command. Returns (rc, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            cwd=str(cwd), timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"[timeout after {timeout}s]"
    except Exception as e:
        return -1, "", str(e)


def _write_vr(vr_file: Path, key: str, status: str, evidence: str) -> None:
    """Write one check entry to verification_record.json."""
    try:
        try:
            record = json.loads(vr_file.read_text())
        except Exception:
            record = {"reset_at": datetime.now().isoformat(), "checks": {}}
        # Session guard: prevent cross-session VR contamination
        _cur_sid = None
        try:
            ct = json.loads((Path.home() / ".claude/data/current_task.json").read_text())
            _cur_sid = ct.get("session_id")
        except Exception:
            pass
        if _cur_sid and record.get("session_id") and record["session_id"] != _cur_sid:
            record = {"reset_at": datetime.now().isoformat(), "session_id": _cur_sid, "checks": {}}
        record.setdefault("checks", {})[key] = {
            "status": status,
            "evidence": evidence[:2000] if evidence else None,
            "timestamp": datetime.now().isoformat(),
            "skip_reason": None,
        }
        vr_file.write_text(json.dumps(record, indent=2))
    except Exception:
        pass


def _is_pending(vr_file: Path, key: str) -> bool:
    try:
        return json.loads(vr_file.read_text()).get("checks", {}).get(key, {}).get("status", "pending") == "pending"
    except Exception:
        return True


def run_dynamic_checks(
    dc_file: Path,
    vr_file: Path,
    cwd: Path,
    only_pending: bool = True,
    timeout_per_check: int = 60,
) -> dict[str, str]:
    """
    Run all registered dynamic checks. Record results in vr_file.
    Returns dict of check_key -> "passed"|"failed"|"skipped"|"not_registered".
    """
    results = {}

    if not dc_file.exists():
        return results

    try:
        dc = json.loads(dc_file.read_text())
    except Exception:
        return results

    # CWD mismatch guard — prevent cross-project execution
    registered_root = dc.get("project_root", "")
    if registered_root and registered_root != str(cwd):
        print(
            f"[dynamic] ⚠️  Skipping: dynamic_checks.json was registered for "
            f"'{registered_root}', current dir is '{cwd}'",
            file=sys.stderr,
        )
        return results

    checks = dc.get("checks", {})
    for key, entry in checks.items():
        if key not in DYNAMIC_CHECK_KEYS:
            continue
        if only_pending and not _is_pending(vr_file, key):
            results[key] = "already_done"
            continue
        if not entry.get("deepseek_approved", False):
            evidence = f"[dynamic: REJECTED by DeepSeek] {entry.get('deepseek_rejection_reason', 'unknown reason')}"
            _write_vr(vr_file, key, "done", evidence)
            results[key] = "rejected"
            print(f"[dynamic] {key}: DeepSeek-rejected, skipping execution", file=sys.stderr)
            continue

        command = entry.get("command", "")
        pattern = entry.get("expected_pattern", "")

        print(f"[dynamic] Running {key}: {command[:60]}...", file=sys.stderr)
        rc, stdout, stderr = _run_cmd(command, cwd, timeout_per_check)
        matched = bool(re.search(pattern, stdout)) if pattern else True

        # Build evidence
        status_tag = "PASSED" if rc == 0 and matched else ("PATTERN NOT MATCHED" if rc == 0 else "FAILED")
        evidence = (
            f"[auto-run: {status_tag}]\n"
            f"$ {command}\n"
            f"exit: {rc}\n"
            f"pattern: '{pattern}' → {'✅ matched' if matched else '❌ not matched'}\n"
            f"{stdout[:1500]}"
        )
        if stderr:
            evidence += f"\nstderr: {stderr[:300]}"

        _write_vr(vr_file, key, "done", evidence)

        # Update run_result in dynamic_checks.json
        try:
            entry["run_result"] = {
                "exit_code": rc,
                "stdout": stdout[:2000],
                "stderr": stderr[:500],
                "matched_pattern": matched,
                "ran_at": datetime.now().isoformat(),
            }
            dc_file.write_text(json.dumps(dc, indent=2))
        except Exception:
            pass

        result_str = "passed" if rc == 0 and matched else "failed"
        results[key] = result_str
        print(f"[dynamic] {key}: {result_str} (exit={rc}, matched={matched})", file=sys.stderr)

    return results


# ── CLI ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pre-review", action="store_true",
                        help="Review and register a dynamic check")
    parser.add_argument("--run", action="store_true",
                        help="Execute registered dynamic checks")
    parser.add_argument("--check")
    parser.add_argument("--command")
    parser.add_argument("--pattern")
    parser.add_argument("--description")
    parser.add_argument("--dc-file", default=".claude/data/dynamic_checks.json")
    parser.add_argument("--vr-file")
    parser.add_argument("--only-pending", action="store_true")
    parser.add_argument("--timeout", type=int, default=60)

    args = parser.parse_args()
    cwd = Path.cwd()

    if args.pre_review:
        for required in ("check", "command", "pattern", "description"):
            if not getattr(args, required):
                print(f"❌ --{required} is required for --pre-review", file=sys.stderr)
                sys.exit(1)
        dc_file = Path(args.dc_file)
        sys.exit(pre_review_and_register(
            args.check, args.command, args.pattern, args.description, dc_file, cwd
        ))

    elif args.run:
        if not args.vr_file:
            print("❌ --vr-file is required for --run", file=sys.stderr)
            sys.exit(1)
        dc_file = Path(args.dc_file)
        vr_file = Path(args.vr_file)
        vr_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            results = run_dynamic_checks(dc_file, vr_file, cwd, args.only_pending, args.timeout)
            failed = [k for k, v in results.items() if v == "failed"]
            if failed:
                print(f"[dynamic] ⚠️  Failed checks: {failed}", file=sys.stderr)
            sys.exit(0)  # Never block stop on dynamic check runner failure
        except Exception as e:
            print(f"[dynamic] error: {e}", file=sys.stderr)
            sys.exit(0)

    else:
        parser.print_help()
        sys.exit(1)
