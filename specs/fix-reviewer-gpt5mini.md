---
title: Fix GPT-5 Mini Reviewer Compatibility — Two-Round Stop System
status: active
created: 2026-04-01
---

## Vision

The stop hook uses a two-round gate: Round 1 (mechanical checks + authorization) and Round 2 (GPT-5 Mini protocol reviewer). The reviewer was broken because gpt-5-mini returns empty content when `response_format` is not set, and the API timeout was too short for its slower response times.

## Requirements

1. The reviewer must call gpt-5-mini (not gpt-4o-mini)
2. gpt-5-mini must return non-empty JSON responses
3. Timeouts must be long enough for gpt-5-mini's latency (~90s per round)
4. The subprocess timeout in stop.py must accommodate the per-round timeout
5. Reviewer errors (non-blocking) must be logged to stderr, not silently swallowed

## Acceptance Criteria

- [x] `reviewer_config.json` model is `"gpt-5-mini"` (not gpt-4o-mini)
- [x] Both OpenAI API calls in `call_reviewer()` include `response_format={"type": "json_object"}`
- [x] `timeout_per_round` in reviewer_config.json is ≥ 90s
- [x] Subprocess timeout in stop.py is ≥ 180s
- [x] `uv run --script hooks/utils/reviewer.py test-session --json` returns valid JSON with findings

## Technical Decisions

- `response_format={"type": "json_object"}` is required for gpt-5-mini to return non-empty content; without it the model returns an empty string
- `uv run --script` subprocess approach used because stop.py runs under bare `python3` without the `openai` package; the subprocess gets its own dependency environment
- Timeout increased from 30s→90s (API) and 120s→180s (subprocess) based on observed gpt-5-mini latency of ~4.4s for small prompts, scaling to ~60-90s for large review packets

## Progress

Completed. Changes committed in 65700ad:
- `data/reviewer_config.json`: model=gpt-5-mini, timeout_per_round=90
- `hooks/utils/reviewer.py`: response_format added to both API calls
- `hooks/stop.py`: subprocess timeout increased to 180s
