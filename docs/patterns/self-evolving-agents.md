# Self-Evolving Agents Pattern

## What It Is

An agent that **updates its own skill files after every execution** to reflect the current state of whatever it manages. This prevents knowledge drift — the gradual divergence between what the agent "knows" (in its skills) and what actually exists in the codebase.

Source: `claude-code-best-practice/.claude/agents/presentation-curator.md`

---

## The Problem It Solves

When an agent manages something that changes over time (a presentation, an architecture, a data model), its domain knowledge becomes stale. Future invocations make decisions based on outdated state. This is especially common with:

- Agents that manage long-lived files (presentations, docs, config)
- Agents that track architecture or schema
- Agents that accumulate learned patterns over multiple sessions

---

## The Pattern

At the end of every execution, the agent performs a "self-evolution" step:

```markdown
### Step N: Self-Evolution (after every execution)

Read the current state of [thing-you-manage] and update your own skills to reflect reality:

1. Update [skill-1] with any changed [facts about structure]
2. Update [skill-2] with any changed [facts about content]
3. Append to your own `## Learnings` section if you encountered edge cases or new patterns

This prevents knowledge drift between your skills and the actual state of [thing-you-manage].
```

### Agent Frontmatter

```yaml
---
name: my-evolving-agent
description: PROACTIVELY use when managing [X]
skills:
  - my-domain/structure-skill
  - my-domain/content-skill
---
```

The `skills:` field preloads domain knowledge into the agent at invocation time. The self-evolution step keeps those skill files current.

---

## When to Use This Pattern

Good candidates for self-evolving agents:
- **Architecture tracker** — reads codebase after each exploration, updates an `architecture-snapshot` skill
- **Code conventions tracker** — updates a `project-conventions` skill as it encounters patterns
- **DeepSeek mistake tracker** — updates a `deepseek-known-mistakes` skill with new mistakes found during validation
- **Schema manager** — updates a `current-schema` skill after each migration
- **Test pattern tracker** — updates a `test-patterns` skill as tests are added

---

## Example: DeepSeek Mistake Tracker

An agent to track common DeepSeek mistakes for better plan review:

```yaml
---
name: deepseek-review-advisor
description: PROACTIVELY use when reviewing a DeepSeek plan to get advice on common mistakes
skills:
  - deepseek/known-mistakes
model: sonnet
maxTurns: 10
---

# DeepSeek Review Advisor

Review the provided plan diff and flag patterns matching known DeepSeek mistakes.

## Known Mistake Categories (from skill)

[Loaded from skills/deepseek/known-mistakes/SKILL.md]

## After Review — Self-Evolution

If you identified a new mistake pattern not in the skill, append it:
1. Read `.claude/skills/deepseek/known-mistakes/SKILL.md`
2. Add the new pattern under `## Patterns`
3. Include: pattern name, description, what to look for, example
```

---

## Learnings

- The `## Learnings` section in the agent file itself is a good place to log edge cases found across invocations — the agent appends to this section, Claude Code reads it on the next invocation since it's in the agent's frontmatter context
- Skills are the right place for structured facts; the `## Learnings` section is better for procedural wisdom ("when X, do Y")
- Skill updates should be targeted diffs, not rewrites — append new facts, update changed ones, remove stale ones
