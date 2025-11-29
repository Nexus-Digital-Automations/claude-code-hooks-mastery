# Claude Code Agent Portfolio

## Overview
This directory contains specialized Claude Code agents for comprehensive development workflows, with emphasis on security analysis and modern application development.

## 🛡️ Security Agents

### Static Analysis (SAST)

**`sast-orchestrator-sonnet`** - Multi-Language Comprehensive SAST
- **Tools**: Semgrep, CodeQL, SonarQube Community, Bearer, Horusec
- **Coverage**: All programming languages
- **Focus**: Comprehensive vulnerability analysis with deduplication and prioritization
- **Use**: When you need broad, multi-language security coverage

**`nodejs-security-sonnet`** - Node.js/JavaScript Security Specialist
- **Tools**: eslint-plugin-security, NodeJsScan, Semgrep JS rules, npm audit
- **Coverage**: JavaScript, TypeScript, Node.js applications
- **Frameworks**: Express, React, Next.js, Vue, Angular
- **Use**: For JavaScript/Node.js-specific security analysis

**`python-security-sonnet`** - Python Security Specialist
- **Tools**: Bandit, pip-audit, safety, Semgrep Python rules
- **Coverage**: Python applications
- **Frameworks**: Django, Flask, FastAPI
- **Use**: For Python-specific security analysis

**`ruby-security-sonnet`** - Ruby/Rails Security Specialist
- **Tools**: Brakeman, bundler-audit, Semgrep Ruby rules
- **Coverage**: Ruby applications
- **Frameworks**: Ruby on Rails
- **Use**: For Ruby and Rails-specific security analysis

**`data-privacy-sonnet`** - Data Security & Privacy Compliance
- **Tools**: Bearer, Semgrep privacy rules, custom data flow analysis
- **Coverage**: PII handling, data privacy, compliance
- **Regulations**: GDPR, CCPA, HIPAA
- **Use**: For privacy compliance and sensitive data analysis

### Dynamic Analysis (DAST)

**`dast-scanner-sonnet`** - Dynamic Application Security Testing
- **Tools**: OWASP ZAP, custom web app testing, API fuzzing
- **Coverage**: Runtime vulnerabilities, web apps, REST/GraphQL APIs
- **Focus**: Injection flaws, XSS, authentication, session management
- **Use**: For testing running applications

**`api-security-sonnet`** - API Security Specialist
- **Tools**: OWASP ZAP (API mode), Semgrep API rules
- **Coverage**: REST and GraphQL endpoints
- **Focus**: OWASP API Security Top 10
- **Use**: For dedicated API security testing

### Specialized Security

**`owasp-guardian-sonnet`** - OWASP Top 10 Guardian
- **Focus**: OWASP Top 10 (2021) comprehensive coverage
- **Integration**: Works with all SAST/DAST tools
- **Use**: For OWASP Top 10-focused analysis

**`secrets-detective-sonnet`** - Secrets & Credentials Detection
- **Tools**: Horusec, TruffleHog, git-secrets, entropy analysis
- **Coverage**: API keys, passwords, tokens, private keys, cloud credentials
- **Use**: Prevent credential leaks before commit

**`dependency-auditor-sonnet`** - Dependency Vulnerability Scanner
- **Tools**: npm audit, pip-audit, bundler-audit, yarn audit, Snyk
- **Coverage**: All package managers (npm, pip, bundler, yarn)
- **Focus**: Vulnerable packages, supply chain attacks, license compliance
- **Use**: Regular dependency security audits

**`infrastructure-security-sonnet`** - Infrastructure & Container Security
- **Tools**: OpenVAS, Docker Bench, Trivy, Kubernetes CIS benchmarks
- **Coverage**: Infrastructure, containers, Kubernetes, cloud configs
- **Cloud**: AWS, Azure, GCP
- **Use**: Infrastructure security and compliance audits

**`waf-rule-generator-sonnet`** - WAF Rule Generator
- **Tools**: ModSecurity rule generation
- **Coverage**: WAF rules for detected vulnerabilities
- **Use**: Generate edge protection rules from security findings

## 🔧 Development Workflow Agents

### Code Quality & Review

**`code-reviewer-sonnet`** - Comprehensive Code Review
- Readability, maintainability, bugs, best practices
- Use after significant code changes

**`refactoring-specialist-sonnet`** - Code Refactoring Expert
- Identifies code smells, reduces duplication, improves structure
- Use when technical debt needs addressing

**`debug-detective-sonnet`** - Debugging Specialist
- Analyzes stack traces, reproduces issues, identifies root causes
- Use when errors occur or bugs are reported

### Testing & Quality Assurance

**`test-engineer-sonnet`** - Testing Specialist
- Unit, integration, E2E tests, test coverage improvement
- Use when features need testing

**`accessibility-specialist-sonnet`** - WCAG Compliance Expert
- Semantic HTML, ARIA, keyboard navigation, screen reader support
- Use for accessibility audits and improvements

### Architecture & Design

**`system-architect-sonnet`** - System Architecture Designer
- System design, component relationships, data flow, tech stack
- Use when designing new systems or major features

**`api-designer-sonnet`** - API Design Specialist
- REST/GraphQL APIs, endpoint structure, schemas, versioning
- Use when designing APIs

**`database-designer-sonnet`** - Database Schema Designer
- Database schemas, migrations, indexes, query optimization
- Use for database design and optimization

**`pattern-advisor-sonnet`** - Design Patterns Expert
- Design patterns, architectural patterns, best practices
- Use for complex design problems

### DevOps & Infrastructure

**`cicd-engineer-sonnet`** - CI/CD Pipeline Specialist
- GitHub Actions, GitLab CI, CircleCI, automated testing
- Use for CI/CD setup and improvements

**`deployment-specialist-sonnet`** - Deployment Configuration Expert
- Dockerfiles, docker-compose, Kubernetes manifests, cloud deployment
- Use for deployment configuration

**`monitoring-specialist-sonnet`** - Observability Expert
- Logging, metrics, alerting, distributed tracing, error tracking
- Use for monitoring and observability setup

**`infrastructure-engineer-sonnet`** - Infrastructure as Code
- Terraform, CloudFormation, cloud resources, networking
- Use for infrastructure management

### Documentation

**`documentation-writer-sonnet`** - Documentation Specialist
- READMEs, API docs, inline comments, architecture documentation
- Use after feature completion or when docs are needed

## 🌐 Specialized Agents

### Research & AI

**`llm-ai-agents-and-eng-research`** - AI Research Specialist
- Latest news in LLMs, AI agents, engineering innovations
- Use for staying current with AI/ML developments

### Utilities

**`meta-agent`** - Agent Generator
- Generates new Claude Code agent configurations
- Use to create new specialized agents

**`work-completion-summary`** - TTS Summary Agent
- Provides audio summaries and suggests next steps
- Use for work completion notifications

**`hello-world-agent`** - Greeting Agent
- Simple greeting responses
- Use for testing agent system

## 📋 Usage Guidelines

### Security Workflow Recommendations

**For JavaScript/Node.js Projects:**
1. Run `nodejs-security-sonnet` for language-specific issues
2. Run `api-security-sonnet` if building APIs
3. Run `dependency-auditor-sonnet` for package vulnerabilities
4. Run `secrets-detective-sonnet` before commits

**For Python Projects:**
1. Run `python-security-sonnet` for language-specific issues
2. Run `dependency-auditor-sonnet` for package vulnerabilities
3. Run `data-privacy-sonnet` if handling PII

**For Multi-Language Projects:**
1. Run `sast-orchestrator-sonnet` for comprehensive coverage
2. Run language-specific agents for deep analysis
3. Run `owasp-guardian-sonnet` for OWASP Top 10 compliance

**For Running Applications:**
1. Run `dast-scanner-sonnet` for runtime testing
2. Run `api-security-sonnet` for API endpoints
3. Run `infrastructure-security-sonnet` for deployment environment

### Parallel Execution

Run multiple specialized agents simultaneously for faster analysis:
```bash
# Example: Comprehensive JavaScript app security scan
- nodejs-security-sonnet (SAST)
- api-security-sonnet (API-specific)
- secrets-detective-sonnet (Credentials)
- dependency-auditor-sonnet (Packages)
```

### Tool Installation

Agents will attempt to auto-detect and install required tools. Common prerequisites:

**For SAST Agents:**
```bash
pip install semgrep bandit
npm install --save-dev eslint-plugin-security
gem install brakeman
```

**For DAST Agents:**
```bash
docker pull owasp/zap2docker-stable
```

**For Container Security:**
```bash
docker pull aquasec/trivy
```

## 🔗 Related Resources

- **Hooks Documentation**: `../.claude/hooks/` - Lifecycle hooks for Claude Code
- **Commands**: `../.claude/commands/` - Custom slash commands
- **Agent Prompts**: `../.claude/commands/agent_prompts/` - Detailed agent instructions
- **Settings**: `../.claude/settings.json` - Claude Code configuration

## 📝 Agent Development

To create a new agent:

1. Use the `meta-agent` to generate agent configuration
2. Or manually create `.md` file in this directory with:
   - Frontmatter (name, description, tools, model, color)
   - Prompt reference: `Read and Execute: .claude/commands/agent_prompts/[name]_prompt.md`
3. Create detailed prompt file in `.claude/commands/agent_prompts/`
4. Test agent activation and behavior

## 🎯 Best Practices

1. **Use Specialized Agents**: Language-specific agents provide better context than generic ones
2. **Run Multiple Agents**: Parallel execution speeds up comprehensive analysis
3. **Regular Audits**: Run security agents regularly, not just before releases
4. **Integrate with CI/CD**: Automate security scanning in pipelines
5. **Keep Tools Updated**: Agents work best with latest tool versions
6. **Review Findings**: Always review and prioritize security findings
7. **Fix Critical First**: Address Critical/High severity issues immediately

---

**Total Agents**: 30+
- **Security**: 12 specialized security agents
- **Development**: 14 workflow agents
- **Utilities**: 4 specialized agents

This portfolio provides world-class security coverage and development workflow automation for modern applications.
