---
name: code-standards
description: Backend coding standards, naming conventions, and quality requirements
always_include: true
---

# Backend Code Standards

These standards apply to ALL tasks. Follow them automatically.

## Read Before Writing

- Read existing files in the same directory to match style
- Use the same naming convention as surrounding code
- Follow the same import organization pattern
- Reuse existing utilities — don't reinvent them

## Naming Conventions

**Python**: `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants, `snake_case.py` files
**JS/TS (backend — Express, Fastify, NestJS)**: `camelCase` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants, `kebab-case` files
**Go**: `camelCase` unexported, `PascalCase` exported, `snake_case.go` files
**File names**: Match project convention

## Backend Directory Conventions

- `src/` — source code (models, routes, services, middleware, utils)
- `tests/` — mirror `src/` structure
- `migrations/` — database migrations (timestamped: `YYYYMMDD_HHMMSS_description`)
- `config/` — configuration modules
- `scripts/` — one-off scripts, seeds, CLI tools
- `output/` — generated artifacts (gitignored)

## Quality Requirements

- **No hardcoded secrets** — use env vars, never API keys/passwords/tokens in source
- **Handle errors explicitly** — no bare `except:`, no empty `catch {}`, no swallowed errors
- **Type hints** where the project uses them
- **Single responsibility** — one function, one job
- **No dead code** — remove unused imports, variables, functions
- **Dependency injection** — pass dependencies as arguments, don't import singletons in business logic
- **Structured logging** — use JSON-structured logs with context (request_id, user_id), never log secrets
- **Config from environment** — `os.environ` / `process.env`, validated at startup

## Debugging & Verification Discipline

When a verification script or test produces unexpected output:
- Diagnose silently: read the output, identify the cause
- Limit diagnostic narration to **3 sentences maximum** before attempting a fix
- Do NOT explain what you're about to do — just do it
- If a verification script has a bug (not the production code), fix the script in one attempt then move on
- Cap self-verification retries at **2 attempts** — if still failing, report the issue and stop

## Before Reporting Done

Evidence, not claims. Run each command and show the output:
1. Run tests — show pass/fail counts
2. Run linter/formatter if configured — show clean output
3. Verify build/start succeeds — show the command output
4. List all files created or modified
Never claim "tests pass" without pasting the actual test output.
