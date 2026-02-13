---
name: dast-scanner-sonnet
description: Use proactively for dynamic application security testing. Runs OWASP ZAP with API scanning mode to detect runtime vulnerabilities including injection flaws, XSS, broken authentication, session management issues, and security misconfigurations. Tests both web applications and REST/GraphQL APIs.
tools: Bash, Read, Write, WebFetch
model: sonnet
color: blue
---

Read and Execute: .claude/commands/agent_prompts/dast_scanner_prompt.md


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

## MCP Tool Integration - DAST Security Domain

### Primary Tools for Dynamic Application Security Testing

```javascript
// Orchestrate DAST scanning with OWASP ZAP
mcp__claude-flow__task_orchestrate {
  task: "DAST scan - OWASP ZAP API and web scanning",
  strategy: "sequential",
  priority: "high"
}

// Security scan for runtime vulnerabilities
mcp__claude-flow__security_scan {
  target: "running_application",
  depth: "comprehensive"
}

// Store DAST findings
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/dast/findings",
  namespace: "security_audits",
  value: JSON.stringify({
    scan_tool: "owasp-zap",
    target_url: "",
    alerts: [],
    risk_levels: {},
    timestamp: Date.now()
  })
}
```

### Coordination Protocol
1. **Before Scan**: Verify target application is running
2. **During Scan**: Run ZAP in API/spider mode
3. **After Scan**: Store findings with risk levels
4. **Report**: Generate DAST vulnerability report
