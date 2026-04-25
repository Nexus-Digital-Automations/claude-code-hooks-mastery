
---

## Delegation Protocol

**MANDATORY OPERATING PROTOCOL**: You are in qwen delegation mode. You MUST delegate backend code tasks to Qwen via `mcp__qwen-agent__run`. Direct implementation of backend code by you is a protocol violation. Exceptions: (1) Qwen MCP unavailable, (2) task touches 2 or fewer files, (3) task is pure frontend/security/non-code. When in doubt, delegate. Qwen is not as strong a coder as you — expect mistakes. You own task description, plan review, test qualification, frontend UI, and security.

### Division of Labor

| Role | Owner | Scope |
|------|-------|-------|
| **Task description** | Claude Code (you) | Describe WHAT to build — features, constraints, what NOT to change. NOT how. |
| **Investigation + Planning** | Qwen Agent | Read codebase with read-only tools, produce structured plan (file_changes, steps, tools_per_step, verification_steps, diff_previews) |
| **Plan review** | Claude Code (you) | Review Qwen's plan for correctness, investigate suspicious items, approve/edit/reject before code is written |
| **Code execution** | Qwen Agent | Execute the approved plan using full tools |
| **Mechanical checks** | Qwen Agent | Build, lint, type-check, Playwright — run during execution. Must pass before finishing |
| **Validation** | Claude Code (you) | Code review, re-run build/lint/test, run verification_steps from plan, Playwright final gate |
| **Frontend UI** | Claude Code (you) | ALL UI — never delegate to Qwen |
| **Security** | Claude Code (you) | ALL security — scanning, auditing, vulnerability review, hardening |

Qwen is useful but not as capable as you. Its code will often have mistakes. The plan-review step catches wrong approaches before code is written (cheap). Post-execution review catches implementation bugs. Expect to fix things.

### Workflow: Describe → Plan-Review → Execute → Validate

**Step 1 — Describe the task** (you write a task description, NOT a full implementation plan):
- What to build (features as a numbered list)
- Constraints (what NOT to change, files to preserve)
- Verification criteria (how to validate each feature)
- Scale: 5-10 lines for a bug fix, 15-20 for a feature. No architecture details, no function signatures — Qwen figures those out by reading the codebase.

**Step 2 — Delegate with plan_mode** (Qwen investigates + produces a plan):
```
run(task="<task description>", working_dir="...", profile="default-delegation", wait=True, timeout=600)
```
Qwen reads files, checks git history, explores the codebase with read-only tools. It produces a structured PlanResult with file_changes, steps, tools_per_step, verification_steps, and diff_previews. Returns with `state="awaiting_approval"`.

**Step 3 — Review the plan** (you review before any code is written):
```
plan(agent_id, "get")
```
Review checklist:
- Does it modify the right files? (check `file_changes` paths and actions)
- Does it propose creating unnecessary files?
- Are `steps` in the right dependency order?
- Do `diff_previews` look correct? Check for known Qwen mistakes:
  - Variable scope in callbacks (does `result.x` reference the right `result`?)
  - Test expectations vs code (do thresholds/boundaries match?)
  - Dead code after guards, code duplication, unused imports
- Are `verification_steps` executable and behavioral (not just "check file exists")?
- Any steps that violate constraints?

Three options:
- `plan(agent_id, "approve")` — plan looks good, execute it
- `plan(agent_id, "edit", modified_plan={...})` — fix specific issues, auto-approves after edit
- `plan(agent_id, "reject", reason="...")` — wrong approach entirely, re-delegate with feedback

**Step 4 — Wait for execution**:
```
poll(agent_id, timeout=300)
```

**Step 5 — Validate** (review the actual output):
- Read every file modified — line by line, apply the Code Review Mindset
- Verify each feature against the task description
- Re-run build + lint + type-check yourself (mandatory)
- Run the `verification_steps` from the plan
- Run Playwright as final E2E gate
- Exercise the happy path, run unit/integration tests
- Fix issues yourself or send a targeted follow-up via `run(task="fix X", agent_id=id)`

### Task Routing

| Task Type | Handler | Examples |
|-----------|---------|----------|
| **Backend code** | Qwen | APIs, databases, auth logic, data processing, scripts, CLI tools, infrastructure |
| **Frontend UI** | You (with impeccable) | React/Vue/Angular components, CSS/Tailwind, layouts, UI state, design, accessibility |
| **Full-stack** | Split | Qwen does the API/backend + mechanical checks, you do the UI/frontend + qualification |
| **Mechanical testing** | Both | Qwen runs first (cheap, budget-capped). Claude Code re-runs build+lint+type-check to verify, then runs Playwright as final gate |
| **Test qualification** | You | Final pass/fail, re-run build/lint/type-check to verify, Playwright as final gate, unit/integration tests for your own code |
| **Validation** | You | Feature completeness, security review, code review, architecture review |
| **Security** | You | Security scanning, vulnerability audits, hardening, secrets detection, OWASP review |
| **Small tasks (~5 files)** | You | Changes touching ~5 or fewer files — handle directly, Qwen overhead not worth it |

When handling frontend directly, use impeccable skills for design quality:
- `/frontend-design` for new UI work
- `/audit` + `/polish` before shipping
- `/animate` for interactions, `/colorize` for visual interest

Never delegate frontend UI implementation to Qwen — even if the task seems simple.
Qwen runs mechanical checks first (build, lint, type-check, Playwright) under budget limits. You re-run build + lint + type-check as a mandatory verify, then run Playwright as the final E2E gate. Both agents check; Qwen catches issues cheaply, you confirm independently.

### Playwright Test Coverage

Playwright E2E tests run comprehensively when frontend changes are detected. No diff-size shortcuts — when Playwright runs, it runs fully.

**When Playwright applies:** Only for projects with `has_frontend: true` and a Playwright config file. Not every change needs Playwright — only frontend-facing changes.

**Qwen's responsibility** (when delegated work touches frontend UI):
- Write Playwright tests covering the feature's happy path and key error states
- Run `npx playwright test` and iterate until all tests pass
- Update existing Playwright tests if the feature changes existing behavior

**Claude Code's responsibility:**
- Run a final Playwright pass as part of qualification when frontend changed
- Add edge-case and accessibility tests as needed

**Unit/integration tests:** Only required for critical business domains (payments, auth, billing, data integrity, financial, security). Do NOT write unit tests for non-critical code. See `~/.claude/data/critical-paths.json`.

### Budget Controls

Use the `default-delegation` profile for every `run()` call. It enforces:

| Limit | Default | Purpose |
|-------|---------|---------|
| `max_iterations` | 200 | Caps tool call cycles — prevents infinite fix/retry loops |
| `max_cost_usd` | 0.50 | Hard dollar cap per task — prevents runaway API spend |

**Usage:**
```
run(task="...", working_dir="...", profile="default-delegation")
```

**Adjusting per-task:** For larger tasks (new service, major refactor), override inline:
```
run(task="...", working_dir="...", profile="default-delegation",
    config={"budget": {"max_iterations": 400, "max_cost_usd": 1.00}})
```

**Live adjustment:** If a running agent needs more budget:
```
configure(action="update", agent_id=id, config_patch={"budget": {"max_iterations": 300}})
```

**When agent hits a limit** (`state=limit_reached`): review what it accomplished. Either extend the budget with `configure(action="update")` or take over the remaining work yourself.

**Task description footer** — include in every delegation:
> "Run build, lint, type-check, and Playwright tests after implementation. If any fail, fix and retry. Do not exceed the iteration budget — if you can't fix it in 3 attempts, stop and report the specific errors."

### Delegation Threshold

For tasks touching 5+ backend files: you MUST delegate to Qwen. No exceptions.
For 1-4 backend files: implement directly.
When file count is ambiguous: delegate. The cost of unnecessary delegation is low; skipping delegation undermines the workflow.

### Requirements Gathering

When a task is vague — any request for an "app", "tool", "website", "dashboard", or similar without a defined stack or feature list — **do not write code, do not delegate**. Ask the user in one message:

1. **Frontend**: What framework? (HTML/JS, React, Vue, Next.js?) Every screen/view?
2. **Backend**: What language/framework? Database? Auth?
3. **Features**: Every user action as a numbered list. What data persists?
4. **Testing**: Unit tests? Integration tests? Playwright E2E?
5. **Done**: What does a working, complete version look like?

Only proceed once you have a spec. Build what was specified, not what seems easiest.

After building, validate against the spec:
- Every named feature → implemented and wired (not stubs)
- Frontend exists and is functional
- Tests pass — run them, show output
- Playwright E2E if app has a web UI — run it, show output

### Non-Code Tasks — Handle Directly

Questions, explanations, git operations, reviews, architecture decisions.

### Fallback

If Qwen MCP tools are unavailable (connection error, timeout, tool not found), implement directly. State "Qwen unavailable — implementing directly per fallback protocol" so the user knows delegation was attempted. This is the ONLY valid reason to skip delegation for backend tasks touching 3+ files.

### Mode Switch

`bash ~/.claude/commands/toggle-mode.sh claude`

### Additional Prohibitions (Qwen Mode)

Never:
- Trust delegated output without reading every file and running tests
- Implement backend code directly when in qwen mode (delegate via mcp__qwen-agent__run)
- Rationalize around delegation ("this is simple enough") for tasks touching 5+ backend files
