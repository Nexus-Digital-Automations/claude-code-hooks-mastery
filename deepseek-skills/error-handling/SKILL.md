---
name: error-handling
description: Structured errors, logging, retries, and circuit breakers
---

# Error Handling

## Error Envelope
Every API error: `{"error": {"code": "ERROR_CODE", "message": "Human-readable", "request_id": "req_abc", "details": []}}`

## Classification
- **4xx** (client): return details so caller can fix. Log at WARN.
- **5xx** (server): log full trace server-side, return generic "Internal server error". Log at ERROR.
- **Transient** (503, timeout): retry with exponential backoff (`base * 2^attempt + jitter`), max 3 retries. Never retry 4xx.

## Structured Logging
JSON with: `level`, `message`, `request_id`, `timestamp`, `service`, `error`. Propagate `request_id` across services. NEVER log passwords, tokens, API keys, PII.

## Circuit Breaker
Closed → Open (10 failures in 60s) → Half-open (30s later, test 1 request) → Closed (3 successes).

## Health Check
`GET /health` returns dependency status. Include `request_id`, `user_id` in all error logs.
