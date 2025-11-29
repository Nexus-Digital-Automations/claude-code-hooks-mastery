#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
NOTIFICATION HOOK - Evidence-Based Messaging System
===================================================

SENIOR DEVELOPER PHILOSOPHY:
"Notifications should be ACTIONABLE and EVIDENCE-BASED. Don't just say
'something happened' - show what happened, why it matters, what to do about it.
Include proof, include context, include next steps."

This hook runs when Claude Code sends notifications and is responsible for:
1. Enriching notifications with relevant context
2. Adding evidence and proof to notification messages
3. Providing actionable next steps
4. Including relevant metrics and data
5. Logging all notifications for audit trail

VALIDATION PHILOSOPHY:
- Evidence-based messaging: Every notification backed by data
- Actionable information: Clear next steps provided
- Comprehensive logging: All notifications archived
- Context enrichment: Relevant project state included
- Multi-method validation: Context + Evidence + Actions + Logs

EXIT CODES:
- 0: Success (notification processed)
- Non-blocking: All errors logged but never block notifications
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


# ============================================================================
# VALIDATION ARTIFACT MANAGEMENT
# ============================================================================

def ensure_artifacts_directory() -> Path:
    """
    Ensure .validation-artifacts directory exists.
    CRITICAL: All evidence must be logged for audit trail.
    """
    artifacts_dir = Path(".validation-artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def log_validation_artifact(artifact_name: str, content: Any) -> Path:
    """
    Log validation artifact to .validation-artifacts/ directory.

    SENIOR DEVELOPER PRINCIPLE:
    "Every notification is evidence. Archive it all."
    """
    artifacts_dir = ensure_artifacts_directory()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    artifact_path = artifacts_dir / f"{timestamp}_{artifact_name}"

    try:
        if isinstance(content, (dict, list)):
            with open(artifact_path, 'w') as f:
                json.dump(content, f, indent=2)
        else:
            with open(artifact_path, 'w') as f:
                f.write(str(content))
        return artifact_path
    except Exception:
        return None


def log_notification_to_archive(notification_data: Dict[str, Any]) -> bool:
    """
    Archive notification to logs/notifications.json for audit trail.

    SENIOR DEVELOPER PRINCIPLE:
    "Build a complete audit trail. Every notification matters."
    """
    try:
        log_dir = Path("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        notifications_file = log_dir / "notifications.json"

        # Load existing notifications
        existing_notifications = []
        if notifications_file.exists():
            try:
                with open(notifications_file, 'r') as f:
                    existing_notifications = json.load(f)
            except json.JSONDecodeError:
                existing_notifications = []

        # Add timestamp
        notification_data['archived_at'] = datetime.now().isoformat()

        # Append
        existing_notifications.append(notification_data)

        # Write back
        with open(notifications_file, 'w') as f:
            json.dump(existing_notifications, f, indent=2)

        return True
    except Exception:
        return False


# ============================================================================
# CONTEXT ENRICHMENT
# ============================================================================

def get_git_context() -> Dict[str, Any]:
    """
    Get current git context for notification enrichment.

    RETURNS:
    - branch: Current git branch
    - uncommitted_files: Number of uncommitted files
    - recent_commit: Latest commit message
    """
    context = {
        'branch': None,
        'uncommitted_files': 0,
        'recent_commit': None
    }

    try:
        # Get current branch
        branch_result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if branch_result.returncode == 0:
            context['branch'] = branch_result.stdout.strip()

        # Get uncommitted files count
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if status_result.returncode == 0:
            files = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
            context['uncommitted_files'] = len(files)

        # Get most recent commit
        commit_result = subprocess.run(
            ['git', 'log', '-1', '--pretty=%B'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if commit_result.returncode == 0:
            context['recent_commit'] = commit_result.stdout.strip()[:100]

    except Exception:
        pass

    return context


def get_task_context() -> Dict[str, Any]:
    """
    Get current task context for notification enrichment.

    RETURNS:
    - pending_tasks: Count of pending tasks
    - in_progress_tasks: Count of in-progress tasks
    - completed_tasks: Count of completed tasks (recent)
    """
    context = {
        'pending_tasks': 0,
        'in_progress_tasks': 0,
        'completed_tasks': 0
    }

    try:
        # Check if TASKS.json exists
        tasks_file = Path("TASKS.json")
        if tasks_file.exists():
            with open(tasks_file, 'r') as f:
                tasks = json.load(f)

            for task in tasks:
                status = task.get('status', '').lower()
                if status == 'pending':
                    context['pending_tasks'] += 1
                elif status == 'in_progress' or status == 'in-progress':
                    context['in_progress_tasks'] += 1
                elif status == 'completed':
                    context['completed_tasks'] += 1

    except Exception:
        pass

    return context


def get_test_status() -> Dict[str, Any]:
    """
    Get current test status for notification enrichment.

    RETURNS:
    - test_command_exists: Whether test command is configured
    - last_test_status: Status of last test run (if available)
    """
    status = {
        'test_command_exists': False,
        'last_test_status': None
    }

    try:
        # Check package.json for test script
        package_json = Path("package.json")
        if package_json.exists():
            with open(package_json, 'r') as f:
                data = json.load(f)
                scripts = data.get('scripts', {})
                if 'test' in scripts:
                    status['test_command_exists'] = True

        # Check for pytest configuration
        if Path("pytest.ini").exists() or Path("pyproject.toml").exists():
            status['test_command_exists'] = True

    except Exception:
        pass

    return status


def enrich_notification_with_context(
    notification_type: str,
    original_message: str
) -> Tuple[str, Dict[str, Any]]:
    """
    Enrich notification message with relevant context.

    SENIOR DEVELOPER PRINCIPLE:
    "Context is everything. A notification without context is just noise."

    RETURNS: (enriched_message, context_data)
    """
    # Gather all context
    git_context = get_git_context()
    task_context = get_task_context()
    test_status = get_test_status()

    context_data = {
        'git': git_context,
        'tasks': task_context,
        'tests': test_status,
        'timestamp': datetime.now().isoformat()
    }

    # Build enriched message
    enriched_lines = [original_message]

    # Add relevant context based on notification type
    if notification_type in ['error', 'warning']:
        # For errors/warnings, add git and test context
        if git_context['branch']:
            enriched_lines.append(f"Branch: {git_context['branch']}")
        if git_context['uncommitted_files'] > 0:
            enriched_lines.append(f"Uncommitted files: {git_context['uncommitted_files']}")

    if notification_type in ['task_complete', 'session_end']:
        # For completion notifications, add task context
        if task_context['completed_tasks'] > 0:
            enriched_lines.append(f"Tasks completed: {task_context['completed_tasks']}")
        if task_context['pending_tasks'] > 0:
            enriched_lines.append(f"Tasks remaining: {task_context['pending_tasks']}")

    enriched_message = "\n".join(enriched_lines)

    return enriched_message, context_data


# ============================================================================
# EVIDENCE GATHERING
# ============================================================================

def gather_evidence_for_notification(
    notification_type: str,
    message: str
) -> Dict[str, Any]:
    """
    Gather evidence to support notification message.

    SENIOR DEVELOPER PRINCIPLE:
    "Back every claim with evidence. Show, don't just tell."

    RETURNS: Evidence dictionary with proof points
    """
    evidence = {
        'log_files': [],
        'metrics': {},
        'file_changes': [],
        'test_results': None
    }

    try:
        # Check for relevant log files
        log_dir = Path("logs")
        if log_dir.exists():
            log_files = list(log_dir.glob("*.json"))
            evidence['log_files'] = [str(f.name) for f in log_files[-5:]]

        # Get file change metrics
        try:
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if status_result.returncode == 0:
                changes = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
                evidence['file_changes'] = changes[:10]  # Limit to 10
                evidence['metrics']['files_modified'] = len(changes)
        except Exception:
            pass

        # Check for test results
        test_results_paths = [
            Path("test-results.json"),
            Path("junit.xml"),
            Path(".pytest_cache/v/cache/lastfailed")
        ]
        for path in test_results_paths:
            if path.exists():
                evidence['test_results'] = str(path.name)
                break

    except Exception:
        pass

    return evidence


# ============================================================================
# ACTIONABLE NEXT STEPS
# ============================================================================

def generate_next_steps(
    notification_type: str,
    context_data: Dict[str, Any],
    evidence: Dict[str, Any]
) -> List[str]:
    """
    Generate actionable next steps based on notification context.

    SENIOR DEVELOPER PRINCIPLE:
    "Every notification should answer: What should I do next?"
    """
    next_steps = []

    # For errors/warnings
    if notification_type in ['error', 'warning']:
        if evidence.get('test_results'):
            next_steps.append("Review test results for failure details")
        if context_data['git']['uncommitted_files'] > 0:
            next_steps.append("Commit or stash uncommitted changes")
        next_steps.append("Check logs directory for detailed error information")

    # For task completion
    elif notification_type in ['task_complete']:
        if context_data['tasks']['pending_tasks'] > 0:
            next_steps.append(f"Continue with {context_data['tasks']['pending_tasks']} remaining tasks")
        if context_data['tests']['test_command_exists']:
            next_steps.append("Run tests to verify changes")
        if context_data['git']['uncommitted_files'] > 0:
            next_steps.append("Review and commit changes")

    # For session end
    elif notification_type in ['session_end']:
        if context_data['git']['uncommitted_files'] > 0:
            next_steps.append("Commit uncommitted changes before next session")
        if context_data['tasks']['in_progress_tasks'] > 0:
            next_steps.append("Resume in-progress tasks in next session")
        next_steps.append("Review session logs in logs/notifications.json")

    # Default fallback
    if not next_steps:
        next_steps.append("Review recent changes with: git status")
        next_steps.append("Check logs directory for detailed information")

    return next_steps


# ============================================================================
# NOTIFICATION ENHANCEMENT
# ============================================================================

def enhance_notification(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enhance notification with context, evidence, and next steps.

    MULTI-METHOD VALIDATION:
    1. Context enrichment (git + tasks + tests)
    2. Evidence gathering (logs + metrics + changes)
    3. Next steps generation (actionable recommendations)
    4. Artifact logging (comprehensive documentation)

    RETURNS: Enhanced notification data
    """
    # Extract notification details
    notification_type = input_data.get('type', 'unknown')
    original_message = input_data.get('message', '')
    session_id = input_data.get('session_id', 'unknown')

    # Step 1: Enrich with context
    enriched_message, context_data = enrich_notification_with_context(
        notification_type, original_message
    )

    # Step 2: Gather evidence
    evidence = gather_evidence_for_notification(notification_type, original_message)

    # Step 3: Generate next steps
    next_steps = generate_next_steps(notification_type, context_data, evidence)

    # Build enhanced notification
    enhanced_notification = {
        'original': {
            'type': notification_type,
            'message': original_message,
            'session_id': session_id
        },
        'enhanced': {
            'message': enriched_message,
            'context': context_data,
            'evidence': evidence,
            'next_steps': next_steps,
            'timestamp': datetime.now().isoformat()
        },
        'validation': {
            'context_enriched': bool(context_data),
            'evidence_gathered': bool(evidence.get('log_files') or evidence.get('file_changes')),
            'next_steps_provided': len(next_steps) > 0,
            'artifacts_logged': False  # Will be updated after logging
        }
    }

    # Step 4: Log artifacts
    artifact_path = log_validation_artifact(
        "notification_enhanced.json",
        enhanced_notification
    )
    enhanced_notification['validation']['artifacts_logged'] = bool(artifact_path)

    # Archive notification
    archive_success = log_notification_to_archive(enhanced_notification)
    enhanced_notification['validation']['archived'] = archive_success

    return enhanced_notification


# ============================================================================
# VALIDATION CONFIDENCE
# ============================================================================

def calculate_validation_confidence(enhanced_notification: Dict[str, Any]) -> int:
    """
    Calculate validation confidence based on evidence methods.

    EVIDENCE METHODS:
    - Context enrichment: +25%
    - Evidence gathering: +25%
    - Next steps provided: +25%
    - Artifacts logged: +25%

    RETURNS: Confidence score (0-100%)
    """
    validation = enhanced_notification.get('validation', {})

    confidence = 0
    if validation.get('context_enriched'):
        confidence += 25
    if validation.get('evidence_gathered'):
        confidence += 25
    if validation.get('next_steps_provided'):
        confidence += 25
    if validation.get('artifacts_logged'):
        confidence += 25

    return confidence


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Main execution - enhance notification with evidence and context.

    CRITICAL: This hook is NON-BLOCKING.
    Always exits with code 0, even if enhancement fails.
    We enrich notifications but never prevent them from being sent.
    """
    try:
        # Read JSON input from stdin
        input_data = {}
        try:
            if not sys.stdin.isatty():
                input_data = json.load(sys.stdin)
        except (json.JSONDecodeError, ValueError):
            # If no valid JSON, just exit gracefully
            sys.exit(0)

        # Enhance notification
        enhanced_notification = enhance_notification(input_data)

        # Calculate validation confidence
        confidence = calculate_validation_confidence(enhanced_notification)

        # Print enhanced notification to stderr (for visibility)
        print("\n" + "=" * 70, file=sys.stderr)
        print("NOTIFICATION - EVIDENCE-BASED MESSAGING", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"Type: {enhanced_notification['original']['type']}", file=sys.stderr)
        print(f"Validation Confidence: {confidence}%", file=sys.stderr)
        print("", file=sys.stderr)
        print("ENHANCED MESSAGE:", file=sys.stderr)
        print(enhanced_notification['enhanced']['message'], file=sys.stderr)
        print("", file=sys.stderr)

        if enhanced_notification['enhanced']['next_steps']:
            print("NEXT STEPS:", file=sys.stderr)
            for i, step in enumerate(enhanced_notification['enhanced']['next_steps'], 1):
                print(f"  {i}. {step}", file=sys.stderr)
            print("", file=sys.stderr)

        print(f"Evidence archived to: logs/notifications.json", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

        # Output enhanced notification as JSON (for Claude Code to consume)
        output = {
            'hookSpecificOutput': {
                'hookEventName': 'Notification',
                'enhancedMessage': enhanced_notification['enhanced']['message'],
                'context': enhanced_notification['enhanced']['context'],
                'nextSteps': enhanced_notification['enhanced']['next_steps'],
                'validationConfidence': confidence
            }
        }
        print(json.dumps(output))

        # Always exit 0 (non-blocking)
        sys.exit(0)

    except Exception as e:
        # Log error but still exit 0
        print(f"\nNotification hook error: {str(e)}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
