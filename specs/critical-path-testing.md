---
title: Critical Path Testing Policy
status: active
created: 2026-04-13
---
## Vision
Make the stop hook and reviewer smart about what to test. Unit/integration tests are only required when changes touch critical business domains (payments, auth, billing, data integrity). Non-critical changes (cleanup, config, docs, refactoring non-critical code) auto-pass test checks. Playwright E2E tests always run comprehensively when frontend changes are detected (no diff-size shortcut).

## Requirements
1. A `critical-paths.json` config file defines critical domains and their file patterns
2. Phase 4 (TESTS) in stop.py uses the config to decide if tests are required
3. Phase 6 (FRONTEND) removes the <10-line diff skip — Playwright always runs comprehensively
4. The `should_require_tests()` function in project_config.py checks critical path patterns
5. The reviewer (protocol-compliance-reference.md) is told about this policy so it doesn't flag missing tests for non-critical changes
6. The config is general-purpose (not project-specific) and lives in ~/.claude/data/

## Acceptance Criteria
- [x] `~/.claude/data/critical-paths.json` exists with critical domains and file patterns
- [x] `should_require_tests()` returns False when no modified files match critical patterns
- [x] `should_require_tests()` returns True when modified files match critical patterns
- [x] Phase 6 (FRONTEND) has no diff-size skip — Playwright always runs when has_frontend
- [x] Reviewer reference updated to document critical-path testing policy
- [x] Non-critical changes (like today's cleanup) would auto-pass Phase 4

## Technical Decisions
- Config at `~/.claude/data/critical-paths.json` — central, not per-project
- Patterns use glob-style matching (fnmatch) against file paths
- Critical domains: payments, auth, billing, data-integrity (extensible)
- Playwright comprehensive = remove diff-size shortcut in Phase 6 only

## Progress
- Implementation complete
