---
title: Standalone Protocol Reviewer Package
status: planning
created: 2026-04-26
---

## Vision

Extract the shared reviewer logic from `~/.claude/hooks/utils/reviewer*.py` and
`Dev_Agent_MCP/src/qwen_agent_mcp/reviewer.py` into a pip-installable Python package
at `/Users/jeremyparker/Desktop/Claude Coding Projects/claude-reviewer`.

Both existing systems keep their current invocation patterns (Claude Code: subprocess;
Dev_Agent_MCP: async method call) but replace their internal reviewer implementations
with thin adapters that delegate to the shared package.

---

## Requirements

### R1 — Package structure

```
claude-reviewer/
├── pyproject.toml                  # uv-managed, src layout
├── src/
│   └── claude_reviewer/
│       ├── __init__.py             # Public surface: ReviewPacket, ReviewerConfig, run_review, run_reviewer_rounds
│       ├── packet.py               # ReviewPacket dataclass (Claude Code's richer schema — canonical)
│       ├── config.py               # ReviewerConfig (merged from both systems)
│       ├── runner.py               # run_review() + run_reviewer_rounds() + approval cache + JSONL log
│       ├── llm.py                  # OpenAI SDK call (temp=0.2, json_object mode, timeout, retry)
│       ├── sandbox.py              # Subprocess sandbox check execution
│       ├── cli.py                  # `reviewer run <session_id> [--last-message ...]` CLI
│       └── prompts/
│           ├── base.md             # Core 18-category system prompt (canonical)
│           ├── claude_code.md      # Claude Code additions (session scope, VR, Qwen delegation)
│           └── qwen_agent.md       # Dev_Agent_MCP additions (profile, tool-policy, plan compliance)
└── tests/
    ├── test_packet.py
    ├── test_runner.py
    └── test_cli.py
```

### R2 — ReviewPacket schema (canonical — Claude Code's richer fields)

Use Claude Code's full ReviewPacket as the canonical schema. All fields optional with
sensible defaults so Dev_Agent_MCP can populate only what it has.

Fields:
- Identity: `session_id`, `task_id`, `prompt_id`, `agent_id`, `task_started_at`
- User intent: `user_requests: list[dict]`
- Pre-impl approval: `spec_status: list[dict]`, `plan_content: str`
- Verification: `sandbox_results: dict[str, dict]`, `verification_artifacts: dict[str, str]`
- Project config: `project_config: dict` (has_frontend, has_tests, has_build, project_type)
- Git state: `git_status`, `git_diff`, `git_diff_content`, `git_log`, `git_show_stat`, `git_show_content`
- Hygiene: `root_clean: bool`, `root_violations: list[str]`
- Agent output: `last_assistant_message: str`, `agent_commentary_summary: str`
- Round metadata: `timestamp: str`, `round_count: int`
- Advisory: `oversized_files: list[tuple[str, int]]`

### R3 — ReviewerConfig (merged from both systems)

```python
@dataclass
class ReviewerConfig:
    model: str = "gpt-5-mini"
    provider: str = "openai"          # from Dev_Agent_MCP
    temperature: float = 0.2
    max_tokens: int = 2000
    max_rounds: int = 5               # Claude Code default; Dev_Agent_MCP was 3
    timeout_per_round: int = 30
    sandbox_timeout: int = 120
    sandbox_timeout_frontend: int = 300
    sandbox_checks: dict[str, str] = field(default_factory=dict)  # from Dev_Agent_MCP
    cache_approvals: bool = True
    skip_categories: list[str] = []
    system_prompt_override: str | None = None  # path to custom system prompt
    system_prompt_extension: str | None = None  # path to per-system addition
    enabled: bool = True
```

### R4 — System prompt strategy

- `prompts/base.md` — canonical 18-category system prompt (migrated from
  `~/.claude/docs/protocol-compliance-reference.md` reviewer sections)
- `prompts/claude_code.md` — appended for Claude Code sessions (session scope rules,
  VR state nuances, Qwen delegation context)
- `prompts/qwen_agent.md` — appended for Dev_Agent_MCP sessions (profile/tool-policy
  awareness, plan approval workflow, autonomous remediation context)
- At runtime: `system_prompt = base.md + (extension if provided)`

### R5 — CLI for subprocess callers

```
reviewer run <session_id> [--last-message <msg>] [--config <path>] [--extension <prompt_path>]
```

- Reads ReviewPacket from stdin as JSON, OR builds it from session artifacts when called
  with just `session_id` (Claude Code compatibility mode)
- Outputs verdict JSON to stdout
- Exit codes: 0=APPROVED, 1=FINDINGS (blocking), 2=ERROR

### R6 — Claude Code integration (adapter)

`~/.claude/hooks/utils/reviewer.py` and `reviewer_core.py` become thin shims:
- `reviewer.py`: build_review_packet() stays (it knows Claude Code's data layout),
  then calls `claude_reviewer.run_review(packet, config)` for LLM round management
- `reviewer_core.py`: can be removed or kept as a re-export shim for backward compat
- `stop.py` subprocess call to `reviewer.py` stays unchanged — no changes to stop.py

### R7 — Dev_Agent_MCP integration (adapter)

`Dev_Agent_MCP/src/qwen_agent_mcp/reviewer.py`:
- `build_packet()` stays (knows Dev_Agent_MCP's data layout, populates what it can)
- Replace `run_reviewer_rounds()` and `run_review()` internals with calls to
  `claude_reviewer.run_reviewer_rounds(packet, config, on_blocking_findings=callback)`
- `on_blocking_findings` callback injects findings as user message (existing behavior)

### R8 — Approval cache (unified, namespaced)

Cache path: `~/.claude-reviewer/cache/{caller_id}_{task_id}.json`
- `caller_id` set by each adapter: `"claude_code"` or `"qwen_agent"`
- Prevents cross-system cache collision
- Same task_id scoping logic as current Claude Code implementation

### R9 — Observability log (unified)

Log path: `~/.claude-reviewer/logs/reviewer.jsonl`
One JSON line per review round:
```json
{"ts": "...", "caller": "claude_code|qwen_agent", "session_id": "...", "task_id": "...",
 "round": 1, "verdict": "APPROVED|FINDINGS|ERROR", "blocking_count": 0,
 "advisory_count": 2, "latency_s": 4.2, "model": "gpt-5-mini"}
```

---

## Acceptance Criteria

- [ ] `cd claude-reviewer && uv pip install -e .` succeeds
- [ ] `reviewer run --help` works; `echo '{"session_id":"test"}' | reviewer run test` returns `{"verdict":"ERROR",...}` (no API key) with exit code 2
- [ ] Claude Code: stop.py's subprocess call to reviewer.py produces identical verdict JSON and exit codes as before the migration
- [ ] Dev_Agent_MCP: `run_reviewer_rounds(runner)` produces APPROVED/FINDINGS verdicts identical to pre-migration for same inputs
- [ ] `base.md` contains all 18 category definitions
- [ ] `claude_code.md` contains session scope, VR, and Qwen delegation additions
- [ ] `qwen_agent.md` contains plan compliance and autonomous remediation additions
- [ ] ReviewPacket dataclass has all fields from both systems; Dev_Agent_MCP adapter populates 12 fields, remaining default to empty
- [ ] Approval cache namespaced by caller_id — Claude Code and Dev_Agent_MCP cannot share approvals
- [ ] `~/.claude-reviewer/logs/reviewer.jsonl` receives one line per review with caller field
- [ ] `ruff check src/` passes with zero errors
- [ ] `mypy src/` passes with zero errors (strict mode)
- [ ] Unit tests pass: `uv run pytest tests/`

---

## Technical Decisions

**Why Claude Code's packet schema as canonical**: It has richer context (specs, plan,
user_requests, project_config) that produces better verdicts. Dev_Agent_MCP gains these
fields over time as it expands; unused fields simply default to empty and the reviewer
ignores them.

**Why subprocess for Claude Code stays**: stop.py runs under bare python3 without the
OpenAI SDK available. Changing the invocation model would require modifying stop.py
(high blast radius). The subprocess pattern already works.

**Why direct import for Dev_Agent_MCP**: It already uses async/await; subprocess would
add latency and complexity. Direct import is cleaner for an async system.

**Why `~/.claude-reviewer/` for cache/logs**: Neutral path not owned by either system.
Both adapters write here. Avoids the `~/.claude/data/` vs `~/.qwen-agent/` split.

---

## Out of Scope

- Web UI or dashboard
- Streaming verdict output
- Changing Claude Code's stop.py invocation pattern
- Changing Dev_Agent_MCP's agent_runner.py async call pattern
- Migrating the packet-building logic (each system keeps its own builder)

---

## Progress

Implementation order:
1. Create repo + pyproject.toml + package skeleton
2. Migrate ReviewPacket (canonical schema)
3. Migrate ReviewerConfig (merged)
4. Migrate base.md (system prompt)
5. Migrate LLM client (llm.py)
6. Migrate round management (runner.py)
7. Implement CLI (cli.py)
8. Write claude_code.md and qwen_agent.md prompt extensions
9. Write Claude Code adapter (thin reviewer.py shim)
10. Write Dev_Agent_MCP adapter (thin reviewer.py shim)
11. Tests
12. Verify both integrations end-to-end
