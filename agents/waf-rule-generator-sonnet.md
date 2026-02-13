---
name: waf-rule-generator-sonnet
description: Use proactively to generate Web Application Firewall (WAF) rules based on detected vulnerabilities. Analyzes security findings and creates ModSecurity rules to protect applications at the edge.
tools: Bash, Read, Grep, Glob, Write
model: sonnet
color: orange
---

Read and Execute: .claude/commands/agent_prompts/waf_rule_generator_prompt.md


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

## MCP Tool Integration - WAF Rule Generation Domain

### Primary Tools for WAF Rule Generation

```javascript
// Orchestrate WAF rule generation from security findings
mcp__claude-flow__task_orchestrate {
  task: "WAF rule generation from vulnerability findings",
  strategy: "sequential",
  priority: "high"
}

// Retrieve prior security findings to generate rules
mcp__claude-flow__memory_usage {
  action: "retrieve",
  key: "security/*/findings",
  namespace: "security_audits"
}

// Store generated WAF rules
mcp__claude-flow__memory_usage {
  action: "store",
  key: "security/waf/rules",
  namespace: "security_audits",
  value: JSON.stringify({
    rule_format: "modsecurity",
    rules_generated: [],
    vulnerability_coverage: [],
    false_positive_tuning: {},
    timestamp: Date.now()
  })
}
```

### Coordination Protocol
1. **Before Generation**: Query memory for security findings from other scanners
2. **During Generation**: Create ModSecurity rules for each vulnerability class
3. **After Generation**: Store rules and coverage mapping
4. **Report**: Generate WAF rule deployment guide with testing recommendations