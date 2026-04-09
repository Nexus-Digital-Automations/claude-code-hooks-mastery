---
name: tdd-workflow
description: Test-driven development red-green-refactor cycle
---

# TDD Workflow

You are using test-driven development. Follow red-green-refactor strictly.

## The Cycle

### Red: Write a Failing Test First

- Write a test for the NEXT piece of functionality
- Run it — it MUST fail (if it passes, the test is wrong)
- The test should be specific and test one behavior
- Never skip the red step — it proves the test actually tests something

### Green: Write Minimal Code to Pass

- Write the SIMPLEST code that makes the test pass
- Do not write more code than needed
- Do not optimize or clean up yet
- Run the test — it must pass now
- Run ALL tests — nothing else should break

### Refactor: Clean Up While Green

- Now improve the code: rename, extract, simplify
- Run tests after EVERY change — stay green
- Apply the code-standards skill during this phase
- Stop refactoring when the code is clean and readable

## Rules

1. **Never write production code without a failing test first**
2. **Never write more test code than needed to fail**
3. **Never write more production code than needed to pass**
4. **Run the full suite after each green and refactor step**
5. **Commit at each green step** (conceptually — save progress)

## Test Quality

- Test behavior, not implementation details
- Use descriptive test names that explain the expected behavior
- One assertion per test when possible
- Tests should be independent — no shared mutable state
