---
name: promptfoo
description: Use when writing, running, or debugging promptfoo evaluation suites — YAML test configs, llm-rubric assertions, OpenAI-compatible providers (Qwen), custom Python providers, CLI flags, reading JSON results, or iterating on failing evals.
---

# promptfoo

Promptfoo evaluates LLM behavior with YAML-configured test suites, multiple assertion types, and provider-agnostic runners.

## Core YAML Structure

```yaml
providers:
  - id: openai:chat:qwen-coder-plus-latest      # or gpt-4o, claude-3-5-sonnet, etc.
    config:
      apiBaseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1   # for OpenAI-compatible APIs
      apiKeyEnvar: QWEN_API_KEY           # env var name (not the value)

defaultTest:                           # applies to ALL tests unless overridden
  options:
    provider:
      id: openai:chat:qwen-coder-plus-latest
      config:
        apiBaseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
        apiKeyEnvar: QWEN_API_KEY

prompts:
  - label: "my-prompt"
    raw: |
      You are an assistant. {{variable}}

tests:
  - description: "short test name"
    vars:
      variable: "some input value"
    assert:
      - type: llm-rubric
        value: >
          Pass if: ... Fail if: ...
        threshold: 0.75
        metric: "metric_name_for_aggregation"

outputPath: tests/promptfoo/results/suite-name.json
```

## Providers

### OpenAI-compatible (Qwen, OpenRouter, etc.)
```yaml
providers:
  - id: openai:chat:qwen-coder-plus-latest
    config:
      apiBaseUrl: https://dashscope.aliyuncs.com/compatible-mode/v1
      apiKeyEnvar: QWEN_API_KEY     # env var name — never hardcode
```

### Custom Python provider
```yaml
providers:
  - id: file://tests/promptfoo/my_provider.py
```

```python
# my_provider.py — must implement call_api()
def call_api(prompt, options, context):
    vars_ = (context or {}).get("vars", {})
    my_var = vars_.get("my_var") or str(prompt)
    # ... call your API ...
    return {
        "output": text,
        "tokenUsage": {
            "prompt": usage.prompt_tokens,
            "completion": usage.completion_tokens,
            "total": usage.total_tokens,
        },
    }
```

Use `context["vars"]` to read test variables inside custom providers.

## Assertion Types

| Type | Use for | Example value |
|------|---------|---------------|
| `llm-rubric` | AI-graded subjective pass/fail | `"Pass if: X. Fail if: Y."` |
| `contains` | Exact substring present | `"expected phrase"` |
| `not-contains` | Substring absent | `"banned phrase"` |
| `regex` | Pattern match | `"\\d{4}-\\d{2}-\\d{2}"` |
| `javascript` | JS expression → bool | `"output.length > 50"` |
| `python` | Python expression → bool | `"'error' not in output"` |
| `semantic-similarity` | Embedding similarity ≥ threshold | `"expected meaning"` |
| `cost` | Token cost below limit | `0.01` |
| `latency` | Response time ms | `5000` |

## Writing Good llm-rubric Assertions

The grader is another LLM reading your criteria — be explicit:

```yaml
assert:
  - type: llm-rubric
    value: >
      Pass if: the response lists ALL three items (create, edit, delete) as
      separate numbered checklist entries. The word "management" alone does not
      count — each operation must appear individually.
      Fail if: groups operations into a single item, lists fewer than 3 items,
      or mentions "management" without enumerating the operations.
    threshold: 0.75      # 0.60–0.80 typical; higher = stricter
    metric: "crud_expansion"   # groups results in summary output
```

**llm-rubric tips:**
- Start with `Pass if:` then `Fail if:` — explicit criteria prevents ambiguity
- Name the exact things that must appear vs. must not appear
- `threshold: 0.75` is safe default; use `0.70` for nuanced criteria
- `metric:` field aggregates scores in the results summary — always include it
- The grader uses `OPENAI_API_KEY` + `OPENAI_BASE_URL` env vars for its model

## CLI Usage

```bash
# Run single suite
./node_modules/.bin/promptfoo eval \
  -c tests/promptfoo/01-suite-name.yaml \
  --no-cache \
  --output tests/promptfoo/results/01-suite-name.json

# View results in browser UI
./node_modules/.bin/promptfoo view

# Run specific test by description (grep filter)
./node_modules/.bin/promptfoo eval -c config.yaml --filter-description "keyword"
```

**`--no-cache`** — always use for fresh runs; promptfoo caches by prompt+provider+vars hash.

## Reading JSON Results

```bash
# Quick pass/fail summary
jq '.results.stats' results/01-suite-name.json

# See which tests failed and why
jq '.results.results[] | select(.success == false) | {desc: .description, score: .score, reason: .gradingResult.reason}' \
  results/01-suite-name.json

# See all test scores with metric
jq '.results.results[] | {desc: .description, metric: .gradingResult.componentResults[0].assertion.metric, score: .score}' \
  results/01-suite-name.json
```

## Environment Variables

`llm-rubric` grader needs its own API key — separate from your test provider:

```bash
# In run script: point grader at Qwen (OpenAI-compatible)
export OPENAI_API_KEY=$QWEN_API_KEY
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"

# Your test provider key
export QWEN_API_KEY="sk-..."
```

Or load from `.env` file:
```bash
export QWEN_API_KEY=$(grep '^QWEN_API_KEY=' ~/.claude/.env | cut -d= -f2-)
```

## Iteration Workflow

1. Write YAML suite → run with `--no-cache`
2. Read JSON: `jq '.results.stats'` for counts, then inspect failing tests
3. Check `.gradingResult.reason` — the grader explains why it failed
4. Fix either: the prompt being tested OR the assertion criteria
5. Re-run; repeat until all pass
6. Add `outputPath:` to YAML so results auto-save to `tests/promptfoo/results/`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Assertion criteria too vague | Spell out exact strings/counts that must appear |
| `threshold: 1.0` on subjective criteria | Use 0.70–0.80; LLM graders aren't perfect |
| Missing `metric:` field | Add it — required for result aggregation |
| Hardcoding API key in YAML | Use `apiKeyEnvar: MY_ENV_VAR` instead |
| Forgetting `--no-cache` | Add to your run script; cached results mask real failures |
| `defaultTest` provider not set | Without it, each test must override provider — verbose |
| Custom provider ignores `context["vars"]` | Always read vars from `context`, not from `prompt` string |
