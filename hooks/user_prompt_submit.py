#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Clear potentially contaminated Python environment variables (same as stop.py)
for _var in ['PYTHONHOME', 'PYTHONPATH']:
    if _var in os.environ:
        del os.environ[_var]

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Add hooks directory to path for utils imports
sys.path.insert(0, str(Path(__file__).parent))


def _record_task_start(session_id: str, prompt: str) -> tuple:
    """Write current_task.json with reliable task-start timestamp and task_id.

    Generates a unique task_id (UUID) for state isolation. If this is a follow-up
    prompt in the same session with non-pending VR checks, preserves the existing
    task_id to prevent authorize-stop → re-prompt → new task_id cycles (IMP-017).

    Returns (task_id, is_followup) tuple.
    """
    task_file = Path.home() / ".claude/data/current_task.json"
    vr_file = Path.home() / ".claude/data/verification_record.json"
    existing_task_id = None
    is_followup = False
    existing_data = {}

    try:
        task_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if this is a follow-up to an existing task
        if task_file.exists():
            try:
                existing_data = json.loads(task_file.read_text())
                if existing_data.get("session_id") == session_id:
                    # Same session — check if VR has work in progress
                    if vr_file.exists():
                        vr = json.loads(vr_file.read_text())
                        checks = vr.get("checks", {})
                        has_progress = any(
                            c.get("status") != "pending"
                            for c in checks.values()
                            if isinstance(c, dict)
                        )
                        if has_progress:
                            existing_task_id = existing_data.get("task_id")
                            is_followup = True
            except Exception:
                pass

        task_id = existing_task_id or str(uuid.uuid4())
        task_file.write_text(json.dumps({
            "task_id": task_id,
            "session_id": session_id,
            "task_started_at": (
                existing_data.get("task_started_at")
                if is_followup
                else datetime.now().isoformat()
            ),
            "prompt": prompt[:500],
            "is_followup": is_followup,
        }, indent=2))
        return task_id, is_followup
    except Exception:
        return str(uuid.uuid4()), False  # Never block prompt submission


def _reset_verification_for_new_task(session_id: str, task_id: str,
                                     is_followup: bool) -> None:
    """Reset verification state at start of each new user prompt.

    Prevents stale evidence from a previous task in the same session
    from being used as proof for the current task's work.
    Mirrors session_start.py:reset_verification_record() but runs per-prompt.

    If is_followup is True (same session, VR has non-pending checks), skips
    the VR reset entirely to preserve check evidence across authorize-stop
    retry cycles (IMP-017).
    """
    if is_followup:
        return  # Preserve existing VR state for follow-up prompts

    vr_file = Path.home() / ".claude/data/verification_record.json"
    try:
        vr_file.parent.mkdir(parents=True, exist_ok=True)
        all_pending = {
            k: {"status": "pending", "evidence": None, "timestamp": None,
                "skip_reason": None}
            for k in ["tests", "build", "lint", "app_starts", "api",
                      "frontend", "happy_path", "error_cases"]
        }
        with open(vr_file, "w") as f:
            json.dump({
                "reset_at": datetime.now().isoformat(),
                "session_id": session_id,
                "task_id": task_id,
                "checks": all_pending,
            }, f, indent=2)
    except Exception:
        pass  # Never block prompt submission

    # Clear DeepSeek state files from PREVIOUS tasks so the reviewer starts
    # fresh. Only delete task-scoped files (deepseek_context_*.json and
    # deepseek_review_state_*.json), plus the legacy global file.
    import glob as _glob
    _claude_data = Path.home() / ".claude" / "data"
    _patterns = [
        "deepseek_context.json",        # Legacy global file
        "deepseek_context_*.json",       # Task-scoped context files
        "deepseek_review_state_*.json",  # Task-scoped review state files
    ]
    for _pattern in _patterns:
        for _path_str in _glob.glob(str(_claude_data / _pattern)):
            try:
                Path(_path_str).unlink(missing_ok=True)
            except Exception:
                pass


def store_request_pattern(session_id, prompt, category, cwd):
    """Store request pattern to Claude-Mem for full-text search across sessions."""
    try:
        from utils.claude_mem import ClaudeMemClient
        project = Path(cwd).name if cwd else "unknown"
        mem_client = ClaudeMemClient(timeout=0.5)
        mem_client.init_session(
            session_id=session_id,
            project=project,
            prompt=prompt
        )
        mem_client.store_observation(
            session_id=session_id,
            tool_name="_user_request",
            tool_input={"category": category, "prompt": prompt[:500],
                        "project": project},
            tool_response=""
        )
    except Exception:
        pass  # Service may not be running; fail silently


def log_user_prompt(session_id, input_data):
    """Log user prompt to logs directory."""
    try:
        # Ensure logs directory exists (absolute path relative to this file)
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'user_prompt_submit.json'

        # Read existing log data or initialize empty list
        if log_file.exists():
            with open(log_file, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        # Append the entire input data
        log_data.append(input_data)

        # Write back to file with formatting
        with open(log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
    except Exception:
        pass  # Logging must never block the hook


# Legacy function removed - now handled by manage_session_data


def manage_session_data(session_id, prompt, name_agent=False):
    """Manage session data in the new JSON structure."""
    import subprocess
    
    # Ensure sessions directory exists (absolute path relative to this file)
    sessions_dir = Path(__file__).parent.parent / "data" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    
    # Load or create session file
    session_file = sessions_dir / f"{session_id}.json"
    
    if session_file.exists():
        try:
            with open(session_file, 'r') as f:
                session_data = json.load(f)
        except (json.JSONDecodeError, ValueError):
            session_data = {"session_id": session_id, "prompts": []}
    else:
        session_data = {"session_id": session_id, "prompts": []}
    
    # Add the new prompt
    session_data["prompts"].append(prompt)

    # Classify and persist task type (additive — short/stop prompts return "other" and don't downgrade)
    try:
        new_type = classify_task_type(prompt)
        existing = session_data.get("task_type", "other")
        if existing == "other" or existing == new_type:
            session_data["task_type"] = new_type
        elif new_type != "other" and existing != new_type:
            session_data["task_type"] = "mixed"
        # else: keep existing (short/stop prompts return "other", don't downgrade)
    except Exception:
        pass

    # Generate agent name if requested and not already present
    if name_agent and "agent_name" not in session_data:
        # Try Ollama first (preferred)
        try:
            result = subprocess.run(
                ["uv", "run", str(Path(__file__).parent / "utils" / "llm" / "ollama.py"), "--agent-name"],
                capture_output=True,
                text=True,
                timeout=5  # Shorter timeout for local Ollama
            )
            
            if result.returncode == 0 and result.stdout.strip():
                agent_name = result.stdout.strip()
                # Check if it's a valid name (not an error message)
                if len(agent_name.split()) == 1 and agent_name.isalnum():
                    session_data["agent_name"] = agent_name
                else:
                    raise Exception("Invalid name from Ollama")
        except Exception:
            # Fall back to Anthropic if Ollama fails
            try:
                result = subprocess.run(
                    ["uv", "run", str(Path(__file__).parent / "utils" / "llm" / "anth.py"), "--agent-name"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0 and result.stdout.strip():
                    agent_name = result.stdout.strip()
                    # Validate the name
                    if len(agent_name.split()) == 1 and agent_name.isalnum():
                        session_data["agent_name"] = agent_name
            except Exception:
                # If both fail, don't block the prompt
                pass
    
    # Save the updated session data
    try:
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    except Exception:
        # Silently fail if we can't write the file
        pass


def classify_task_type(prompt: str) -> str:
    """Returns: "research", "docs", "code", "config", "mixed", or "other". Never raises."""
    try:
        if not prompt or not isinstance(prompt, str):
            return "other"
    except Exception:
        return "other"

    def _has_ext(text: str, ext: str) -> bool:
        """True if ext appears as a full extension (not a prefix of a longer extension)."""
        idx = text.find(ext)
        while idx != -1:
            end = idx + len(ext)
            if end >= len(text) or not text[end].isalpha():
                return True
            idx = text.find(ext, idx + 1)
        return False

    p = prompt.lower()
    is_research = (p.endswith("?") or any(p.startswith(w) for w in
        ["what", "how", "why", "explain", "describe", "tell me", "can you"])
        or any(kw in p for kw in ["what is", "how does", "show me how"]))
    is_docs = any(kw in p for kw in [".md", "readme", "changelog", "docstring",
        "documentation", "comment", "jsdoc", "docs", "document"])
    is_code = (any(kw in p for kw in [
        "fix", "implement", "refactor", "add feature", "build", "create",
        "write", "make", "develop", "generate", "set up", "add",
        "app", "dashboard", "website", "webpage", "component", "function",
        "script", "program", "api", "class", "module", "feature", "page",
        "service", "test", "migrate", "deploy", "integrate",
    ])
        or any(_has_ext(p, ext) for ext in [".py", ".js", ".ts", ".go", ".rs", ".rb",
            ".java", ".cpp", ".c", ".sh", ".html", ".css", ".sql"]))
    is_config = (any(kw in p for kw in ["hook", "settings", "config", "workflow"])
        or any(_has_ext(p, ext) for ext in [".json", ".yaml", ".toml", ".sh", ".env"]))
    matches = sum([is_research, is_docs, is_code, is_config])
    if matches >= 2:
        return "mixed"
    if is_research:
        return "research"
    if is_docs:
        return "docs"
    if is_code:
        return "code"
    if is_config:
        return "config"
    return "other"


def categorize_prompt(prompt):
    """
    Categorize prompt into: bug, feature, question, command, or other.
    Returns tuple: (category, is_trackable)
    """
    prompt_lower = prompt.lower().strip()

    # Skip non-trackable prompts
    skip_patterns = ['ok', 'continue', 'yes', 'no', 'thanks', 'got it', 'sounds good',
                     'perfect', 'great', 'nice', 'cool', 'done', 'good', 'fine']
    if prompt_lower in skip_patterns or len(prompt_lower) < 10:
        return ('other', False)

    # Categorize based on keywords
    if any(kw in prompt_lower for kw in ['bug', 'fix', 'error', 'broken', 'issue', 'crash', 'failing', 'wrong']):
        return ('bug', True)
    elif any(kw in prompt_lower for kw in ['add', 'create', 'implement', 'build', 'feature', 'new', 'make', 'update', 'modify', 'change']):
        return ('feature', True)
    elif prompt_lower.startswith(('what', 'how', 'why', 'where', 'when', 'can you explain', 'could you', 'is there')):
        return ('question', True)
    elif prompt_lower.startswith('/') or prompt_lower.startswith('@'):
        return ('command', False)
    else:
        return ('request', True)  # General request


def update_user_requests(cwd, prompt, category, session_id):
    """Append categorized request to USER_REQUESTS.md"""
    docs_dir = Path(cwd) / "docs" / "development"
    docs_dir.mkdir(parents=True, exist_ok=True)

    requests_file = docs_dir / "USER_REQUESTS.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Create file with header if doesn't exist
    if not requests_file.exists():
        header = """# User Requests Log

Automatically tracked by Claude Code UserPromptSubmit hook.

## Categories
- **bug**: Bug reports and fixes
- **feature**: Feature requests
- **question**: Questions and clarifications
- **request**: General requests

---

"""
        requests_file.write_text(header)

    # Append new entry with delimiter structure
    entry = "\n-----\n"
    entry += f"### [{category.upper()}] {timestamp}\n"
    entry += f"**Session:** `{session_id[:8]}...`\n"
    entry += f"**Request:** {prompt[:500]}{'...' if len(prompt) > 500 else ''}\n"
    entry += "**Status:** [ ] Pending\n"
    entry += "-----\n"

    with open(requests_file, 'a') as f:
        f.write(entry)


def update_features(cwd, prompt, session_id):
    """Add feature request to FEATURES.md"""
    docs_dir = Path(cwd) / "docs" / "development"
    docs_dir.mkdir(parents=True, exist_ok=True)

    features_file = docs_dir / "FEATURES.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Create file with header if doesn't exist
    if not features_file.exists():
        header = """# Features Tracker

Automatically tracked by Claude Code UserPromptSubmit hook.

## Status Legend
- [ ] Requested - Feature has been requested
- [~] In Progress - Currently being implemented
- [x] Completed - Feature implemented and verified

---

## Requested Features

"""
        features_file.write_text(header)

    # Append new feature entry with delimiter structure
    entry = "\n-----\n"
    entry += f"### [FEATURE] {timestamp}\n"
    entry += f"**Session:** `{session_id[:8]}...`\n"
    entry += f"**Request:** {prompt[:200]}{'...' if len(prompt) > 200 else ''}\n"
    entry += "- [ ] Pending\n"
    entry += "-----\n"

    with open(features_file, 'a') as f:
        f.write(entry)


def build_deepseek_delegation_directive(prompt, mode_config):
    """Returns a DeepSeek delegation directive string, or None for non-delegatable prompts."""
    prompt_stripped = prompt.strip()
    # Skip very short prompts, slash commands, simple acks
    if len(prompt_stripped) < 15 or prompt_stripped.startswith('/'):
        return None
    trivial = {
        'ok', 'yes', 'no', 'sure', 'thanks', 'done', 'good', 'fine',
        'great', 'perfect', 'got it', 'sounds good', 'continue', 'proceed'
    }
    if prompt_stripped.lower() in trivial:
        return None

    # Check delegation policy against task type
    policy = mode_config.get('delegation_policy', {})
    task_type = classify_task_type(prompt)

    # Map task types to policy keys
    type_to_policy = {
        'code': 'code_tasks',
        'research': 'research_tasks',
        'config': 'config_tasks',
        'docs': 'docs_tasks',
    }
    policy_key = type_to_policy.get(task_type)
    if not policy_key or not policy.get(policy_key, False):
        return None  # Not a delegatable task type per policy

    profile = "confined"  # Always use confined profile — scopes DeepSeek to Claude Coding Projects
    plan_mode = mode_config.get('deepseek_plan_mode', True)

    return f"""⚠️ THIS DIRECTIVE OVERRIDES CLAUDE.md'S AUTONOMOUS-OPERATION RULE ⚠️
DEEPSEEK DELEGATION MODE — You are the SUPERVISOR.

FOR THIS CODE TASK: Delegate implementation to DeepSeek via MCP tools.

WORKSPACE CONSTRAINT (MANDATORY):
• DeepSeek MUST operate inside a subdirectory of:
    /Users/jeremyparker/Desktop/Claude Coding Projects
• You MUST pass working_dir="<full path to the specific project>" in every run() call.
• The base path itself (/Users/jeremyparker/Desktop/Claude Coding Projects) is NOT valid.
• If no project subdirectory has been identified yet, ask the user before delegating.

DELEGATION STEPS:
1. Identify the project directory (must be a subpath of the workspace above).
2. Formulate a PRECISE task description (include file paths, expected behavior, constraints)
3. Call: mcp__deepseek-agent__run with
     profile="{profile}",
     plan_mode={str(plan_mode).lower()},
     working_dir="<absolute path to project subdirectory>"
   - Specify exact files to create/modify
4. Monitor: mcp__deepseek-agent__get_state to check progress
5. Retrieve: mcp__deepseek-agent__get_output when complete

SKEPTICAL REVIEW PROTOCOL (MANDATORY after DeepSeek completes):
1. Read EVERY file DeepSeek modified — use the Read tool, line by line
2. Look for bugs with a magnifying glass:
   - Off-by-one errors, wrong variable names, hardcoded values
   - Missing error handling, broken imports, security vulnerabilities
   - Logic that doesn't match the original spec
3. Run tests independently — do NOT trust DeepSeek's claims
4. Run linter independently
5. Rate confidence: "high" / "needs-fixes" / "redo"
   - "high": No issues found after thorough review (cite evidence)
   - "needs-fixes": Issues found — fix them yourself or send specific follow-up
   - "redo": Fundamentally wrong — send new task with clearer spec

DO NOT DELEGATE: questions, explanations, git ops, reviews, validation, security checks.
If DeepSeek is unavailable, implement directly yourself."""


def build_agent_routing_directive(prompt):
    """Returns agent routing directive string, or None for trivial prompts."""
    prompt_stripped = prompt.strip()
    # Skip very short prompts, slash commands, simple acks
    if len(prompt_stripped) < 15 or prompt_stripped.startswith('/'):
        return None
    trivial = {
        'ok', 'yes', 'no', 'sure', 'thanks', 'done', 'good', 'fine',
        'great', 'perfect', 'got it', 'sounds good', 'continue', 'proceed'
    }
    if prompt_stripped.lower() in trivial:
        return None

    return """BEFORE ANSWERING: Check if this task falls into a specialist domain:
• Implementing features in a specific language or framework (Rust, Go, Python, FastAPI, React, etc.)
• Security analysis, audit, or hardening
• ML/AI model training, evaluation, or deployment
• Infrastructure, cloud, or DevOps setup
• Database design, migration, or optimization
• Code review, test suite creation, or performance profiling

If YES → dispatch: Task(subagent_type="<agent>", prompt="<full task>")
          then announce: "Routing to <agent> for <reason>."
If NO  → answer directly (questions, explanations, quick edits, clarifications).

AVAILABLE AGENTS (subagent_type: <name> in Task tool):
[CODE]     python-pro, typescript-pro, javascript-pro, rust-pro, golang-pro, java-pro, scala-pro, csharp-pro, ruby-pro, elixir-pro, bash-pro, cpp-pro, c-pro
[BACKEND]  backend-architect, fastapi-pro, django-pro, graphql-architect, api-designer-sonnet
[FRONTEND] frontend-developer, ui-ux-designer, mobile-developer, flutter-expert, ios-developer
[SECURITY] security-auditor, threat-modeling-expert, backend-security-coder, frontend-security-coder, owasp-guardian-sonnet
[ML/DATA]  data-scientist, ml-engineer, mlops-engineer, data-engineer, ai-engineer, prompt-engineer
[DATABASE] database-architect, database-optimizer, sql-pro, database-admin
[INFRA]    kubernetes-architect, terraform-specialist, cloud-architect, deployment-engineer, cicd-engineer-sonnet
[TESTING]  test-automator, tdd-orchestrator, architect-review, code-reviewer, performance-engineer
[OPS]      incident-responder, devops-troubleshooter, observability-engineer, error-detective, debugger
[DOCS]     docs-architect, tutorial-engineer, mermaid-expert, c4-code, c4-component, c4-container, c4-context
[OTHER]    legacy-modernizer, dx-optimizer, quant-analyst, payment-integration, blockchain-developer

Full catalog: ~/.claude/agents/AGENT_INDEX.md"""


def inject_ambiguity_prompt(prompt):
    """
    Inject context telling agent to resolve ambiguities.
    Only for substantial requests (not simple confirmations).
    """
    prompt_lower = prompt.lower().strip()

    # Skip for simple responses
    skip_patterns = ['ok', 'yes', 'no', 'continue', 'thanks', 'got it', 'sounds good',
                     'perfect', 'great', 'nice', 'cool', 'done', 'good', 'fine']
    if prompt_lower in skip_patterns or len(prompt_lower) < 20:
        return None

    return """STEP 1 — UPFRONT CLARITY: If this task has ≥2 valid interpretations that would lead to
different implementations, ask ALL clarifying questions in one batch NOW. For each option,
mark your preferred choice [Recommended]. Then wait for a response before proceeding.
If the task is clear, skip to Step 2 immediately.

STEP 2 — AUTONOMOUS EXECUTION: Once task is clear, proceed fully autonomously.
Never ask "should I proceed?", "do you want me to X?", or "want me to continue?".
Errors = fix immediately. Mid-task ambiguity = resolve with best judgment, don't ask.
Actions you can execute = EXECUTE THEM. Never write "I recommend X" or "You should run Y" — those are tasks, not suggestions. If risky/destructive, confirm once then execute."""


def validate_prompt(prompt):
    """
    Validate the user prompt for security or policy violations.
    Returns tuple (is_valid, reason).
    """
    # Example validation rules (customize as needed)
    blocked_patterns = [
        # Add any patterns you want to block
        # Example: ('rm -rf /', 'Dangerous command detected'),
    ]
    
    prompt_lower = prompt.lower()
    
    for pattern, reason in blocked_patterns:
        if pattern.lower() in prompt_lower:
            return False, reason
    
    return True, None


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--validate', action='store_true', 
                          help='Enable prompt validation')
        parser.add_argument('--log-only', action='store_true',
                          help='Only log prompts, no validation or blocking')
        parser.add_argument('--store-last-prompt', action='store_true',
                          help='Store the last prompt for status line display')
        parser.add_argument('--name-agent', action='store_true',
                          help='Generate an agent name for the session')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract session_id and prompt
        session_id = input_data.get('session_id', 'unknown')
        prompt = input_data.get('prompt', '')

        # Record task start time (authoritative timestamp for transcript filtering)
        task_id, is_followup = _record_task_start(session_id, prompt)

        # Reset verification state for new task (per-prompt isolation)
        # Skips reset if this is a follow-up prompt with existing check progress
        _reset_verification_for_new_task(session_id, task_id, is_followup)

        # Log the user prompt
        log_user_prompt(session_id, input_data)

        # Manage session data with JSON structure
        if args.store_last_prompt or args.name_agent:
            manage_session_data(session_id, prompt, name_agent=args.name_agent)

        # Track requests in docs/development/ if cwd is available
        cwd = input_data.get('cwd', '')

        if cwd and args.store_last_prompt:
            try:
                category, is_trackable = categorize_prompt(prompt)

                if is_trackable:
                    update_user_requests(cwd, prompt, category, session_id)

                    if category == 'feature':
                        update_features(cwd, prompt, session_id)

                    store_request_pattern(session_id, prompt, category, cwd)
            except Exception:
                pass
        
        # Validate prompt if requested and not in log-only mode
        if args.validate and not args.log_only:
            is_valid, reason = validate_prompt(prompt)
            if not is_valid:
                # Exit code 2 blocks the prompt with error message
                print(f"Prompt blocked: {reason}", file=sys.stderr)
                sys.exit(2)

        # Inject ambiguity detection context for substantial requests
        ambiguity_context = inject_ambiguity_prompt(prompt)

        # Build additional context with recommendations
        context_parts = []

        # Prepend routing directive — deepseek delegation or normal agent routing
        try:
            from utils.config_loader import get_config
            mode_config = get_config().get_agent_mode()
            if mode_config.get("mode") == "deepseek":
                directive = build_deepseek_delegation_directive(prompt, mode_config)
                if directive:
                    context_parts.insert(0, directive)
            else:
                agent_directive = build_agent_routing_directive(prompt)
                if agent_directive:
                    context_parts.insert(0, agent_directive)
        except Exception:
            agent_directive = build_agent_routing_directive(prompt)
            if agent_directive:
                context_parts.insert(0, agent_directive)

        if ambiguity_context:
            context_parts.append(ambiguity_context)

        # Add plugin suggestions from New Tools marketplace
        try:
            from utils.plugin_resolver import get_plugin_suggestions_for_prompt
            plugin_suggestions = get_plugin_suggestions_for_prompt(prompt)
            if plugin_suggestions:
                context_parts.append(f"\n{plugin_suggestions}")
        except Exception:
            pass  # Graceful degradation

        # Output combined context
        if context_parts:
            output = {
                "hookSpecificOutput": {
                    "additionalContext": "\n".join(context_parts)
                }
            }
            print(json.dumps(output))

        # Success - prompt will be processed
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == '__main__':
    main()