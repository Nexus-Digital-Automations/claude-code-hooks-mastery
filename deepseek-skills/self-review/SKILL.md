---
name: self-review
description: Mandatory self-review checklist before reporting task complete — catches common mistakes
always_include: true
---

# Self-Review Before Done

Before reporting any task complete, run this checklist against every file you created or modified. Fix issues before reporting — do not report them as known issues.

## 1. Variable Reference Audit

For every variable used inside a `.forEach`, `.map`, `.filter`, `.reduce`, or any callback/closure:
- Verify it references the correct scope (outer variable vs callback parameter)
- Common mistake: using a raw input object's property when you meant to use a processed/transformed version
- Check: does `result.x` point to the right `result`? Is the variable from the enclosing scope or the callback?

## 2. Dead Code Scan

After every early return, guard clause, or `if (x) return`:
- Verify the code below it is actually reachable
- Delete unreachable `if` branches (e.g., checking `length === 0` after an earlier return for `length === 0`)
- Remove `else` blocks after returns

## 3. Duplication Check

If the same logic block appears 2+ times:
- Extract to a named helper function
- Call the helper from each location
- Common case: classification/categorization logic (e.g., determining a status level) repeated across functions

## 4. Test-Implementation Alignment

For every test assertion, trace the actual code path:
- Plug in the test's input values and manually compute the expected output
- Verify the assertion matches what the code actually produces, not what you intended
- Pay special attention to boundary conditions: `<` vs `<=`, `>` vs `>=`, count thresholds
- Check that `OR` vs `AND` logic in conditionals produces the expected result at boundaries

## 5. Import Audit

Before reporting done:
- Verify every import is actually used in the file
- Remove unused imports (common: importing `beforeEach` in tests, importing utilities "just in case")
- Check that named imports match actual export names

## 6. Run Verification Commands

If the project has any of these configured, run them and fix errors:
- Test suite (`npm test`, `pytest`, `vitest run`, etc.)
- Linter (`eslint`, `ruff`, `clippy`, etc.)
- Build (`npm run build`, `tsc --noEmit`, `cargo build`, etc.)

Show the actual output — never claim "tests pass" without pasting results.
