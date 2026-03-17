---
name: api-builder
description: REST/GraphQL API design and implementation patterns
---

# API Builder

You are building an API. Follow these patterns for clean, maintainable endpoints.

## REST Conventions

- Use nouns for resources: `/users`, `/orders`, `/products`
- Use HTTP methods correctly: GET (read), POST (create), PUT (replace), PATCH (update), DELETE (remove)
- Use plural nouns: `/users` not `/user`
- Nest related resources: `/users/{id}/orders`
- Return appropriate status codes: 200, 201, 204, 400, 401, 403, 404, 422, 500

## Input Validation

- Validate ALL input at the boundary (request handlers)
- Return 400/422 with specific error messages for invalid input
- Never trust client-provided data — validate types, ranges, formats
- Sanitize string inputs to prevent injection

## Error Response Format

Use a consistent error response structure:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable description",
    "details": [{"field": "email", "message": "Invalid email format"}]
  }
}
```

## Authentication & Authorization

- Place auth middleware BEFORE route handlers
- Validate tokens/sessions on every protected endpoint
- Return 401 for missing/invalid credentials, 403 for insufficient permissions
- Never expose internal auth details in error messages

## Implementation Order

1. Define routes and request/response schemas
2. Implement input validation
3. Write the business logic
4. Add error handling
5. Write integration tests for each endpoint
6. Test edge cases: invalid input, missing auth, not found

## Testing

- Test each endpoint with valid and invalid input
- Test authentication and authorization separately
- Test error responses match the expected format
- Use the actual HTTP layer (integration tests), not just unit tests
