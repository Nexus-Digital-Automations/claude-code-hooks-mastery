---
title: Project-Local Hook State Storage
status: active
created: 2026-04-24
---

## Vision

Per-session, per-task, and per-project agent state must live inside the project that produced it, never in the user's global `~/.claude/data/` folder. The `~/.claude` repository is special-cased: it is its own project, so its data continues to live at `~/.claude/data/` (no `.claude/.claude/data/` nesting).

## Requirements

R1. A single helper `get_project_data_dir(cwd)` in `hooks/utils/project_config.py` resolves to `<git_root>/.claude/data/`, with the special case that `git_root == ~/.claude` collapses to `~/.claude/data/`.

R2. Every hook that writes a per-session state file under `~/.claude/data/` switches to `get_project_data_dir(cwd)` using the cwd from its stdin input.

R3. Every hook that reads those files uses the same resolver.

R4. Shell scripts (`authorize-stop.sh`, `approve-spec-edit.sh`) compute the project data dir with the same special-case rule.

R5. On first write into a project's `.claude/` state folders, hooks ensure the project's `.gitignore` contains `.claude/data/`, `.claude/artifacts/`, and `.claude/reports/` (skipped for the `~/.claude` meta-repo, whose `.gitignore` is hand-curated).

R6. Truly global config (`critical-paths.json`, `reviewer_config.json`, `settings.json`) and harness-managed state (auto-memory, plan files) stay where they are.

R7. `CLAUDE.md` Rule 2b documents the new path.

## Acceptance Criteria

- [x] `get_project_data_dir` exists in `hooks/utils/project_config.py` and returns the correct path for both `~/.claude` and an external project.
- [x] Running a session in a non-`~/.claude` project writes `agent_identity_<sid>.json`, `verification_record_<sid>.json`, `current_task_<sid>.json`, `session_scope_<sid>.json`, `commit_push_state_<sid>.json`, `stop_authorization_<sid>.json`, `reviewer_approval_<sid>.json`, `user_requests_<sid>.json`, `active_sessions.json`, `sessions/<sid>_tools.json`, `delegation_meta_<sid>.json`, and `sandbox_executions.json` into `<project>/.claude/data/`, never `~/.claude/data/`.
- [x] Running a session in `~/.claude` keeps writing those files at `~/.claude/data/` (no nesting).
- [x] `lessons.json` and `error_catalog.json` move from `<cwd>` root to `<project>/.claude/data/` (no more root pollution).
- [x] `architectural_decisions.json` moves from `~/.claude/.validation-artifacts/` to `<project>/.claude/artifacts/`.
- [x] Security scan reports move from `~/.claude/reports/security/` to `<project>/.claude/reports/security/`.
- [x] `bash ~/.claude/commands/authorize-stop.sh` and `bash ~/.claude/commands/approve-spec-edit.sh` write to project-local paths.
- [x] First write into a non-meta project auto-appends a marked block to `.gitignore`; second run is idempotent.
- [x] `CLAUDE.md` Rule 2b describes the new path with the meta-repo special case.
- [x] `uvx ruff check hooks/` passes with zero errors.
- [x] `~/.claude/plans/`, auto-memory, settings, `critical-paths.json`, `reviewer_config.json` are unchanged (verified by grep).

## Technical Decisions

**Path convention: `<project>/.claude/data/`** — matches the existing `.claude/` config-folder convention used by Claude Code projects. Adding a sibling `data/` keeps state segregated from config.

**Special case for `~/.claude`** — the meta-repo IS its own project, so naive `<git_root>/.claude/data/` would produce `~/.claude/.claude/data/`, doubling the prefix. Helper detects equality and short-circuits.

**Auto-gitignore** — without it, every hook write dirties the user's `git status`. Idempotent block append with a comment marker is the lesser evil; users can remove or edit. Skipped for the meta-repo.

**Drop legacy no-sid fallbacks** — `vr_utils.py` and `llm_verifier.py` previously fell back to `current_task.json` / `agent_identity.json` (no sid) at the global path. Nothing writes those anymore; readers stop checking them.

**No data migration** — old `~/.claude/data/session_*` files from prior sessions become orphans. The existing `reset_verification_record` cleanup handles their disposal.

## Progress

Implementation tracked in `plans/ran-3-stop-shimmering-crown.md`.
