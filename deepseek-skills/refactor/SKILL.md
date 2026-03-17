---
name: refactor
description: Safe refactoring with test preservation
---

# Refactor

You are refactoring code. Safety is the priority — behavior must not change.

## 1. Establish a Baseline

Before touching any code:
- Run the full test suite and save the results
- Note the current test count and pass rate
- If there are no tests, write characterization tests first
- These tests are your safety net

## 2. One Change at a Time

Make refactoring changes incrementally:
- Rename → run tests → commit mentally
- Extract function → run tests → commit mentally
- Move code → run tests → commit mentally
- NEVER batch multiple refactoring steps without testing between them

## 3. Preserve Behavior

The cardinal rule of refactoring:
- Tests must still pass after every change
- Public API signatures should not change unless explicitly requested
- Do NOT add new features during a refactoring task
- Do NOT fix bugs during a refactoring task (note them separately)

## 4. Common Safe Refactorings

- **Extract function**: Pull repeated logic into a named function
- **Rename**: Make names clearer and more descriptive
- **Inline**: Remove unnecessary abstractions
- **Move**: Relocate code to a more logical module
- **Simplify conditionals**: Flatten nested if/else chains

## 5. Verify Final State

After all changes:
- Run the full test suite — same pass count as baseline
- Run the linter if configured
- Verify no behavior changes were introduced
- Report what was refactored and why it's better
