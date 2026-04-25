---
title: Port claude-code patterns to Deepseek_Agent_MCP
status: completed
created: 2026-04-02
project: /Users/jeremyparker/.claude/Deepseek_Agent_MCP
---

## Vision

Apply four production-proven patterns from the Claude Code TypeScript codebase
(`~/.claude/claude-code/`) to the Python DeepSeek Agent MCP server — improving
type safety, test reliability, error handling, and listing determinism.

## Requirements

1. **Typed IDs** — `NewType` wrappers (`AgentId`, `TaskId`, `SessionId`) with
   `make_*` factory and `parse_*` validation helpers.
2. **Error utilities** — Centralised `to_error()`, `error_message()`,
   `is_abort_error()`, `short_error_stack()` plus `AgentAbortError` and
   `BudgetExceededError` structured subclasses.
3. **`_reset_for_testing()` helpers** — Per-module reset functions on
   `AgentManager`, `MetricsCollector`, and `IssueTracker` for test isolation.
4. **Deterministic `list_dir`** — Explicit alphabetical sort in `file_ops.py`
   instead of undefined `iterdir()` order.

## Acceptance Criteria

- [x] `src/deepseek_agent_mcp/types.py` exists with `AgentId`, `TaskId`,
      `SessionId`, `make_*`, and `parse_*` helpers.
- [x] `parse_agent_id(valid_uuid)` → branded string; `parse_agent_id("bad")` → `None`.
- [x] `src/deepseek_agent_mcp/errors.py` exists with all utility functions and
      `AgentAbortError`, `BudgetExceededError`.
- [x] `is_abort_error(asyncio.CancelledError())` → `True`;
      `is_abort_error(ValueError())` → `False`.
- [x] `_reset_agent_manager_for_testing`, `_reset_metrics_for_testing`,
      `_reset_issue_tracker_for_testing` exported and documented.
- [x] `file_ops.py` `list_dir` entries sorted alphabetically by name.
- [x] 914 tests pass, 1 skipped, zero regressions.
- [x] `ruff check src/` zero errors.

## Technical Decisions

- NewType is identity at runtime — zero overhead, no wire-format changes.
- Spec location: also committed at
  `Deepseek_Agent_MCP/specs/claude-code-patterns-port.md` (project-local copy).

## Delegation Record

Delegation was attempted via `mcp__deepseek-agent__run` with
`working_dir="/Users/jeremyparker/.claude/Deepseek_Agent_MCP"`.

The `pre_tool_use` hook **blocked the call**:

```
BLOCKED: working_dir '/Users/jeremyparker/.claude/Deepseek_Agent_MCP'
is outside the allowed workspace.
Allowed: subdirectories of /Users/jeremyparker/Desktop/Claude Coding Projects
Tip: set DEEPSEEK_PROJECTS_ROOT env var to change the allowed root.
```

Per CLAUDE.md fallback protocol: "If DeepSeek MCP tools are unavailable
(connection error, timeout, tool not found), implement directly."
The hook enforces that Deepseek_Agent_MCP is outside the permitted workspace,
making DeepSeek effectively unavailable for this task. Implemented directly
with `state "DeepSeek unavailable — implementing directly per fallback
protocol"` documented in the session.

## Test Evidence

Project uses `uv` for dependency management.
Command: `uv run pytest tests/ -q`

Output (run 2026-04-02):
```
914 passed, 1 skipped, 2 warnings in 31.83s
```

`python -m pytest` without activating the uv venv will fail with
"No module named pytest" — this is expected behaviour; the correct
invocation is `uv run pytest`.

## Progress

- [x] Plan approved by user via plan mode (2026-04-01)
- [x] Spec created (2026-04-02)
- [x] Implementation committed: `4920de0` in Deepseek_Agent_MCP
- [x] 914 passed, 1 skipped
