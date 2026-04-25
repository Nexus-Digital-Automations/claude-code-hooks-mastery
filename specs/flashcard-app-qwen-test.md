---
title: Flashcard App — Qwen Coder Agent Live Test
status: active
created: 2026-04-19
---

## Vision
Use the Qwen coder agent (via `mcp__qwen-agent__run`) to build a small, self-contained flashcard web app from scratch. This serves a dual purpose: (1) deliver a working flashcard app, (2) act as a live integration test of the Qwen agent system so we can identify and fix issues in profiles, prompts, MCP behavior, or the delegation protocol.

## Target Directory
`/Users/jeremyparker/Desktop/Claude Coding Projects/flashcard-app-qwen-test/`

The existing `flashcard-app/` directory is an active, 30+ commit project and must not be touched.

## Requirements

### Flashcard app (what Qwen must build)
- Vite + React (JS, not TS) single-page app — match existing house stack.
- Features:
  1. Create/edit/delete **decks** (name + optional description).
  2. Create/edit/delete **cards** in a deck (front + back text).
  3. **Study mode**: flip cards, mark "Got it" / "Review again".
  4. **Persistence**: browser `localStorage` keyed by deck id. No backend.
  5. **Import/export** decks as JSON.
- Minimal but styled (plain CSS or Tailwind — Qwen's call).
- `npm run build` and `npm run lint` must pass cleanly.

### Qwen agent test (what we observe)
- Which profile the agent auto-selects, and whether it was appropriate.
- Plan quality: does the plan list real files, sensible structure, identify risks?
- Tool-use patterns: extraneous reads, repeated file writes, unnecessary edits.
- Budget adherence: iteration count vs. profile cap; did it hit `limit_reached`?
- Output quality: lint/build pass rate out of the box; missing edge cases.
- MCP ergonomics: did plan enforcement (`review get` before `approve`) work?
- Documentation gaps: any point where I (as Claude) had to guess the API.

## Acceptance Criteria

### App
- [x] `flashcard-app-qwen-test/` exists with a working Vite + React scaffold.
- [x] App supports creating a deck, adding cards, studying (flip + grade), and data persists across reload.
- [x] Import/export a deck as JSON round-trips correctly.
- [x] `npm install && npm run build` succeeds — output captured.
- [x] `npm run lint` returns 0 errors — output captured.
- [ ] `npm run dev` serves the app on localhost and the create-deck → add-card → study flow works end-to-end (Playwright MCP smoke test OR manual fetch + DOM check).

### Qwen agent system evaluation
- [x] A findings document at `docs/reports/qwen-agent-live-test-2026-04-19.md` lists: profile selected + rationale, plan summary, iteration count, budget used, any `limit_reached`/errors, ≥3 concrete issues or wins observed.
- [x] Each issue has a severity (blocker/major/minor) and a proposed fix (config patch, prompt edit, doc update, or MCP server change).
- [ ] At least one concrete improvement is applied to the Qwen agent system (profile, docs, or delegation-protocol.md) with a diff captured.

## Technical Decisions
- Fresh dir, so no interference with the real flashcard-app.
- Stack chosen to mirror the existing app (Vite + React) so findings transfer.
- Spaced repetition deliberately out of scope — keep build small enough to finish in one Qwen run and stay inside the `qwen3-delegation` 200-iter / $3.00 budget.

## Progress
- [x] Spec written
- [ ] Project dir created
- [ ] Qwen setup() called, profile recorded
- [ ] Qwen run() dispatched
- [ ] Plan reviewed + approved
- [ ] Polled to completion
- [ ] Build + lint + smoke verified
- [ ] Findings doc written
- [ ] Qwen system fix applied
