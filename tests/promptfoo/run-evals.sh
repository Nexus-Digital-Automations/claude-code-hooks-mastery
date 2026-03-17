#!/bin/bash
# Run all promptfoo hook evaluations from ~/.claude/
# Usage:  bash tests/promptfoo/run-evals.sh [01|02|03|04|all]

set -e
cd /Users/jeremyparker/.claude

# Load DeepSeek API key from ~/.claude/.env if not already set
if [ -z "$DEEPSEEK_API_KEY" ] && [ -f ~/.claude/.env ]; then
  export DEEPSEEK_API_KEY=$(grep '^DEEPSEEK_API_KEY=' ~/.claude/.env | cut -d= -f2- | tr -d '"'"'" | head -1) # nosec
fi

if [ -z "$DEEPSEEK_API_KEY" ]; then
  echo "ERROR: DEEPSEEK_API_KEY not set."
  echo "Add it to ~/.claude/.env:  DEEPSEEK_API_KEY=sk-..."
  exit 1
fi

# Point promptfoo's built-in llm-rubric grader at DeepSeek (OpenAI-compatible)
export OPENAI_API_KEY=$DEEPSEEK_API_KEY  # nosec — forwards env var, not a hardcoded secret
export OPENAI_BASE_URL="https://api.deepseek.com"

PROMPTFOO="./node_modules/.bin/promptfoo"
RESULTS_DIR="tests/promptfoo/results"
AGENTS_DIR="tests/promptfoo/agents"
SKILLS_DIR_PF="tests/promptfoo/skills"
mkdir -p "$RESULTS_DIR"

PASS=0
FAIL=0

run_eval() {
  local num=$1 label=$2 config="tests/promptfoo/${1}-${2}.yaml"
  echo "Running eval ${num}: ${label}"
  if $PROMPTFOO eval \
    -c "$config" \
    --no-cache \
    --output "${RESULTS_DIR}/${num}-${label}.json" \
    2>&1; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
  echo "Done: ${RESULTS_DIR}/${num}-${label}.json"
  echo ""
}

run_agent_eval() {
  local agent_name=$1 config="${AGENTS_DIR}/${agent_name}.yaml"
  echo "Running agent eval: ${agent_name}"
  if $PROMPTFOO eval \
    -c "$config" \
    --no-cache \
    --output "${RESULTS_DIR}/agent-${agent_name}.json" \
    2>&1; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
  echo "Done: ${RESULTS_DIR}/agent-${agent_name}.json"
  echo ""
}

run_skill_eval() {
  local skill_name=$1 config="${SKILLS_DIR_PF}/${skill_name}.yaml"
  echo "Running skill eval: ${skill_name}"
  if $PROMPTFOO eval \
    -c "$config" \
    --no-cache \
    --output "${RESULTS_DIR}/skill-${skill_name}.json" \
    2>&1; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi
  echo "Done: ${RESULTS_DIR}/skill-${skill_name}.json"
  echo ""
}

SUITE=${1:-all}

case "$SUITE" in
  01) run_eval "01" "agent-routing-directive" ;;
  02) run_eval "02" "ambiguity-injection" ;;
  03) run_eval "03" "validation-protocol" ;;
  04) run_eval "04" "prompt-ab-comparison" ;;
  05) run_eval "05" "claude-md-eval" ;;
  11) run_eval "11" "skills-quality" ;;
  13) run_eval "13" "lazy-execution" ;;
  14) run_eval "14" "deepseek-mode-delegation" ;;
  15) run_eval "15" "feature-completeness-validation" ;;
  16) run_eval "16" "feature-checklist-delegation" ;;
  hooks)
    run_eval "01" "agent-routing-directive"
    run_eval "02" "ambiguity-injection"
    run_eval "03" "validation-protocol"
    run_eval "04" "prompt-ab-comparison"
    run_eval "05" "claude-md-eval"
    run_eval "14" "deepseek-mode-delegation"
    ;;
  per-agent)
    # Run each per-agent YAML file individually
    for yaml_file in "${AGENTS_DIR}"/*.yaml; do
      agent_name=$(basename "$yaml_file" .yaml)
      run_agent_eval "$agent_name"
    done
    # Run per-skill YAML files
    for yaml_file in "${SKILLS_DIR_PF}"/*.yaml; do
      skill_name=$(basename "$yaml_file" .yaml)
      run_skill_eval "$skill_name"
    done
    ;;
  all)
    run_eval "01" "agent-routing-directive"
    run_eval "02" "ambiguity-injection"
    run_eval "03" "validation-protocol"
    run_eval "04" "prompt-ab-comparison"
    run_eval "05" "claude-md-eval"
    run_eval "13" "lazy-execution"
    run_eval "14" "deepseek-mode-delegation"
    run_eval "15" "feature-completeness-validation"
    run_eval "16" "feature-checklist-delegation"
    for yaml_file in "${AGENTS_DIR}"/*.yaml; do
      agent_name=$(basename "$yaml_file" .yaml)
      run_agent_eval "$agent_name"
    done
    for yaml_file in "${SKILLS_DIR_PF}"/*.yaml; do
      skill_name=$(basename "$yaml_file" .yaml)
      run_skill_eval "$skill_name"
    done
    ;;
  *)
    echo "Usage: $0 [01-05|11|13|14|hooks|per-agent|all]"
    exit 1
    ;;
esac

echo ""
echo "=================================================="
echo "  Suites passed: $PASS   Failed: $FAIL"
echo "  View results:  ./node_modules/.bin/promptfoo view"
echo "=================================================="
[ "$FAIL" -eq 0 ]
