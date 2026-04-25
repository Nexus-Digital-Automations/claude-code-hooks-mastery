# Qwen Coder Agent Live Test — 2026-04-19

**Task:** Build a Vite + React flashcard app with deck/card CRUD, study mode, localStorage persistence, and JSON import/export.  
**Working dir:** `/Users/jeremyparker/Desktop/Claude Coding Projects/flashcard-app-qwen-test/flashcard-app/`  
**Spec:** `specs/flashcard-app-qwen-test.md`

---

## Profile Selected

**Profile:** `qwen3-delegation`  
**Rationale (auto-selected):** 5+ file greenfield feature — matches the delegation routing rule for new features.  
**Budget:** 200 iterations / $3.00 cap  
**Model:** `qwen3-coder-plus`

This was the correct profile choice. The task was clearly a multi-file feature build, not a bug fix or refactor.

---

## Plan Summary

Three agent runs were required to reach a partial result. Each stalled or was hard-stopped for a different reason.

| Run | Agent ID | Outcome |
|-----|----------|---------|
| 1 | first attempt | Stalled in plan phase — greenfield detection capped planning at 2 rounds; agent never produced an approvable plan |
| 2 | second attempt | Wrong Vite scaffold (`--template react-js` → TypeScript vanilla template, no React); agent then created a nested `my-flashcard-app/` subdirectory |
| 3 | `76460d80` | Pre-scaffolded directory provided by Claude; agent wrote 6/7 files before file_ops loop guard hard-stopped it. `App.css` not written. |

**Run 3 plan quality:** Reasonable — identified the 7 required files, correct component decomposition (DeckList, DeckForm, CardEditor, StudyMode, storage util). No unnecessary abstraction. Plan did not flag the file_ops guard as a risk (it couldn't know).

**Iteration count (run 3):** ~15 file-write iterations before guard fired. Well under the 200-iteration budget — the guard, not the budget, was the binding constraint.

---

## Files Written (Run 3)

| File | Status | Quality |
|------|--------|---------|
| `src/App.jsx` | ✅ Written | Good — clean routing, correct hooks usage |
| `src/components/DeckList.jsx` | ✅ Written | Minor bug (see Issue 5) |
| `src/components/DeckForm.jsx` | ✅ Written | Good — validation, crypto.randomUUID() |
| `src/components/CardEditor.jsx` | ✅ Written | Good — inline edit UX, correct IDs |
| `src/components/StudyMode.jsx` | ✅ Written | Good — shuffle, queue, flip animation hooks |
| `src/utils/storage.js` | ✅ Written | Good — all 8 functions, correct localStorage schema |
| `src/App.css` | ❌ Not written | Loop guard fired before agent reached this file |

Build status: **not verified** — CSS missing, build not run.

---

## Issues Observed

### Issue 1 — Greenfield detection kills the plan phase
**Severity:** Blocker  
**Observed:** With `plan_mode: true`, the Qwen server detected the task as "greenfield" and automatically capped `max_planning_iterations` to 2. The agent completed 1 planning round, then stalled — it couldn't produce an approvable plan within the imposed cap. Claude had to restart with `plan_mode: false`.  
**Impact:** First run completely wasted; user had to diagnose and restart.  
**Proposed fix:** Remove or raise the greenfield cap. If the intent is to prevent runaway planning on simple scaffolds, the cap should be ≥ 5 rounds for any task with a non-trivial description (>50 words or >3 mentioned files). Alternatively, expose the cap in `configure()` so Claude can override it per-task.

---

### Issue 2 — Wrong Vite template name in agent knowledge
**Severity:** Major  
**Observed:** Agent ran `npm create vite@latest flashcard-app -- --template react-js`. In Vite 8, the correct template is `react` (not `react-js`). This silently scaffolded a vanilla TypeScript template with no React, wasting a full run.  
**Impact:** Second run produced the wrong scaffold; required manual pre-scaffolding.  
**Proposed fix:** Add to the `qwen3-delegation` system prompt (or a "common tool gotchas" section in the profile config): `Vite 8 template names: react, react-ts, vue, vue-ts, svelte. There is no react-js template.` Also worth noting: `npm create vite@latest <dir> -- --template react` (note double `--`) is the correct invocation in npm 7+.

---

### Issue 3 — Agent creates nested subdirectory instead of scaffolding in-place
**Severity:** Major  
**Observed:** Agent ran `npm init vite@latest my-flashcard-app` inside the target `working_dir`, creating `flashcard-app-qwen-test/flashcard-app/my-flashcard-app/`. All subsequent writes went into the nested dir.  
**Impact:** Required Claude to delete the subdirectory and pre-scaffold at the correct path.  
**Proposed fix:** When the `working_dir` passed to `run()` is the intended project root, the agent should scaffold with `.` as the target (e.g. `npm create vite@latest . -- --template react`) rather than inventing a project name. The system prompt should include: "Use `.` as the Vite project directory when `working_dir` is already the intended project root."

---

### Issue 4 — file_ops loop guard too tight for greenfield work
**Severity:** Major  
**Observed:** The Qwen server hard-stopped run 3 after ~15 consecutive file-write operations, cutting off before `App.css` was written. The guard fires at 15 calls regardless of task type.  
**Impact:** 6/7 required files written; app left in non-buildable state. Claude had to manually write the missing CSS and fix a bug the agent introduced.  
**Proposed fix (short term):** Expose `file_ops_hard_limit` in `configure()` so Claude can raise it for known greenfield tasks (e.g. `config={"file_ops_hard_limit": 30}`).  
**Proposed fix (long term):** Make the guard context-aware — greenfield tasks where the plan lists N files should allow at least N+5 consecutive writes. The guard is valuable for preventing runaway edits on existing codebases; it should not penalize initial scaffolding.

---

### Issue 5 — Dynamic import inside FileReader callback (generated code bug)
**Severity:** Minor  
**Observed:** `DeckList.jsx` line 63 used `import('../utils/storage').then(module => module.importDeck(...))` inside a `FileReader.onload` callback. The static import `import { ..., exportDeck } from '../utils/storage'` at the top of the file already brings in the module — `importDeck` was simply not added to the destructure list. Vite will bundle both paths correctly but the dynamic import is unnecessary overhead and confusing to read.  
**Proposed fix (already applied):** Add `importDeck` to the static import at the top; replace the dynamic import with a direct call.

---

### Issue 6 — npm cache EACCES not handled
**Severity:** Minor  
**Observed:** `npm install` failed with `EACCES: permission denied` on `~/.npm/_cacache`. The agent had no fallback.  
**Impact:** Required Claude to run `npm install --cache /tmp/npm-cache` manually.  
**Proposed fix:** Add to the `qwen3-delegation` system prompt: "If `npm install` fails with EACCES on the npm cache, retry with `--cache /tmp/npm-cache`."

---

## Wins

1. **Storage schema design was correct first try.** `storage.js` embedded cards inside deck objects under `deck.cards[]`, used a single `DECKS_KEY`, and implemented all 8 required functions (load/save/delete for decks and cards, plus export/import). No architectural changes needed.

2. **`crypto.randomUUID()` used throughout.** Both `DeckForm.jsx` and `CardEditor.jsx` generated IDs with `crypto.randomUUID()` — matching the project's coding standard without being instructed to.

3. **StudyMode queue implementation was solid.** The shuffle-on-mount, splice-on-"Got it", and wrap-around-on-"Review again" pattern is correct and handles the empty-deck and single-card edge cases.

4. **Component decomposition matched the spec.** The agent independently arrived at the same 4-component split (DeckList, DeckForm, CardEditor, StudyMode) that a human architect would choose. No over-engineering.

---

## Concrete Improvement Applied

**Fix applied:** Added `importDeck` to the static import in `DeckList.jsx` and removed the dynamic `import()` call (Issue 5).

**System prompt patch (pending):** The `qwen3-delegation` profile's system prompt should be updated with the Vite template name correction and the npm cache fallback (Issues 2 and 6). This is a one-line addition to the profile config.

See diff: `DeckList.jsx` line 2 — `import { loadDecks, deleteDeck, exportDeck, importDeck } from '../utils/storage';`; lines 63–70 replaced with `importDeck(jsonString); refreshDecks(); setImportError('');`.

---

## MCP Ergonomics Notes

- `review(agent_id, "get")` before `approve` worked as designed — plan was readable and enumerated files correctly.
- `poll()` correctly reported `completed` state when the loop guard fired; no ambiguity.
- `configure()` did NOT expose `max_planning_iterations` override in a way that affected the greenfield cap — the cap appears to be server-side and not surfaced to the client. This is a documentation gap: the configure() docs should list which parameters are overridable and which are hard server-side limits.
- No `limit_reached` status was returned; the agent completed (partially) rather than hitting the iteration budget. The loop guard is a separate mechanism not reflected in the polling status — the caller has no signal that a hard stop occurred mid-run.

---

## Summary

The Qwen agent system is capable of generating correct, idiomatic React code when it reaches the implementation phase. The blockers are all pre-implementation: plan phase stalling on greenfield tasks, incorrect scaffold commands, and a file_ops guard calibrated for edit workflows rather than creation workflows. Fix those three issues and this same task would succeed in a single run.
