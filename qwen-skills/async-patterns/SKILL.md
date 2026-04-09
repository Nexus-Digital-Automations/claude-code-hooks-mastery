---
name: async-patterns
description: Async/await, task queues, WebSockets, event-driven patterns, concurrency
---

# Async Patterns

## Async/Await

- Use async for I/O-bound operations (DB queries, HTTP calls, file I/O)
- Never block the event loop with synchronous operations in async code
- Gather concurrent independent operations: `asyncio.gather()` / `Promise.all()`
- Set timeouts on all async operations — never wait indefinitely
- Support cancellation for long-running operations

## Task Queues

- Use established libraries: Celery (Python), Bull/BullMQ (Node), Sidekiq (Ruby)
- Jobs MUST be idempotent — safe to execute twice with the same input
- Retry with exponential backoff for transient failures (max 3-5 retries)
- Track job status: pending → running → completed/failed
- Monitor queue depth — alert when backlog grows beyond threshold
- Dead letter queue for permanently failed jobs

## WebSocket Patterns

- Heartbeat/ping-pong to detect stale connections (30s interval)
- Reconnection with exponential backoff on client disconnect
- Authenticate on connection (token in query param or first message)
- Use rooms/channels for topic-based broadcasting
- Clean up server-side state on disconnect (remove from rooms, release resources)

## Event-Driven

- Explicit event schemas: define the shape of every event
- Past-tense event names: `user_created`, `order_completed`, `payment_failed`
- Handlers MUST be idempotent — events may be delivered more than once
- Dead letter queue for events that fail after max retries
- Correlation ID in every event — trace the originating request

## Concurrency Safety

- Protect shared state: use database-level locks, not in-memory locks (multi-instance)
- Optimistic concurrency: version column, retry on conflict
- Rate limit outbound calls to external services
- Circuit breaker for failing dependencies (see error-handling skill)

## Debugging Async Issues

Check 4 bottleneck dimensions:
1. **Communication**: queue delays, message serialization overhead
2. **Processing**: CPU-bound work blocking async runtime
3. **Memory**: unbounded buffers, leaked connections
4. **Network**: connection pool limits, DNS resolution, timeout misconfiguration
