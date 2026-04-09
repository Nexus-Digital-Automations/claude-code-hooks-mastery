---
name: code-standards
description: Backend coding standards, naming conventions, and quality requirements
always_include: true
---

# Backend Code Standards

## Read Before Writing
Read existing files in the same directory to match style, naming conventions, import patterns. Reuse existing utilities.

## Naming
- **Python**: `snake_case` functions, `PascalCase` classes, `UPPER_SNAKE` constants
- **JS/TS**: `camelCase` functions, `PascalCase` classes, `kebab-case` files
- **Go**: `camelCase` unexported, `PascalCase` exported

## Directory Layout
`src/` (models, routes, services, middleware) · `tests/` (mirrors src/) · `migrations/` · `config/` · `scripts/`

## Quality Rules
- No hardcoded secrets — use env vars
- Handle errors explicitly — no bare `except:`, no empty `catch {}`
- Single responsibility — one function, one job
- No dead code — remove unused imports/variables
- Structured JSON logging with request_id — never log secrets
- Config from environment, validated at startup

## Debugging Discipline
- Limit diagnostic narration to **3 sentences max** before fixing
- Cap self-verification retries at **2 attempts** — if still failing, report and stop
- Do NOT explain what you're about to do — just do it

## Before Reporting Done
Evidence, not claims:
1. Run tests — show pass/fail counts
2. Run linter — show output
3. Verify build succeeds — show output
4. List all files created/modified
