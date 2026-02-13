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

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Add hooks directory to path for utils imports
sys.path.insert(0, str(Path(__file__).parent))


def track_agent_coordination(session_id, input_data):
    """
    Track subagent coordination patterns for multi-agent learning.
    All operations are non-blocking with graceful fallback.
    Enhanced with MCP tool integrations for DAA, neural, and swarm coordination.
    """
    agent_type = input_data.get("agent_type", "unknown")
    parent_session = input_data.get("parent_session_id", "")
    task_summary = input_data.get("task_summary", "")

    # 1. ReasoningBank: Store agent coordination pattern
    try:
        from utils.claude_flow import ClaudeFlowClient
        cf = ClaudeFlowClient(timeout=2.0)
        cf.memory_store(
            f"agent_{agent_type}_{session_id[:8]}",
            {
                "agent_type": agent_type,
                "parent_session": parent_session,
                "task_preview": task_summary[:200] if task_summary else "",
                "completion_time": datetime.now().isoformat(),
                "success": True
            },
            namespace="agent_coordination",
            confidence=0.7
        )
    except Exception:
        pass  # Graceful degradation

    # 2. Claude-Mem: Store observation for full-text search
    try:
        from utils.claude_mem import ClaudeMemClient
        mem = ClaudeMemClient(timeout=2.0)
        mem.store_observation(
            session_id=parent_session or session_id,
            tool_name="_subagent_complete",
            tool_input={"agent_type": agent_type, "session_id": session_id},
            tool_response=task_summary[:1000] if task_summary else ""
        )
    except Exception:
        pass  # Graceful degradation

    # 3. NEW: DAA Knowledge Sharing - Share learnings with other agents
    try:
        from utils.swarm_client import get_swarm_client
        swarm = get_swarm_client(timeout=5.0)

        # Share knowledge from completed subagent to swarm
        swarm.daa_knowledge_share(
            source_agent_id=f"subagent_{session_id[:8]}",
            target_agent_ids=["swarm_coordinator", "parent_agent"],
            knowledge_domain=agent_type,
            knowledge_content={
                "task_outcome": "success",
                "task_summary": task_summary[:500] if task_summary else "",
                "agent_type": agent_type,
                "completion_time": datetime.now().isoformat()
            }
        )
    except Exception:
        pass  # Graceful degradation

    # 4. NEW: Neural Pattern Learning - Train from successful subagent completion
    try:
        from utils.neural_client import get_neural_client
        neural = get_neural_client(timeout=3.0)

        # Learn coordination pattern from this agent type
        neural.analyze_patterns(
            action='learn',
            operation=f'subagent:{agent_type}',
            outcome='success',
            metadata={
                'session': session_id[:8],
                'parent': parent_session[:8] if parent_session else '',
                'task_length': len(task_summary) if task_summary else 0,
                'confidence': 0.7
            }
        )
    except Exception:
        pass  # Graceful degradation

    # 5. NEW: Swarm Coordination Update - Update swarm state
    try:
        from utils.swarm_client import get_swarm_client
        swarm = get_swarm_client(timeout=3.0)

        # Check if swarm is active and update coordination
        status = swarm.swarm_status(verbose=False)
        if status and status.get('status') == 'active':
            # Sync coordination state
            swarm.coordination_sync()

            # Store subagent completion in memory
            from utils.mcp_client import get_mcp_client
            mcp = get_mcp_client(timeout=3.0)
            mcp.memory_store(
                key=f'subagent/{session_id[:8]}/complete',
                value=json.dumps({
                    'agent_type': agent_type,
                    'parent_session': parent_session,
                    'completed_at': datetime.now().isoformat(),
                    'success': True
                }),
                namespace='swarm_coordination',
                ttl=3600  # 1 hour TTL
            )
    except Exception:
        pass  # Graceful degradation

    # 6. NEW: Analytics Tracking - Record subagent metrics
    try:
        from utils.analytics_client import get_analytics_client
        analytics = get_analytics_client(timeout=3.0)

        # Collect metrics for this subagent completion
        analytics.metrics_collect(components=['subagent', agent_type])
    except Exception:
        pass  # Graceful degradation


def get_tts_script_path():
    """
    Determine which TTS script to use based on available API keys.
    Priority order: ElevenLabs > OpenAI > pyttsx3
    """
    # Get current script directory and construct utils/tts path
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"
    
    # Check for ElevenLabs API key (highest priority)
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)
    
    # Check for OpenAI API key (second priority)
    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)
    
    # Fall back to pyttsx3 (no API key required)
    pyttsx3_script = tts_dir / "pyttsx3_tts.py"
    if pyttsx3_script.exists():
        return str(pyttsx3_script)
    
    return None


def announce_subagent_completion():
    """Announce subagent completion using the best available TTS service."""
    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return  # No TTS scripts available
        
        # Use fixed message for subagent completion
        completion_message = "Subagent Complete"
        
        # Call the TTS script with the completion message
        subprocess.run([
            "uv", "run", tts_script, completion_message
        ], 
        capture_output=True,  # Suppress output
        timeout=10  # 10-second timeout
        )
        
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Fail silently if TTS encounters issues
        pass
    except Exception:
        # Fail silently for any other errors
        pass


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        parser.add_argument('--notify', action='store_true', help='Enable TTS completion announcement')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract required fields
        session_id = input_data.get("session_id", "")
        _stop_hook_active = input_data.get("stop_hook_active", False)  # Reserved

        # Track agent coordination to ReasoningBank and Claude-Mem
        if session_id:
            track_agent_coordination(session_id, input_data)

        # Ensure log directory exists
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, "subagent_stop.json")

        # Read existing log data or initialize empty list
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []
        
        # Append new data
        log_data.append(input_data)
        
        # Write back to file with formatting
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        # Handle --chat switch (same as stop.py)
        if args.chat and 'transcript_path' in input_data:
            transcript_path = input_data['transcript_path']
            if os.path.exists(transcript_path):
                # Read .jsonl file and convert to JSON array
                chat_data = []
                try:
                    with open(transcript_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # Skip invalid lines
                    
                    # Write to logs/chat.json
                    chat_file = os.path.join(log_dir, 'chat.json')
                    with open(chat_file, 'w') as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass  # Fail silently

        # Announce subagent completion via TTS (only if --notify flag is set)
        if args.notify:
            announce_subagent_completion()

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()