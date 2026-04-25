---
description: "RPI Phase 2 — Generate a comprehensive implementation plan from research"
---

# RPI: Plan

Perform Phase 2 (Plan) of the RPI workflow. Requires Phase 1 (Research) to have produced a GO verdict.

**Usage:** `/rpi:plan <feature-slug>`

---

## Prerequisites

Verify before proceeding:
- `rpi/<feature-slug>/research/RESEARCH.md` exists
- Verdict in RESEARCH.md is **GO** (not NO-GO)

If NO-GO, stop and show the reason from RESEARCH.md.

---

## Step 1: Read Research Context

Read:
1. `rpi/<feature-slug>/REQUEST.md`
2. `rpi/<feature-slug>/research/RESEARCH.md`

Extract open questions from RESEARCH.md — these must be resolved during planning.

---

## Step 2: Parallel Planning

Launch these agents **in a single message** (parallel):

**Agent 1 — Product Manager:**
Prompt: "Read `rpi/<feature-slug>/REQUEST.md` and `rpi/<feature-slug>/research/RESEARCH.md`.
Write `rpi/<feature-slug>/plan/pm.md` containing:
1. User stories (As a [user], I want [action] so that [outcome])
2. Acceptance criteria (testable, specific)
3. Out-of-scope items (what this feature explicitly does NOT include)
4. Success metrics
5. Answers to open questions from RESEARCH.md"

**Agent 2 — UX Designer (only if feature has UI):**
Prompt: "Read `rpi/<feature-slug>/REQUEST.md` and `rpi/<feature-slug>/plan/pm.md` (once written).
Write `rpi/<feature-slug>/plan/ux.md` containing:
1. User flows (step-by-step for each use case)
2. Component/screen inventory
3. Edge cases and error states
4. Accessibility considerations"

**Agent 3 — Senior Engineer:**
Prompt: "Read `rpi/<feature-slug>/REQUEST.md`, `rpi/<feature-slug>/research/RESEARCH.md`, and explore the codebase.
Write `rpi/<feature-slug>/plan/eng.md` containing:
1. Architecture decisions with rationale
2. File changes (which files to create/modify and why)
3. Data model changes (if any)
4. API contract (if applicable)
5. Test plan (unit, integration, E2E)
6. Migration plan (if touching existing data/behavior)
Note: backend code will be delegated to DeepSeek; write the plan so DeepSeek can execute it."

---

## Step 3: Synthesize into PLAN.md

After agents complete, read all three plan files and synthesize:

Create `rpi/<feature-slug>/plan/PLAN.md`:

```markdown
# Plan: <Feature Name>

**Date:** <today>
**Status:** PENDING APPROVAL

## Overview
<2-3 sentences>

## Phases

### Phase 1: <name> (estimated: <simple/moderate/complex>)
- [ ] Task 1
- [ ] Task 2

### Phase 2: <name>
- [ ] Task 3

### Phase 3: Testing & Polish
- [ ] Unit tests
- [ ] Integration tests
- [ ] Playwright E2E tests
- [ ] Code review

## Implementation Notes
<key decisions from eng.md>

## Delegation Plan
- Backend tasks → DeepSeek (list specific files/components)
- Frontend tasks → Claude Code directly
- Security review → Claude Code

## Verification Steps
1. <behavioral test>
2. <behavioral test>
```

---

## Step 4: Present and Get Approval

Show the plan summary. Ask user:
1. Does the phasing make sense?
2. Any changes before implementation?

Once approved, update PLAN.md status to `APPROVED` and suggest: `/rpi:implement <feature-slug>`
