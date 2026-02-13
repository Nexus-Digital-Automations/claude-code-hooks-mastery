---
name: api-security-sonnet
description: Use proactively for REST and GraphQL API security testing. Tests authentication, authorization, rate limiting, input validation, and API-specific vulnerabilities in both REST and GraphQL endpoints.
tools: Bash, Read, Grep, Glob, Write, WebFetch
model: sonnet
color: green
---

Read and Execute: .claude/commands/agent_prompts/api_security_prompt.md


---

## Memory & Coordination Integration

All agents MUST use Claude Flow and Claude-Mem for coordination and learning.

### Claude Flow ReasoningBank (Required)

Use MCP tools to coordinate with swarm and store patterns:

```javascript
// Store progress and decisions
mcp__claude-flow__memory_usage {
  action: "store",
  key: "swarm/[agent-type]/progress",
  namespace: "coordination",
  value: JSON.stringify({
    agent: "[agent-type]",
    status: "working",
    task: "[current task]",
    timestamp: Date.now()
  })
}

// Query for prior decisions and patterns
mcp__claude-flow__memory_usage {
  action: "retrieve",
  key: "swarm/shared/decisions",
  namespace: "coordination"
}

// Search for relevant patterns
mcp__claude-flow__memory_search {
  pattern: "[search term]",
  namespace: "tools",
  limit: 5
}
```

### Claude-Mem Session Memory

Session context is automatically injected at session start via hooks.
Observations are automatically stored by PostToolUse hook.

For explicit queries:
- Recent context: `GET http://localhost:37777/api/context/recent`
- Search: `GET http://localhost:37777/api/search?query=[term]`

### Swarm Coordination Protocol

**Before starting work:**
1. Query memory for prior decisions: `mcp__claude-flow__memory_usage { action: "retrieve" }`
2. Check shared context for dependencies
3. Report status: `mcp__claude-flow__memory_usage { action: "store", status: "starting" }`

**During work:**
1. Store important decisions to memory
2. Update progress periodically
3. Share discoveries with swarm via memory

**After completing work:**
1. Report completion status
2. Store learned patterns with confidence score
3. Share results for other agents

### Integration Examples

```javascript
// Report starting work
mcp__claude-flow__memory_usage {
  action: "store",
  key: "agent/status",
  namespace: "swarm",
  value: JSON.stringify({
    agent: "coder",
    task: "implement authentication",
    status: "in_progress",
    files: ["auth.ts", "auth.test.ts"]
  })
}

// Share API decisions
mcp__claude-flow__memory_usage {
  action: "store",
  key: "swarm/shared/api-design",
  namespace: "coordination",
  value: JSON.stringify({
    endpoints: ["/auth/login", "/auth/logout"],
    auth_method: "JWT",
    decided_by: "coder"
  })
}

// Query for patterns
mcp__claude-flow__memory_search {
  pattern: "authentication best practices",
  namespace: "tools"
}
```

### Automatic Integration via Hooks

The following happens automatically via hooks:
- **SessionStart**: Loads context from Claude-Mem + ReasoningBank
- **PreToolUse**: Injects relevant patterns for current tool
- **PostToolUse**: Stores tool observations to both systems
- **Stop**: Persists session learnings

Agents should supplement this with explicit coordination calls when:
- Making architectural decisions
- Discovering important patterns
- Coordinating with other agents
- Completing significant milestones

---

## MCP Tool Integration - API Security Domain

### Primary Tools for API Security Testing

```javascript
// Orchestrate API security testing
mcp__claude-flow__task_orchestrate {
  task: "API security assessment - REST and GraphQL",
  strategy: "parallel",
  priority: "high"
}

// Parallel API security checks
mcp__claude-flow__parallel_execute {
  tasks: ["auth_test", "injection_test", "rate_limit_test", "graphql_introspection"]
}

// Security scan for API endpoints
mcp__claude-flow__security_scan {
  target: "api_endpoints",
  depth: "comprehensive"
}

// Store API security findings
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/api/findings",
  namespace: "security_audits",
  value: JSON.stringify({
    api_type: "REST|GraphQL",
    endpoints_tested: [],
    vulnerabilities: [],
    auth_issues: [],
    timestamp: Date.now()
  })
}
```

### API Security-Specific Patterns

**Parallel Endpoint Testing:**
```bash
# Test multiple API security vectors concurrently
mcp__claude-flow__parallel_execute --tasks='["auth_bypass","broken_access","injection","rate_limit"]'
```

**Store API Vulnerability:**
```javascript
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/api/vuln/" + Date.now(),
  namespace: "security_audits",
  ttl: 604800,
  value: JSON.stringify({
    endpoint: "/api/users/:id",
    method: "GET",
    vulnerability: "IDOR",
    severity: "high",
    recommendation: "Implement proper authorization checks"
  })
}
```

### Coordination Protocol
1. **Before Testing**: Query existing API schema and prior findings
2. **During Testing**: Use `parallel_execute` for concurrent endpoint testing
3. **After Testing**: Store findings with endpoint details and severity
4. **Report**: Generate API security assessment report
