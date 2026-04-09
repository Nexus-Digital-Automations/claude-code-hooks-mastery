---
name: database-patterns
description: Schema design, migrations, queries, ORM usage, and connection management
---

# Database Patterns

## Schema Design

- Normalize by default — denormalize only with measured performance justification
- Standard columns: `id` (UUID or auto-increment), `created_at`, `updated_at` (auto-set)
- Foreign keys with explicit ON DELETE behavior (CASCADE, SET NULL, or RESTRICT)
- Index strategy: index foreign keys, columns in WHERE/ORDER BY, unique constraints
- Use appropriate types: `timestamptz` not `varchar` for dates, `numeric` for money

## Migrations

- Forward-only in production — never edit a deployed migration
- Naming: `YYYYMMDD_HHMMSS_description.sql` (or framework convention)
- Every migration must be reversible (include up + down)
- Separate schema migrations from data migrations
- Test migrations against a copy of production data when possible

## Query Patterns

- **Parameterized queries always** — never concatenate user input into SQL
- **N+1 detection**: if you query inside a loop, rewrite as a JOIN or IN clause
- **SELECT specific columns** — avoid `SELECT *` in production queries
- **EXPLAIN** queries touching large tables — verify index usage
- **Cursor pagination** for large result sets — avoid OFFSET on large tables

## Connection Management

- Use connection pooling (pgbouncer, HikariCP, pool settings in ORM)
- Set query timeout (30s default, shorter for user-facing)
- Retry connection failures with exponential backoff
- Close connections on application shutdown (graceful cleanup)

## Transactions

- Wrap multi-step writes in a transaction
- Keep transactions short — no network calls or slow operations inside
- Choose isolation level deliberately (READ COMMITTED default, SERIALIZABLE for critical)
- Handle deadlocks: catch, retry with backoff (max 3 attempts)

## ORM Guidance

- Model definitions must match migration state exactly
- Use raw SQL for complex queries (multi-join, CTEs, window functions)
- Define relationships explicitly — don't rely on implicit discovery
- Eager-load related data when you know you'll need it (avoid lazy-load N+1)
