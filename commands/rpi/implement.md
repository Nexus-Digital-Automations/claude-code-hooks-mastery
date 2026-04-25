---
description: "RPI Phase 3 — Execute the approved plan with validation gates"
---

# RPI: Implement

Perform Phase 3 (Implement) of the RPI workflow. Requires Phase 2 (Plan) to have an APPROVED PLAN.md.

**Usage:** `/rpi:implement <feature-slug>`

---

## Prerequisites

Verify before proceeding:
- `rpi/<feature-slug>/plan/PLAN.md` exists
- Status in PLAN.md is **APPROVED** (not PENDING)

If not approved, stop and ask user to run `/rpi:plan <feature-slug>` first.

---

## Step 0: Read the Plan

Read all plan files:
1. `rpi/<feature-slug>/plan/PLAN.md` — phases and tasks
2. `rpi/<feature-slug>/plan/eng.md` — technical spec
3. `rpi/<feature-slug>/plan/pm.md` — acceptance criteria
4. `rpi/<feature-slug>/plan/ux.md` — UX spec (if exists)

Identify:
- Which tasks are backend (delegate to DeepSeek)
- Which tasks are frontend (implement directly)
- Dependencies between tasks

---

## Phase Execution

Execute phases one at a time. **Do not start Phase N+1 until Phase N passes its validation gate.**

For each phase:

### Backend Tasks — Delegate to DeepSeek

```
run(task="<task description from eng.md>", working_dir="<project_dir>", profile="default-delegation")
```

Include in every DeepSeek task description:
- The specific files to create/modify (from eng.md)
- What NOT to change
- Verification steps
- "Run build, lint, type-check, and Playwright tests after implementation. If any fail, fix and retry."

After DeepSeek completes:
1. Review plan: `review(agent_id, "get")`
2. Approve if correct: `review(agent_id, "approve")`
3. Poll: `poll(agent_id, timeout=300)`
4. Read every modified file — line by line
5. Re-run build + lint + type-check yourself

### Frontend Tasks — Implement Directly

Implement frontend work directly. Use impeccable skills:
- `/frontend-design` for new components
- Run Playwright tests after implementation

---

## Validation Gates

After each phase, verify against acceptance criteria from `pm.md`:

```
Phase N Gate:
✓ All tasks in this phase complete
✓ Build passes
✓ Lint/type-check passes (zero errors)
✓ Unit tests pass
✓ Integration tests pass (if applicable)
✓ Playwright E2E passes for this phase's features
```

If gate fails: fix before moving to next phase.

---

## Final Gate

After all phases:
1. Run full test suite
2. Run all Playwright E2E tests
3. Verify every acceptance criterion from `pm.md` with actual output
4. Security review (if feature touches auth, data, or external APIs)

---

## Step N: Write IMPLEMENT.md

Create `rpi/<feature-slug>/implement/IMPLEMENT.md`:

```markdown
# Implementation: <Feature Name>

**Date:** <today>
**Status:** COMPLETE / IN PROGRESS / BLOCKED

## Phase Results
| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | PASS/FAIL | |
| Phase 2 | PASS/FAIL | |
| Phase 3 | PASS/FAIL | |

## Acceptance Criteria Results
| Criterion | Status | Evidence |
|-----------|--------|---------|
| <from pm.md> | PASS/FAIL | <command output> |

## Deviations from Plan
<any changes made during implementation and why>

## Known Issues
<anything not addressed>
```

---

## Done Criteria

Feature is complete when:
- All acceptance criteria from `pm.md` verified with actual output
- All tests pass (show output)
- IMPLEMENT.md status is COMPLETE
- `authorize-stop.sh` confirms stop is authorized
