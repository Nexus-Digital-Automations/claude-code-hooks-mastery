---
name: middleware-patterns
description: Request pipeline ordering, CORS, rate limiting, validation, logging
---

# Middleware Patterns

## Middleware Ordering (Critical)

Order matters. Follow this sequence:
1. **CORS** — handle preflight before anything else
2. **Request ID** — generate/propagate correlation ID
3. **Request logging** — log method, path, start time
4. **Rate limiting** — reject before doing expensive work
5. **Authentication** — verify identity
6. **Authorization** — verify permissions
7. **Input validation** — validate request body/params/query
8. **Route handler** — business logic
9. **Error handling** — catch-all, format response
10. **Response logging** — log status, duration, request_id

## Request Validation

- Validate schema BEFORE the handler runs (middleware or decorator)
- Return 400 for malformed requests, 422 for valid structure but invalid values
- Include field-level errors: `{"field": "email", "message": "Invalid format"}`
- Validate path params, query params, and headers — not just body

## Logging Middleware

- Structured JSON: `method`, `path`, `status`, `duration_ms`, `request_id`
- Log request start and response end as separate entries
- NEVER log request/response bodies containing secrets, passwords, or tokens
- Include user_id when authenticated

## Rate Limiting

- Per-IP for unauthenticated, per-user for authenticated
- Sliding window algorithm preferred
- Return 429 with `Retry-After` header (seconds until reset)
- Use Redis or equivalent for multi-instance deployments
- Different limits for different endpoints (writes stricter than reads)

## Error Handling Middleware

- Catch-all at the end of the pipeline
- Convert unhandled exceptions to structured error responses
- Log full stack trace server-side
- Return generic "Internal server error" to client (never expose internals)
- Preserve the request_id in error responses

## CORS Configuration

- Whitelist specific origins — never `Access-Control-Allow-Origin: *` in production
- Explicitly configure allowed methods and headers
- Handle OPTIONS preflight requests
- Set `Access-Control-Max-Age` to reduce preflight frequency
