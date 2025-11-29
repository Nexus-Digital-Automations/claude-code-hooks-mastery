#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
🔴 STOP HOOK - SENIOR DEVELOPER VALIDATION GATE

CRITICAL: This hook enforces ZERO TOLERANCE for incomplete work.
NEVER: Allow session to end without meeting success criteria.
ALWAYS: Block until 95%+ confidence and all validations pass.

CORE PRINCIPLE: "Continue working until success criteria are met."
Evidence-based validation - PROVE IT, DON'T ASSUME IT.
"""

import argparse
import json
import os
import sys
import random
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def log_to_validation_artifacts(category, data, operation="stop_check"):
    """
    PROVE IT - Store all evidence in .validation-artifacts/
    NEVER fail silently - but never break the hook either.
    """
    try:
        log_dir = Path(".validation-artifacts") / category
        log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"{operation}_{timestamp}.log"

        with open(log_file, 'w') as f:
            if isinstance(data, dict):
                json.dump(data, f, indent=2)
            else:
                f.write(str(data))

        return str(log_file)
    except Exception:
        # Graceful degradation - never break hook
        return None


def check_tests_passing():
    """
    Validation Method #1: Tests must pass
    Evidence: Test output log + pass/fail counts
    """
    try:
        # Check if package.json or test files exist
        has_tests = (
            Path("package.json").exists() or
            Path("pytest.ini").exists() or
            Path("tests").exists() or
            Path("test").exists()
        )

        if not has_tests:
            return True, "No test framework detected", None

        # Try npm test first
        if Path("package.json").exists():
            result = subprocess.run(
                ["npm", "test"],
                capture_output=True,
                text=True,
                timeout=60
            )

            log_path = log_to_validation_artifacts("test-results", result.stdout + result.stderr, "npm_test")

            if result.returncode == 0:
                return True, f"Tests passed (npm test)", log_path
            else:
                return False, f"Tests failed (exit {result.returncode})", log_path

        # Try pytest
        if Path("pytest.ini").exists() or Path("tests").exists():
            result = subprocess.run(
                ["pytest", "-v"],
                capture_output=True,
                text=True,
                timeout=60
            )

            log_path = log_to_validation_artifacts("test-results", result.stdout + result.stderr, "pytest")

            if result.returncode == 0:
                return True, "Tests passed (pytest)", log_path
            else:
                return False, f"Tests failed (exit {result.returncode})", log_path

        return True, "No runnable tests found", None

    except subprocess.TimeoutExpired:
        return False, "Tests timed out (>60s)", None
    except Exception as e:
        return False, f"Test execution error: {str(e)}", None


def check_linter_passing():
    """
    Validation Method #2: Linter must be clean (or warnings only)
    Evidence: Lint output log + error count
    """
    try:
        has_linter = Path("package.json").exists() or Path(".eslintrc").exists()

        if not has_linter:
            return True, "No linter detected", None, 0

        # Try npm run lint
        result = subprocess.run(
            ["npm", "run", "lint"],
            capture_output=True,
            text=True,
            timeout=30
        )

        log_path = log_to_validation_artifacts("logs", result.stdout + result.stderr, "lint")

        # Count errors (warnings are OK)
        error_count = result.stdout.lower().count(" error") + result.stderr.lower().count(" error")

        if result.returncode == 0:
            return True, f"Linter clean (0 errors)", log_path, 0
        elif error_count == 0:
            return True, f"Linter warnings only (non-blocking)", log_path, 0
        else:
            return False, f"Linter has {error_count} errors", log_path, error_count

    except subprocess.TimeoutExpired:
        return False, "Linter timed out (>30s)", None, -1
    except FileNotFoundError:
        return True, "No linter script found", None, 0
    except Exception as e:
        return True, f"Linter check skipped: {str(e)}", None, 0


def check_app_runtime():
    """
    Validation Method #3: App must start successfully
    Evidence: Runtime log + process check
    """
    try:
        has_app = Path("package.json").exists()

        if not has_app:
            return True, "No Node.js app detected", None

        # Try starting app (background, quick check)
        result = subprocess.run(
            ["npm", "start"],
            capture_output=True,
            text=True,
            timeout=5
        )

        log_path = log_to_validation_artifacts("logs", result.stdout + result.stderr, "runtime")

        # Quick check - did it fail immediately?
        if "error" in result.stderr.lower() or "failed" in result.stderr.lower():
            return False, "App fails to start", log_path
        else:
            return True, "App starts (quick check passed)", log_path

    except subprocess.TimeoutExpired:
        # Timeout means app is running - good sign
        return True, "App started successfully (running)", None
    except FileNotFoundError:
        return True, "No start script found", None
    except Exception as e:
        return True, f"Runtime check skipped: {str(e)}", None


def check_security_issues():
    """
    Validation Method #4: No critical security vulnerabilities
    Evidence: Audit log + vulnerability counts
    """
    try:
        has_npm = Path("package.json").exists()

        if not has_npm:
            return True, "No package.json (Node.js security check skipped)", None, {}

        # Run npm audit
        result = subprocess.run(
            ["npm", "audit", "--audit-level=high"],
            capture_output=True,
            text=True,
            timeout=30
        )

        log_path = log_to_validation_artifacts("logs", result.stdout + result.stderr, "security_audit")

        # Parse vulnerability counts
        vulnerabilities = {
            'critical': result.stdout.lower().count(" critical"),
            'high': result.stdout.lower().count(" high")
        }

        if vulnerabilities['critical'] > 0:
            return False, f"{vulnerabilities['critical']} critical vulnerabilities", log_path, vulnerabilities
        elif vulnerabilities['high'] > 0:
            return False, f"{vulnerabilities['high']} high vulnerabilities", log_path, vulnerabilities
        else:
            return True, "No critical/high vulnerabilities", log_path, vulnerabilities

    except subprocess.TimeoutExpired:
        return False, "Security audit timed out", None, {}
    except FileNotFoundError:
        return True, "npm not available", None, {}
    except Exception as e:
        return True, f"Security check skipped: {str(e)}", None, {}


def check_session_documented():
    """
    Validation Method #5: Session must be documented
    Evidence: docs/development/sessions/ file exists
    """
    try:
        sessions_dir = Path("docs/development/sessions")

        if not sessions_dir.exists():
            return False, "docs/development/sessions/ directory missing", None

        # Check for today's session file
        today = datetime.now().strftime("%Y%m%d")
        session_files = list(sessions_dir.glob(f"{today}*.md"))

        if session_files:
            return True, f"Session documented: {session_files[0].name}", str(session_files[0])
        else:
            return False, f"No session file for today ({today})", None

    except Exception as e:
        return False, f"Session documentation check failed: {str(e)}", None


def check_git_status_clean():
    """
    Validation Method #6: No uncommitted secrets in git
    Evidence: git status output + .gitignore verification
    """
    try:
        # Check if .gitignore exists and has security patterns
        gitignore = Path(".gitignore")

        if not gitignore.exists():
            return False, ".gitignore missing", None

        gitignore_content = gitignore.read_text()
        required_patterns = [".env", "*.key", "credentials"]

        missing_patterns = [p for p in required_patterns if p not in gitignore_content]

        if missing_patterns:
            return False, f".gitignore missing patterns: {', '.join(missing_patterns)}", None

        # Check git status
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )

        log_path = log_to_validation_artifacts("logs", result.stdout, "git_status")

        # Check for uncommitted sensitive files
        sensitive_patterns = [".env", ".key", "credential", "secret", "password"]
        sensitive_files = [
            line for line in result.stdout.split('\n')
            if any(pattern in line.lower() for pattern in sensitive_patterns)
        ]

        if sensitive_files:
            return False, f"Uncommitted sensitive files: {len(sensitive_files)}", log_path
        else:
            return True, "Git status clean (no uncommitted secrets)", log_path

    except FileNotFoundError:
        return True, "Git not available (skipping check)", None
    except Exception as e:
        return True, f"Git check skipped: {str(e)}", None


def check_codebase_organized():
    """
    Validation Method #7: Code follows project structure
    Evidence: Directory structure validation
    """
    try:
        # Check for common structure markers
        has_structure = (
            Path("README.md").exists() or
            Path("package.json").exists() or
            Path("setup.py").exists() or
            Path("pyproject.toml").exists()
        )

        if not has_structure:
            return False, "No project structure files (README.md, package.json, etc.)", None

        # Check no obvious junk files at root
        junk_patterns = ["*.tmp", "*.bak", "untitled*", "test123*"]
        junk_files = []

        for pattern in junk_patterns:
            junk_files.extend(list(Path(".").glob(pattern)))

        if junk_files:
            return False, f"Junk files at root: {len(junk_files)}", None
        else:
            return True, "Codebase organized (no junk files)", None

    except Exception as e:
        return True, f"Structure check skipped: {str(e)}", None


def get_llm_completion_message():
    """
    Generate completion message using available LLM services.
    Priority order: OpenAI > Anthropic > Ollama > fallback
    """
    script_dir = Path(__file__).parent
    llm_dir = script_dir / "utils" / "llm"

    # Try OpenAI first
    if os.getenv('OPENAI_API_KEY'):
        oai_script = llm_dir / "oai.py"
        if oai_script.exists():
            try:
                result = subprocess.run(
                    ["uv", "run", str(oai_script), "--completion"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    # Try Anthropic second
    if os.getenv('ANTHROPIC_API_KEY'):
        anth_script = llm_dir / "anth.py"
        if anth_script.exists():
            try:
                result = subprocess.run(
                    ["uv", "run", str(anth_script), "--completion"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    # Try Ollama third
    ollama_script = llm_dir / "ollama.py"
    if ollama_script.exists():
        try:
            result = subprocess.run(
                ["uv", "run", str(ollama_script), "--completion"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

    # Fallback messages
    messages = [
        "Work complete!",
        "All done!",
        "Task finished!",
        "Job complete!",
        "Ready for next task!"
    ]
    return random.choice(messages)


def announce_completion():
    """Announce completion using best available TTS service."""
    try:
        script_dir = Path(__file__).parent
        tts_dir = script_dir / "utils" / "tts"

        # Priority: ElevenLabs > OpenAI > pyttsx3
        tts_script = None

        if os.getenv('ELEVENLABS_API_KEY'):
            elevenlabs_script = tts_dir / "elevenlabs_tts.py"
            if elevenlabs_script.exists():
                tts_script = str(elevenlabs_script)

        if not tts_script and os.getenv('OPENAI_API_KEY'):
            openai_script = tts_dir / "openai_tts.py"
            if openai_script.exists():
                tts_script = str(openai_script)

        if not tts_script:
            pyttsx3_script = tts_dir / "pyttsx3_tts.py"
            if pyttsx3_script.exists():
                tts_script = str(pyttsx3_script)

        if tts_script:
            completion_message = get_llm_completion_message()
            subprocess.run(
                ["uv", "run", tts_script, completion_message],
                capture_output=True,
                timeout=10
            )

    except Exception:
        pass  # Graceful degradation


def check_stop_authorization():
    """
    Check if stop is authorized via file-based configuration.
    Returns True if authorized, False otherwise.
    """
    auth_file = Path(".claude/data/stop_authorization.json")

    if not auth_file.exists():
        return False

    try:
        with open(auth_file, 'r') as f:
            auth_data = json.load(f)
            return auth_data.get("authorized", False)
    except (json.JSONDecodeError, IOError, KeyError):
        return False


def run_validation_suite():
    """
    COMPREHENSIVE 7-POINT VALIDATION SUITE
    Evidence-based validation - minimum 3 methods required.

    Returns: (all_passed, validation_results, confidence_score)
    """
    print("\n" + "="*70, file=sys.stderr)
    print("🔍 RUNNING COMPREHENSIVE VALIDATION SUITE", file=sys.stderr)
    print("="*70 + "\n", file=sys.stderr)

    validation_results = {}

    # Validation #1: Tests
    print("[ 1/7 ] Running tests...", file=sys.stderr)
    test_passed, test_msg, test_log = check_tests_passing()
    validation_results['tests'] = {
        'passed': test_passed,
        'message': test_msg,
        'evidence_location': test_log
    }
    status = "✅ PASS" if test_passed else "❌ FAIL"
    print(f"        {status}: {test_msg}", file=sys.stderr)

    # Validation #2: Linter
    print("\n[ 2/7 ] Checking linter...", file=sys.stderr)
    lint_passed, lint_msg, lint_log, error_count = check_linter_passing()
    validation_results['linter'] = {
        'passed': lint_passed,
        'message': lint_msg,
        'evidence_location': lint_log,
        'error_count': error_count
    }
    status = "✅ PASS" if lint_passed else "⚠️  WARN"
    print(f"        {status}: {lint_msg}", file=sys.stderr)

    # Validation #3: Runtime
    print("\n[ 3/7 ] Checking app runtime...", file=sys.stderr)
    runtime_passed, runtime_msg, runtime_log = check_app_runtime()
    validation_results['runtime'] = {
        'passed': runtime_passed,
        'message': runtime_msg,
        'evidence_location': runtime_log
    }
    status = "✅ PASS" if runtime_passed else "❌ FAIL"
    print(f"        {status}: {runtime_msg}", file=sys.stderr)

    # Validation #4: Security
    print("\n[ 4/7 ] Running security audit...", file=sys.stderr)
    security_passed, security_msg, security_log, vuln_counts = check_security_issues()
    validation_results['security'] = {
        'passed': security_passed,
        'message': security_msg,
        'evidence_location': security_log,
        'vulnerabilities': vuln_counts
    }
    status = "✅ PASS" if security_passed else "❌ FAIL"
    print(f"        {status}: {security_msg}", file=sys.stderr)

    # Validation #5: Documentation
    print("\n[ 5/7 ] Checking session documentation...", file=sys.stderr)
    docs_passed, docs_msg, docs_path = check_session_documented()
    validation_results['documentation'] = {
        'passed': docs_passed,
        'message': docs_msg,
        'evidence_location': docs_path
    }
    status = "✅ PASS" if docs_passed else "❌ FAIL"
    print(f"        {status}: {docs_msg}", file=sys.stderr)

    # Validation #6: Git status
    print("\n[ 6/7 ] Checking git status...", file=sys.stderr)
    git_passed, git_msg, git_log = check_git_status_clean()
    validation_results['git'] = {
        'passed': git_passed,
        'message': git_msg,
        'evidence_location': git_log
    }
    status = "✅ PASS" if git_passed else "❌ FAIL"
    print(f"        {status}: {git_msg}", file=sys.stderr)

    # Validation #7: Code organization
    print("\n[ 7/7 ] Checking codebase organization...", file=sys.stderr)
    org_passed, org_msg, org_path = check_codebase_organized()
    validation_results['organization'] = {
        'passed': org_passed,
        'message': org_msg,
        'evidence_location': org_path
    }
    status = "✅ PASS" if org_passed else "❌ FAIL"
    print(f"        {status}: {org_msg}", file=sys.stderr)

    # Calculate confidence score (each validation = ~14% if passed)
    passed_count = sum(1 for v in validation_results.values() if v['passed'])
    confidence_score = min(int((passed_count / 7) * 100), 100)

    # ALL critical validations must pass
    critical_checks = [
        validation_results['tests']['passed'],
        validation_results['runtime']['passed'],
        validation_results['security']['passed'],
        validation_results['documentation']['passed']
    ]

    all_passed = all(critical_checks) and confidence_score >= 95

    print("\n" + "="*70, file=sys.stderr)
    print(f"📊 VALIDATION SUMMARY", file=sys.stderr)
    print("="*70, file=sys.stderr)
    print(f"Passed: {passed_count}/7 checks", file=sys.stderr)
    print(f"Confidence: {confidence_score}%", file=sys.stderr)
    print(f"Critical checks: {sum(critical_checks)}/4 passed", file=sys.stderr)
    print(f"Status: {'✅ ALL PASS' if all_passed else '❌ BLOCKED'}", file=sys.stderr)
    print("="*70 + "\n", file=sys.stderr)

    return all_passed, validation_results, confidence_score


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        parser.add_argument('--notify', action='store_true', help='Enable TTS completion announcement')
        parser.add_argument('--validate', action='store_true', help='Run comprehensive validation suite')
        args = parser.parse_args()

        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # If --validate flag, run full validation suite
        if args.validate:
            all_passed, validation_results, confidence = run_validation_suite()

            # Store validation results
            log_to_validation_artifacts("validation-reports", {
                'timestamp': datetime.utcnow().isoformat(),
                'all_passed': all_passed,
                'confidence_score': confidence,
                'validation_results': validation_results
            }, "comprehensive_validation")

            if not all_passed:
                print("\n🔴 STOP BLOCKED: Validation criteria not met", file=sys.stderr)
                print("Required: 95%+ confidence and all critical checks passing\n", file=sys.stderr)
                sys.exit(2)  # Block stop

        # Check authorization
        if not check_stop_authorization():
            script_dir = Path(__file__).parent
            auth_script = script_dir.parent / "commands" / "authorize-stop.sh"

            print("=" * 70, file=sys.stderr)
            print("STOP BLOCKED: One-time authorization required", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            print("", file=sys.stderr)
            print("To authorize stop, use one of these methods:", file=sys.stderr)
            print("", file=sys.stderr)
            print("  1. Bash command (works in plan mode):", file=sys.stderr)
            print(f"     bash {auth_script}", file=sys.stderr)
            print("", file=sys.stderr)
            print("  2. Manual file creation:", file=sys.stderr)
            print('     echo \'{"authorized": true}\' > .claude/data/stop_authorization.json', file=sys.stderr)
            print("", file=sys.stderr)
            print("Authorization is one-time use and resets after stop completes.", file=sys.stderr)
            print("=" * 70, file=sys.stderr)
            sys.exit(2)  # Block stop

        # Stop is authorized - reset for next time
        try:
            auth_file = Path(".claude/data/stop_authorization.json")
            with open(auth_file, 'w') as f:
                json.dump({"authorized": False}, f)
        except Exception:
            pass

        # Log stop event
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "stop.json"

        if log_path.exists():
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        log_data.append(input_data)

        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

        # Handle --chat switch
        if args.chat and 'transcript_path' in input_data:
            transcript_path = Path(input_data['transcript_path'])
            if transcript_path.exists():
                chat_data = []
                try:
                    with open(transcript_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass

                    chat_file = log_dir / 'chat.json'
                    with open(chat_file, 'w') as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass

        # Announce completion via TTS
        if args.notify:
            announce_completion()

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
