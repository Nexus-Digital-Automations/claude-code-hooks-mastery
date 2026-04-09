---
name: infrastructure
description: Docker, health checks, graceful shutdown, environment management, CI/CD
---

# Infrastructure

## Dockerfiles

- Multi-stage builds: build stage (with dev deps) → production stage (runtime only)
- Pin base image versions: `python:3.12-slim`, not `python:latest`
- Order layers: system deps → app deps (lock file) → source code (maximize cache hits)
- Run as non-root user: `USER appuser`
- Include `.dockerignore` (node_modules, .git, .env, __pycache__)
- Add `HEALTHCHECK` instruction

## Docker Compose

- Named volumes for persistent data (databases, uploads)
- Restart policies: `unless-stopped` for services
- Health checks with `depends_on: condition: service_healthy`
- Environment variables via `.env` file (not hardcoded in compose)
- Separate `docker-compose.dev.yml` override for development

## Environment Management

- Commit `.env.example` with all variables (empty values or safe defaults)
- NEVER commit `.env` — ensure it's in `.gitignore`
- Validate required env vars at application startup — fail fast with clear message
- Group related vars: `DB_HOST`, `DB_PORT`, `DB_NAME` etc.
- Use `dotenv` libraries for local dev, real env vars in production

## Health Checks

- `GET /health` endpoint that checks all dependencies (DB, cache, queues)
- Return `{"status": "healthy", "checks": {"db": "ok", "redis": "ok"}}` or 503
- Separate liveness (is the process alive?) from readiness (can it serve traffic?)
- Include version/build info in health response

## Graceful Shutdown

- Handle SIGTERM and SIGINT signals
- Stop accepting new requests/connections
- Finish in-flight requests (with timeout: 30s default)
- Close database connections, flush log buffers, deregister from service discovery
- Exit with code 0 on clean shutdown

## CI/CD Basics

- Run tests + lint + typecheck before deploy — fail the pipeline on any failure
- Separate build and deploy stages
- Pin dependencies with lock files (package-lock.json, poetry.lock, go.sum)
- Security scanning: dependency audit in CI, container image scanning
- Never deploy from local machine — always through the pipeline
