---
title: DeepSeek Agent Test Report
date: 2026-04-05
test: Add keyboard shortcuts to flashcard-app
agent_id: 6bae65b0-5e2f-4bd1-a94d-14928252932d
profile: default-delegation
---

# DeepSeek Agent Test Report

## Task

Add keyboard shortcuts to a React flashcard app (5 files: new hook, new component, 3 file modifications).

## Result

**Plan rejected. Feature implemented manually.**

---

## Bug Found and Fixed: `max_plan_tokens` misconfiguration

### Symptom
First agent invocation (id: `28383712-edc3-475a-8a7c-158a6f10f92c`) failed immediately with:
```
Planning API call failed: Error code: 400 - Invalid max_tokens value, the valid range of max_tokens is [1, 8192]
```

### Root Cause
`profiles/default-delegation.json` had `"max_plan_tokens": 32768`. During planning, `planning_coordinator.py:307` overrides the model config:
```python
plan_model_cfg = self._config.model.model_copy(
    update={"max_tokens": self._config.plan_mode.max_plan_tokens}
)
```
DeepSeek's API cap is 8192. All other profiles correctly use 8192; `default-delegation` was the only outlier.

### Fix Applied
- `profiles/default-delegation.json`: `max_plan_tokens` changed from `32768` → `8192`
- Profile cache reloaded via `mcp__deepseek-agent__reload`

---

## Planning Phase Observations

After the fix, the agent successfully entered planning and completed 16 rounds over ~5 minutes.

### Token Cost of Planning

| Metric | Value |
|--------|-------|
| Planning rounds | 16 (hit max) |
| Planning tokens | 207,716 / 250,000 (83%) |
| Cost (planning only) | $0.069 |
| Wall time | ~5 minutes |
| Unit tests in codebase | 237 |

For a 5-file frontend feature, 207k planning tokens is **extremely expensive**. The agent over-investigated and hit the planning round cap.

### Why Planning Overran

1. **Read-only tool access loops.** During planning the agent has `planning_tools: "read_only"`. It called `list_dir` and `read_file` 13+ times before producing a plan. For a 20-file React app this is excessive.
2. **Completeness validator retry loop.** The plan was submitted twice with incomplete fields (`_remaining_issues` flagged 2 issues), causing 2 extra rounds. The issues were false positives caused by the validator comparing relative paths in `file_changes` to absolute paths in `codebase_analysis.files_read`.
3. **Skill context padding.** The task prompt included 7 full skill documents (~4000 tokens of backend-focused guidelines irrelevant to React). This inflated input tokens on every planning round.

---

## Plan Quality Assessment

The final plan was structurally correct (correct files, correct strategy) but contained critical implementation errors:

### ✅ Correct
- New hook `useKeyboardShortcuts.js` — logic sound, clean implementation
- New component `KeyboardShortcutsHelp.jsx` — correct, idiomatic React
- `RatingButtons.jsx` edits — exact `old_string` matches verified

### ❌ Broken (caused plan rejection)

**Edit #6 — StudySession state block:**
```json
"old_string": "const { session, startSession, flip, rate, resetSession } = useStudySession()\n  const [isFlipped, setIsFlipped] = useState(false)\n  const [showSummary, setShowSummary] = useState(false)"
```
Actual file:
```js
const { session, startSession, flip, rate, resetSession } = useStudySession()
const sessionStart = useRef(new Date().toISOString())
const [selectedMode, setSelectedMode] = useState(null)
```
`showSummary` state doesn't exist. `isFlipped` comes from `session`, not a local `useState`.

**Edit #6 — callback references:** Plan used `handleFlip()` and referenced `showSummary`, neither of which exist. The actual flip is `flip()` directly.

**Missing: duplicate event listener.** `StudySession.jsx` already had a `useEffect` keydown handler (lines 55-72). The plan ignored it and would have registered a second conflicting listener.

**Edit #7 — ambiguous `old_string`:** `"      </div>\n    </div>\n  )"` appears 3 times in the file. The edit would have modified the wrong closing tag.

### Why These Errors Occurred

The agent read `StudySession.jsx` during planning but its `entities_found` listed `handleRate` at line 67 and `handleFlip` at line 63. In the actual file, there is no `handleFlip` — the flip is inline (`flip()` from the hook). The agent fabricated a function name and state variable that appeared in its training data for "typical flashcard apps" rather than from actual file content.

This suggests the agent's investigation notes were a mix of real file content and hallucinated "expected" patterns.

---

## Completeness Validator False Positives

The validator correctly enforces that files to be modified must be listed in `codebase_analysis.files_read`. It compared:

- `file_changes[].path`: `"src/components/StudySession.jsx"` (relative)
- `codebase_analysis.files_read[]`: `"/Users/jeremyparker/Desktop/Claude Coding Projects/flashcard-app/src/components/StudySession.jsx"` (absolute)

These are the same file but the validator sees them as different strings. This caused 2 unnecessary retry rounds and 18k+ extra tokens. The validator should normalize paths before comparison.

---

## Issues to Fix

### P0 — Critical

| # | Issue | File | Fix |
|---|-------|------|-----|
| 1 | `max_plan_tokens: 32768` in default-delegation profile crashes DeepSeek API | `profiles/default-delegation.json` | **Fixed** — changed to 8192 |

### P1 — High Impact

| # | Issue | Fix |
|---|-------|-----|
| 2 | Agent hallucinates function names and state vars instead of quoting actual file content | Stronger instruction in planning prompt: "Before writing ANY old_string, paste the EXACT LINE from read_file output. Do not paraphrase." |
| 3 | Validator path comparison fails on absolute vs relative paths | Normalize both paths in `validate_plan_completeness` before string comparison |
| 4 | Agent ignores existing handlers when adding new functionality | Add to planning prompt: "Search for existing event listeners / handlers before adding new ones." |

### P2 — Quality

| # | Issue | Fix |
|---|-------|-----|
| 5 | 16 planning rounds / 207k tokens for a 5-file React feature | Lower `max_planning_iterations` in profile to 8 for `default-delegation`; add `list_dir` call budget |
| 6 | Skills injected into task prompt contain backend-only guidelines irrelevant to this task | Route frontend tasks to a frontend-specific profile without backend-skill padding |
| 7 | No warning when planning tokens exceed 50% of budget until 62% | Lower `planning_warning_threshold` to 0.4 |

---

## Final Output Quality

After manual implementation with correct old_strings and duplicate-handler removal:

```
npm run lint → ✅ 0 errors
npm test     → ✅ 237 tests passed (3 pre-existing e2e failures unrelated to this change)
```

The feature works: Space/Enter flips, Arrow keys rate after flip, Escape exits, `?` button shows shortcuts popover, rating buttons show key badges.

---

## Summary

The DeepSeek agent system **works** (API, plan generation, tool orchestration all functional after the P0 fix) but produces **unreliable `old_string` values** for file edits. The plan review gate correctly caught this before execution — which is exactly what it's designed for.

The primary failure mode is the agent reading files but producing `old_string` values from memory rather than file content, particularly when existing code doesn't match "typical" patterns for its training distribution. This is a fundamental LLM limitation that the tooling can partially mitigate through stronger prompting.
