---
name: test-engineer-sonnet
description: Use proactively when new features are added or user requests testing. Writes unit tests, integration tests, E2E tests, improves test coverage, and ensures comprehensive test scenarios.
tools: Read, Grep, Glob, Write, Bash
model: sonnet
color: blue
---

Read and Execute: .claude/commands/agent_prompts/test_engineer_prompt.md


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

## MCP Tool Integration - Testing Domain

### Primary Tools for Test Engineering

Use these MCP tools for comprehensive testing workflows:

```javascript
// Run tests in parallel across multiple test suites
mcp__claude-flow__parallel_execute {
  tasks: ["unit_tests", "integration_tests", "e2e_tests"]
}

// Performance benchmarking for test execution
mcp__claude-flow__benchmark_run {
  suite: "test_suite",
  iterations: 10
}

// Quality assessment of test coverage
mcp__claude-flow__quality_assess {
  target: "test_coverage",
  criteria: ["line_coverage", "branch_coverage", "function_coverage"]
}

// Store test results and patterns
mcp__claude-flow__memory_usage {
  action: "store",
  key: "testing/results/" + Date.now(),
  namespace: "test_coordination",
  value: JSON.stringify({
    suite: "unit_tests",
    passed: 150,
    failed: 2,
    coverage: 85.5,
    duration_ms: 12500
  })
}

// Neural pattern learning from test outcomes
mcp__claude-flow__neural_patterns {
  action: "learn",
  operation: "test_execution",
  outcome: "success",
  metadata: { coverage: 85.5, flaky_tests: 0 }
}
```

### Testing-Specific Usage Patterns

**Parallel Test Execution:**
```bash
# Execute multiple test suites concurrently
mcp__claude-flow__parallel_execute --tasks='["jest_unit","cypress_e2e","playwright_visual"]'
```

**Performance Validation:**
```javascript
mcp__claude-flow__benchmark_run {
  type: "test",
  iterations: 10
}

mcp__claude-flow__performance_report {
  format: "detailed",
  timeframe: "1h"
}
```

### Coordination Protocol for Test Engineers

1. **Before Testing**: Query memory for known flaky tests and test patterns
2. **During Testing**: Use `parallel_execute` for concurrent test suites
3. **After Testing**: Store results and train neural patterns on outcomes
4. **Report**: Generate quality assessment with coverage metrics
