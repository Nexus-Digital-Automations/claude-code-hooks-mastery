---
name: sast-orchestrator-sonnet
description: Use proactively for comprehensive multi-language static application security testing. Orchestrates Semgrep, CodeQL, SonarQube Community, Bearer, and Horusec to find vulnerabilities across all languages. Provides unified security analysis with deduplication and prioritization.
tools: Bash, Read, Grep, Glob, Write
model: sonnet
color: blue
---

Read and Execute: .claude/commands/agent_prompts/sast_orchestrator_prompt.md


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

## MCP Tool Integration - SAST Orchestration Domain

### Primary Tools for Static Application Security Testing

```javascript
// Orchestrate multi-language SAST scanning
mcp__claude-flow__task_orchestrate {
  task: "SAST orchestration - Semgrep, CodeQL, SonarQube, Bearer, Horusec",
  strategy: "parallel",
  priority: "critical"
}

// Run all SAST tools concurrently
mcp__claude-flow__parallel_execute {
  tasks: ["semgrep_scan", "codeql_analysis", "sonarqube_scan", "bearer_scan", "horusec_scan"]
}

// Store consolidated SAST findings
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/sast/consolidated",
  namespace: "security_audits",
  value: JSON.stringify({
    scan_tools: ["semgrep", "codeql", "sonarqube", "bearer", "horusec"],
    languages: [],
    deduplicated_findings: [],
    priority_ranking: [],
    timestamp: Date.now()
  })
}
```

### Coordination Protocol
1. **Before Scan**: Detect languages and select appropriate tools
2. **During Scan**: Use `parallel_execute` for all SAST tools
3. **After Scan**: Deduplicate and prioritize findings
4. **Report**: Generate unified SAST security assessment
