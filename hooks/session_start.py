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
import subprocess
from pathlib import Path
from datetime import datetime

# Add hooks directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Fix Python environment warnings
for var in ['PYTHONHOME', 'PYTHONPATH']:
    if var in os.environ:
        del os.environ[var]

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional


def log_session_start(input_data):
    """Log session start event to logs directory."""
    # Ensure logs directory exists
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / 'session_start.json'
    
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


def get_git_status():
    """Get current git status information."""
    try:
        # Get current branch
        branch_result = subprocess.run(
            ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
            capture_output=True,
            text=True,
            timeout=5
        )
        current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "unknown"
        
        # Get uncommitted changes count
        status_result = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if status_result.returncode == 0:
            changes = status_result.stdout.strip().split('\n') if status_result.stdout.strip() else []
            uncommitted_count = len(changes)
        else:
            uncommitted_count = 0
        
        return current_branch, uncommitted_count
    except Exception:
        return None, None


def get_recent_issues():
    """Get recent GitHub issues if gh CLI is available."""
    try:
        # Check if gh is available
        gh_check = subprocess.run(['which', 'gh'], capture_output=True)
        if gh_check.returncode != 0:
            return None
        
        # Get recent open issues
        result = subprocess.run(
            ['gh', 'issue', 'list', '--limit', '5', '--state', 'open'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _generate_agent_identity(session_id: str) -> str:
    """Generate a unique agent_id for this session and persist it.

    The agent_id is a UUID that uniquely identifies this session's agent.
    It scopes all DeepSeek reviewer state files and prevents cross-session
    contamination. Written to ~/.claude/data/agent_identity_{session_id}.json
    (session-scoped to avoid clobbering across concurrent sessions).

    Returns the agent_id string.
    """
    import uuid
    agent_id = str(uuid.uuid4())
    identity_file = Path.home() / f".claude/data/agent_identity_{session_id}.json"
    try:
        identity_file.parent.mkdir(parents=True, exist_ok=True)
        identity_file.write_text(json.dumps({
            "agent_id": agent_id,
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
        }, indent=2))
    except Exception:
        pass  # Never block session start
    return agent_id


def _register_active_session(session_id: str, working_dir: str) -> None:
    """Register this session in active_sessions.json keyed by working_dir.

    This lookup table lets shell scripts (authorize-stop.sh) find the correct
    session_id for the current working directory without a global singleton file.
    Multiple concurrent sessions write to different keys, avoiding clobber.
    """
    sessions_file = Path.home() / ".claude/data/active_sessions.json"
    try:
        sessions = {}
        if sessions_file.exists():
            sessions = json.loads(sessions_file.read_text())
        sessions[working_dir] = session_id
        sessions_file.write_text(json.dumps(sessions, indent=2))
    except Exception:
        pass  # Never block session start


def reset_verification_record(session_id: str = "unknown") -> None:
    """Clean up stale state files from previous sessions.

    Deletes VR files, legacy global files, stale session-scoped identity/task
    files, and orphaned DeepSeek files so the new session starts clean.
    """
    import glob as _glob
    _claude_data = Path.home() / ".claude" / "data"
    _claude_data.mkdir(parents=True, exist_ok=True)

    # Read previous agent identity (session-scoped) for targeted cleanup
    _old_agent_id = None
    _identity_file = _claude_data / f"agent_identity_{session_id}.json"
    if not _identity_file.exists():
        # Fallback: check legacy global file
        _identity_file = _claude_data / "agent_identity.json"
    try:
        if _identity_file.exists():
            _old = json.loads(_identity_file.read_text())
            _old_agent_id = _old.get("agent_id")
    except Exception:
        pass

    # Targeted cleanup: delete state files belonging to the old agent
    if _old_agent_id:
        for _suffix in [
            f"deepseek_context_{_old_agent_id}.json",
            f"deepseek_review_state_{_old_agent_id}.json",
            f"deepseek_review_state_{_old_agent_id}.rejections",
        ]:
            try:
                (_claude_data / _suffix).unlink(missing_ok=True)
            except Exception:
                pass

    # Delete legacy global VR
    legacy = _claude_data / "verification_record.json"
    if legacy.exists():
        try:
            legacy.unlink(missing_ok=True)
        except Exception:
            pass

    # Delete all task-scoped VR files (fresh start)
    for p in _glob.glob(str(_claude_data / "verification_record_*.json")):
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass

    # Clean up stale session-scoped files (not matching current session)
    for _pattern in [
        "agent_identity_*.json",         # Session-scoped identity files
        "current_task_*.json",           # Session-scoped task files
        "stop_authorization_*.json",     # Session-scoped auth files
    ]:
        for _path_str in _glob.glob(str(_claude_data / _pattern)):
            # Keep the current session's files
            if session_id != "unknown" and session_id in _path_str:
                continue
            try:
                Path(_path_str).unlink(missing_ok=True)
            except Exception:
                pass

    # Clean up legacy global singleton files (replaced by session-scoped versions)
    for _legacy_name in [
        "agent_identity.json",
        "current_task.json",
        "stop_authorization.json",
    ]:
        try:
            (_claude_data / _legacy_name).unlink(missing_ok=True)
        except Exception:
            pass

    # Glob-based fallback: clean up orphaned DeepSeek files from any agent.
    # user_prompt_submit.py also does this, but session_start provides a belt-and-
    # suspenders guarantee even if prompt-submit cleanup fails silently.
    for _pattern in [
        "deepseek_context.json",        # Legacy global file
        "deepseek_context_*.json",       # Agent/task-scoped context files
        "deepseek_review_state_*.json",  # Agent/task-scoped review state files
        "deepseek_review_state_*.rejections",  # Rejection counters (IMP-027)
        "deepseek_run_snapshot.json",    # Mutation-detection snapshot
        "deepseek_delegations.json",     # Delegation ring buffer
    ]:
        for _path_str in _glob.glob(str(_claude_data / _pattern)):
            try:
                Path(_path_str).unlink(missing_ok=True)
            except Exception:
                pass


def load_development_context(source, agent_id=""):
    """Load relevant development context based on session source."""
    context_parts = []

    # Add timestamp and agent identity
    context_parts.append(f"Session started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    context_parts.append(f"Session source: {source}")
    if agent_id:
        context_parts.append(f"Agent ID: {agent_id}")

    # Add session rules (autonomous + validation, concise)
    session_rules = """
--- SESSION RULES ---
1. AUTONOMOUS: Never ask permission mid-task. Decide and proceed. Fix errors immediately.
2. VALIDATE: Before declaring any task complete, run actual commands and show output.
   Minimum: tests + build. No claims without evidence.
   Format: Command: <x> | Result: ✅/❌ | Output: <actual snippet>
3. VERIFICATION PLAN: State your verification commands (pytest, npm test, build, curl) BEFORE
   implementing. Reading code (find, cat, grep) is investigation, NOT verification.
   No test/build proof = not done.
4. ROOT CLEAN: Never create files at project root except essential configs.
5. STOP: Use /authorize-stop after presenting validation proof.
6. EXECUTE DON'T RECOMMEND: If you can do it, do it. Never say "I recommend X" or "You should Y" for actions within your capability.
"""
    context_parts.append(session_rules)

    # Verify CLAUDE.md matches current mode (auto-fix if mismatched)
    try:
        from utils.config_loader import get_config
        current_mode = get_config().get_agent_mode().get("mode", "claude")
        claude_dir = Path.home() / ".claude"
        source_file = claude_dir / f"CLAUDE.{current_mode}.md"
        dest_file = claude_dir / "CLAUDE.md"
        if source_file.exists() and dest_file.exists():
            if source_file.read_text() != dest_file.read_text():
                import shutil
                shutil.copy2(str(source_file), str(dest_file))
    except Exception:
        pass

    # Inject DeepSeek supervisor context if in deepseek mode
    try:
        from utils.config_loader import get_config
        if get_config().is_deepseek_mode():
            session_rules_ds = """
DEEPSEEK DELEGATION MODE — THIS OVERRIDES CLAUDE.md'S "AUTONOMOUS OPERATION" RULE

You are the architect and quality gate. DeepSeek builds code but is not as
strong a coder as you — expect mistakes. Its code will often have missing error
handling, wrong variable names, logic bugs, and incomplete implementations.
Thorough review and testing catch real problems every time.

BEFORE DELEGATING — WRITE A TASK DESCRIPTION (not a full plan):
- Features: what to build as a numbered list
- Constraints: what NOT to change, what to preserve
- Verification criteria: how you will validate each feature
Scale to the task: 5-10 lines for a bug fix, 15-20 for a feature.
Do NOT include architecture, function signatures, or file-by-file instructions.
DeepSeek investigates the codebase and produces its own comprehensive plan.

DIVISION OF LABOR:
- You (Claude Code): task description, plan review, verify build/lint/type-check, final Playwright gate, frontend UI, security
- DeepSeek Agent: codebase investigation, planning, code building, first-pass mechanical checks (build/lint/type-check/Playwright, budget-capped), Playwright test writing
- Both: Playwright test coverage — comprehensive E2E tests mandatory for every frontend feature

DELEGATION PROTOCOL:
- Write the task description, then delegate via mcp__deepseek-agent__run
- Use profile="default-delegation" — plan mode is enabled by default
- DeepSeek investigates the codebase with read-only tools and produces a comprehensive plan
- Returns state="awaiting_approval" — review the plan before any code is written
- Monitor with mcp__deepseek-agent__poll

PLAN REVIEW (mandatory — before approving):
- plan(agent_id, "get") to inspect the plan
- Check codebase_analysis: did it read the right files? Do entity signatures match?
  READ THE FILES YOURSELF to verify claims.
- Check tool_calls_planned: do old_string values match actual file contents?
  READ THE FILES YOURSELF to verify edit strings.
- Check risk_assessment: are risks identified for each change?
- Red flags: editing a file not in files_read, empty old_string, no risk assessment
- plan(agent_id, "approve") / plan(agent_id, "edit", ...) / plan(agent_id, "reject", ...)

AFTER AGENT COMPLETES (mandatory — every time):
1. Read EVERY file the agent modified — line by line, not skimming
2. Check for: off-by-one errors, missing error handling, wrong variable names,
   hardcoded values, broken imports, security vulnerabilities, logic that
   doesn't match the plan
3. Re-run build + lint + type-check yourself (mandatory — should pass in seconds if agent passed)
4. Run Playwright yourself as the final E2E gate
5. Run any unit/integration tests the agent didn't cover
6. Start the app and exercise the happy path yourself
7. If you find ANY issue: fix it yourself OR send a specific follow-up task
8. Never say "output looks good" without citing specific evidence

TASKS YOU KEEP (do NOT delegate):
- Plan review and approval — investigate anything suspicious
- Test qualification — re-run build/lint/type-check, final Playwright gate, unit/integration tests
- ALL frontend UI work — use impeccable skills (DeepSeek writes Playwright tests for features it adds, not UI code)
- Questions, explanations, read-only reviews
- Git operations, security audits
- ALL security work — scanning, auditing, vulnerability review, hardening
- Stop authorization and verification

DELEGATION THRESHOLD:
- Only deploy DeepSeek for tasks touching ~5+ files
- Small tasks (~5 files or fewer): implement directly yourself
- Delegation overhead (run, poll, review, fix) exceeds direct implementation for small changes

FALLBACK: If DeepSeek is unavailable, implement directly yourself.

You are the architect and the quality gate. Every deliverable gets verified.
"""
            context_parts.insert(0, session_rules_ds)  # Highest priority — must appear first
    except Exception:
        pass  # Graceful degradation

    # Add git information
    branch, changes = get_git_status()
    if branch:
        context_parts.append(f"Git branch: {branch}")
        if changes > 0:
            context_parts.append(f"Uncommitted changes: {changes} files")
    
    # Load project-specific context files if they exist
    context_files = [
        ".claude/CONTEXT.md",
        ".claude/TODO.md",
        "TODO.md",
        ".github/ISSUE_TEMPLATE.md"
    ]
    
    for file_path in context_files:
        if Path(file_path).exists():
            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    if content:
                        context_parts.append(f"\n--- Content from {file_path} ---")
                        context_parts.append(content[:1000])  # Limit to first 1000 chars
            except Exception:
                pass
    
    # Add recent issues if available
    issues = get_recent_issues()
    if issues:
        context_parts.append("\n--- Recent GitHub Issues ---")
        context_parts.append(issues)

    # Detect project type and surface relevant plugins from New Tools
    try:
        from utils.plugin_resolver import get_plugins_for_project
        cwd = os.getcwd()
        plugin_ctx = get_plugins_for_project(cwd)
        if plugin_ctx:
            context_parts.append(f"\n{plugin_ctx}")
    except Exception:
        pass  # Graceful degradation

    return "\n".join(context_parts)


def assess_task_complexity(prompt: str) -> dict:
    """
    Assess task complexity to determine if swarm orchestration is beneficial.

    Analyzes prompt for indicators of multi-agent potential:
    - Multi-component: frontend, backend, API, database mentions
    - Large scope: Long prompt with many requirements
    - Comprehensive: Keywords suggesting full-system work
    - Parallel: Multiple independent subtasks

    Returns:
        dict with complexity scores and swarm recommendation
    """
    prompt_lower = prompt.lower()
    indicators = {}

    # Multi-component indicators
    multi_component_keywords = ['frontend', 'backend', 'api', 'database', 'server',
                                'client', 'ui', 'service', 'microservice', 'component']
    indicators['multi_component'] = sum(1 for kw in multi_component_keywords if kw in prompt_lower)

    # Large scope indicators
    indicators['large_scope'] = len(prompt) > 500 or prompt.count('\n') > 5

    # Comprehensive work indicators
    comprehensive_keywords = ['comprehensive', 'complete', 'full', 'entire', 'all',
                             'refactor', 'redesign', 'overhaul', 'migrate', 'upgrade']
    indicators['comprehensive'] = any(kw in prompt_lower for kw in comprehensive_keywords)

    # Parallel subtask indicators
    parallel_keywords = ['and also', 'additionally', 'as well as', 'plus', 'along with',
                        '1.', '2.', '- ', '* ', 'first', 'second', 'then']
    indicators['parallel_tasks'] = sum(1 for kw in parallel_keywords if kw in prompt)

    # Plugin match count enrichment
    try:
        from utils.plugin_resolver import get_resolver
        resolver = get_resolver()
        plugin_matches = resolver.resolve_by_task(prompt)
        indicators['plugin_matches'] = len(plugin_matches)
    except Exception:
        indicators['plugin_matches'] = 0

    # Calculate complexity score
    complexity_score = (
        indicators['multi_component'] * 2 +
        (3 if indicators['large_scope'] else 0) +
        (4 if indicators['comprehensive'] else 0) +
        indicators['parallel_tasks'] +
        min(indicators.get('plugin_matches', 0), 3)  # Up to 3 bonus from plugin matches
    )

    # Recommend swarm if complexity is high enough
    recommend_swarm = complexity_score >= 5

    # Determine topology based on task type
    if indicators['multi_component'] >= 3:
        recommended_topology = "hierarchical"  # Queen coordinates specialists
    elif indicators['parallel_tasks'] >= 3:
        recommended_topology = "mesh"  # Peer agents work in parallel
    else:
        recommended_topology = "adaptive"  # Dynamic switching

    return {
        'complexity_score': complexity_score,
        'recommend_swarm': recommend_swarm,
        'recommended_topology': recommended_topology,
        'indicators': indicators
    }


def auto_init_swarm(complexity: dict, session_id: str) -> dict:
    """
    Initialize swarm orchestration if complexity assessment recommends it.
    Uses MCP-based swarm client for direct tool integration.

    Args:
        complexity: Result from assess_task_complexity
        session_id: Session ID for tracking

    Returns:
        dict with swarm initialization results
    """
    if not complexity.get('recommend_swarm', False):
        return {'initialized': False, 'reason': 'complexity below threshold'}

    results = {
        'initialized': False,
        'topology': complexity.get('recommended_topology', 'adaptive'),
        'swarm_id': None,
        'agents_spawned': 0,
        'neural_loaded': False
    }

    # 1. Try MCP-based swarm initialization first (new integration)
    try:
        from utils.swarm_client import get_swarm_client
        client = get_swarm_client(timeout=10.0)

        # Initialize swarm with recommended topology
        swarm_result = client.init_swarm(
            topology=results['topology'],
            strategy='adaptive',
            max_agents=8
        )

        if swarm_result:
            results['initialized'] = True
            results['swarm_id'] = swarm_result.get('swarmId', session_id[:12])

            # Store session context in swarm memory
            from utils.mcp_client import get_mcp_client
            mcp = get_mcp_client(timeout=5.0)
            mcp.memory_store(
                key=f'session/{session_id[:8]}',
                value=json.dumps({
                    'session_id': session_id,
                    'topology': results['topology'],
                    'complexity_score': complexity.get('complexity_score', 0),
                    'initialized_at': datetime.now().isoformat()
                }),
                namespace='swarm_sessions',
                ttl=86400  # 24 hour TTL
            )
    except Exception:
        pass  # Graceful degradation

    # 2. Fallback to legacy claude_flow client if MCP fails
    if not results['initialized']:
        try:
            from utils.claude_flow import ClaudeFlowClient
            cf = ClaudeFlowClient(timeout=5.0)

            swarm_result = cf.swarm_init(topology=results['topology'])
            if swarm_result:
                results['initialized'] = True
                results['swarm_id'] = swarm_result.get('swarm_id', session_id[:12])

                cf.memory_store(
                    f"swarm_{session_id[:8]}",
                    {
                        "session_id": session_id,
                        "topology": results['topology'],
                        "complexity_score": complexity.get('complexity_score', 0),
                        "initialized_at": datetime.now().isoformat()
                    },
                    namespace="swarm_sessions",
                    confidence=0.7
                )
        except Exception:
            pass  # Graceful degradation

    # 3. NEW: Load neural patterns for session
    try:
        from utils.neural_client import get_neural_client
        neural = get_neural_client(timeout=5.0)

        # Get neural status
        status = neural.neural_status()
        if status:
            results['neural_loaded'] = True
    except Exception:
        pass  # Graceful degradation

    return results


def load_workflow_context(session_id: str) -> str:
    """
    Load workflow context from workflow client.
    Returns context string or empty string.
    """
    try:
        from utils.workflow_client import get_workflow_client
        client = get_workflow_client(timeout=5.0)

        # Get recent workflows
        workflows = client.workflow_list(limit=3)
        if workflows:
            lines = ["--- Recent Workflows ---"]
            for w in workflows[:2]:
                name = w.get('name', 'Unnamed')
                status = w.get('status', 'unknown')
                lines.append(f"- {name} ({status})")
            return "\n".join(lines)
    except Exception:
        pass
    return ""


def load_analytics_context() -> str:
    """
    Load recent performance metrics from analytics client.
    Returns context string or empty string.
    """
    try:
        from utils.analytics_client import get_analytics_client
        client = get_analytics_client(timeout=5.0)

        # Get health check
        health = client.health_check()
        if health and health.get('status') == 'healthy':
            return "✓ Analytics system healthy"
    except Exception:
        pass
    return ""


def get_initial_prompt(input_data: dict) -> str:
    """Extract initial prompt from session data if available."""
    # Check various locations for initial prompt
    prompt = ""

    # Check conversation history
    conversation = input_data.get('conversation', [])
    if conversation:
        for msg in conversation:
            if msg.get('role') == 'user':
                content = msg.get('content', '')
                if isinstance(content, str):
                    prompt = content
                elif isinstance(content, list):
                    prompt = ' '.join(c.get('text', '') for c in content if isinstance(c, dict))
                break

    # Check direct prompt field
    if not prompt:
        prompt = input_data.get('prompt', '') or input_data.get('initial_prompt', '')

    return prompt


def load_reasoning_context() -> str:
    """Load patterns and strategies from Claude-Mem, PatternLearner, and ReasoningBank."""
    context_parts = []

    # Try to load from Claude-Mem (port 37777)
    try:
        from utils.claude_mem import load_recent_context
        context_str = load_recent_context()
        if context_str:
            context_parts.append(context_str)
    except Exception:
        pass  # Graceful degradation

    # Try to load from PatternLearner
    try:
        from utils.pattern_learner import PatternLearner
        learner = PatternLearner()
        strategies = learner.get_recommended_strategies(limit=3)
        if strategies:
            context_parts.append("--- Recommended Strategies ---")
            for s in strategies:
                desc = s.get('description', s.get('pattern_key', 'Unknown'))
                rate = s.get('success_rate', 0)
                context_parts.append(f"- {desc} ({rate:.0%} success)")
    except Exception:
        pass  # Graceful degradation

    # Try to load from Claude Flow ReasoningBank with status reporting
    try:
        from utils.claude_flow import ClaudeFlowClient
        cf = ClaudeFlowClient(timeout=10.0)

        # Check if ReasoningBank is available
        if cf.is_reasoningbank_available():
            rb_context = cf.memory_query("session patterns", namespace="sessions", limit=3)
            if rb_context:
                context_parts.append("--- ReasoningBank Patterns ---")
                context_parts.append(rb_context[:500])
            else:
                context_parts.append("✓ ReasoningBank initialized (no patterns yet)")

            # Also try to get stats
            stats = cf.memory_stats()
            if stats and isinstance(stats, dict):
                total = stats.get('total_memories', stats.get('raw', 'unknown'))
                context_parts.append(f"  Memory entries: {total}")
        else:
            context_parts.append("⚠ ReasoningBank not available (run: npx claude-flow@alpha memory stats)")
    except Exception as e:
        context_parts.append(f"⚠ ReasoningBank error: {str(e)[:50]}")

    return "\n".join(context_parts) if context_parts else ""


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--load-context', action='store_true',
                          help='Load development context at session start')
        parser.add_argument('--announce', action='store_true',
                          help='Announce session start via TTS')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())
        
        # Extract fields
        session_id = input_data.get('session_id', 'unknown')
        source = input_data.get('source', 'unknown')  # "startup", "resume", or "clear"

        # Reset verification record — prevent stale cross-session evidence
        reset_verification_record(session_id)

        # Generate unique agent identity for this session (scopes DeepSeek state)
        agent_id = _generate_agent_identity(session_id)

        # Register this session in active_sessions.json for shell script lookups
        _register_active_session(session_id, os.getcwd())

        # Log the session start event
        log_session_start(input_data)

        # Assess task complexity and auto-init swarm if beneficial
        initial_prompt = get_initial_prompt(input_data)
        swarm_context = ""
        if initial_prompt and len(initial_prompt) > 50:
            complexity = assess_task_complexity(initial_prompt)
            if complexity.get('recommend_swarm', False):
                swarm_result = auto_init_swarm(complexity, session_id)
                if swarm_result.get('initialized', False):
                    swarm_context = f"""
--- Swarm Mode Activated ---
Topology: {swarm_result.get('topology', 'adaptive')}
Complexity Score: {complexity.get('complexity_score', 0)}
Swarm ID: {swarm_result.get('swarm_id', 'N/A')}
Multi-agent coordination enabled for this session.
"""

        # Load development context if requested
        if args.load_context:
            context = load_development_context(source, agent_id=agent_id)
            # Add swarm context if initialized
            if swarm_context:
                context = swarm_context + "\n" + context
            # Add reasoning context (patterns, strategies)
            reasoning_ctx = load_reasoning_context()
            if reasoning_ctx:
                context = context + "\n\n" + reasoning_ctx if context else reasoning_ctx
            # NEW: Add workflow context
            workflow_ctx = load_workflow_context(session_id)
            if workflow_ctx:
                context = context + "\n\n" + workflow_ctx if context else workflow_ctx
            # NEW: Add analytics context
            analytics_ctx = load_analytics_context()
            if analytics_ctx:
                context = context + "\n\n" + analytics_ctx if context else analytics_ctx
            if context:
                # Using JSON output to add context
                output = {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": context
                    }
                }
                print(json.dumps(output))
                sys.exit(0)
        
        # Announce session start if requested
        if args.announce:
            try:
                # Try to use TTS to announce session start
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
                pass
        
        # Success
        sys.exit(0)
        
    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == '__main__':
    main()