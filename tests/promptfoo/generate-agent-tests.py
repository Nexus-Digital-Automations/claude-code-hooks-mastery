#!/usr/bin/env python3
"""
Generate promptfoo test configs for all Claude Code sub-agents.

Groups agents by category and creates one YAML config per category.
Each agent is tested with 2-3 representative tasks using LLM-rubric grading.

Usage:
    python3 tests/promptfoo/generate-agent-tests.py [--dry-run] [--category CATEGORY]
"""

import re
import sys
import yaml
import json
import argparse
from pathlib import Path

ROOT = Path.home() / ".claude"
AGENTS_DIR = ROOT / "agents"
SKILLS_DIR = ROOT / "skills"
OUTPUT_DIR = ROOT / "tests" / "promptfoo"

# ── Deepseek provider config ─────────────────────────────────────────────────
DEEPSEEK_PROVIDER = {
    "id": "openai:chat:deepseek-chat",
    "config": {
        "apiBaseUrl": "https://api.deepseek.com",
        "apiKeyEnvar": "DEEPSEEK_API_KEY",
        "max_tokens": 1500,
        "temperature": 0.0,
    },
}

DEEPSEEK_GRADER = {
    "id": "openai:chat:deepseek-chat",
    "config": {
        "apiBaseUrl": "https://api.deepseek.com",
        "apiKeyEnvar": "DEEPSEEK_API_KEY",
    },
}

# ── Test cases per agent/category ────────────────────────────────────────────
# Maps agent name → list of (task, rubric, threshold)
AGENT_TESTS = {
    # Language agents
    "python-pro": [
        ("Write an async Python function that fetches multiple URLs concurrently with timeout handling and retries",
         "Response uses modern asyncio patterns, proper type hints, error handling, and is production-quality Python 3.12+",
         0.7),
        ("How would you configure ruff and mypy strict mode for a new Python project?",
         "Provides pyproject.toml or config file content for ruff, mentions mypy or type checking configuration, shows specific rules or settings",
         0.6),
    ],
    "typescript-pro": [
        ("Create a TypeScript generic utility type that makes all nested object properties optional",
         "Response demonstrates deep TypeScript type system knowledge, uses proper generic constraints, and the type works correctly",
         0.7),
        ("Write a TypeScript decorator for method memoization with TTL support",
         "Uses proper TypeScript decorator syntax, handles method metadata correctly, TypeScript strict mode compatible",
         0.7),
    ],
    "rust-pro": [
        ("Write a Rust async TCP server using tokio with connection pooling and graceful shutdown",
         "Uses modern tokio async/await patterns, proper Rust error handling (anyhow/thiserror or custom errors), correct ownership semantics with Arc/Mutex where needed",
         0.6),
        ("Explain the difference between Arc<Mutex<T>> and RefCell<T> and when to use each",
         "Accurately explains thread safety, runtime vs compile-time borrowing, and gives concrete examples",
         0.7),
    ],
    "golang-pro": [
        ("Write a Go HTTP server with graceful shutdown and structured logging using slog",
         "Uses modern Go 1.21+ patterns, context cancellation, slog structured logging, proper error handling",
         0.7),
        ("How do you implement a worker pool pattern in Go for processing concurrent tasks?",
         "Uses goroutines and channels correctly, handles context cancellation, uses WaitGroup or similar synchronization",
         0.6),
    ],
    "java-pro": [
        ("Write a Java 21 virtual threads-based HTTP server that handles 10,000 concurrent connections",
         "Uses Project Loom virtual threads correctly, structured concurrency, modern Java 21+ patterns",
         0.7),
    ],
    "javascript-pro": [
        ("Write a JavaScript event emitter class with proper memory leak prevention and TypeScript-compatible JSDoc",
         "Uses modern ES6+ class syntax, handles edge cases, includes proper cleanup, has useful JSDoc",
         0.7),
    ],
    "bash-pro": [
        ("Write a defensive bash script that backs up a directory with rotation, error handling, and logging",
         "Uses set -euo pipefail, proper quoting, error handling, logging to stderr, and safe temp files",
         0.7),
    ],
    "csharp-pro": [
        ("Write a C# record type hierarchy for a domain model with validation using a Result<T> pattern",
         "Uses modern C# records, pattern matching, and clean error handling without exceptions for domain errors",
         0.7),
    ],
    # Backend/architecture agents
    "backend-architect": [
        ("Design a microservices architecture for an e-commerce platform with order management, inventory, and payments",
         "Defines service boundaries using DDD, explains inter-service communication, mentions resilience patterns like circuit breakers",
         0.7),
        ("What are the trade-offs between synchronous REST and asynchronous event-driven communication in microservices?",
         "Provides specific trade-offs, mentions eventual consistency, gives guidance on when to use each approach",
         0.7),
    ],
    "graphql-architect": [
        ("Design a GraphQL schema for a social platform with users, posts, comments, and real-time notifications",
         "Shows GraphQL schema with types for users, posts, and comments. Includes at least queries and types (mutations/subscriptions a bonus)",
         0.6),
    ],
    "fastapi-pro": [
        ("Create a FastAPI endpoint with JWT authentication, request validation, and background tasks",
         "Uses FastAPI's Depends() for auth, Pydantic models for validation, BackgroundTasks, proper HTTP status codes",
         0.7),
    ],
    # Security agents
    "security-auditor": [
        ("Review this authentication code for security vulnerabilities: `def login(user, pwd): return db.query(f'SELECT * FROM users WHERE username={user} AND password={pwd}')`",
         "Identifies SQL injection, missing password hashing, recommends parameterized queries and bcrypt/argon2",
         0.8),
        ("What are the top 3 security issues to check when reviewing a REST API that handles sensitive data?",
         "Mentions authentication/authorization, input validation, rate limiting, proper TLS, and data encryption at rest",
         0.7),
    ],
    "threat-modeling-expert": [
        ("Perform a STRIDE threat model for a web app with user authentication, file uploads, and payment processing",
         "Applies STRIDE categories (Spoofing, Tampering, Repudiation, Info Disclosure, DoS, Elevation) to the system components",
         0.7),
    ],
    "backend-security-coder": [
        ("Show me secure code patterns for handling user file uploads in a Node.js/Express application",
         "Covers at least 3 of: file type validation, size limits, safe storage path, sanitized filenames, malware scanning. Shows secure coding patterns",
         0.6),
    ],
    # Database agents
    "database-architect": [
        ("Design a PostgreSQL schema for a multi-tenant SaaS application with row-level security",
         "Uses proper schema design, row-level security policies, tenant isolation, indexing strategy",
         0.7),
    ],
    "database-optimizer": [
        ("This query is slow: SELECT * FROM orders JOIN order_items ON orders.id = order_items.order_id WHERE orders.created_at > '2024-01-01'. How do you optimize it?",
         "Identifies missing indexes, suggests composite index, mentions EXPLAIN ANALYZE, avoids SELECT *, suggests specific columns",
         0.7),
    ],
    "sql-pro": [
        ("Write an optimized SQL query to find the top 10 customers by revenue in the last 90 days with their order count",
         "Uses window functions or GROUP BY correctly, date arithmetic, proper joins, efficient indexing hints",
         0.7),
    ],
    # Infrastructure agents
    "kubernetes-architect": [
        ("Design a Kubernetes deployment for a stateful application with horizontal pod autoscaling and persistent storage",
         "Covers at least 3 of: StatefulSet or Deployment, HPA configuration, persistent storage (PVC/StorageClass), health probes, or resource limits. Shows production-quality K8s knowledge",
         0.6),
    ],
    "terraform-specialist": [
        ("Write a Terraform module for an AWS EKS cluster with node groups and IAM roles",
         "Proper Terraform module structure, uses variables/outputs, IAM IRSA pattern, EKS managed node groups",
         0.7),
    ],
    "cloud-architect": [
        ("Design a multi-region active-active architecture for a web application on AWS with < 100ms latency",
         "Covers at least 3 of: Route53 routing, CloudFront/CDN, multi-region data replication, latency optimization, high availability design",
         0.6),
    ],
    # Testing agents
    "test-automator": [
        ("Write a comprehensive Playwright E2E test for a login flow with 2FA, error handling, and visual regression",
         "Uses Playwright best practices, page objects, handles both success and failure cases, screenshot comparison",
         0.7),
    ],
    "tdd-orchestrator": [
        ("Show me the TDD cycle for implementing a shopping cart with add/remove/total functionality in Python",
         "Demonstrates red-green-refactor cycle, starts with failing test, implements minimum code, refactors, proper assertions",
         0.7),
    ],
    # DevOps/operations agents
    "deployment-engineer": [
        ("Design a zero-downtime deployment strategy for a stateful PostgreSQL-backed API on Kubernetes",
         "Covers rolling updates, DB migration strategy, health checks, rollback procedure, blue-green or canary option",
         0.7),
    ],
    "devops-troubleshooter": [
        ("Our API response times increased from 50ms to 2000ms after deploying a new version. Walk me through the debugging process.",
         "Systematic approach: check metrics, logs, traces; identify bottlenecks; correlate with deployment changes; suggests tools like Jaeger/DataDog",
         0.7),
    ],
    "incident-responder": [
        ("We have a P1 incident: our payment service is returning 500 errors for 20% of transactions. Lead the incident response.",
         "Follows incident command structure, immediate mitigation steps, communication plan, investigation, escalation criteria",
         0.7),
    ],
    # AI/ML agents
    "ai-engineer": [
        ("Build a RAG (Retrieval Augmented Generation) pipeline for querying internal documentation",
         "Mentions at least 3 of: embedding model, vector store, chunking, retrieval strategy, prompt engineering. Shows practical implementation knowledge",
         0.6),
    ],
    "data-scientist": [
        ("Analyze a dataset for churn prediction. What features would you engineer and what model would you choose?",
         "Covers feature engineering ideas for churn (behavioral/temporal signals), discusses at least one model type with reasoning, mentions model evaluation approach",
         0.6),
    ],
    # Documentation agents
    "docs-architect": [
        ("Create a documentation architecture for a large open-source project with API docs, tutorials, and reference guides",
         "Covers documentation structure with clear sections (tutorials, how-tos, reference), considers audience/user journey, addresses organization and navigation",
         0.6),
    ],
    "mermaid-expert": [
        ("Create a Mermaid sequence diagram for a JWT authentication flow with refresh tokens",
         "Valid Mermaid syntax, covers login, token issuance, API request with bearer token, refresh flow, logout",
         0.7),
    ],
    # Frontend agents
    "frontend-developer": [
        ("Implement a React component for an infinite scroll list with virtualization and loading states",
         "Uses React hooks correctly, implements virtualization (react-virtual or similar), handles loading/error/empty states",
         0.7),
    ],
    # Specialized agents
    "prompt-engineer": [
        ("Write a chain-of-thought system prompt for a customer support agent that handles refund requests",
         "Produces a structured system prompt with chain-of-thought reasoning steps, covers edge cases, uses proper prompt engineering technique",
         0.6),
    ],
    "architect-review": [
        ("Review this architecture: a Python Flask monolith with SQLAlchemy, Celery for async tasks, and Redis for caching. Should we migrate to microservices?",
         "Provides balanced analysis of monolith vs microservices trade-offs, asks clarifying questions about scale/team size, gives conditional recommendation",
         0.7),
    ],
    # Business/other agents
    "business-analyst": [
        ("Build a business case for migrating from on-premises servers to AWS cloud infrastructure",
         "Covers at least 3 of: cost/TCO analysis, migration risks, business benefits, ROI metrics, timeline. Structured business case format",
         0.6),
    ],
    "legal-advisor": [
        ("Draft a privacy policy section covering data collection and user rights for a B2C mobile app",
         "Covers data types collected, mentions at least 2 user rights (access/deletion/portability/opt-out), references privacy regulations (GDPR or CCPA)",
         0.6),
    ],
    # SEO agents
    "seo-content-writer": [
        ("Write an SEO-optimized introduction for a blog post about 'Python async programming best practices'",
         "Includes target keyword naturally, compelling hook, indicates search intent, meta-description ready length",
         0.7),
    ],
    "seo-meta-optimizer": [
        ("Write an SEO title and meta description for a page about 'Kubernetes deployment best practices 2024'",
         "Title under 60 chars, meta under 160 chars, includes primary keyword, compelling CTA, unique value prop",
         0.7),
    ],
    # Security - delegation agents
    "owasp-guardian-sonnet": [
        ("Review this Express.js route for OWASP Top 10 vulnerabilities: app.get('/user', req => db.query('SELECT * FROM users WHERE id=' + req.query.id))",
         "Identifies SQL injection (A03), missing authentication (A01), recommends parameterized queries and auth middleware",
         0.7),
    ],
    "python-security-sonnet": [
        ("Scan this Python Flask endpoint for security issues: it passes user input directly to subprocess.run() and stores passwords without hashing",
         "Identifies command injection via subprocess, insecure password storage, recommends safe alternatives for both",
         0.7),
    ],
    "secrets-detective-sonnet": [
        ("Check this config file for exposed secrets: API_KEY = 'sk-1234567890abcdef' and db_url = 'postgresql://admin:password123@localhost/prod'",  # nosec
         "Detects hardcoded API key and database credentials with password, suggests environment variables or secrets manager",
         0.7),
    ],
    # Code quality agents
    "code-reviewer": [
        ("Review this Python function: `def process(data): result = []; [result.append(x*2) for x in data if x > 0]; return result`",
         "Identifies list comprehension misuse, suggests cleaner alternatives, mentions performance, checks for edge cases",
         0.7),
    ],
    "refactoring-specialist-sonnet": [
        ("Refactor this deeply nested if-else block into a cleaner pattern:\nif condition1:\n  if condition2:\n    if condition3:\n      do_something()\n    else:\n      do_other()\n  else:\n    fallback()\nelse:\n  default()",
         "Suggests early returns / guard clauses, or strategy pattern, or table-driven approach — with actual code",
         0.7),
    ],
    # C4 architecture agents
    "c4-code": [
        ("Generate C4 Code-level documentation for a Python FastAPI authentication module with JWT handling",
         "Documents code structure at function/class level, shows dependencies and relationships between components, organized and readable",
         0.6),
    ],
}

# ── Category groupings for YAML configs ───────────────────────────────────────
CATEGORIES = {
    "06-language-agents": [
        "python-pro", "typescript-pro", "rust-pro", "golang-pro",
        "java-pro", "javascript-pro", "bash-pro", "csharp-pro",
    ],
    "07-security-agents": [
        "security-auditor", "threat-modeling-expert", "backend-security-coder",
        "owasp-guardian-sonnet", "python-security-sonnet", "secrets-detective-sonnet",
    ],
    "08-architecture-agents": [
        "backend-architect", "graphql-architect", "fastapi-pro",
        "database-architect", "database-optimizer", "sql-pro",
        "cloud-architect", "kubernetes-architect", "terraform-specialist",
    ],
    "09-quality-testing-agents": [
        "test-automator", "tdd-orchestrator", "code-reviewer",
        "refactoring-specialist-sonnet", "architect-review",
    ],
    "10-operations-ai-agents": [
        "deployment-engineer", "devops-troubleshooter", "incident-responder",
        "ai-engineer", "data-scientist", "docs-architect", "mermaid-expert",
        "frontend-developer", "prompt-engineer", "business-analyst",
        "legal-advisor", "seo-content-writer", "seo-meta-optimizer",
        "c4-code",
    ],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def find_agent_file(agent_name: str) -> Path | None:
    """Find the .md file for a given agent name by scanning the agents dir."""
    for path in AGENTS_DIR.rglob("*.md"):
        content = path.read_text(encoding="utf-8", errors="replace")
        # Check frontmatter name field
        if content.startswith("---"):
            end_idx = content.find("\n---", 3)
            if end_idx > 0:
                fm_text = content[3:end_idx]
                for line in fm_text.splitlines():
                    if line.strip().startswith("name:"):
                        val = line.split(":", 1)[1].strip().strip('"').strip("'")
                        if val.lower() == agent_name.lower():
                            return path
        else:
            # No frontmatter — check if filename matches
            stem = path.stem.lower().replace("_", "-")
            if stem == agent_name.lower().replace("_", "-"):
                return path
    return None


def resolve_delegation_prompt(path: Path) -> Path | None:
    """If agent delegates via 'Read and Execute: <path>', resolve the target.

    Paths use '.claude/...' meaning they're relative to ~/ (not ~/.claude/).
    """
    content = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Read and Execute:\s*(.+\.md)", content)
    if not m:
        return None
    rel = m.group(1).strip()
    # Paths like '.claude/commands/agent_prompts/foo.md'
    # Path.home() / '.claude/...' resolves to ~/.claude/... correctly
    candidate = Path.home() / rel
    if candidate.exists():
        return candidate
    # Generic fallback
    for base in [ROOT, Path.home()]:
        c = base / rel.lstrip("./")
        if c.exists():
            return c
    return None


def load_agent_system_prompt(path: Path, max_chars: int = 2000) -> str:
    """Load and clean agent file, returning the system prompt body.

    Handles:
    - Standard agents with frontmatter + body
    - Delegation agents that say 'Read and Execute: <path>'
    - Plugin templates without frontmatter
    """
    content = path.read_text(encoding="utf-8", errors="replace")

    # Strip frontmatter
    if content.startswith("---"):
        end_idx = content.find("\n---", 3)
        if end_idx > 0:
            body = content[end_idx + 4:].strip()
        else:
            body = content
    else:
        body = content

    # If this is a delegation agent, load the actual prompt file
    if re.search(r"Read and Execute:\s*.+\.md", body):
        target = resolve_delegation_prompt(path)
        if target and target.exists():
            body = target.read_text(encoding="utf-8", errors="replace")
        else:
            # Strip the delegation line and use the rest
            body = re.sub(r"Read and Execute:.*\n?", "", body)

    # Remove Memory/Coordination boilerplate injected by hooks
    body = re.sub(r"\n## Memory & Coordination Integration.*", "", body, flags=re.DOTALL)
    body = re.sub(r"\n---\n$", "", body)

    # Truncate to max_chars, at a paragraph boundary if possible
    body = body.strip()
    if len(body) > max_chars:
        truncated = body[:max_chars]
        last_newline = truncated.rfind("\n")
        if last_newline > max_chars * 0.7:
            truncated = truncated[:last_newline]
        body = truncated + "\n\n[... truncated ...]"

    return body.strip()


def build_prompt_template(system_prompt: str) -> str:
    """Build a chat-format prompt template."""
    # Escape any special YAML characters in the system prompt
    return json.dumps([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "{{task}}"},
    ], ensure_ascii=False)


def build_per_agent_yaml(agent_name: str) -> dict | None:
    """Build a promptfoo YAML for a SINGLE agent with its specific tests.

    Using a single prompt avoids the cross-product matrix problem where
    unrelated tests are run against wrong agents.
    """
    path = find_agent_file(agent_name)
    if not path:
        print(f"  ⚠️  Agent not found: {agent_name}", file=sys.stderr)
        return None

    system_prompt = load_agent_system_prompt(path)
    if not system_prompt or len(system_prompt) < 50:
        print(f"  ⚠️  Empty/thin system prompt for: {agent_name}", file=sys.stderr)
        return None

    test_cases = AGENT_TESTS.get(agent_name, [(
        "Demonstrate your core capabilities with a challenging, real-world task in your domain",
        f"Response demonstrates specific expertise of a {agent_name}, with actionable and domain-appropriate output",
        0.6,
    )])

    tests = []
    for i, (task, rubric, threshold) in enumerate(test_cases):
        tests.append({
            "description": f"[{i+1}] {task[:80]}",
            "vars": {"task": task},
            "assert": [{
                "type": "llm-rubric",
                "value": rubric,
                "threshold": threshold,
                "metric": f"{agent_name}_quality",
            }],
        })

    return {
        "description": f"Agent quality: {agent_name}",
        "providers": [DEEPSEEK_PROVIDER],
        "defaultTest": {"options": {"provider": DEEPSEEK_GRADER}},
        "prompts": [{
            "label": agent_name,
            "raw": build_prompt_template(system_prompt),
        }],
        "tests": tests,
    }


def write_yaml(config: dict, output_path: Path):
    """Write config to YAML file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        # Write description as comment at top
        f.write(f"# {config.get('description', '')}\n\n")
        # Use safe_dump with allow_unicode
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True,
                  sort_keys=False, width=120)
    print(f"  ✅ Written: {output_path}")


SKILL_TESTS = [
    {
        "name": "python-testing-patterns",
        "task": "Show me how to write parameterized pytest tests with fixtures for a database model",
        "rubric": "Demonstrates pytest.mark.parametrize usage, defines at least one fixture, shows actual test code with assertions",
        "threshold": 0.6,
    },
    {
        "name": "code-review-excellence",
        "task": "What is the code review checklist for a new PR adding a REST API endpoint?",
        "rubric": "Provides specific checklist items covering at least 3 of: security, error handling, tests, documentation, performance",
        "threshold": 0.6,
    },
    {
        "name": "architecture-patterns",
        "task": "When should I use CQRS pattern vs a simple CRUD approach for a new service?",
        "rubric": "Gives specific decision criteria with pros/cons, mentions when CQRS adds value vs overhead",
        "threshold": 0.6,
    },
    {
        "name": "debugging-strategies",
        "task": "Walk me through debugging a memory leak in a Node.js production application",
        "rubric": "Provides systematic debugging steps, mentions at least 2 specific tools or techniques (heap snapshots, profiler, etc.)",
        "threshold": 0.6,
    },
]


def build_per_skill_yaml(skill_name: str, task: str, rubric: str, threshold: float) -> dict | None:
    """Build a promptfoo YAML for a SINGLE skill with its specific test."""
    skill_dir = SKILLS_DIR / skill_name
    if not skill_dir.exists():
        print(f"  ⚠️  Skill not found: {skill_name}", file=sys.stderr)
        return None

    skill_md = skill_dir.resolve() / "SKILL.md"
    if not skill_md.exists():
        print(f"  ⚠️  No SKILL.md for: {skill_name}", file=sys.stderr)
        return None

    system_prompt = load_agent_system_prompt(skill_md, max_chars=4000)
    if not system_prompt or len(system_prompt) < 50:
        return None

    return {
        "description": f"Skill quality: {skill_name}",
        "providers": [DEEPSEEK_PROVIDER],
        "defaultTest": {"options": {"provider": DEEPSEEK_GRADER}},
        "prompts": [{"label": skill_name, "raw": build_prompt_template(system_prompt)}],
        "tests": [{
            "description": f"skill/{skill_name}: {task[:60]}",
            "vars": {"task": task},
            "assert": [{
                "type": "llm-rubric",
                "value": rubric,
                "threshold": threshold,
                "metric": f"skill_{skill_name}_quality",
            }],
        }],
    }


def main():
    parser = argparse.ArgumentParser(description="Generate promptfoo test configs for agents")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be generated")
    parser.add_argument("--agent", help="Only generate for specific agent name")
    args = parser.parse_args()

    print("Generating per-agent promptfoo test configs...", file=sys.stderr)

    agents_output_dir = OUTPUT_DIR / "agents"
    agents_output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    skipped = []

    agents_to_run = [args.agent] if args.agent else list(AGENT_TESTS.keys())

    for agent_name in agents_to_run:
        print(f"\n🤖 {agent_name}", file=sys.stderr)
        config = build_per_agent_yaml(agent_name)
        if not config:
            skipped.append(agent_name)
            continue

        output_path = agents_output_dir / f"{agent_name}.yaml"

        if args.dry_run:
            print(f"  Would write: {output_path}", file=sys.stderr)
            print(f"  Tests: {len(config['tests'])}", file=sys.stderr)
        else:
            write_yaml(config, output_path)
            print(f"  Tests: {len(config['tests'])}", file=sys.stderr)
            generated.append(output_path)

    # Generate per-skill configs
    skills_output_dir = OUTPUT_DIR / "skills"
    skills_output_dir.mkdir(parents=True, exist_ok=True)

    print("\n📚 Skills", file=sys.stderr)
    for skill_test in SKILL_TESTS:
        sname = skill_test["name"]
        if args.agent and sname != args.agent:
            continue
        print(f"\n🔧 {sname}", file=sys.stderr)
        config = build_per_skill_yaml(sname, skill_test["task"], skill_test["rubric"], skill_test["threshold"])
        if not config:
            skipped.append(f"skill:{sname}")
            continue
        output_path = skills_output_dir / f"{sname}.yaml"
        if args.dry_run:
            print(f"  Would write: {output_path}", file=sys.stderr)
        else:
            write_yaml(config, output_path)
            generated.append(output_path)

    print(f"\n✅ Generated: {len(generated)} configs ({len([g for g in generated if 'agents' in str(g)])} agents, {len([g for g in generated if 'skills' in str(g)])} skills)", file=sys.stderr)
    if skipped:
        print(f"⚠️  Skipped: {len(skipped)}: {', '.join(skipped)}", file=sys.stderr)
    print("\nRun all: bash tests/promptfoo/run-evals.sh per-agent", file=sys.stderr)


if __name__ == "__main__":
    main()
