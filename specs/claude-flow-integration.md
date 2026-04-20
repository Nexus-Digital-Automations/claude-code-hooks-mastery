---
title: Claude Flow Integration — Active Memory & Richer Status
status: planning
created: 2026-04-14
---

## Vision

Claude Flow currently runs passively — collecting system metrics and storing lessons at session end. The agent never queries past experience during active work. This plan makes Flow a live participant: recalling relevant lessons at session start, and surfacing meaningful data (not just CPU/RAM) in the status line.

## Requirements

### Phase 1: Session-Start Recall (hook)
Add a `session_start` hook that queries ReasoningBank for lessons relevant to the current project directory. Inject a summary into the session context so the agent starts with institutional memory.

- Query ReasoningBank `lessons` namespace filtered by current working directory
- Retrieve top 3-5 lessons by confidence score (>= 0.7)
- Write a brief summary to a scratch file the agent can read
- Target file: `hooks/session_start_recall.py`
- Uses existing `claude_flow.py` client's `memory_query()` method

### Phase 2: Richer Flow Status Line
Replace the system-metrics-only Flow row with data that reflects actual agent activity:

- **ReasoningBank stats**: entry count, last lesson timestamp
- **Session lessons**: count of lessons stored this session
- **Drop CPU/memory**: these are system metrics, not Flow metrics — misleading in a "Flow" row

New Flow row format:
```
Flow     active hierarchical · 5 agents  brain 142 lessons (last 2h ago)  tasks 3/4
```

- Target file: `statusline-command.sh` lines 302+
- Data source: `memory_stats()` via `claude_flow.py` or direct sqlite3 query on `.swarm/memory.db`

### Phase 3: Pre-Plan Memory Query (optional, future)
Before writing a plan for any task, query ReasoningBank for:
- Similar past tasks (by semantic similarity)
- Relevant architectural decisions
- Known pitfalls in the affected area

This is more invasive (requires hook or agent behavior change) and should be evaluated after Phase 1 proves value.

## Acceptance Criteria

- [ ] Session start hook queries ReasoningBank and writes <= 500 char summary to `output/session-recall.txt`
- [ ] Hook completes in < 3 seconds (timeout fallback to skip)
- [ ] Status line Flow row shows lesson count and recency instead of system memory
- [ ] CPU bar removed from Flow row (it's not Flow-specific data)
- [ ] No regression in status line render time (< 500ms)
- [ ] Works gracefully when ReasoningBank is empty or `.swarm/memory.db` doesn't exist

## Technical Decisions

**Why sqlite3 direct query for status line?** The status line is a bash script. Calling `npx claude-flow@alpha` adds ~2s startup overhead. A direct `sqlite3 .swarm/memory.db "SELECT count(*) FROM ..."` completes in < 50ms.

**Why not query Flow during active work?** Adding MCP calls mid-conversation adds latency and context noise. Session-start recall (Phase 1) and pre-plan query (Phase 3) are the right insertion points — bounded, predictable, and non-intrusive.

**Why drop CPU/memory from Flow row?** They're system metrics, not Flow metrics. They belong in a "System" row if anywhere. The Flow row should reflect Flow's value: knowledge, agents, and tasks.

## Implementation Steps

### Phase 1: Session-Start Recall
1. Create `hooks/session_start_recall.py`
   - Import existing `hooks/utils/claude_flow.py` ClaudeFlowClient
   - Query `memory_query("lessons relevant to {cwd}", namespace="lessons", limit=5)`
   - Filter results with confidence >= 0.7
   - Write formatted summary to `output/session-recall.txt`
   - 3-second timeout, graceful skip on any failure
2. Register hook in `settings.json` under session start hooks
3. Verify: start a new session, check `output/session-recall.txt` is populated

### Phase 2: Richer Flow Status Line
1. In `statusline-command.sh`, replace the system-metrics block (current lines ~317-335) with:
   - sqlite3 query on `.swarm/memory.db` for lesson count + most recent timestamp
   - Format: `brain N lessons (last Xh ago)` or `brain empty`
   - Keep task success ratio (already useful)
   - Remove CPU bar and memory display
2. Verify: run the statusline test command, confirm new format renders correctly

## Risks

- **ReasoningBank empty**: First sessions won't have lessons. Handle gracefully — show "brain empty" or skip.
- **sqlite3 not available**: Extremely unlikely on macOS. Fallback: skip the brain section.
- **Stale lessons**: Old lessons may be wrong. Confidence scoring + `memory_consolidate()` (already runs at session end) mitigates this.
- **Status line latency**: sqlite3 query adds ~50ms. Acceptable within the 500ms budget.

## Progress

- [ ] Phase 1: Session-start recall hook
- [ ] Phase 2: Richer Flow status line
- [ ] Phase 3: Pre-plan memory query (future, pending Phase 1 results)
