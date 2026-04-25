#!/usr/bin/env python3
"""Background codebase indexer for claude-context MCP.

Owns: connecting to the claude-context MCP server and triggering index_codebase.
Does NOT own: deciding when to run (session_start.py does that), MCP server lifecycle.
Called by: session_start.py via Popen(start_new_session=True) — always runs detached.
Calls: ~/.npm-global/bin/claude-context-mcp via stdio JSON-RPC.

Reads MCP env vars from ~/.claude.json so config stays in one place.
Incremental indexing is handled server-side (Merkle tree diff) — safe to call every session.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

def _mcp_launch() -> tuple[list[str], dict] | None:
    """Read command, args, and env from ~/.claude.json mcpServers.claude-context.

    Single source of truth — stays in sync with what Claude Code uses automatically.
    Returns None if config is missing or the executable does not exist.
    """
    try:
        config = json.loads((Path.home() / '.claude.json').read_text())
        cc = config['mcpServers']['claude-context']
        cmd = [cc['command']] + cc.get('args', [])
        if not Path(cmd[0]).exists():
            return None
        return cmd, cc.get('env', {})
    except Exception:
        return None


def _run(cwd: str) -> None:
    launch = _mcp_launch()
    if not launch:
        return
    cmd, mcp_env = launch
    env = {**os.environ, **mcp_env}
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=cwd,
        bufsize=0,
    )

    responses: queue.Queue = queue.Queue()

    def _reader(stream):
        for raw in stream:
            try:
                responses.put(json.loads(raw))
            except Exception:
                pass
        responses.put(None)  # sentinel — stream closed

    threading.Thread(target=_reader, args=(proc.stdout,), daemon=True).start()

    def send(msg_id: int, method: str, params: dict) -> None:
        line = json.dumps({'jsonrpc': '2.0', 'id': msg_id, 'method': method, 'params': params}) + '\n'
        proc.stdin.write(line.encode())
        proc.stdin.flush()

    def await_response(target_id: int, timeout: float) -> dict | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                resp = responses.get(timeout=remaining)
                if resp is None:
                    return None  # stream closed
                if resp.get('id') == target_id:
                    return resp
            except queue.Empty:
                return None
        return None

    send(1, 'initialize', {
        'protocolVersion': '2024-11-05',
        'capabilities': {},
        'clientInfo': {'name': 'auto-indexer', 'version': '1.0'},
    })
    if not await_response(1, timeout=10):
        proc.kill()
        return

    # index_codebase is incremental — server skips unchanged files via Merkle diff.
    # Calling on every session start keeps the index current with minimal overhead.
    send(2, 'tools/call', {'name': 'index_codebase', 'arguments': {'path': cwd}})
    await_response(2, timeout=300)  # 5-min ceiling for very large codebases

    proc.stdin.close()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


if __name__ == '__main__':
    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    _run(cwd)
