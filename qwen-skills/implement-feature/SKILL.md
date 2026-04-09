---
name: implement-feature
description: Step-by-step feature implementation workflow for DeepSeek coding agents
---

# Implement Feature

You are implementing a feature. Follow these steps in order.

## 1. Understand the Codebase

Before writing anything, read existing code to understand:
- Project structure and file organization
- Naming conventions (camelCase vs snake_case, file naming)
- Import patterns and module organization
- Existing abstractions you should reuse (not reinvent)

Run `ls` and read key files before creating new ones.

## 2. Plan File Structure

Decide which files to create or modify BEFORE writing code:
- Source files go in `src/` (never at project root)
- Test files go in `tests/` (mirror the src/ structure)
- Generated output goes in `output/` (gitignored)
- Follow existing directory conventions

## 3. Write Tests Alongside Implementation

Do NOT save all testing for the end:
- Write a test for each function/component as you build it
- Run tests frequently — catch issues early
- Test edge cases, not just the happy path

## 4. Implement Incrementally

- Start with the core logic, then add supporting code
- Keep functions small and focused (single responsibility)
- Handle errors explicitly — never swallow exceptions silently
- No hardcoded secrets, API keys, or credentials

## 5. Verify Before Reporting Done

Before claiming the task is complete:
- Run the full test suite: all tests must pass
- Run the linter if one is configured
- Check that the application starts/builds without errors
- List all files you created or modified in your summary

## 6. Report What You Did

End with a clear summary:
- Files created (with paths)
- Files modified (with what changed)
- Test results (pass/fail counts)
- Any known limitations or follow-up items
