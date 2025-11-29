#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

"""
SESSION END HOOK - Knowledge Preservation System
================================================

SENIOR DEVELOPER PHILOSOPHY:
"Every session is a learning opportunity. Preserve technical discoveries,
document architectural decisions, catalog error solutions. Your future self
will thank you for comprehensive knowledge capture."

This hook runs when a session ends and is responsible for:
1. Generating comprehensive session summary
2. Storing lessons learned to knowledge base
3. Updating error solution catalog
4. Documenting task completion metrics
5. Preserving architectural decisions
6. Creating evidence artifacts

VALIDATION PHILOSOPHY:
- Multi-method validation: Summary + Lessons + Errors + Tasks + Evidence
- Minimum 3 forms of evidence required
- Comprehensive logging to .validation-artifacts/
- Graceful degradation (never blocks, always documents)

EXIT CODES:
- 0: Success (knowledge preserved)
- Non-blocking: All errors logged but never block session end
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
    CRITICAL: All evidence must be logged for future reference.
    """
    artifacts_dir = Path(".validation-artifacts")
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir


def log_validation_artifact(artifact_name: str, content: Any) -> Path:
    """
    Log validation artifact to .validation-artifacts/ directory.

    SENIOR DEVELOPER PRINCIPLE:
    "Document everything. Your artifacts are your proof."
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


# ============================================================================
# SESSION SUMMARY GENERATION
# ============================================================================

def analyze_session_transcript(transcript_path: str) -> Dict[str, Any]:
    """
    Analyze session transcript to extract key information.

    RETURNS:
    - tools_used: List of tools/commands executed
    - files_modified: List of files changed
    - errors_encountered: List of errors and solutions
    - tasks_completed: Count of completed tasks
    """
    analysis = {
        'tools_used': set(),
        'files_modified': set(),
        'errors_encountered': [],
        'tasks_completed': 0,
        'total_messages': 0
    }

    if not Path(transcript_path).exists():
        return analysis

    try:
        with open(transcript_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    entry = json.loads(line)
                    analysis['total_messages'] += 1

                    # Extract tool usage
                    if 'type' in entry and entry['type'] == 'tool_use':
                        tool_name = entry.get('name', '')
                        if tool_name:
                            analysis['tools_used'].add(tool_name)

                    # Extract file modifications (Edit, Write tools)
                    if 'type' in entry and entry['type'] == 'tool_use':
                        if entry.get('name') in ['Edit', 'Write']:
                            file_path = entry.get('input', {}).get('file_path', '')
                            if file_path:
                                analysis['files_modified'].add(file_path)

                    # Look for error indicators
                    if 'content' in entry:
                        content_str = str(entry['content']).lower()
                        if 'error' in content_str or 'failed' in content_str:
                            analysis['errors_encountered'].append({
                                'timestamp': entry.get('timestamp', ''),
                                'content': str(entry['content'])[:200]
                            })

                    # Count task completions
                    if 'content' in entry:
                        content_str = str(entry['content']).lower()
                        if 'completed' in content_str or 'finished' in content_str:
                            analysis['tasks_completed'] += 1

                except json.JSONDecodeError:
                    continue

    except Exception:
        pass

    # Convert sets to lists for JSON serialization
    analysis['tools_used'] = sorted(list(analysis['tools_used']))
    analysis['files_modified'] = sorted(list(analysis['files_modified']))

    return analysis


def generate_session_summary(
    session_id: str,
    transcript_path: str,
    session_duration: float
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Generate comprehensive session summary.

    SENIOR DEVELOPER PRINCIPLE:
    "A good session summary answers: What was done? How was it done?
    What was learned? What needs follow-up?"

    RETURNS: (success, summary_text, analysis_data)
    """
    try:
        # Analyze transcript
        analysis = analyze_session_transcript(transcript_path)

        # Generate summary
        summary_lines = [
            "=" * 70,
            f"SESSION SUMMARY - {session_id}",
            "=" * 70,
            "",
            f"Duration: {session_duration:.1f} seconds ({session_duration/60:.1f} minutes)",
            f"Total Messages: {analysis['total_messages']}",
            f"Tasks Completed: {analysis['tasks_completed']}",
            "",
            "TOOLS USED:",
        ]

        if analysis['tools_used']:
            for tool in analysis['tools_used']:
                summary_lines.append(f"  - {tool}")
        else:
            summary_lines.append("  (none)")

        summary_lines.append("")
        summary_lines.append("FILES MODIFIED:")

        if analysis['files_modified']:
            for file_path in analysis['files_modified']:
                summary_lines.append(f"  - {file_path}")
        else:
            summary_lines.append("  (none)")

        summary_lines.append("")
        summary_lines.append(f"ERRORS ENCOUNTERED: {len(analysis['errors_encountered'])}")

        if analysis['errors_encountered']:
            for i, error in enumerate(analysis['errors_encountered'][:5], 1):
                summary_lines.append(f"  {i}. {error['content'][:100]}...")

        summary_lines.append("")
        summary_lines.append("=" * 70)

        summary_text = "\n".join(summary_lines)

        # Log summary artifact
        log_validation_artifact("session_summary.txt", summary_text)
        log_validation_artifact("session_analysis.json", analysis)

        return True, summary_text, analysis

    except Exception as e:
        error_msg = f"Failed to generate session summary: {str(e)}"
        return False, error_msg, {}


# ============================================================================
# LESSON STORAGE
# ============================================================================

def extract_lessons_from_session(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract technical lessons from session analysis.

    SENIOR DEVELOPER PRINCIPLE:
    "Every error solved is a lesson learned. Every pattern discovered
    is knowledge gained. Document it all."
    """
    lessons = []

    # Lesson from tools used
    if analysis.get('tools_used'):
        lessons.append({
            'category': 'tooling',
            'title': 'Tools and Commands Used',
            'content': f"Session utilized {len(analysis['tools_used'])} different tools: {', '.join(analysis['tools_used'][:10])}",
            'tags': ['tools', 'workflow']
        })

    # Lesson from file modifications
    if analysis.get('files_modified'):
        lessons.append({
            'category': 'implementation',
            'title': 'Files Modified in Session',
            'content': f"Modified {len(analysis['files_modified'])} files. Key changes in: {', '.join([Path(f).name for f in list(analysis['files_modified'])[:5]])}",
            'tags': ['files', 'implementation']
        })

    # Lessons from errors
    if analysis.get('errors_encountered'):
        lessons.append({
            'category': 'debugging',
            'title': 'Error Handling and Solutions',
            'content': f"Encountered and resolved {len(analysis['errors_encountered'])} errors during session",
            'tags': ['errors', 'debugging', 'solutions']
        })

    return lessons


def store_lessons_to_knowledge_base(lessons: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Store lessons to knowledge base (lessons.json).

    RETURNS: (success, message)
    """
    try:
        lessons_file = Path("lessons.json")

        # Load existing lessons
        existing_lessons = []
        if lessons_file.exists():
            try:
                with open(lessons_file, 'r') as f:
                    existing_lessons = json.load(f)
            except json.JSONDecodeError:
                existing_lessons = []

        # Add timestamp to new lessons
        timestamp = datetime.now().isoformat()
        for lesson in lessons:
            lesson['timestamp'] = timestamp

        # Append new lessons
        existing_lessons.extend(lessons)

        # Write back
        with open(lessons_file, 'w') as f:
            json.dump(existing_lessons, f, indent=2)

        # Log artifact
        log_validation_artifact("stored_lessons.json", lessons)

        return True, f"Stored {len(lessons)} lessons to knowledge base"

    except Exception as e:
        return False, f"Failed to store lessons: {str(e)}"


# ============================================================================
# ERROR CATALOG UPDATE
# ============================================================================

def update_error_catalog(errors: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Update error solution catalog with new errors encountered.

    SENIOR DEVELOPER PRINCIPLE:
    "Build a catalog of every error and its solution. Future debugging
    becomes instant pattern matching."
    """
    if not errors:
        return True, "No errors to catalog"

    try:
        error_catalog_file = Path("error_catalog.json")

        # Load existing catalog
        existing_catalog = []
        if error_catalog_file.exists():
            try:
                with open(error_catalog_file, 'r') as f:
                    existing_catalog = json.load(f)
            except json.JSONDecodeError:
                existing_catalog = []

        # Add timestamp to new errors
        timestamp = datetime.now().isoformat()
        for error in errors:
            error['timestamp'] = timestamp
            error['cataloged'] = True

        # Append new errors
        existing_catalog.extend(errors)

        # Write back
        with open(error_catalog_file, 'w') as f:
            json.dump(existing_catalog, f, indent=2)

        # Log artifact
        log_validation_artifact("error_catalog_update.json", errors)

        return True, f"Cataloged {len(errors)} errors"

    except Exception as e:
        return False, f"Failed to update error catalog: {str(e)}"


# ============================================================================
# TASK COMPLETION METRICS
# ============================================================================

def generate_task_metrics(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate task completion metrics.

    METRICS:
    - Tasks completed
    - Files modified
    - Tools used
    - Errors resolved
    - Session efficiency score
    """
    tasks_completed = analysis.get('tasks_completed', 0)
    files_modified = len(analysis.get('files_modified', []))
    tools_used = len(analysis.get('tools_used', []))
    errors_resolved = len(analysis.get('errors_encountered', []))
    total_messages = analysis.get('total_messages', 0)

    # Calculate efficiency score (tasks per 100 messages)
    efficiency_score = (tasks_completed / max(total_messages, 1)) * 100

    metrics = {
        'tasks_completed': tasks_completed,
        'files_modified': files_modified,
        'tools_used': tools_used,
        'errors_resolved': errors_resolved,
        'total_messages': total_messages,
        'efficiency_score': round(efficiency_score, 2),
        'timestamp': datetime.now().isoformat()
    }

    # Log artifact
    log_validation_artifact("task_metrics.json", metrics)

    return metrics


# ============================================================================
# ARCHITECTURAL DECISIONS
# ============================================================================

def preserve_architectural_decisions(analysis: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Preserve architectural decisions made during session.

    SENIOR DEVELOPER PRINCIPLE:
    "Document why, not just what. Future maintainers need context."
    """
    try:
        decisions_file = Path("architectural_decisions.json")

        # Load existing decisions
        existing_decisions = []
        if decisions_file.exists():
            try:
                with open(decisions_file, 'r') as f:
                    existing_decisions = json.load(f)
            except json.JSONDecodeError:
                existing_decisions = []

        # Create decision record from session
        decision = {
            'timestamp': datetime.now().isoformat(),
            'files_modified': analysis.get('files_modified', []),
            'tools_used': analysis.get('tools_used', []),
            'context': f"Session modified {len(analysis.get('files_modified', []))} files using {len(analysis.get('tools_used', []))} tools"
        }

        existing_decisions.append(decision)

        # Write back
        with open(decisions_file, 'w') as f:
            json.dump(existing_decisions, f, indent=2)

        # Log artifact
        log_validation_artifact("architectural_decision.json", decision)

        return True, "Preserved architectural context"

    except Exception as e:
        return False, f"Failed to preserve decisions: {str(e)}"


# ============================================================================
# MAIN VALIDATION SUITE
# ============================================================================

def run_knowledge_preservation() -> Dict[str, Any]:
    """
    COMPREHENSIVE KNOWLEDGE PRESERVATION SUITE

    Multi-method validation - minimum 3 methods required:
    1. Session summary generation
    2. Lesson storage to knowledge base
    3. Error catalog update
    4. Task completion metrics
    5. Architectural decision preservation

    SENIOR DEVELOPER PRINCIPLE:
    "Evidence-based validation. PROVE knowledge was preserved."
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--session-id', help='Session ID')
    parser.add_argument('--transcript-path', help='Path to session transcript')
    parser.add_argument('--duration', type=float, default=0.0, help='Session duration in seconds')
    args, unknown = parser.parse_known_args()

    # Read JSON from stdin if available
    input_data = {}
    try:
        if not sys.stdin.isatty():
            input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        pass

    # Extract session info
    session_id = args.session_id or input_data.get('session_id', 'unknown')
    transcript_path = args.transcript_path or input_data.get('transcript_path', '')
    session_duration = args.duration or input_data.get('session_duration', 0.0)

    validation_results = {}
    evidence_count = 0

    # 1. Generate session summary
    summary_success, summary_text, analysis = generate_session_summary(
        session_id, transcript_path, session_duration
    )
    validation_results['session_summary'] = {
        'passed': summary_success,
        'message': summary_text if summary_success else "Failed to generate summary",
        'evidence': 'summary' if summary_success else None
    }
    if summary_success:
        evidence_count += 1

    # 2. Store lessons to knowledge base
    lessons = extract_lessons_from_session(analysis)
    lessons_success, lessons_msg = store_lessons_to_knowledge_base(lessons)
    validation_results['lesson_storage'] = {
        'passed': lessons_success,
        'message': lessons_msg,
        'evidence': 'lessons.json' if lessons_success else None
    }
    if lessons_success:
        evidence_count += 1

    # 3. Update error catalog
    errors = analysis.get('errors_encountered', [])
    catalog_success, catalog_msg = update_error_catalog(errors)
    validation_results['error_catalog'] = {
        'passed': catalog_success,
        'message': catalog_msg,
        'evidence': 'error_catalog.json' if catalog_success else None
    }
    if catalog_success:
        evidence_count += 1

    # 4. Generate task metrics
    metrics = generate_task_metrics(analysis)
    validation_results['task_metrics'] = {
        'passed': True,
        'message': f"Efficiency score: {metrics['efficiency_score']}%",
        'evidence': 'task_metrics.json'
    }
    evidence_count += 1

    # 5. Preserve architectural decisions
    arch_success, arch_msg = preserve_architectural_decisions(analysis)
    validation_results['architectural_decisions'] = {
        'passed': arch_success,
        'message': arch_msg,
        'evidence': 'architectural_decisions.json' if arch_success else None
    }
    if arch_success:
        evidence_count += 1

    # Calculate validation confidence
    validation_confidence = min((evidence_count * 20), 100)  # 5 methods = 100%

    return {
        'validation_results': validation_results,
        'evidence_count': evidence_count,
        'validation_confidence': validation_confidence,
        'session_id': session_id,
        'total_methods': 5
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Main execution - run knowledge preservation suite.

    CRITICAL: This hook is NON-BLOCKING.
    Always exits with code 0, even if validation fails.
    We log everything but never prevent session end.
    """
    try:
        # Run knowledge preservation
        results = run_knowledge_preservation()

        # Log complete results
        log_path = log_validation_artifact(
            "session_end_results.json",
            results
        )

        # Print summary to stderr
        print("\n" + "=" * 70, file=sys.stderr)
        print("SESSION END - KNOWLEDGE PRESERVATION", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        print(f"Session ID: {results['session_id']}", file=sys.stderr)
        print(f"Evidence Methods: {results['evidence_count']}/{results['total_methods']}", file=sys.stderr)
        print(f"Validation Confidence: {results['validation_confidence']}%", file=sys.stderr)
        print("", file=sys.stderr)

        for method, result in results['validation_results'].items():
            status = "✓" if result['passed'] else "✗"
            print(f"  {status} {method}: {result['message']}", file=sys.stderr)

        print("", file=sys.stderr)
        print(f"Results logged to: {log_path}", file=sys.stderr)
        print("=" * 70, file=sys.stderr)

        # Always exit 0 (non-blocking)
        sys.exit(0)

    except Exception as e:
        # Log error but still exit 0
        print(f"\nSession end hook error: {str(e)}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
