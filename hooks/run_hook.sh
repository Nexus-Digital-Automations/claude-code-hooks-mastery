#!/bin/bash
# Wrapper script to run uv hooks with clean environment and suppress Python warnings
# Usage: run_hook.sh <script.py> [args...]

# Unset conda/python environment variables that cause warnings
unset PYTHONHOME PYTHONPATH CONDA_PREFIX CONDA_PYTHON_EXE CONDA_DEFAULT_ENV CONDA_EXE CONDA_SHLVL _CE_CONDA CONDA_PROMPT_MODIFIER

# Create temp files for stdout and stderr
STDOUT_TMP=$(mktemp)
STDERR_TMP=$(mktemp)

# Run uv and capture both stdout and stderr
uv run "$@" >"$STDOUT_TMP" 2>"$STDERR_TMP"
EXIT_CODE=$?

# Output stdout (this is the JSON that Claude Code expects)
cat "$STDOUT_TMP"

# Filter and output stderr (remove the platform warning and zsh eval errors)
grep -v -E "(Could not find platform independent libraries|^\(eval\):)" "$STDERR_TMP" >&2

# Cleanup and exit with original code
rm -f "$STDOUT_TMP" "$STDERR_TMP"
exit $EXIT_CODE
