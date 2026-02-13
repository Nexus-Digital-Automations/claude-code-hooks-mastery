---
name: python-security-sonnet
description: Use proactively for Python security testing. Runs Bandit, pip-audit, Semgrep Python rules, and safety to find vulnerabilities specific to Python applications including Django, Flask, FastAPI, and other Python frameworks.
tools: Bash, Read, Grep, Glob, Write
model: sonnet
color: blue
---

Read and Execute: .claude/commands/agent_prompts/python_security_prompt.md


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

## MCP Tool Integration - Python Security Domain

### Primary Tools for Python Security Analysis

```javascript
// Orchestrate parallel Python security scans
mcp__claude-flow__task_orchestrate {
  task: "Python security scan - Bandit, pip-audit, safety",
  strategy: "parallel",
  priority: "high"
}

// Run parallel security scanners
mcp__claude-flow__parallel_execute {
  tasks: ["bandit_scan", "pip_audit", "safety_check", "semgrep_python"]
}

// Security scan for Python-specific vulnerabilities
mcp__claude-flow__security_scan {
  target: "./",
  depth: "comprehensive"
}

// Store Python security findings
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/python/findings",
  namespace: "security_audits",
  value: JSON.stringify({
    scan_tools: ["bandit", "pip-audit", "safety", "semgrep"],
    vulnerabilities: [],
    framework: "django|flask|fastapi",
    timestamp: Date.now()
  })
}
```

### Python-Specific Security Patterns

**Parallel Scanner Execution:**
```bash
# Run all Python security tools concurrently
mcp__claude-flow__parallel_execute --tasks='["bandit_scan","pip_audit_scan","safety_scan","semgrep_python"]'
```

**Store Dependency Vulnerability:**
```javascript
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/python/dependency/" + Date.now(),
  namespace: "security_audits",
  ttl: 604800,
  value: JSON.stringify({
    package: "requests",
    version: "2.25.0",
    cve: "CVE-2023-XXXX",
    severity: "high",
    fixed_version: "2.31.0"
  })
}
```

### Coordination Protocol
1. **Before Scan**: Check for existing Python security findings
2. **During Scan**: Use `parallel_execute` to run Bandit, pip-audit, safety concurrently
3. **After Scan**: Store findings to `security_audits` namespace with severity
4. **Report**: Generate comprehensive security report
