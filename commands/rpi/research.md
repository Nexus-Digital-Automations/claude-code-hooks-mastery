---
description: "RPI Phase 1 — Research a feature request and produce a GO/NO-GO verdict"
---

# RPI: Research

Perform Phase 1 (Research) of the RPI workflow for a feature request.

**Usage:** `/rpi:research rpi/<feature-slug>/REQUEST.md`

---

## What This Does

Analyzes the feature request using parallel research agents, then produces a `RESEARCH.md` with a GO/NO-GO verdict before any planning begins.

---

## Step 0: Setup

If `rpi/<feature-slug>/` doesn't exist yet, create it:
```
rpi/<feature-slug>/
└── REQUEST.md   ← paste feature description here first
```

Read the REQUEST.md now. Extract:
- Feature name
- Core problem being solved
- Stated requirements
- Any stated constraints

---

## Step 1: Parallel Research

Launch these agents **in a single message** (parallel):

**Agent 1 — Requirement Parser + Product Manager:**
Prompt: "Read `rpi/<feature-slug>/REQUEST.md`. As a product manager:
1. Extract all explicit and implicit requirements
2. Identify success criteria
3. Flag any ambiguities or missing information
4. Assess strategic fit: does this align with the project's existing direction?
5. Rate feasibility: HIGH / MEDIUM / LOW with reasoning
Return a structured report."

**Agent 2 — Senior Engineer + CTO:**
Prompt: "Read `rpi/<feature-slug>/REQUEST.md` and explore the codebase to understand the existing architecture.
1. Identify which files/systems this feature touches
2. Estimate complexity: SIMPLE / MODERATE / COMPLEX
3. Identify technical risks or blockers
4. Check for existing patterns to reuse
5. Recommend the implementation approach at a high level
Return a structured technical report."

---

## Step 2: GO/NO-GO Decision

Read both agent reports. Synthesize into a verdict:

**GO criteria** (all must be met):
- Requirements are clear or can be clarified in one round
- No blocking technical risk
- Feasibility is MEDIUM or HIGH
- Aligned with project direction

**NO-GO criteria** (any one blocks):
- Ambiguous requirements with no clear resolution path
- Blocking technical risk (data migration risk, security concern, etc.)
- Out of scope for current project state
- Would require undoing existing work

---

## Step 3: Write RESEARCH.md

Create `rpi/<feature-slug>/research/RESEARCH.md`:

```markdown
# Research: <Feature Name>

**Date:** <today>
**Verdict:** GO / NO-GO

## Summary
<2-3 sentences>

## Requirements Analysis
<from Agent 1>

## Technical Analysis
<from Agent 2>

## Verdict Reasoning
<why GO or NO-GO>

## Open Questions (if GO)
<questions to resolve during planning>

## Risks
<identified risks and mitigations>
```

---

## Step 4: Present to User

Show the verdict and key findings. If GO, suggest: `/rpi:plan <feature-slug>`
If NO-GO, explain what would need to change to make it viable.
