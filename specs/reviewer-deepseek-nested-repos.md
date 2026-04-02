---
title: Reviewer — DeepSeek + Nested Repo Awareness
status: completed
created: 2026-04-02
---

## Vision

Switch the stop-hook reviewer from GPT-5 Mini (OpenAI) to DeepSeek Chat for cost
reduction, and fix the fundamental blind spot where work committed to nested git
repositories (like `Deepseek_Agent_MCP/`) was completely invisible to the reviewer,
causing repeated blocking that required manual artifact commits as workarounds.

## Requirements

1. Reviewer calls DeepSeek Chat instead of GPT-5 Mini.
2. API key read from `DEEPSEEK_API_KEY` environment variable — never as a subprocess
   argument, never hardcoded.
3. `run_sandbox_checks()` detects nested git repos (direct-child subdirs with `.git`)
   and includes their recent commits, HEAD stat, uncommitted changes, and lint output
   in the review packet.
4. `format_packet_for_prompt()` exposes nested repo activity as a distinct section.
5. Reviewer system prompt explicitly instructs the LLM to accept nested repo activity
   as sufficient evidence for cross-repo work.
6. Reviewer system prompt explicitly allows delegation fallback when MCP security
   scope rejects delegation and a spec documents the rejection.

## Acceptance Criteria

- [x] `call_reviewer()` uses `DEEPSEEK_API_KEY` and `base_url="https://api.deepseek.com/v1"`
- [x] `run_review()` pre-flight check tests `DEEPSEEK_API_KEY` (not OPENAI_API_KEY)
- [x] `stop.py` checks `DEEPSEEK_API_KEY` in env and `.env` file
- [x] `find_nested_git_repos()` function exists and returns nested repo paths
- [x] `ReviewPacket.nested_repo_activity` field added
- [x] `build_review_packet()` populates nested_repo_activity (log, diff_stat, show_stat, lint)
- [x] `format_packet_for_prompt()` renders NESTED REPO ACTIVITY section
- [x] `reviewer_config.json` model is `deepseek-chat`, timeout_per_round=60, max_tokens=4096
- [x] `protocol-compliance-reference.md` updated with rules 18 (nested repos) and 19 (delegation fallback)
- [x] `ruff check hooks/utils/reviewer.py hooks/stop.py` passes
- [x] Nested repo detection smoke test: finds `Deepseek_Agent_MCP`, `claude-mem`, etc.

## Technical Decisions

- DeepSeek uses the same `openai` Python package via `base_url` parameter — no new
  dependencies.
- `find_nested_git_repos()` scans direct children only (depth=1) to avoid recursing
  into deeply nested structures.
- Lint auto-detection: `pyproject.toml` → `ruff check .`, `package.json` → `npm run lint`.
- No test re-runs at stop time for nested repos (adds 30s+ per repo) — lint + recent
  commit history is sufficient for the reviewer to verify the work.

## Progress

Completed 2026-04-02. All acceptance criteria met.
