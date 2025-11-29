#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
📐 SESSION START HOOK - COMPREHENSIVE CONTEXT LOADER

CRITICAL: Load ALL relevant project context before work begins.
NEVER: Start work without understanding project structure and state.
ALWAYS: Verify security baseline and code quality tools exist.

CORE PRINCIPLE: "Load comprehensive context before any work begins."
Evidence-based context - PROVE what exists, DON'T ASSUME.
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def log_to_validation_artifacts(category, data, operation="session_start"):
    """
    Store all context loading evidence in .validation-artifacts/
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
        return None


def check_git_status():
    """
    PROVE IT: Load git context with evidence.
    Evidence: Current branch, uncommitted file count, recent commits
    """
    try:
        # Get current branch
        branch_result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None

        # Get uncommitted changes
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=5
        )

        uncommitted_files = []
        if status_result.returncode == 0 and status_result.stdout.strip():
            uncommitted_files = [
                line.strip() for line in status_result.stdout.strip().split('\n')
                if line.strip()
            ]

        # Get recent commits
        log_result = subprocess.run(
            ['git', 'log', '--oneline', '-5'],
            capture_output=True,
            text=True,
            timeout=5
        )
        recent_commits = log_result.stdout.strip() if log_result.returncode == 0 else None

        # Log evidence
        git_context = {
            'branch': current_branch,
            'uncommitted_count': len(uncommitted_files),
            'uncommitted_files': uncommitted_files[:10],  # First 10
            'recent_commits': recent_commits
        }

        log_path = log_to_validation_artifacts("context", git_context, "git_status")

        return git_context, log_path

    except FileNotFoundError:
        return {'branch': None, 'uncommitted_count': 0, 'error': 'Git not available'}, None
    except Exception as e:
        return {'error': str(e)}, None


def check_security_baseline():
    """
    CRITICAL: Verify security patterns exist.
    Evidence: .gitignore patterns, pre-commit hooks, npm audit results
    """
    security_status = {
        'gitignore_exists': False,
        'gitignore_has_security_patterns': False,
        'missing_patterns': [],
        'precommit_hooks_configured': False,
        'npm_vulnerabilities': None
    }

    # Check .gitignore
    gitignore = Path(".gitignore")
    security_status['gitignore_exists'] = gitignore.exists()

    if gitignore.exists():
        try:
            gitignore_content = gitignore.read_text()
            required_patterns = [".env", "*.key", "credentials"]

            security_status['missing_patterns'] = [
                p for p in required_patterns if p not in gitignore_content
            ]

            security_status['gitignore_has_security_patterns'] = len(security_status['missing_patterns']) == 0

            # Auto-add missing patterns
            if security_status['missing_patterns']:
                try:
                    with open(gitignore, 'a') as f:
                        f.write("\n# Security patterns (auto-added by hook)\n")
                        for pattern in security_status['missing_patterns']:
                            f.write(f"{pattern}\n")
                    security_status['patterns_auto_added'] = True
                    security_status['gitignore_has_security_patterns'] = True
                except Exception:
                    security_status['patterns_auto_added'] = False

        except Exception as e:
            security_status['gitignore_error'] = str(e)

    else:
        # Create .gitignore with security patterns
        try:
            gitignore.write_text("""# Security
*.env
*.env.*
!.env.example
*.key
*.pem
*.p12
credentials/
secrets/

# Dependencies
node_modules/
__pycache__/
*.pyc

# Build outputs
dist/
build/
*.log
""")
            security_status['gitignore_created'] = True
            security_status['gitignore_exists'] = True
            security_status['gitignore_has_security_patterns'] = True
        except Exception as e:
            security_status['gitignore_creation_error'] = str(e)

    # Check pre-commit hooks
    security_status['precommit_hooks_configured'] = (
        Path(".pre-commit-config.yaml").exists() or
        Path(".husky").exists()
    )

    # Quick npm audit if package.json exists
    if Path("package.json").exists():
        try:
            result = subprocess.run(
                ["npm", "audit", "--audit-level=high"],
                capture_output=True,
                text=True,
                timeout=30
            )

            security_status['npm_vulnerabilities'] = {
                'critical': result.stdout.lower().count(" critical"),
                'high': result.stdout.lower().count(" high")
            }
        except Exception as e:
            security_status['npm_audit_error'] = str(e)

    log_path = log_to_validation_artifacts("security", security_status, "security_baseline")

    return security_status, log_path


def check_code_quality_tools():
    """
    VERIFY: Code quality tooling exists.
    Evidence: Linter config, test framework, formatter config
    """
    quality_tools = {
        'linter_configured': False,
        'linter_type': None,
        'test_framework_detected': False,
        'test_framework_type': None,
        'formatter_configured': False,
        'formatter_type': None
    }

    # Check linters
    linter_configs = [
        ("eslint.config.mjs", "ESLint (flat config)"),
        (".eslintrc.js", "ESLint"),
        (".eslintrc.json", "ESLint"),
        ("pyproject.toml", "Python (Ruff/Black)"),
        (".pylintrc", "Pylint"),
        (".ruff.toml", "Ruff")
    ]

    for config_file, linter_type in linter_configs:
        if Path(config_file).exists():
            quality_tools['linter_configured'] = True
            quality_tools['linter_type'] = linter_type
            break

    # Check test frameworks
    test_indicators = [
        ("jest.config.js", "Jest"),
        ("vitest.config.js", "Vitest"),
        ("pytest.ini", "Pytest"),
        ("tests", "Tests directory"),
        ("test", "Test directory")
    ]

    for indicator, framework in test_indicators:
        if Path(indicator).exists():
            quality_tools['test_framework_detected'] = True
            quality_tools['test_framework_type'] = framework
            break

    # Check formatters
    formatter_configs = [
        (".prettierrc", "Prettier"),
        ("prettier.config.js", "Prettier"),
        ("pyproject.toml", "Black (if Python)")
    ]

    for config_file, formatter in formatter_configs:
        if Path(config_file).exists():
            quality_tools['formatter_configured'] = True
            quality_tools['formatter_type'] = formatter
            break

    log_path = log_to_validation_artifacts("quality-tools", quality_tools, "quality_tools_check")

    return quality_tools, log_path


def load_project_documentation():
    """
    LOAD: Project-specific documentation and context files.
    Evidence: CLAUDE.md, README.md, docs/development/ contents
    """
    documentation = {
        'claude_md_exists': False,
        'readme_exists': False,
        'development_docs_found': [],
        'context_loaded': []
    }

    # Check CLAUDE.md
    claude_md = Path("CLAUDE.md")
    if claude_md.exists():
        documentation['claude_md_exists'] = True
        try:
            content = claude_md.read_text()
            documentation['claude_md_lines'] = len(content.split('\n'))
            documentation['context_loaded'].append(f"CLAUDE.md ({documentation['claude_md_lines']} lines)")
        except Exception:
            pass

    # Check README.md
    readme = Path("README.md")
    if readme.exists():
        documentation['readme_exists'] = True
        try:
            content = readme.read_text()
            documentation['readme_lines'] = len(content.split('\n'))
            documentation['context_loaded'].append(f"README.md ({documentation['readme_lines']} lines)")
        except Exception:
            pass

    # Check docs/development/
    dev_docs_dir = Path("docs/development")
    if dev_docs_dir.exists():
        try:
            dev_docs = list(dev_docs_dir.glob("*.md"))
            documentation['development_docs_found'] = [f.name for f in dev_docs]
            documentation['context_loaded'].extend([f"docs/development/{f.name}" for f in dev_docs[:5]])
        except Exception:
            pass

    # Check other common context files
    other_context_files = [
        ".claude/CONTEXT.md",
        ".claude/TODO.md",
        "TODO.md",
        "CONTRIBUTING.md"
    ]

    for file_path in other_context_files:
        if Path(file_path).exists():
            documentation['context_loaded'].append(file_path)

    log_path = log_to_validation_artifacts("documentation", documentation, "doc_loading")

    return documentation, log_path


def get_recent_github_issues():
    """
    OPTIONAL: Load recent GitHub issues if gh CLI available.
    Evidence: Open issues list
    """
    try:
        # Check if gh CLI is available
        gh_check = subprocess.run(['which', 'gh'], capture_output=True, timeout=2)
        if gh_check.returncode != 0:
            return None, "gh CLI not available"

        # Get recent open issues
        result = subprocess.run(
            ['gh', 'issue', 'list', '--limit', '5', '--state', 'open'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0 and result.stdout.strip():
            issues = result.stdout.strip()
            log_path = log_to_validation_artifacts("context", issues, "github_issues")
            return issues, log_path

        return None, "No open issues"

    except Exception as e:
        return None, f"Error: {str(e)}"


def generate_context_summary(source, git_context, security_status, quality_tools, documentation, github_issues):
    """
    SYNTHESIZE: Create comprehensive context summary for Claude.
    Senior developer voice - ASSERTIVE and SPECIFIC.
    """
    summary_parts = []

    # Header
    summary_parts.append("="*70)
    summary_parts.append("🚀 SESSION START - COMPREHENSIVE CONTEXT LOADED")
    summary_parts.append("="*70)
    summary_parts.append("")

    summary_parts.append(f"📅 Session started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    summary_parts.append(f"📌 Session source: {source}")
    summary_parts.append("")

    # Git context
    summary_parts.append("📂 GIT CONTEXT:")
    if git_context.get('branch'):
        summary_parts.append(f"   Branch: {git_context['branch']}")
        summary_parts.append(f"   Uncommitted files: {git_context['uncommitted_count']}")
        if git_context.get('recent_commits'):
            summary_parts.append("   Recent commits:")
            for line in git_context['recent_commits'].split('\n')[:3]:
                summary_parts.append(f"     {line}")
    else:
        summary_parts.append("   ⚠️  Git not available or not a git repository")
    summary_parts.append("")

    # Security baseline
    summary_parts.append("🔒 SECURITY BASELINE:")
    if security_status['gitignore_exists']:
        if security_status['gitignore_has_security_patterns']:
            summary_parts.append("   ✅ .gitignore exists with security patterns")
        else:
            summary_parts.append(f"   ⚠️  .gitignore missing patterns: {', '.join(security_status['missing_patterns'])}")
    else:
        summary_parts.append("   ❌ .gitignore missing (CRITICAL)")

    if security_status['precommit_hooks_configured']:
        summary_parts.append("   ✅ Pre-commit hooks configured")
    else:
        summary_parts.append("   ⚠️  No pre-commit hooks detected")

    if security_status.get('npm_vulnerabilities'):
        vuln = security_status['npm_vulnerabilities']
        if vuln['critical'] > 0 or vuln['high'] > 0:
            summary_parts.append(f"   ⚠️  VULNERABILITIES: {vuln['critical']} critical, {vuln['high']} high")
        else:
            summary_parts.append("   ✅ No critical/high vulnerabilities")
    summary_parts.append("")

    # Code quality tools
    summary_parts.append("🔧 CODE QUALITY TOOLS:")
    if quality_tools['linter_configured']:
        summary_parts.append(f"   ✅ Linter: {quality_tools['linter_type']}")
    else:
        summary_parts.append("   ⚠️  No linter detected")

    if quality_tools['test_framework_detected']:
        summary_parts.append(f"   ✅ Tests: {quality_tools['test_framework_type']}")
    else:
        summary_parts.append("   ⚠️  No test framework detected")

    if quality_tools['formatter_configured']:
        summary_parts.append(f"   ✅ Formatter: {quality_tools['formatter_type']}")
    summary_parts.append("")

    # Documentation
    summary_parts.append("📚 DOCUMENTATION LOADED:")
    if documentation['context_loaded']:
        for doc in documentation['context_loaded']:
            summary_parts.append(f"   ✅ {doc}")
    else:
        summary_parts.append("   ⚠️  No project documentation found")
    summary_parts.append("")

    # GitHub issues
    if github_issues:
        summary_parts.append("🐛 RECENT GITHUB ISSUES:")
        for line in github_issues.split('\n')[:5]:
            summary_parts.append(f"   {line}")
        summary_parts.append("")

    # Footer
    summary_parts.append("="*70)
    summary_parts.append("💡 READY TO START WORK")
    summary_parts.append("="*70)

    return "\n".join(summary_parts)


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--load-context', action='store_true',
                          help='Load comprehensive development context')
        parser.add_argument('--announce', action='store_true',
                          help='Announce session start via TTS')
        args = parser.parse_args()

        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Extract fields
        session_id = input_data.get('session_id', 'unknown')
        source = input_data.get('source', 'unknown')  # "startup", "resume", or "clear"

        # Log session start event
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'session_start.json'

        if log_file.exists():
            with open(log_file, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        log_data.append(input_data)

        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)

        # Load comprehensive context if requested
        if args.load_context:
            print("\n🔍 Loading comprehensive project context...\n", file=sys.stderr)

            # Run all context checks
            git_context, git_log = check_git_status()
            security_status, security_log = check_security_baseline()
            quality_tools, quality_log = check_code_quality_tools()
            documentation, docs_log = load_project_documentation()
            github_issues, issues_info = get_recent_github_issues()

            # Generate comprehensive summary
            context_summary = generate_context_summary(
                source, git_context, security_status, quality_tools,
                documentation, github_issues
            )

            # Print to stderr for user visibility
            print(context_summary, file=sys.stderr)

            # Save full context report
            full_context = {
                'timestamp': datetime.utcnow().isoformat(),
                'session_id': session_id,
                'source': source,
                'git_context': git_context,
                'security_status': security_status,
                'quality_tools': quality_tools,
                'documentation': documentation,
                'github_issues': github_issues if github_issues else issues_info
            }

            log_to_validation_artifacts("context", full_context, "comprehensive_context")

        # Announce session start if requested
        if args.announce:
            try:
                script_dir = Path(__file__).parent
                tts_script = script_dir / "utils" / "tts" / "pyttsx3_tts.py"

                if tts_script.exists():
                    messages = {
                        "startup": "Claude Code session started",
                        "resume": "Resuming previous session",
                        "clear": "Starting fresh session"
                    }
                    message = messages.get(source, "Session started")

                    subprocess.run(
                        ["uv", "run", str(tts_script), message],
                        capture_output=True,
                        timeout=5
                    )
            except Exception:
                pass  # Graceful degradation

        # Success
        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == '__main__':
    main()
