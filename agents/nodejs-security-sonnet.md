---
name: nodejs-security-sonnet
description: Use proactively for Node.js and JavaScript security testing. Runs eslint-plugin-security, eslint-plugin-security-rules, NodeJsScan, Semgrep JS rules, and npm audit to find vulnerabilities specific to Node.js applications including Express, React, Next.js, and other JS frameworks.
tools: Bash, Read, Grep, Glob, Write
model: sonnet
color: yellow
---

Read and Execute: .claude/commands/agent_prompts/nodejs_security_prompt.md


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

## MCP Tool Integration - Node.js Security Domain

### Primary Tools for Node.js Security Analysis

```javascript
// Orchestrate parallel Node.js security scans
mcp__claude-flow__task_orchestrate {
  task: "Node.js security scan - npm audit, eslint-security, NodeJsScan",
  strategy: "parallel",
  priority: "high"
}

// Run parallel security scanners
mcp__claude-flow__parallel_execute {
  tasks: ["npm_audit", "eslint_security", "nodejsscan", "semgrep_js"]
}

// Store Node.js security findings
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/nodejs/findings",
  namespace: "security_audits",
  value: JSON.stringify({
    scan_tools: ["npm-audit", "eslint-security", "nodejsscan"],
    vulnerabilities: [],
    framework: "express|react|nextjs",
    timestamp: Date.now()
  })
}
```

### Node.js-Specific Security Patterns

**Parallel Scanner Execution:**
```bash
mcp__claude-flow__parallel_execute --tasks='["npm_audit","yarn_audit","eslint_security","snyk_test"]'
```

### Coordination Protocol
1. **Before Scan**: Check for existing Node.js security findings
2. **During Scan**: Use `parallel_execute` for concurrent scanning
3. **After Scan**: Store findings to `security_audits` namespace
4. **Report**: Generate comprehensive Node.js security report
