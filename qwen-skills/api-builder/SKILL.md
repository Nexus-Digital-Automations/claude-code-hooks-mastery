---
name: api-builder
description: REST API design — pagination, versioning, rate limiting, error format
---

# API Builder

## REST Conventions
Plural nouns for resources (`/users`, `/orders`). Nested: `/users/{id}/orders`.
GET=read, POST=create, PUT=replace, PATCH=update, DELETE=remove.

## Status Codes
200 success · 201 created (+ Location header) · 204 no body (DELETE) · 400 malformed · 401 no auth · 403 forbidden · 404 not found · 409 conflict · 422 validation fail · 429 rate limit (+ Retry-After) · 500 server error

## Error Format
`{"error": {"code": "VALIDATION_ERROR", "message": "Human-readable", "details": [{"field": "email", "message": "Invalid format"}]}}`

## Pagination
Cursor-based for large sets. Response: `{"data": [...], "pagination": {"next_cursor": "abc", "has_more": true}}`. Default 20, max 100.

## Rate Limiting
Per-endpoint (writes stricter). Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`. 429 + `Retry-After`.

## Implementation Order
1. Routes + schemas → 2. Input validation → 3. Service layer → 4. Error handling → 5. Integration tests → 6. Edge cases
