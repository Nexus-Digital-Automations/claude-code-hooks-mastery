# Security Scan Report

**Generated:** demo_output  
**Directory:** `/tmp/test-project`  
**Duration:** 2.3s

## Summary

| Metric | Value |
|--------|-------|
| Critical findings | 1 |
| Warning findings | 0 |
| Suppressed (.security-ignore) | 2 |
| Tools run | gitleaks, pattern-scanner |
| Tools failed/skipped | none |
| Scan duration | 2.3s |

## Critical Findings (1)

### 1. hardcoded-secret
- **File:** `src/main.py:10`
- **Tool:** gitleaks
- **Description:** Hardcoded password
- **Recommendation:** Remove or replace with environment variable / secret manager

## Warning Findings

None found.

## Suppressed Findings (2)

*These findings matched rules in `.security-ignore` and are excluded from counts.*

### 1. dynamic-code-evaluation [warning]
- **File:** `vendor/lib/eval_helper.py:5`
- **Tool:** pattern-scanner
- **Description:** eval() usage
- **Ignore reason:** Third-party vendored code, pre-audited

### 2. ssl-verification-bypass [warning]
- **File:** `tests/helpers/http_client.py:12`
- **Tool:** pattern-scanner
- **Description:** verify=False
- **Ignore reason:** Intentional for test HTTP client isolation

## Patching Instructions

Paste this prompt to Claude to fix the critical findings above:

```
Fix the following critical security findings in this codebase:

1. [gitleaks] hardcoded-secret at src/main.py:10: Hardcoded password

After fixing, run /authorize-stop to re-run the security scan.
```

## Infrastructure Tools (Manual Setup Required)

These tools require separate infrastructure setup and are not run inline:

- **SonarQube:** Requires a running server + project configuration. https://www.sonarsource.com/products/sonarqube/
- **CodeQL:** Requires GitHub Actions or multi-GB binary install + query compilation. https://codeql.github.com/
- **OWASP ZAP:** DAST proxy scanner (dynamic, not static analysis). https://www.zaproxy.org/
- **OpenVAS:** Network/infrastructure vulnerability scanner; not a code scanner. https://www.openvas.org/
