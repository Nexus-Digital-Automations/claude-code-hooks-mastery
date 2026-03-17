---
name: code-standards
description: Project coding standards, naming conventions, and quality requirements
always_include: true
---

# Code Standards

These standards apply to ALL tasks. Follow them automatically.

## Read Before Writing

Before creating or modifying code:
- Read existing files in the same directory to match style
- Use the same naming convention as surrounding code
- Follow the same import organization pattern
- Reuse existing utilities — don't reinvent them

## Naming Conventions

Match the project's language conventions:

**Python**: `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants
**JavaScript/TypeScript**: `camelCase` functions/variables, `PascalCase` classes/components, `UPPER_SNAKE` constants
**File names**: Match project convention (usually `kebab-case` or `snake_case`)

## Quality Requirements

- **No hardcoded secrets** — no API keys, passwords, or tokens in source code
- **Handle errors explicitly** — never use bare `except:` or swallow errors silently
- **Use type hints** where the project uses them (Python type annotations, TypeScript types)
- **Keep functions focused** — one function, one responsibility
- **No dead code** — remove unused imports, variables, and functions

## File Organization

- Source code belongs in `src/` (not at project root)
- Tests belong in `tests/`
- Generated output belongs in `output/` (gitignored)
- Follow existing project structure — don't create new top-level directories without reason

## Before Reporting Done

- Run tests if a test suite exists
- Run the linter/formatter if configured
- Verify the build succeeds
- List all files created or modified
