---
title: AI-Agent Codebase Legibility Enforcement
status: active
created: 2026-04-04
---

## Vision

Make codebases navigable by future AI agents with no prior session history. Enforce documentation
patterns that serve agents differently than humans: dense cross-references, explicit boundary
declarations, failure mode documentation, state machine diagrams, and ubiquitous language
consistency.

## Requirements

1. All 10 legibility patterns surfaced in discussion are covered by at least one enforcement mechanism
2. Hook injection fires at code-generation time (pre_tool_use) and task-start time (user_prompt_submit)
3. Reviewer category 16 covers diff-verifiable legibility signals — advisory-only, never blocks
4. No new dependencies

## Acceptance Criteria

- [x] `pre_tool_use.py` `_CODING_STANDARDS` has a DOCUMENTATION section covering: module boundary docstrings, failure mode docs, state machine diagrams, inline decision records, cross-references, extension point / stability annotations, behavioral test names
- [x] `user_prompt_submit.py` `_EXECUTION_RULES` includes UBIQUITOUS LANGUAGE rule (one concept = one name, check existing codebase before naming)
- [x] `protocol-compliance-reference.md` has category 16 covering: missing module docstrings, missing failure mode docs, missing state machine docs, missing cross-references, missing stability signals, non-behavioral test names, ubiquitous language violations, missing inline decision records
- [x] Category 16 is advisory-only (nuance 19 added)
- [x] `ruff check hooks/` exit 0
- [x] Smoke test: pre_tool_use Edit emits DOCUMENTATION section in additionalContext
- [x] Smoke test: user_prompt_submit emits UBIQUITOUS LANGUAGE in additionalContext

## Technical Decisions

- DOCUMENTATION section appended to existing `_CODING_STANDARDS` constant — fires on same Write/Edit/MultiEdit events, no new hook needed
- UBIQUITOUS LANGUAGE appended to `_EXECUTION_RULES` — fires at task-start for all substantial prompts
- Category 16 is fully advisory (nuance 19) — legibility debt should accumulate as advisory notes, never block

## Progress

Implementation complete at commit after 68ef427.
