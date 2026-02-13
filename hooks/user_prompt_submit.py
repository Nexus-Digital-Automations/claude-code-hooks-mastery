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

# Add hooks directory to path for utils imports
sys.path.insert(0, str(Path(__file__).parent))


def store_request_pattern(session_id, prompt, category, cwd):
    """
    Store request pattern to ReasoningBank and Claude-Mem.
    All operations are non-blocking with graceful fallback.
    Enhanced with MCP tool integrations for workflow and neural patterns.
    """
    # 1. ReasoningBank: Store pattern via Claude Flow (increased timeout)
    try:
        from utils.claude_flow import ClaudeFlowClient
        cf = ClaudeFlowClient(timeout=5.0)
        cf.memory_store(
            f"request_{category}_{session_id[:8]}",
            {
                "category": category,
                "prompt_preview": prompt[:200],
                "project": Path(cwd).name if cwd else "unknown",
                "timestamp": datetime.now().isoformat()
            },
            namespace="user_requests",
            confidence=0.5
        )
    except Exception:
        pass  # Graceful degradation

    # 2. Claude-Mem: Store for full-text search (increased timeout)
    try:
        from utils.claude_mem import ClaudeMemClient
        mem_client = ClaudeMemClient(timeout=5.0)
        mem_client.store_observation(
            session_id=session_id,
            tool_name="_user_request",
            tool_input={"category": category, "prompt": prompt[:500]},
            tool_response=""
        )
    except Exception:
        pass  # Graceful degradation

    # 3. NEW: Neural Pattern Analysis - Learn from user request patterns
    try:
        from utils.neural_client import get_neural_client
        neural = get_neural_client(timeout=3.0)

        # Analyze cognitive patterns from this request type
        neural.analyze_patterns(
            action='learn',
            operation=f'user_request:{category}',
            outcome='received',
            metadata={
                'session': session_id[:8],
                'category': category,
                'prompt_length': len(prompt),
                'project': Path(cwd).name if cwd else 'unknown'
            }
        )
    except Exception:
        pass  # Graceful degradation


def get_workflow_recommendation(prompt, category):
    """
    Get workflow recommendation based on prompt complexity and category.
    Returns workflow config or None if not applicable.
    """
    # Only recommend workflows for substantial feature/bug requests
    if category not in ['feature', 'bug'] or len(prompt) < 50:
        return None

    # Determine complexity based on keywords
    complex_keywords = [
        'implement', 'build', 'create', 'refactor', 'migrate',
        'integrate', 'redesign', 'optimize', 'comprehensive', 'full'
    ]
    prompt_lower = prompt.lower()

    is_complex = any(kw in prompt_lower for kw in complex_keywords)
    if not is_complex:
        return None

    # Build workflow configuration
    if category == 'feature':
        return {
            'name': f'feature_{datetime.now().strftime("%Y%m%d_%H%M")}',
            'steps': [
                {'name': 'analyze', 'description': 'Analyze requirements'},
                {'name': 'design', 'description': 'Design architecture'},
                {'name': 'implement', 'description': 'Implement feature'},
                {'name': 'test', 'description': 'Test implementation'},
                {'name': 'review', 'description': 'Code review'}
            ],
            'triggers': ['on_start'],
            'priority': 'high' if 'urgent' in prompt_lower else 'medium'
        }
    elif category == 'bug':
        return {
            'name': f'bugfix_{datetime.now().strftime("%Y%m%d_%H%M")}',
            'steps': [
                {'name': 'reproduce', 'description': 'Reproduce the bug'},
                {'name': 'diagnose', 'description': 'Diagnose root cause'},
                {'name': 'fix', 'description': 'Implement fix'},
                {'name': 'verify', 'description': 'Verify fix works'},
                {'name': 'test', 'description': 'Run regression tests'}
            ],
            'triggers': ['on_start'],
            'priority': 'critical' if 'critical' in prompt_lower else 'high'
        }

    return None


def create_workflow_for_request(session_id, prompt, category):
    """
    Create an automated workflow for complex requests.
    Non-blocking with graceful fallback.
    """
    workflow_config = get_workflow_recommendation(prompt, category)
    if not workflow_config:
        return None

    try:
        from utils.workflow_client import get_workflow_client
        workflow = get_workflow_client(timeout=5.0)

        # Create the workflow
        result = workflow.create_workflow(
            name=workflow_config['name'],
            steps=workflow_config['steps'],
            triggers=workflow_config.get('triggers', [])
        )

        if result and result.get('workflowId'):
            return result['workflowId']
    except Exception:
        pass  # Graceful degradation

    return None


def get_agent_recommendation(category, prompt):
    """
    Get recommended agent type based on request category and content.
    Returns agent type string or None.
    """
    prompt_lower = prompt.lower()

    # Security-related keywords
    if any(kw in prompt_lower for kw in ['security', 'vulnerability', 'owasp', 'authentication', 'authorization']):
        return 'owasp-guardian-sonnet'

    # Testing keywords
    if any(kw in prompt_lower for kw in ['test', 'coverage', 'tdd', 'unit test', 'integration test']):
        return 'test-engineer-sonnet'

    # Performance keywords
    if any(kw in prompt_lower for kw in ['performance', 'optimize', 'slow', 'benchmark', 'profil']):
        return 'perf-analyzer'

    # API/design keywords
    if any(kw in prompt_lower for kw in ['api', 'endpoint', 'rest', 'graphql', 'schema']):
        return 'api-designer-sonnet'

    # Architecture keywords
    if any(kw in prompt_lower for kw in ['architect', 'design', 'structure', 'pattern', 'refactor']):
        return 'system-architect-sonnet'

    # Documentation keywords
    if any(kw in prompt_lower for kw in ['document', 'readme', 'docs', 'comment', 'jsdoc']):
        return 'documentation-writer-sonnet'

    # Default by category
    category_map = {
        'bug': 'debug-detective-sonnet',
        'feature': 'coder',
        'question': 'researcher'
    }

    return category_map.get(category)


def get_sparc_mode_recommendation(prompt, category):
    """
    Recommend SPARC mode based on request type.
    Returns mode string or None.
    """
    prompt_lower = prompt.lower()

    # TDD keywords
    if any(kw in prompt_lower for kw in ['tdd', 'test-driven', 'test first', 'red green']):
        return 'test'

    # API keywords
    if any(kw in prompt_lower for kw in ['api', 'endpoint', 'rest', 'graphql']):
        return 'api'

    # UI keywords
    if any(kw in prompt_lower for kw in ['ui', 'frontend', 'component', 'react', 'vue']):
        return 'ui'

    # Refactor keywords
    if any(kw in prompt_lower for kw in ['refactor', 'clean', 'improve', 'optimize code']):
        return 'refactor'

    # Default to dev mode for features
    if category == 'feature':
        return 'dev'

    return None


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

    return """UPFRONT: Clarify ambiguity NOW. Mark recommended with [Recommended].

PLAN VALIDATION (3+ methods before stopping):
• Tests: npm test, pytest, cargo test
• Build: npm run build, tsc --noEmit
• Lint: eslint, flake8, mypy
• Logs: console.log, app logs
• Runtime: start app, verify
• Browser: Puppeteer screenshots
• API: curl endpoints

Execute autonomously—no mid-task questions."""


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
        workflow_id = None
        recommended_agent = None
        sparc_mode = None

        if cwd and args.store_last_prompt:
            try:
                category, is_trackable = categorize_prompt(prompt)

                if is_trackable:
                    update_user_requests(cwd, prompt, category, session_id)

                    # Also track in FEATURES.md if it's a feature request
                    if category == 'feature':
                        update_features(cwd, prompt, session_id)

                    # Store to ReasoningBank and Claude-Mem
                    store_request_pattern(session_id, prompt, category, cwd)

                    # NEW: Create workflow for complex requests
                    workflow_id = create_workflow_for_request(session_id, prompt, category)

                    # NEW: Get agent recommendation
                    recommended_agent = get_agent_recommendation(category, prompt)

                    # NEW: Get SPARC mode recommendation
                    sparc_mode = get_sparc_mode_recommendation(prompt, category)
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

        # Build additional context with recommendations
        context_parts = []
        if ambiguity_context:
            context_parts.append(ambiguity_context)

        # Add workflow context if created
        if workflow_id:
            context_parts.append(f"\n📋 WORKFLOW: Auto-created workflow '{workflow_id}' for this request.")

        # Add agent recommendation
        if recommended_agent:
            context_parts.append(f"\n🤖 RECOMMENDED AGENT: Consider using '{recommended_agent}' for this task.")

        # Add SPARC mode recommendation
        if sparc_mode:
            context_parts.append(f"\n⚡ SPARC MODE: '{sparc_mode}' mode recommended for this type of work.")

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