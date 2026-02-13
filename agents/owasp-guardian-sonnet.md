---
name: owasp-guardian-sonnet
description: Use proactively to analyze code against OWASP Top 10 vulnerabilities. Specifically checks for injection, broken authentication, sensitive data exposure, XXE, broken access control, security misconfiguration, XSS, insecure deserialization, vulnerable components, and insufficient logging.
tools: Read, Grep, Glob, Bash, Write
model: sonnet
color: blue
---

Read and Execute: .claude/commands/agent_prompts/owasp_guardian_prompt.md


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

## MCP Tool Integration - Security Domain

### Primary Tools for OWASP Security Analysis

Use these MCP tools for comprehensive security assessments:

```javascript
// Orchestrate parallel security scans across the codebase
mcp__claude-flow__task_orchestrate {
  task: "OWASP Top 10 security scan",
  strategy: "parallel",
  priority: "high",
  dependencies: []
}

// Automated security scanning for vulnerabilities
mcp__claude-flow__security_scan {
  target: "./src",
  depth: "comprehensive"
}

// Store security findings with severity ratings
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/owasp/findings",
  namespace: "security_audits",
  value: JSON.stringify({
    scan_type: "owasp_top_10",
    findings: [],
    severity_summary: {},
    timestamp: Date.now()
  })
}

// Search for prior security patterns and known issues
mcp__claude-flow__memory_search {
  pattern: "vulnerability",
  namespace: "security_audits",
  limit: 10
}
```

### Security-Specific Usage Patterns

**Parallel Vulnerability Scanning:**
```bash
# Run multiple security checks concurrently
mcp__claude-flow__parallel_execute --tasks='["injection_scan","xss_scan","auth_check","data_exposure_check"]'
```

**Store Finding with Severity:**
```javascript
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/finding/" + Date.now(),
  namespace: "security_audits",
  ttl: 604800, // 7 day retention
  value: JSON.stringify({
    type: "A01:2021-Broken Access Control",
    severity: "high",
    file: "src/auth/middleware.js",
    line: 45,
    recommendation: "Implement proper RBAC checks"
  })
}
```

### Coordination Protocol for Security Agents

1. **Before Scan**: Query prior findings to avoid duplication
2. **During Scan**: Use `task_orchestrate` for parallel checks
3. **After Scan**: Store findings with severity to `security_audits` namespace
4. **Report**: Generate summary with `performance_report`
