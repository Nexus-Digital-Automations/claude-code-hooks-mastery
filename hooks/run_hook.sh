#!/bin/bash
# Wrapper script to run uv hooks with clean environment and suppress Python warnings
# Usage: run_hook.sh <script.py> [args...]

# Unset conda/python environment variables that cause warnings
unset PYTHONHOME PYTHONPATH CONDA_PREFIX CONDA_PYTHON_EXE CONDA_DEFAULT_ENV CONDA_EXE CONDA_SHLVL _CE_CONDA CONDA_PROMPT_MODIFIER

# Create temp file for stderr
STDERR_TMP=$(mktemp)

# Run uv and capture stderr
uv run "$@" 2>"$STDERR_TMP"
EXIT_CODE=$?

# Filter and output stderr (remove the platform warning)
grep -v "Could not find platform independent libraries" "$STDERR_TMP" >&2

# Cleanup and exit with original code
rm -f "$STDERR_TMP"
exit $EXIT_CODE
