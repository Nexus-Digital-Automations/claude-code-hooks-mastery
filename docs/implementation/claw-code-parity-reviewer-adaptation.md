# Claw-Code-Parity Reviewer Adaptation

**Status:** Completed
**Implemented:** 2026-04-05
**Commits:** `0c389c9` (reviewer split + claw adapter), `e512b15` (claw run_review.sh)

## Goal

Adapt the protocol compliance reviewer (previously Claude Code-only) to also work with
[claw-code-parity](https://github.com/Nexus-Digital-Automations/claw-code-parity) — a Rust
reimplementation of the Claude Code harness. Maximum code reuse: one shared reviewer brain,
two project-specific packet assemblers.

## Architecture

Split `reviewer.py` into a pure shared core + two project-specific assemblers:

```
hooks/utils/reviewer_core.py       ← shared pure logic (no path deps)
hooks/utils/reviewer.py            ← Claude Code entry point (imports from core)
hooks/utils/packet_builder_claw.py ← claw packet assembler
hooks/claw_stop.py                 ← claw entry point (uv script)
claw-code-parity/scripts/run_review.sh ← thin wrapper
```

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `hooks/utils/reviewer_core.py` | Created | Shared: `ReviewPacket`, `ReviewerConfig`, `SandboxResult`, `format_packet_for_prompt`, `call_reviewer` |
| `hooks/utils/reviewer.py` | Modified | Removed extracted logic; imports from `reviewer_core` |
| `hooks/utils/packet_builder_claw.py` | Created | Reads `.claude/sessions/*.json` → builds `ReviewPacket` |
| `hooks/claw_stop.py` | Created | CLI entry point; persists conversations to `{project}/.claw/data/` |
| `claw-code-parity/scripts/run_review.sh` | Created | `uv run --script ~/.claude/hooks/claw_stop.py <project>` |

## Key Design Decisions

**What's shared:**
- `ReviewPacket` schema, `format_packet_for_prompt()`, `call_reviewer()` (GPT-5 Mini)
- `protocol-compliance-reference.md` (same file used by both entry points)
- Spec parsing (`specs/*.md` — identical format in both projects)
- `.claude-project.json` loading (identical format)

**What's claw-specific:**
- Session data source: `.claude/sessions/session-*.json` (role=user/assistant blocks)
- No task scoping (no `task_id`, no `current_task_*.json`)
- Agent mode hardcoded `"claw"` (Category 8 delegation checks always skipped)
- Conversation persistence: `{project}/.claw/data/`
- Trigger: `scripts/run_review.sh` (no stop hook yet — Rust runtime lacks SessionEnd)

## Invocation

```bash
# From claw-code-parity project root:
./scripts/run_review.sh           # human-readable output
./scripts/run_review.sh --json    # JSON + exit 0/1/2
```

## Verification Results

| Check | Result |
|-------|--------|
| `ruff check hooks/` | ✅ exit 0, all checks passed |
| AST parse: reviewer_core.py | ✅ |
| AST parse: reviewer.py | ✅ (build_review_packet, run_review present) |
| AST parse: packet_builder_claw.py | ✅ (build_claw_packet present) |
| AST parse: claw_stop.py | ✅ (run_claw_review, main present) |
| Dry-run vs claw-code-parity | ✅ Ran end-to-end, produced FINDINGS verdict |
| Claude Code stop hook regression | ✅ Stop authorized after implementation |

## Future Wiring

When the Rust runtime adds a `SessionEnd` lane event, register in `.claw/settings.json`:
```json
{ "hooks": { "SessionEnd": ["./scripts/run_review.sh --json"] } }
```
