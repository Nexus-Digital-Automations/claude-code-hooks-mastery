---
title: AI Coding Standards Enforcement (Hooks + Reviewer)
status: active
created: 2026-04-04
---

## Vision

Enforce the 6-section AI coding agent standard (execution rules, architecture, component/API design,
code generation, robustness, testing) through the Claude Code hooks system and the GPT-5 Mini reviewer.
Human-centric advice is excluded — only machine-enforceable agent execution rules remain.

## Requirements

1. All 6 standard sections are covered by at least one enforcement mechanism (hook injection or reviewer check)
2. Hook injection fires at code-generation time (pre_tool_use Write/Edit/MultiEdit) and at task-start time (user_prompt_submit)
3. Reviewer category 15 checks diff-verifiable signals from all 6 sections
4. No new dependencies; stays within existing hook architecture

## Acceptance Criteria

- [x] `pre_tool_use.py` `_CODING_STANDARDS` covers all 6 sections (architecture, functions, naming, comments, errors, null, concurrency, testing)
- [x] `user_prompt_submit.py` injects execution-mode rules (Boy Scout, Design Twice, TDD, tracer-code) at task-start
- [x] Reviewer category 15 expanded to cover: architecture signals, function design, naming, comments, error handling, null, concurrency, AND testing signals (TDD, FIRST, state coverage)
- [x] `ruff check hooks/` exit 0
- [x] Smoke test: `pre_tool_use` Edit call emits all 6 sections in additionalContext
- [x] Smoke test: `user_prompt_submit` emits execution-rule context

## Technical Decisions

- Execution rules (Boy Scout, Design Twice, Iterative Prototyping) go in `user_prompt_submit.py` — they govern how a task is approached, not what code looks like
- Code-generation standards (`_CODING_STANDARDS`) go in `pre_tool_use.py` — fires on every file write/edit
- Reviewer category 15 extended with testing section; remains advisory-heavy (only bool-flag params and obvious concurrency races are blocking)

## Progress

Initial partial implementation (category 15 + 7-line standards) committed at 526943e.
This spec covers the full enforcement pass.
