---
name: self-review
description: Mandatory self-review checklist before reporting task complete — catches common mistakes
always_include: true
---

# Self-Review Before Done

Run this checklist against every file you created or modified. Fix before reporting.

1. **Variable scope audit**: In every callback/closure (`.map`, `.forEach`, `.filter`), verify variables reference the correct scope — outer vs callback parameter. Check: does `result.x` point to the right `result`?

2. **Dead code scan**: After every early return/guard, verify code below is reachable. Delete unreachable branches and `else` after returns.

3. **Duplication check**: Same logic 2+ times → extract to a named helper.

4. **Test-implementation alignment**: Trace each test assertion through actual code. Check boundary conditions (`<` vs `<=`), `OR` vs `AND` logic at thresholds.

5. **Import audit**: Remove unused imports. Verify named imports match actual export names.

6. **Run verification**: Run available test suite, linter, and build. Show actual output — never claim "tests pass" without pasting results.
