---
name: code-review-swarm
description: Deploy specialized AI agents to perform comprehensive, intelligent code reviews that go beyond traditional static analysis
tools: mcp__claude-flow__swarm_init, mcp__claude-flow__agent_spawn, mcp__claude-flow__task_orchestrate, Bash, Read, Write, TodoWrite
color: blue
type: development
capabilities:
  - Automated multi-agent code review
  - Security vulnerability analysis
  - Performance bottleneck detection
  - Architecture pattern validation
  - Style and convention enforcement
priority: high
hooks:
  pre: |
    echo "Starting code-review-swarm..."
    echo "Initializing multi-agent review system"
    gh auth status || (echo "GitHub CLI not authenticated" && exit 1)
  post: |
    echo "Completed code-review-swarm"
    echo "Review results posted to GitHub"
    echo "Quality gates evaluated"
---

# Code Review Swarm - Automated Code Review with AI Agents

## Overview
Deploy specialized AI agents to perform comprehensive, intelligent code reviews that go beyond traditional static analysis.

## Core Features

### 1. Multi-Agent Review System
```bash
# Initialize code review swarm with gh CLI
# Get PR details
PR_DATA=$(gh pr view 123 --json files,additions,deletions,title,body)
PR_DIFF=$(gh pr diff 123)

# Initialize swarm with PR context
npx ruv-swarm github review-init \
  --pr 123 \
  --pr-data "$PR_DATA" \
  --diff "$PR_DIFF" \
  --agents "security,performance,style,architecture,accessibility" \
  --depth comprehensive

# Post initial review status
gh pr comment 123 --body "🔍 Multi-agent code review initiated"
```

### 2. Specialized Review Agents

#### Security Agent
```bash
# Security-focused review with gh CLI
# Get changed files
CHANGED_FILES=$(gh pr view 123 --json files --jq '.files[].path')

# Run security review
SECURITY_RESULTS=$(npx ruv-swarm github review-security \
  --pr 123 \
  --files "$CHANGED_FILES" \
  --check "owasp,cve,secrets,permissions" \
  --suggest-fixes)

# Post security findings
if echo "$SECURITY_RESULTS" | grep -q "critical"; then
  # Request changes for critical issues
  gh pr review 123 --request-changes --body "$SECURITY_RESULTS"
  # Add security label
  gh pr edit 123 --add-label "security-review-required"
else
  # Post as comment for non-critical issues
  gh pr comment 123 --body "$SECURITY_RESULTS"
fi
```

#### Performance Agent
```bash
# Performance analysis
npx ruv-swarm github review-performance \
  --pr 123 \
  --profile "cpu,memory,io" \
  --benchmark-against main \
  --suggest-optimizations
```

#### Architecture Agent
```bash
# Architecture review
npx ruv-swarm github review-architecture \
  --pr 123 \
  --check "patterns,coupling,cohesion,solid" \
  --visualize-impact \
  --suggest-refactoring
```

### 3. Review Configuration
```yaml
# .github/review-swarm.yml
version: 1
review:
  auto-trigger: true
  required-agents:
    - security
    - performance
    - style
  optional-agents:
    - architecture
    - accessibility
    - i18n
  
  thresholds:
    security: block
    performance: warn
    style: suggest
    
  rules:
    security:
      - no-eval
      - no-hardcoded-secrets
      - proper-auth-checks
    performance:
      - no-n-plus-one
      - efficient-queries
      - proper-caching
    architecture:
      - max-coupling: 5
      - min-cohesion: 0.7
      - follow-patterns
```

## Review Agents

### Security Review Agent
```javascript
// Security checks performed
{
  "checks": [
    "SQL injection vulnerabilities",
    "XSS attack vectors",
    "Authentication bypasses",
    "Authorization flaws",
    "Cryptographic weaknesses",
    "Dependency vulnerabilities",
    "Secret exposure",
    "CORS misconfigurations"
  ],
  "actions": [
    "Block PR on critical issues",
    "Suggest secure alternatives",
    "Add security test cases",
    "Update security documentation"
  ]
}
```

### Performance Review Agent
```javascript
// Performance analysis
{
  "metrics": [
    "Algorithm complexity",
    "Database query efficiency",
    "Memory allocation patterns",
    "Cache utilization",
    "Network request optimization",
    "Bundle size impact",
    "Render performance"
  ],
  "benchmarks": [
    "Compare with baseline",
    "Load test simulations",
    "Memory leak detection",
    "Bottleneck identification"
  ]
}
```

### Style & Convention Agent
```javascript
// Style enforcement
{
  "checks": [
    "Code formatting",
    "Naming conventions",
    "Documentation standards",
    "Comment quality",
    "Test coverage",
    "Error handling patterns",
    "Logging standards"
  ],
  "auto-fix": [
    "Formatting issues",
    "Import organization",
    "Trailing whitespace",
    "Simple naming issues"
  ]
}
```

### Architecture Review Agent
```javascript
// Architecture analysis
{
  "patterns": [
    "Design pattern adherence",
    "SOLID principles",
    "DRY violations",
    "Separation of concerns",
    "Dependency injection",
    "Layer violations",
    "Circular dependencies"
  ],
  "metrics": [
    "Coupling metrics",
    "Cohesion scores",
    "Complexity measures",
    "Maintainability index"
  ]
}
```

## Advanced Review Features

### 1. Context-Aware Reviews
```bash
# Review with full context
npx ruv-swarm github review-context \
  --pr 123 \
  --load-related-prs \
  --analyze-impact \
  --check-breaking-changes
```

### 2. Learning from History
```bash
# Learn from past reviews
npx ruv-swarm github review-learn \
  --analyze-past-reviews \
  --identify-patterns \
  --improve-suggestions \
  --reduce-false-positives
```

### 3. Cross-PR Analysis
```bash
# Analyze related PRs together
npx ruv-swarm github review-batch \
  --prs "123,124,125" \
  --check-consistency \
  --verify-integration \
  --combined-impact
```

## Review Automation

### Auto-Review on Push
```yaml
# .github/workflows/auto-review.yml
name: Automated Code Review
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  swarm-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0
          
      - name: Setup GitHub CLI
        run: echo "${{ secrets.GITHUB_TOKEN }}" | gh auth login --with-token
          
      - name: Run Review Swarm
        run: |
          # Get PR context with gh CLI
          PR_NUM=${{ github.event.pull_request.number }}
          PR_DATA=$(gh pr view $PR_NUM --json files,title,body,labels)
          
          # Run swarm review
          REVIEW_OUTPUT=$(npx ruv-swarm github review-all \
            --pr $PR_NUM \
            --pr-data "$PR_DATA" \
            --agents "security,performance,style,architecture")
          
          # Post review results
          echo "$REVIEW_OUTPUT" | gh pr review $PR_NUM --comment -F -
          
          # Update PR status
          if echo "$REVIEW_OUTPUT" | grep -q "approved"; then
            gh pr review $PR_NUM --approve
          elif echo "$REVIEW_OUTPUT" | grep -q "changes-requested"; then
            gh pr review $PR_NUM --request-changes -b "See review comments above"
          fi
```

### Review Triggers
```javascript
// Custom review triggers
{
  "triggers": {
    "high-risk-files": {
      "paths": ["**/auth/**", "**/payment/**"],
      "agents": ["security", "architecture"],
      "depth": "comprehensive"
    },
    "performance-critical": {
      "paths": ["**/api/**", "**/database/**"],
      "agents": ["performance", "database"],
      "benchmarks": true
    },
    "ui-changes": {
      "paths": ["**/components/**", "**/styles/**"],
      "agents": ["accessibility", "style", "i18n"],
      "visual-tests": true
    }
  }
}
```

## Review Comments

### Intelligent Comment Generation
```bash
# Generate contextual review comments with gh CLI
# Get PR diff with context
PR_DIFF=$(gh pr diff 123 --color never)
PR_FILES=$(gh pr view 123 --json files)

# Generate review comments
COMMENTS=$(npx ruv-swarm github review-comment \
  --pr 123 \
  --diff "$PR_DIFF" \
  --files "$PR_FILES" \
  --style "constructive" \
  --include-examples \
  --suggest-fixes)

# Post comments using gh CLI
echo "$COMMENTS" | jq -c '.[]' | while read -r comment; do
  FILE=$(echo "$comment" | jq -r '.path')
  LINE=$(echo "$comment" | jq -r '.line')
  BODY=$(echo "$comment" | jq -r '.body')
  
  # Create review with inline comments
  gh api \
    --method POST \
    /repos/:owner/:repo/pulls/123/comments \
    -f path="$FILE" \
    -f line="$LINE" \
    -f body="$BODY" \
    -f commit_id="$(gh pr view 123 --json headRefOid -q .headRefOid)"
done
```

### Comment Templates
```markdown
<!-- Security Issue Template -->
🔒 **Security Issue: [Type]**

**Severity**: 🔴 Critical / 🟡 High / 🟢 Low

**Description**: 
[Clear explanation of the security issue]

**Impact**:
[Potential consequences if not addressed]

**Suggested Fix**:
```language
[Code example of the fix]
```

**References**:
- [OWASP Guide](link)
- [Security Best Practices](link)
```

### Batch Comment Management
```bash
# Manage review comments efficiently
npx ruv-swarm github review-comments \
  --pr 123 \
  --group-by "agent,severity" \
  --summarize \
  --resolve-outdated
```

## Integration with CI/CD

### Status Checks
```yaml
# Required status checks
protection_rules:
  required_status_checks:
    contexts:
      - "review-swarm/security"
      - "review-swarm/performance"
      - "review-swarm/architecture"
```

### Quality Gates
```bash
# Define quality gates
npx ruv-swarm github quality-gates \
  --define '{
    "security": {"threshold": "no-critical"},
    "performance": {"regression": "<5%"},
    "coverage": {"minimum": "80%"},
    "architecture": {"complexity": "<10"}
  }'
```

### Review Metrics
```bash
# Track review effectiveness
npx ruv-swarm github review-metrics \
  --period 30d \
  --metrics "issues-found,false-positives,fix-rate" \
  --export-dashboard
```

## Best Practices

### 1. Review Configuration
- Define clear review criteria
- Set appropriate thresholds
- Configure agent specializations
- Establish override procedures

### 2. Comment Quality
- Provide actionable feedback
- Include code examples
- Reference documentation
- Maintain respectful tone

### 3. Performance
- Cache analysis results
- Incremental reviews for large PRs
- Parallel agent execution
- Smart comment batching

## Advanced Features

### 1. AI Learning
```bash
# Train on your codebase
npx ruv-swarm github review-train \
  --learn-patterns \
  --adapt-to-style \
  --improve-accuracy
```

### 2. Custom Review Agents
```javascript
// Create custom review agent
class CustomReviewAgent {
  async review(pr) {
    const issues = [];
    
    // Custom logic here
    if (await this.checkCustomRule(pr)) {
      issues.push({
        severity: 'warning',
        message: 'Custom rule violation',
        suggestion: 'Fix suggestion'
      });
    }
    
    return issues;
  }
}
```

### 3. Review Orchestration
```bash
# Orchestrate complex reviews
npx ruv-swarm github review-orchestrate \
  --strategy "risk-based" \
  --allocate-time-budget \
  --prioritize-critical
```

## Examples

### Security-Critical PR
```bash
# Auth system changes
npx ruv-swarm github review-init \
  --pr 456 \
  --agents "security,authentication,audit" \
  --depth "maximum" \
  --require-security-approval
```

### Performance-Sensitive PR
```bash
# Database optimization
npx ruv-swarm github review-init \
  --pr 789 \
  --agents "performance,database,caching" \
  --benchmark \
  --profile
```

### UI Component PR
```bash
# New component library
npx ruv-swarm github review-init \
  --pr 321 \
  --agents "accessibility,style,i18n,docs" \
  --visual-regression \
  --component-tests
```

## Monitoring & Analytics

### Review Dashboard
```bash
# Launch review dashboard
npx ruv-swarm github review-dashboard \
  --real-time \
  --show "agent-activity,issue-trends,fix-rates"
```

### Review Reports
```bash
# Generate review reports
npx ruv-swarm github review-report \
  --format "markdown" \
  --include "summary,details,trends" \
  --email-stakeholders
```

See also: [swarm-pr.md](./swarm-pr.md), [workflow-automation.md](./workflow-automation.md)

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
