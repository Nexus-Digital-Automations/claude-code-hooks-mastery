---
title: Fix Reviewer Packet — Include HEAD Commit Diff When Working Tree Is Clean
status: completed
created: 2026-04-02
---

## Vision

The stop-hook reviewer was unable to inspect committed work because it only ran
`git diff HEAD` (working-tree diff), which is empty after all changes are committed.
This made the reviewer block every session where work was cleanly committed —
it would see "(No diff content available)" and could not verify code quality.

## Requirements

1. When the working tree is clean (no uncommitted changes), the reviewer must still
   be able to inspect the most recently committed code.
2. `git show HEAD` must be included in the review packet as a fallback.
3. The `format_packet_for_prompt` section must clearly label which source is used
   (working-tree diff vs HEAD commit diff).
4. No regression: when uncommitted changes ARE present, the working-tree diff takes
   precedence (existing behavior preserved).

## Acceptance Criteria

- [x] `run_sandbox_checks()` runs `git show HEAD --stat` and `git show HEAD`
- [x] `ReviewPacket` has `git_show_stat` and `git_show_content` fields
- [x] `build_review_packet()` populates both fields from sandbox results
- [x] `format_packet_for_prompt()` uses `git_diff_content` if non-empty, otherwise
      falls back to `git_show_content` with a label indicating the source
- [x] `ruff check hooks/` passes with zero errors
- [x] Stop authorization succeeds after the fix is committed

## Technical Decisions

- `git show HEAD` output truncated at 5000 chars (same limit as `git diff HEAD`)
  to avoid bloating the review packet.
- Fallback label "(HEAD commit diff — all changes committed)" added so the reviewer
  can distinguish the two cases and not penalize clean-commit workflows.

## Progress

Completed 2026-04-02. Committed in dfbf663.
- `hooks/utils/reviewer.py`: added two git checks, two ReviewPacket fields,
  populated in build_review_packet, exposed in format_packet_for_prompt with fallback.
