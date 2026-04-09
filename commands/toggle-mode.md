---
description: Toggle between claude and qwen agent modes
allowed-tools: Bash
---

Toggle the agent mode between `claude` (direct implementation) and `qwen` (supervisor/delegation mode).

Run: `bash ~/.claude/commands/toggle-mode.sh $ARGUMENTS`

- No argument toggles the current mode
- Pass `claude` or `qwen` to set explicitly

After running, confirm the new mode to the user.
