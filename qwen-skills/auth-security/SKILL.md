---
name: auth-security
description: JWT, OAuth2, RBAC, OWASP input sanitization, password handling
---

# Auth & Security

## Password Handling

- Hash with bcrypt or argon2 — NEVER MD5, SHA-1, or plain SHA-256
- Cost factor >= 12 for bcrypt
- Rate limit login attempts (5 failures → cooldown)
- Never store plaintext passwords, never log them

## JWT

- Store signing secret in environment variable — never in code
- Short access token expiry (15-30 min) + longer refresh token
- Minimal claims: `sub`, `iat`, `exp`, `role` — no sensitive data in payload
- Validate token on every protected request (signature, expiry, issuer)
- Implement token revocation (blacklist or short-lived + refresh rotation)

## OAuth2

- Use Authorization Code flow (not Implicit) for server-side apps
- Validate `state` parameter to prevent CSRF
- Store tokens server-side, never expose to client beyond access token
- Handle token refresh transparently

## Session Management

- Crypto-random session IDs (`crypto.randomUUID()` or equivalent)
- Cookie flags: `HttpOnly`, `Secure`, `SameSite=Strict`
- Set expiry, implement idle timeout
- Invalidate sessions on logout, password change, role change

## RBAC

- Define roles as data (database or config), not hardcoded conditionals
- Check permissions at the handler/middleware level, before business logic
- Principle of least privilege — default deny
- Audit log: who did what, when, to which resource

## Input Sanitization (OWASP)

Systematically check each category:
- **SQL injection**: parameterized queries, never string concatenation
- **XSS (output)**: escape HTML in server-rendered templates
- **Path traversal**: validate file paths, reject `..`, use allowlists
- **SSRF**: validate/allowlist outbound URLs, block internal IPs
- **Mass assignment**: explicitly define allowed fields, reject unexpected keys
- **Command injection**: never pass user input to shell commands; use library APIs
