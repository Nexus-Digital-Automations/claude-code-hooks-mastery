---
name: cli-tools
description: Argument parsing, config management, output formatting, script safety
---

# CLI Tools

## Argument Parsing

- Use a proper library: argparse/click (Python), commander/yargs (Node), cobra (Go)
- Never manually parse `sys.argv` / `process.argv`
- Include `--help` with usage examples
- Use subcommands for multi-action tools (`tool import`, `tool export`)
- Validate arguments early, fail with clear error messages

## Configuration Hierarchy

Priority (highest to lowest):
1. CLI flags (`--port 8080`)
2. Environment variables (`PORT=8080`)
3. Config file (`.config.json`, `.env`)
4. Defaults

Document the hierarchy in `--help` output.

## Output

- **stdout** for program output (data, results) — pipeable
- **stderr** for errors, warnings, progress messages
- `--json` flag for machine-readable output
- `--quiet` flag to suppress non-essential output
- `--no-color` flag (also respect `NO_COLOR` env var)
- Exit codes: 0 = success, 1 = runtime error, 2 = usage error

## Error Handling

- Human-readable errors to stderr: what went wrong + what to do about it
- Include context: file path, line number, input value
- Suggest fixes when possible ("Did you mean X?", "Try --flag")
- `--debug` or `--verbose` flag for full stack traces (off by default)

## Script Safety (Bash/Shell)

- `set -euo pipefail` at the top of every script
- Quote all variables: `"$var"` not `$var`
- Use `mktemp` for temporary files, `trap cleanup EXIT` for cleanup
- Scripts must be idempotent: safe to run twice
- Check dependencies at script start (`command -v jq` or equivalent)
