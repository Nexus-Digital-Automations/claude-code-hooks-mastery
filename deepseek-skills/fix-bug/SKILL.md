---
name: fix-bug
description: Systematic bug fix methodology with reproduction and verification
---

# Fix Bug

You are fixing a bug. Follow this systematic approach.

## 1. Reproduce First

Before changing anything:
- Read the error message and stack trace carefully
- Find the exact file and line where the error occurs
- Write a failing test that demonstrates the bug
- If you can't reproduce it, investigate further before guessing

## 2. Understand the Intent

Read the surrounding code to understand:
- What the code is SUPPOSED to do (not just what it does)
- Why the original author wrote it this way
- What other code depends on this function/module
- Whether this is a regression (was it working before?)

## 3. Fix with Minimal Changes

- Change as little code as possible to fix the bug
- Do NOT refactor surrounding code as part of a bug fix
- Do NOT add features while fixing a bug
- If the fix requires broader changes, note them as follow-ups

## 4. Verify the Fix

After applying your fix:
- Run the failing test — it must now pass
- Run the full test suite — no regressions
- Run the linter if configured
- Test edge cases related to the fix

## 5. Explain the Root Cause

In your summary, explain:
- What caused the bug (root cause, not just symptoms)
- Why the fix works
- What the failing test covers
- Any related areas that might have similar issues
