# Claude Code — Tools & Plugins Overview

A comprehensive reference of all tools, plugins, agents, MCP servers, skills, and commands
configured in this Claude Code setup (`~/.claude`).

---

## Table of Contents

1. [MCP Servers](#1-mcp-servers)
2. [Hooks System](#2-hooks-system)
3. [Plugins (67 total)](#3-plugins-67-total)
4. [Slash Commands / Skills](#4-slash-commands--skills)
5. [Swarm & Orchestration Commands](#5-swarm--orchestration-commands)
6. [Utility Skills (107 total)](#6-utility-skills-107-total)
7. [Custom Slash Commands](#7-custom-slash-commands)
8. [Agent Prompts](#8-agent-prompts)
9. [Memory & Persistence Systems](#9-memory--persistence-systems)

---

## 1. MCP Servers

External MCP servers that extend Claude with real-time data and specialized capabilities.

| Server | Purpose |
|--------|---------|
| **claude-flow** | Swarm orchestration, task coordination, memory, neural pattern training |
| **ruv-swarm** | Multi-agent swarm init/spawn, benchmarking, neural patterns, DAA agents |

| **maverick-mcp** | Additional tool integrations |
| **wrds-mcp** | Financial data — CRSP, Compustat, S&P 500, macro (FRED), Schwab trading, options analytics |
| **ThetaData** | Real-time and historical US equity/options market data, Greeks, IV surfaces |
| **kroger-mcp** | Kroger grocery API — products, cart, deals, recipes, pantry, meal plans |
| **mcp-python-executor** | Execute Python code in isolated environments, manage packages/venvs |
| **local-whisper** | Local speech-to-text transcription via whisper.cpp (no external API) |
| **ElevenLabs** | Text-to-speech audio generation and playback |
| **firecrawl-mcp** | Web scraping and search |
| **claude_ai_PubMed** | PubMed medical literature search and article retrieval |

---

## 2. Hooks System

Automated scripts that fire at lifecycle events to enforce workflow rules.

| Hook | Script | What It Does |
|------|--------|-------------|
| **SessionStart** | `session_start.py` | Loads recent context from Claude-Mem, checks git status, injects ReasoningBank patterns |
| **PreToolUse** | `pre_tool_use.py` | Blocks `.env` file access, resolves relevant plugins by context, logs tool calls |
| **PostToolUse** | `post_tool_use.py` | Stores observations to Claude-Mem, logs tool results |
| **Stop** | `stop.py` | Blocks stopping until `/authorize-stop` is run; checks root folder cleanliness; detects rate limits to auto-bypass |
| **SubagentStop** | `subagent_stop.py` | Logs subagent completions, optional TTS notification |
| **UserPromptSubmit** | `user_prompt_submit.py` | Logs prompts, stores last prompt, resolves plugin context, generates agent names |
| **Notification** | `notification.py` | TTS alerts (ElevenLabs) when agent needs user input |
| **PreCompact** | `pre_compact.py` | Logs compaction events, optional transcript backup |
| **SessionEnd** | `session_end.py` | Persists session learnings, marks session complete in Claude-Mem |

### Hook Utilities (`hooks/utils/`)

| Utility | Purpose |
|---------|---------|
| `claude_mem.py` | Claude-Mem HTTP API client (port 37777) |
| `pattern_learner.py` | PatternLearner — tracks and recommends successful strategies |
| `plugin_resolver.py` | Resolves relevant plugins by file extension and task keywords |
| `claude_flow.py` | Claude-Flow MCP client wrapper |
| `swarm_client.py` | Swarm coordination client |
| `neural_client.py` | Neural training client |
| `mcp_client.py` | Generic MCP client utilities |
| `workflow_client.py` | Workflow automation client |
| `analytics_client.py` | Analytics/telemetry client |

---

## 3. Plugins (67 total)

Auto-resolved plugins from `~/.claude/New Tools/agents/plugins/`. Each plugin bundles agents,
commands, and skills. Resolution is automatic via hooks based on file type and task context.

### Development

| Plugin | Description |
|--------|-------------|
| **backend-development** | Backend API design, GraphQL, Temporal workflow orchestration, TDD |
| **frontend-mobile-development** | React/Next.js UI, React Native cross-platform mobile |
| **full-stack-orchestration** | End-to-end feature delivery (testing, security, performance, deploy) |
| **multi-platform-apps** | Cross-platform apps coordinating web, iOS, Android, and desktop |
| **developer-essentials** | Git, SQL, error handling, code review, E2E testing, auth, monorepo |
| **debugging-toolkit** | Interactive debugging, developer experience optimization |
| **api-scaffolding** | REST and GraphQL API scaffolding, framework selection, code generation |

### Languages

| Plugin | Description |
|--------|-------------|
| **python-development** | Python 3.12+, Django, FastAPI, async patterns |
| **javascript-typescript** | ES6+, Node.js, React, TypeScript |
| **systems-programming** | Rust, Go, C, C++ for performance-critical code |
| **jvm-languages** | Java, Scala, C# with enterprise patterns |
| **web-scripting** | PHP, Ruby for web apps and CMS |
| **functional-programming** | Elixir, OTP patterns, Phoenix, distributed systems |
| **julia-development** | Julia 1.10+, scientific computing, high-performance numerical code |
| **arm-cortex-microcontrollers** | Firmware for Teensy, STM32, nRF52, SAMD |
| **shell-scripting** | Defensive Bash, POSIX-compliant scripts, testing |

### Testing & Quality

| Plugin | Description |
|--------|-------------|
| **unit-testing** | Unit/integration test automation for Python and JavaScript |
| **tdd-workflows** | TDD red-green-refactor cycles, code review |
| **code-review-ai** | AI-powered architectural review and code quality |
| **comprehensive-review** | Multi-perspective analysis: architecture, security, best practices |
| **performance-testing-review** | Performance analysis, test coverage, AI code quality |
| **api-testing-observability** | API test automation, mocking, OpenAPI docs, observability |

### Security

| Plugin | Description |
|--------|-------------|
| **security-scanning** | SAST, dependency vuln scanning, OWASP Top 10, container security |
| **security-compliance** | SOC2, HIPAA, GDPR validation, secrets scanning, regulatory docs |
| **backend-api-security** | API hardening, authentication, authorization, rate limiting |
| **frontend-mobile-security** | XSS prevention, CSRF, CSP, mobile app security, secure storage |

### Infrastructure & DevOps

| Plugin | Description |
|--------|-------------|
| **kubernetes-operations** | K8s manifests, networking, security policies, GitOps, auto-scaling |
| **cloud-infrastructure** | AWS/Azure/GCP architecture, Terraform IaC, hybrid networking, cost optimization |
| **cicd-automation** | GitHub Actions/GitLab CI setup, deployment pipeline orchestration |
| **deployment-strategies** | Deployment patterns, rollback automation, infrastructure templates |
| **deployment-validation** | Pre-deployment checks, config validation, readiness assessment |

### Operations

| Plugin | Description |
|--------|-------------|
| **incident-response** | Production incident management, triage, automated resolution |
| **error-diagnostics** | Error tracing, root cause analysis, production debugging |
| **distributed-debugging** | Distributed system tracing across microservices |
| **observability-monitoring** | Metrics, logging, distributed tracing, SLO, monitoring dashboards |

### Performance

| Plugin | Description |
|--------|-------------|
| **application-performance** | App profiling, optimization, frontend/backend observability |
| **database-cloud-optimization** | Query optimization, cloud cost optimization, scalability |

### Database

| Plugin | Description |
|--------|-------------|
| **database-design** | DB architecture, schema design, SQL optimization |
| **database-migrations** | Migration automation, observability, cross-database strategies |

### Data & AI/ML

| Plugin | Description |
|--------|-------------|
| **data-engineering** | ETL pipelines, data warehouse design, batch processing |
| **data-validation-suite** | Schema validation, data quality monitoring, streaming validation |
| **llm-application-dev** | LLM app development, prompt engineering, AI assistant optimization |
| **agent-orchestration** | Multi-agent system optimization, context management |
| **context-management** | Context persistence and restoration for long conversations |
| **machine-learning-ops** | ML training pipelines, hyperparameter tuning, MLOps, experiment tracking |

### Modernization & Refactoring

| Plugin | Description |
|--------|-------------|
| **framework-migration** | Framework updates, migration planning, architectural transformation |
| **codebase-cleanup** | Technical debt reduction, dependency updates, refactoring automation |
| **code-refactoring** | Code cleanup, refactoring automation, context restoration |

### Workflows & Collaboration

| Plugin | Description |
|--------|-------------|
| **git-pr-workflows** | Git workflow automation, PR enhancement, onboarding |
| **team-collaboration** | Issue management, standup automation, developer experience |
| **dependency-management** | Dependency auditing, version management, vuln scanning |
| **error-debugging** | Error analysis, trace debugging, multi-agent problem diagnosis |

### Documentation

| Plugin | Description |
|--------|-------------|
| **code-documentation** | Doc generation, code explanation, technical writing, tutorials |
| **documentation-generation** | OpenAPI specs, Mermaid diagrams, API reference docs |
| **c4-architecture** | C4 architecture documentation: code → component → container → context |

### Business & Marketing

| Plugin | Description |
|--------|-------------|
| **business-analytics** | Business metrics, KPI tracking, financial reporting |
| **hr-legal-compliance** | HR policies, GDPR/SOC2/HIPAA templates, employment contracts |
| **customer-sales-automation** | Customer support automation, sales pipeline, email campaigns |
| **content-marketing** | Content strategy, web research, marketing operations |
| **seo-content-creation** | SEO content writing, planning, E-E-A-T quality auditing |
| **seo-technical-optimization** | Meta tags, keywords, structure, featured snippets |
| **seo-analysis-monitoring** | Content freshness, cannibalization detection, authority building |

### Specialized

| Plugin | Description |
|--------|-------------|
| **blockchain-web3** | Solidity smart contracts, DeFi, NFT platforms, Web3 architecture |
| **quantitative-trading** | Quant analysis, algorithmic trading, portfolio risk, backtesting |
| **payment-processing** | Stripe/PayPal integration, subscription billing, PCI compliance |
| **game-development** | Unity C# scripting, Minecraft Bukkit/Spigot plugin development |
| **accessibility-compliance** | WCAG auditing, screen reader testing, keyboard navigation |

---

## 4. Slash Commands / Skills

### Core Workflow Commands

| Command | Description |
|---------|-------------|
| `/prime` | Load codebase context — analyzes README, docs, git structure for a new session |
| `/prime_tts` | Prime with TTS audio summary on completion |
| `/authorize-stop` | Authorize Claude to stop after presenting validation proof |
| `/all_tools` | List all available tools with signatures |
| `/sentient` | Extended reasoning mode |
| `/question` | Structured Q&A mode |
| `/git_status` | Show current git status summary |
| `/update_status_line` | Configure the Claude Code terminal status line |

### Crypto Research Commands

| Command | Description |
|---------|-------------|
| `/crypto_research [TICKER]` | Full crypto research using all crypto agents in parallel |
| `/crypto_research_haiku [TICKER]` | Faster crypto research using Haiku model |
| `/cook` | Comprehensive multi-agent cooking/recipe workflow |
| `/cook_research_only` | Recipe research without shopping cart operations |

---

## 5. Swarm & Orchestration Commands

### SPARC Methodology (`/sparc:*`)

Structured development phases: Specification → Pseudocode → Architecture → Refinement → Completion

| Command | Purpose |
|---------|---------|
| `/sparc:architect` | System design and architecture planning |
| `/sparc:coder` | Implementation with TDD practices |
| `/sparc:tester` | Comprehensive test writing |
| `/sparc:tdd` | Full red-green-refactor TDD workflow |
| `/sparc:researcher` | Deep research and information gathering |
| `/sparc:debugger` | Error analysis and debugging |
| `/sparc:reviewer` | Code review and quality assurance |
| `/sparc:documenter` | Documentation generation |
| `/sparc:designer` | UI/UX design workflows |
| `/sparc:optimizer` | Performance optimization |
| `/sparc:innovator` | Creative problem solving |
| `/sparc:analyzer` | Codebase analysis |
| `/sparc:architect` | Architecture decisions |
| `/sparc:memory-manager` | Persistent memory management |
| `/sparc:batch-executor` | Parallel batch task execution |
| `/sparc:workflow-manager` | Workflow orchestration |
| `/sparc:swarm-coordinator` | Multi-agent swarm coordination |

### Swarm Commands (`/swarm:*`)

| Command | Purpose |
|---------|---------|
| `/swarm` | Launch a full swarm for complex tasks |
| `/swarm:swarm-init` | Initialize swarm with topology selection |
| `/swarm:swarm-spawn` | Spawn specialized agents |
| `/swarm:swarm-monitor` | Real-time swarm progress monitoring |
| `/swarm:swarm-status` | Check swarm health and agent status |
| `/swarm:swarm-analysis` | Analyze swarm performance |
| `/swarm:swarm-modes` | View available swarm modes |
| `/swarm:swarm-strategies` | Choose swarm strategies |
| `/swarm:swarm-background` | Run swarm tasks in background |

### Hive Mind Commands (`/hive-mind:*`)

Collective intelligence with persistent shared memory across agents.

| Command | Purpose |
|---------|---------|
| `/hive-mind:hive-mind` | Launch hive mind for complex collective tasks |
| `/hive-mind:hive-mind-init` | Initialize hive mind cluster |
| `/hive-mind:hive-mind-wizard` | Guided hive mind setup |
| `/hive-mind:hive-mind-spawn` | Spawn hive mind agents |
| `/hive-mind:hive-mind-consensus` | Run consensus decision making |
| `/hive-mind:hive-mind-memory` | Manage shared hive memory |
| `/hive-mind:hive-mind-status` | Check hive health |
| `/hive-mind:hive-mind-metrics` | View performance metrics |
| `/hive-mind:hive-mind-sessions` | List and manage sessions |
| `/hive-mind:hive-mind-resume` | Resume a previous hive session |
| `/hive-mind:hive-mind-stop` | Gracefully stop hive mind |

### Coordination Commands (`/coordination:*`)

| Command | Purpose |
|---------|---------|
| `/coordination:init` | Initialize multi-agent coordination |
| `/coordination:swarm-init` | Initialize swarm via ruv-swarm MCP |
| `/coordination:agent-spawn` | Spawn a specialized agent |
| `/coordination:spawn` | Quick agent spawn |
| `/coordination:orchestrate` | Orchestrate task across agents |
| `/coordination:task-orchestrate` | Structured task orchestration |

### GitHub Commands (`/github:*`)

| Command | Purpose |
|---------|---------|
| `/github:code-review` | AI-powered code review |
| `/github:pr-enhance` | Enhance PR descriptions and details |
| `/github:issue-triage` | Triage and categorize GitHub issues |
| `/github:repo-analyze` | Analyze repository structure and quality |
| `/github:github-swarm` | Launch swarm for GitHub-wide operations |

### Automation Commands (`/automation:*`)

| Command | Purpose |
|---------|---------|
| `/automation:auto-agent` | Auto-spawn agents based on task type |
| `/automation:smart-agents` | Intelligent agent selection |
| `/automation:smart-spawn` | Smart agent spawning with context |
| `/automation:self-healing` | Self-healing workflow execution |
| `/automation:workflow-select` | Select optimal workflow for task |
| `/automation:session-memory` | Persist and restore session state |

### Monitoring Commands (`/monitoring:*`)

| Command | Purpose |
|---------|---------|
| `/monitoring:status` | Overall system status |
| `/monitoring:agents` | List all active agents |
| `/monitoring:agent-metrics` | Agent performance metrics |
| `/monitoring:real-time-view` | Live real-time monitoring dashboard |
| `/monitoring:swarm-monitor` | Monitor swarm execution |

### Workflow Commands (`/workflows:*`)

| Command | Purpose |
|---------|---------|
| `/workflows:development` | Standard development workflow |
| `/workflows:research` | Research and analysis workflow |
| `/workflows:workflow-create` | Create a custom workflow |
| `/workflows:workflow-execute` | Execute a saved workflow |
| `/workflows:workflow-export` | Export workflow for reuse |

### Memory Commands (`/memory:*`)

| Command | Purpose |
|---------|---------|
| `/memory:memory-usage` | View memory utilization |
| `/memory:memory-persist` | Persist current session to memory |
| `/memory:memory-search` | Search stored memories |
| `/memory:neural` | Neural pattern management |

### Optimization Commands (`/optimization:*`)

| Command | Purpose |
|---------|---------|
| `/optimization:topology-optimize` | Optimize swarm topology |
| `/optimization:auto-topology` | Auto-select optimal topology |
| `/optimization:parallel-execute` | Execute tasks in parallel |
| `/optimization:parallel-execution` | Parallel execution management |
| `/optimization:cache-manage` | Manage caches and memory |

### Analysis Commands (`/analysis:*`)

| Command | Purpose |
|---------|---------|
| `/analysis:token-usage` | Analyze token consumption |
| `/analysis:token-efficiency` | Token efficiency report |
| `/analysis:performance-report` | Performance analysis report |
| `/analysis:bottleneck-detect` | Detect workflow bottlenecks |

### Training Commands (`/training:*`)

| Command | Purpose |
|---------|---------|
| `/training:neural-train` | Train neural patterns from session data |
| `/training:pattern-learn` | Learn from successful patterns |
| `/training:specialization` | Specialize agent for domain |
| `/training:model-update` | Update model preferences |
| `/training:neural-patterns` | View learned neural patterns |

### Hooks Commands (`/hooks:*`)

| Command | Purpose |
|---------|---------|
| `/hooks:setup` | Configure hook system |
| `/hooks:pre-task` | Run pre-task checks |
| `/hooks:post-task` | Run post-task validation |
| `/hooks:pre-edit` | Pre-edit hook actions |
| `/hooks:post-edit` | Post-edit hook actions |
| `/hooks:session-end` | Session end procedures |

---

## 6. Utility Skills (107 total)

Fine-grained skills available via the Skill tool, organized by category.

### AgentDB (Vector Memory)
`agentdb-advanced`, `agentdb-learning`, `agentdb-memory-patterns`, `agentdb-optimization`, `agentdb-vector-search`

### AI & LLM Engineering
`embedding-strategies`, `hybrid-search-implementation`, `llm-evaluation`, `prompt-engineering-patterns`, `rag-implementation`, `similarity-search-patterns`, `vector-index-tuning`

### Architecture & Design
`api-design-principles`, `architecture-decision-records`, `architecture-patterns`, `cqrs-implementation`, `event-store-design`, `microservices-patterns`, `projection-patterns`, `saga-orchestration`

### Backend Development
`async-python-patterns`, `fastapi-templates`, `go-concurrency-patterns`, `nodejs-backend-patterns`, `rust-async-patterns`, `stream-chain`, `workflow-orchestration-patterns`, `temporal-python-testing`

### Frontend & Mobile
`nextjs-app-router-patterns`, `react-modernization`, `react-native-architecture`, `react-state-management`, `tailwind-design-system`

### Testing
`bats-testing-patterns`, `e2e-testing-patterns`, `javascript-testing-patterns`, `python-testing-patterns`, `web3-testing`, `verification-quality`, `tdd-london-swarm`

### Database & Data
`dbt-transformation-patterns`, `database-migration`, `data-quality-frameworks`, `postgresql`, `spark-optimization`, `sql-optimization-patterns`

### Security
`attack-tree-construction`, `auth-implementation-patterns`, `gdpr-data-handling`, `memory-safety-patterns`, `pci-compliance`, `sast-configuration`, `secrets-management`, `security-requirement-extraction`, `solidity-security`, `stride-analysis-patterns`, `threat-mitigation-mapping`, `wcag-audit-patterns`

### DevOps & Infrastructure
`bazel-build-optimization`, `deployment-pipeline-design`, `distributed-tracing`, `github-actions-templates`, `github-code-review`, `github-multi-repo`, `github-project-management`, `github-release-management`, `github-workflow-automation`, `gitlab-ci-patterns`, `gitops-workflow`, `helm-chart-scaffolding`, `istio-traffic-management`, `k8s-manifest-generator`, `k8s-security-policies`, `linkerd-patterns`, `mtls-configuration`, `multi-cloud-architecture`, `prometheus-configuration`, `service-mesh-observability`, `terraform-module-library`, `turborepo-caching`

### Monitoring & Observability
`grafana-dashboards`, `on-call-handoff-patterns`, `slo-implementation`

### Languages & Platforms
`agentic-jujutsu`, `airflow-dag-patterns`, `angular-migration`, `bash-defensive-patterns`, `godot-gdscript-patterns`, `hybrid-cloud-networking`, `nx-workspace-patterns`, `shellcheck-configuration`, `uv-package-manager`, `unity-ecs-patterns`

### Specialized
`backtesting-frameworks`, `billing-automation`, `changelog-automation`, `cost-optimization`, `data-storytelling`, `defi-protocol-templates`, `dependency-upgrade`, `employment-contract-templates`, `error-handling-patterns`, `kpi-dashboard-design`, `nft-standards`, `openapi-spec-generation`, `pair-programming`, `paypal-integration`, `performance-analysis`, `postmortem-writing`, `python-packaging`, `python-performance-optimization`, `risk-metrics-calculation`, `screen-reader-testing`, `skill-builder`, `sparc-methodology`, `stripe-integration`, `swarm-advanced`, `swarm-orchestration`, `typescript-advanced-types`

### ReasoningBank (Pattern Intelligence)
`reasoningbank-agentdb`, `reasoningbank-intelligence` — Persistent pattern memory with confidence scoring across sessions

---

## 7. Custom Slash Commands

High-level workflow commands that orchestrate multiple agents.

| Command | What It Does |
|---------|-------------|
| `/cook` | Full recipe research + shopping workflow using Kroger MCP |
| `/cook_research_only` | Recipe research without cart/shopping operations |
| `/crypto_research [TICKER]` | Launches all crypto agents in parallel: price check, coin analysis, market overview, movers, news scanner, investment plays, macro correlation |
| `/crypto_research_haiku [TICKER]` | Same as above using Haiku for speed/cost |
| `/prime` | Loads project context from README, git, and docs at session start |
| `/prime_tts` | Prime with ElevenLabs audio summary |
| `/authorize-stop` | Marks stop as authorized after presenting validation proof |
| `/sentient` | Activates extended thinking/reasoning mode |
| `/question` | Structured question-answering with depth |
| `/update_status_line` | Configure terminal status line display |
| `/git_status` | Summarize current git state |
| `/all_tools` | Display all tools in TypeScript signature format |

---

## 8. Agent Prompts

Pre-built agent prompts for specialized tasks (`commands/agent_prompts/`).

| Prompt | Purpose |
|--------|---------|
| `accessibility_specialist_prompt` | WCAG compliance and accessibility review |
| `api_designer_prompt` | REST/GraphQL API design |
| `api_security_prompt` | API security testing and hardening |
| `cicd_engineer_prompt` | CI/CD pipeline design and setup |
| `code_reviewer_prompt` | Comprehensive code review |
| `dast_scanner_prompt` | Dynamic application security testing |
| `data_privacy_prompt` | PII detection and GDPR/CCPA compliance |
| `database_designer_prompt` | Database schema and architecture |
| `debug_detective_prompt` | Stack trace analysis and root cause |
| `dependency_auditor_prompt` | Dependency vulnerability scanning |
| `deployment_specialist_prompt` | Deployment configuration and orchestration |
| `documentation_writer_prompt` | README, API docs, inline comments |
| `infrastructure_engineer_prompt` | Terraform, CloudFormation, cloud resources |
| `infrastructure_security_prompt` | Container/K8s/cloud security scanning |
| `monitoring_specialist_prompt` | Logging, metrics, alerting setup |
| `nodejs_security_prompt` | Node.js/JS security testing |
| `owasp_guardian_prompt` | OWASP Top 10 vulnerability analysis |
| `pattern_advisor_prompt` | Design pattern recommendations |
| `python_security_prompt` | Python-specific security testing |
| `refactoring_specialist_prompt` | Code smell detection and refactoring |
| `ruby_security_prompt` | Rails/Ruby security testing |
| `sast_orchestrator_prompt` | Multi-language static analysis orchestration |
| `secrets_detective_prompt` | Hardcoded secrets and credential detection |
| `system_architect_prompt` | System architecture design |
| `waf_rule_generator_prompt` | Web Application Firewall rule generation |
| **Crypto agents:** | |
| `crypto_coin_analyzer_agent_prompt` | Deep analysis of a specific coin |
| `crypto_investment_plays_agent_prompt` | Investment opportunities and plays |
| `crypto_market_agent_prompt` | Overall market overview |
| `crypto_movers_agent_prompt` | Top gainers/losers |
| `crypto_news_scanner_agent_prompt` | News and sentiment scanning |
| `crypto_price_check_agent_prompt` | Real-time price data |
| `macro_crypto_correlation_scanner_agent_prompt` | Macro-to-crypto correlation analysis |

---

## 9. Memory & Persistence Systems

### Claude-Mem (HTTP Memory Service)
- **Port:** 37777 | **Web UI:** http://localhost:37777
- Full-text search (FTS5), session observation storage, summarization
- Fallback: `~/.claude/data/memory/` JSON files when service unavailable
- Integrated into SessionStart, PreToolUse, PostToolUse, Stop hooks

### ReasoningBank
- Persistent pattern storage with confidence scoring
- Stores successful strategies across sessions
- Queried at session start and before tool use for context injection
- Consolidated via `npx claude-flow@alpha memory consolidate`

### PatternLearner (`hooks/utils/pattern_learner.py`)
- Tracks which patterns and approaches succeed
- Recommends strategies at session start based on history

### Session Memory (`~/.claude/data/`)
- `stop_authorization.json` — tracks stop authorization state
- `memory/` — fallback JSON memory files
- `stop_attempts.json` — logs of stop attempts

### Auto Memory (`memory/MEMORY.md`)
- User preference file updated by Claude across sessions
- Stores model preferences, workflow notes, project patterns
- Max 200 lines; additional detail in linked topic files

---

---

## 10. Swarm Recipes (Agents per Scenario)

Quick reference for which `subagent_type` values to deploy in parallel for common scenarios.

| Scenario | Agents to Deploy in Parallel |
|----------|------------------------------|
| Full-stack feature | `backend-architect`, `frontend-developer`, `test-automator`, `security-auditor`, `deployment-engineer` |
| Backend API | `backend-architect`, `tdd-orchestrator`, `sql-pro`, `backend-security-coder` |
| Security audit | `threat-modeling-expert`, `backend-security-coder`, `frontend-security-coder`, `security-auditor` |
| Performance issue | `performance-engineer`, `database-optimizer`, `observability-engineer` |
| Production incident | `incident-responder`, `devops-troubleshooter`, `error-detective` |
| Architecture docs | `c4-code` → `c4-component` → `c4-container` → `c4-context` (sequential pipeline) |
| ML pipeline | `data-scientist`, `ml-engineer`, `mlops-engineer`, `data-engineer` |
| Infra setup | `kubernetes-architect`, `terraform-specialist`, `cloud-architect` |
| Code review | `architect-review`, `code-reviewer`, `security-auditor` |
| Debugging | `debugger`, `error-detective`, `dx-optimizer` |
| Frontend feature | `frontend-developer`, `ui-ux-designer`, `ui-visual-validator`, `accessibility-specialist-sonnet` |

### SPARC Methodology — Recommended Agents per Phase

| Phase | Goal | Recommended Agents |
|-------|------|--------------------|
| **S**pecification | Clarify ALL requirements upfront | `system-architect-sonnet`, `backend-architect` |
| **P**seudocode | Plan logic before coding | `backend-architect`, `architecture` skill |
| **A**rchitecture | Design patterns and interfaces | `architect-review`, `c4-code` → `c4-component` → `c4-container` → `c4-context` |
| **R**efinement | TDD cycles (test → implement → refactor) | Language pro (`python-pro`, `typescript-pro`, etc.) + `tdd-orchestrator` |
| **C**ompletion | Validate, document, authorize stop | `test-automator`, `security-auditor`, `performance-engineer`, `docs-architect` |

### Security Agents — Proactive Deployment Triggers

| Trigger | Agent |
|---------|-------|
| New system or major architectural change | `threat-modeling-expert` |
| Adding authentication or authorization | `backend-security-coder` |
| Frontend forms, CSP, or XSS risk areas | `frontend-security-coder` |
| Mobile app security | `mobile-security-coder` |
| Pre-stop comprehensive audit | `security-auditor` |

---

*Generated from `~/.claude` configuration — 67 plugins, 107+ skills, 232 agents, 8 MCP servers*
