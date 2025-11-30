#!/usr/bin/env -S env -u PYTHONHOME -u PYTHONPATH uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def log_user_prompt(session_id, input_data):
    """Log user prompt to logs directory."""
    # Ensure logs directory exists
    log_dir = Path("logs")
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


# Legacy function removed - now handled by manage_session_data


def manage_session_data(session_id, prompt, name_agent=False):
    """Manage session data in the new JSON structure."""
    import subprocess
    
    # Ensure sessions directory exists
    sessions_dir = Path(".claude/data/sessions")
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
    
    # Generate agent name if requested and not already present
    if name_agent and "agent_name" not in session_data:
        # Try Ollama first (preferred)
        try:
            result = subprocess.run(
                ["uv", "run", ".claude/hooks/utils/llm/ollama.py", "--agent-name"],
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
                    ["uv", "run", ".claude/hooks/utils/llm/anth.py", "--agent-name"],
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

    return """🔍 BEFORE STARTING: If this request has any ambiguity or multiple valid approaches, ask clarifying questions first. Mark your recommended answer with [Recommended]."""


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

                    # Also track in FEATURES.md if it's a feature request
                    if category == 'feature':
                        update_features(cwd, prompt, session_id)
            except Exception:
                # Don't block on tracking errors
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
        if ambiguity_context:
            output = {
                "hookSpecificOutput": {
                    "additionalContext": ambiguity_context
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