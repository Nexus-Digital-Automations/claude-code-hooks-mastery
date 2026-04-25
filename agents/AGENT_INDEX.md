# Agent Index — Full Catalog

Complete reference for all available agents. Use `subagent_type: <name>` in the Task tool.

> **File locations:** Language agents → `agents/languages/`, SEO agents → `agents/seo/`, all others → `agents/` root.
> Claude Code scans `agents/` recursively — subdirectory moves do not affect agent invocation.

---

## Languages

> Files: `agents/languages/*.md`

| Agent | Description |
|-------|-------------|
| `python-pro` | Python 3.12+: async, Pydantic, FastAPI, uv, ruff, mypy strict |
| `typescript-pro` | TypeScript: advanced types, generics, decorators, strict mode |
| `javascript-pro` | Modern JS: ES6+, async patterns, Node.js APIs, event loops |
| `rust-pro` | Rust 1.75+: async/tokio, ownership, axum, systems programming |
| `golang-pro` | Go 1.21+: concurrency, generics, microservices, performance |
| `java-pro` | Java 21+: virtual threads, pattern matching, Spring Boot 3.x |
| `scala-pro` | Scala: Akka/Pekko, Spark, ZIO, functional, distributed systems |
| `csharp-pro` | C# / .NET: records, pattern matching, async/await, enterprise |
| `ruby-pro` | Ruby / Rails: metaprogramming, gems, testing frameworks |
| `elixir-pro` | Elixir: OTP, supervision trees, Phoenix LiveView, BEAM |
| `php-pro` | PHP: generators, SPL, modern OOP, high-performance |
| `haskell-pro` | Haskell: type-level programming, concurrency, pure functional |
| `julia-pro` | Julia 1.10+: scientific computing, performance, multiple dispatch |
| `cpp-pro` | C++: RAII, smart pointers, templates, move semantics |
| `c-pro` | C: memory management, pointers, embedded, kernel modules |
| `bash-pro` | Bash: defensive scripting, CI/CD pipelines, system utilities |
| `posix-shell-pro` | POSIX sh: strict portability across dash/ash/sh/bash --posix |
| `flutter-expert` | Flutter/Dart 3: multi-platform, state management, animations |
| `ios-developer` | Swift/SwiftUI: iOS 18, UIKit, Core Data, App Store |
| `arm-cortex-expert` | ARM Cortex-M: firmware, drivers, DMA, interrupts, embedded |

---

## Backend / API

| Agent | Description |
|-------|-------------|
| `backend-architect` | Scalable API design, microservices, REST/GraphQL/gRPC, event-driven |
| `graphql-architect` | GraphQL federation, performance optimization, enterprise security |
| `fastapi-pro` | FastAPI: async views, SQLAlchemy 2.0, Pydantic V2, WebSockets |
| `django-pro` | Django 5.x: async views, DRF, Celery, Channels, ORM optimization |
| `api-designer-sonnet` | REST/GraphQL API specs, endpoint structure, versioning, OpenAPI |

---

## Frontend / Mobile

| Agent | Description |
|-------|-------------|
| `frontend-developer` | React 19, Next.js 15, responsive layouts, client-side state |
| `ui-ux-designer` | Design systems, wireframes, design tokens, accessibility |
| `ui-visual-validator` | Visual regression, screenshot analysis, design system compliance |
| `mobile-developer` | React Native / Flutter: cross-platform, native integrations, offline |
| `flutter-expert` | Flutter: Dart 3, widgets, state management, multi-platform |
| `ios-developer` | Native iOS: Swift, SwiftUI, UIKit, Core Data |
| `accessibility-specialist-sonnet` | WCAG compliance, ARIA, keyboard nav, screen reader compatibility |

---

## Infrastructure / DevOps

| Agent | Description |
|-------|-------------|
| `kubernetes-architect` | K8s: GitOps, ArgoCD/Flux, service mesh, EKS/AKS/GKE, multi-tenancy |
| `terraform-specialist` | Terraform/OpenTofu: IaC, state management, multi-cloud, GitOps |
| `cloud-architect` | AWS/Azure/GCP: multi-cloud, FinOps, serverless, disaster recovery |
| `hybrid-cloud-architect` | Hybrid/multi-cloud: workload placement, edge computing, compliance |
| `infrastructure-engineer-sonnet` | Terraform configs, CloudFormation, networking, auto-scaling |
| `deployment-engineer` | CI/CD, GitOps, zero-downtime deployments, progressive delivery |
| `cicd-engineer-sonnet` | GitHub Actions, GitLab CI, CircleCI, automated testing pipelines |
| `network-engineer` | Cloud networking, zero-trust, SSL/TLS, CDN, load balancing |

---

## Security

| Agent | Description |
|-------|-------------|
| `security-auditor` | DevSecOps, vulnerability assessment, OWASP, threat modeling |
| `backend-security-coder` | Secure backend: input validation, authentication, API security |
| `frontend-security-coder` | XSS prevention, output sanitization, client-side security |
| `mobile-security-coder` | Mobile security: WebView, input validation, mobile-specific patterns |
| `owasp-guardian-sonnet` | OWASP Top 10 analysis: injection, XSS, broken auth, misconfig |
| `sast-orchestrator-sonnet` | Multi-language SAST: Semgrep, CodeQL, SonarQube, Bearer, Horusec |
| `dast-scanner-sonnet` | Dynamic testing: OWASP ZAP, runtime vulnerabilities, API scanning |
| `api-security-sonnet` | REST/GraphQL API security: auth, rate limiting, injection |
| `secrets-detective-sonnet` | Hardcoded secrets detection: API keys, tokens, credentials |
| `dependency-auditor-sonnet` | Dependency vulnerabilities: npm audit, pip-audit, Snyk |
| `waf-rule-generator-sonnet` | WAF rules: ModSecurity rules from detected vulnerabilities |
| `infrastructure-security-sonnet` | Container/K8s security: Trivy, Docker Bench, CIS benchmarks |
| `nodejs-security-sonnet` | Node.js/JS security: eslint-security, NodeJsScan, npm audit |
| `python-security-sonnet` | Python security: Bandit, pip-audit, Semgrep, safety |
| `ruby-security-sonnet` | Ruby/Rails security: Brakeman, bundler-audit, Semgrep |
| `data-privacy-sonnet` | PII handling, GDPR/CCPA compliance, Bearer data analysis |

---

## Data / ML / AI

| Agent | Description |
|-------|-------------|
| `data-scientist` | Analytics, ML modeling, statistical analysis, business intelligence |
| `ml-engineer` | Production ML: PyTorch, TensorFlow, model serving, A/B testing |
| `mlops-engineer` | MLOps: MLflow, Kubeflow, training pipelines, model registry |
| `data-engineer` | Data pipelines: Spark, dbt, Airflow, cloud-native data platforms |
| `ai-engineer` | LLM applications, RAG systems, vector search, agent orchestration |
| `prompt-engineer` | Prompting techniques, chain-of-thought, constitutional AI, LLM optimization |

---

## Database

| Agent | Description |
|-------|-------------|
| `database-architect` | Schema design, technology selection, data modeling, migrations |
| `database-optimizer` | Query optimization, indexing, N+1 resolution, caching, partitioning |
| `database-designer-sonnet` | Schema design, indexes, relationships, integrity constraints |
| `database-admin` | Cloud databases, HA/DR, performance tuning, compliance |
| `sql-pro` | Advanced SQL: OLTP/OLAP, cloud-native databases, query optimization |

---

## Testing / Quality

| Agent | Description |
|-------|-------------|
| `test-automator` | Test automation: frameworks, self-healing tests, CI/CD integration |
| `tdd-orchestrator` | TDD: red-green-refactor, test-first discipline, multi-agent TDD |
| `test-engineer-sonnet` | Unit, integration, E2E tests, coverage improvement |
| `test-coverage-analyzer` | Coverage analysis, untested paths, edge cases, priority ranking |
| `architect-review` | Architecture review: clean architecture, DDD, microservices patterns |
| `code-reviewer` | Code quality: security, performance, production reliability |
| `code-reviewer-sonnet` | Readability, maintainability, bugs, best practices analysis |
| `superpowers:code-reviewer` | Elite code review with AI-powered analysis |
| `performance-engineer` | OpenTelemetry, distributed tracing, load testing, Core Web Vitals |
| `performance-optimizer` | Performance bottleneck identification across all stack layers |

---

## Ops / Reliability

| Agent | Description |
|-------|-------------|
| `incident-responder` | SRE incident response, blameless post-mortems, error budget |
| `devops-troubleshooter` | Rapid debugging, log analysis, Kubernetes debugging, root cause |
| `observability-engineer` | Monitoring, logging, tracing, SLI/SLO, incident response workflows |
| `error-detective` | Log/codebase error pattern search, stack trace correlation |
| `debugger` | Debugging specialist: errors, test failures, unexpected behavior |
| `debug-detective-sonnet` | Stack trace analysis, root cause identification, fix suggestions |
| `monitoring-specialist-sonnet` | Winston/Bunyan logging, Prometheus/Grafana, distributed tracing |

---

## Documentation

| Agent | Description |
|-------|-------------|
| `docs-architect` | Comprehensive technical docs: architecture guides, technical manuals |
| `tutorial-engineer` | Step-by-step tutorials: progressive learning, hands-on examples |
| `mermaid-expert` | Mermaid diagrams: flowcharts, sequence, ERD, architecture |
| `smart-doc-generator` | Auto-generate docs from source: README, API docs, changelogs |
| `documentation-writer-sonnet` | READMEs, API docs, inline comments, architecture docs |
| `api-documenter` | OpenAPI 3.1, interactive docs, SDK generation, developer portals |
| `c4-code` | C4 code-level docs: function signatures, dependencies, structure |
| `c4-component` | C4 component-level: component boundaries, interfaces, relationships |
| `c4-container` | C4 container-level: deployment units, container interfaces, APIs |
| `c4-context` | C4 context-level: system diagrams, personas, external dependencies |

---

## Finance / Business

| Agent | Description |
|-------|-------------|
| `quant-analyst` | Financial models, backtesting, risk metrics, statistical arbitrage |
| `risk-manager` | Portfolio risk, R-multiples, hedging strategies, stop-losses |
| `payment-integration` | Stripe/PayPal, checkout flows, subscriptions, PCI compliance |
| `business-analyst` | KPI frameworks, predictive models, strategic recommendations |
| `legal-advisor` | Privacy policies, ToS, GDPR, data processing agreements |
| `hr-pro` | Hiring, onboarding, PTO, performance, compliant HR policies |

---

## Marketing / SEO

> SEO agent files: `agents/seo/*.md`

| Agent | Description |
|-------|-------------|
| `seo-content-writer` | SEO-optimized content: keywords, engagement, best practices |
| `seo-meta-optimizer` | Meta titles, descriptions, URL suggestions, keyword-rich metadata |
| `seo-structure-architect` | Header hierarchy, schema markup, internal linking, content organization |
| `seo-keyword-strategist` | Keyword density, semantic variations, LSI keywords, optimization |
| `seo-cannibalization-detector` | Keyword overlap detection, differentiation strategies |
| `seo-content-auditor` | Content quality, E-E-A-T signals, scoring, improvement recommendations |
| `seo-authority-builder` | E-E-A-T improvements, credibility elements, trust signals |
| `seo-snippet-hunter` | Featured snippet formatting, SERP feature optimization |
| `seo-content-refresher` | Outdated content identification, statistics/date updates |
| `seo-content-planner` | Content outlines, topic clusters, content calendars, gap analysis |
| `content-marketer` | AI-powered content creation, omnichannel distribution, conversion |
| `sales-automator` | Cold emails, follow-ups, proposal templates, sales scripts |
| `customer-support` | Conversational AI, automated ticketing, sentiment analysis |

---

## Blockchain / Web3

| Agent | Description |
|-------|-------------|
| `blockchain-developer` | Smart contracts, DeFi protocols, NFT platforms, DAOs, Web3 apps |

---

## Legacy / DX

| Agent | Description |
|-------|-------------|
| `legacy-modernizer` | Legacy refactoring, framework migration, technical debt reduction |
| `dx-optimizer` | Developer experience, tooling, setup, workflow improvements |
| `refactoring-specialist-sonnet` | Code smell identification, complexity reduction, design patterns |

---

## Core Generalists

| Agent | Description |
|-------|-------------|
| `coder` | Implementation specialist: clean, efficient code |
| `researcher` | Deep research and information gathering |
| `reviewer` | Code review and quality assurance |
| `tester` | Comprehensive testing and quality assurance |
| `planner` | Strategic planning and task orchestration |
| `debugger` | Debugging specialist for errors and unexpected behavior |
| `system-architect-sonnet` | System architecture, component relationships, tech stack selection |

---

## Swarm / Coordination

| Agent | Description |
|-------|-------------|
| `adaptive-coordinator` | Dynamic topology switching, self-organizing swarm patterns |
| `hierarchical-coordinator` | Queen-led hierarchical swarm with specialized worker delegation |
| `mesh-coordinator` | Peer-to-peer mesh network with distributed decision making |
| `task-orchestrator` | Central coordination: task decomposition, execution, result synthesis |
| `goal-planner` | GOAP specialist: dynamic plans for complex multi-step objectives |
| `code-goal-planner` | Code-centric GOAP: software development milestones and criteria |
| `sparc-coord` | SPARC methodology orchestrator for systematic development phases |

---

## Scenario → Agent Mapping (Quick Reference)

| Task | Recommended Agents |
|------|--------------------|
| Full-stack feature | `backend-architect`, `frontend-developer`, `test-automator`, `security-auditor` |
| Backend API | `backend-architect`, `fastapi-pro`/`django-pro`, `sql-pro`, `backend-security-coder` |
| Security audit | `security-auditor`, `owasp-guardian-sonnet`, `sast-orchestrator-sonnet` |
| Performance issue | `performance-engineer`, `database-optimizer`, `observability-engineer` |
| Production incident | `incident-responder`, `devops-troubleshooter`, `error-detective` |
| ML pipeline | `data-scientist`, `ml-engineer`, `mlops-engineer` |
| Infra setup | `kubernetes-architect`, `terraform-specialist`, `cloud-architect` |
| Code review | `architect-review`, `code-reviewer`, `security-auditor` |
| Debugging | `debugger`, `error-detective`, `debug-detective-sonnet` |
| Frontend feature | `frontend-developer`, `ui-ux-designer`, `ui-visual-validator`, `accessibility-specialist-sonnet` |
| Architecture docs | `c4-code` → `c4-component` → `c4-container` → `c4-context` (sequential) |
