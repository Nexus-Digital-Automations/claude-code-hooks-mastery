"""Review data types, packet formatter, and LLM client for the hooks harness.

Owns: ReviewPacket schema, ReviewerConfig, SandboxResult, format_packet_for_prompt,
call_reviewer, async_call_reviewer.

Does NOT own: packet *building* (reviewer.py builds the packet from git/sandbox/specs),
round management (reviewer.py run_review()), or file-size registry I/O (file_size_registry.py).

Called by: reviewer.py, packet_builder_claw.py, claw_stop.py.
Counterpart: Dev_Agent_MCP has its own copy at qwen_agent_mcp/reviewer_types.py.

# WHY a separate module: reviewer.py is 1000+ lines; inlining the schema and LLM
# client there would push it over 1400 lines. Separating types/transport from the
# orchestration logic (packet building, conversation management) keeps each module
# under a meaningful complexity ceiling without creating pass-through layers.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any


# ── Sandbox Result ────────────────────────────────────────────────────

@dataclass
class SandboxResult:
    check_key: str
    command: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    timed_out: bool = False
    skipped: bool = False
    skip_reason: str = ""


# ── Configuration ─────────────────────────────────────────────────────

@dataclass
class ReviewerConfig:
    model: str = "deepseek-v4-flash"
    temperature: float = 0.2
    max_tokens: int = 2000
    max_rounds: int = 5
    timeout_per_round: int = 30
    sandbox_timeout: int = 120
    sandbox_timeout_frontend: int = 300
    provider: str = "deepseek"        # "deepseek" | "openai" — controls base_url + key env var
    strictness: str = "standard"
    enabled: bool = True


# ── Review Packet ─────────────────────────────────────────────────────

@dataclass
class ReviewPacket:
    session_id: str = ""
    task_id: str = ""
    prompt_id: str = ""
    agent_id: str = ""
    task_started_at: str = ""
    user_requests: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    spec_status: list[dict] = field(default_factory=list)  # type: ignore[type-arg]
    sandbox_results: dict[str, dict] = field(default_factory=dict)  # type: ignore[type-arg]
    project_config: dict = field(default_factory=dict)  # type: ignore[type-arg]
    git_status: str = ""
    git_diff: str = ""
    git_diff_content: str = ""
    git_log: str = ""
    git_show_stat: str = ""
    git_show_content: str = ""
    # All commits the agent made during this task (oldest task commit ^ .. HEAD).
    # Empty when task_started_at is unknown or no commits were made.
    session_diff_content: str = ""
    root_clean: bool = True
    root_violations: list[str] = field(default_factory=list)
    last_assistant_message: str = ""
    agent_commentary_summary: str = ""
    plan_content: str = ""
    timestamp: str = ""
    verification_artifacts: dict[str, str] = field(default_factory=dict)
    oversized_files: list[tuple[str, int]] = field(default_factory=list)
    # Populated from FileSizeRegistry.as_review_dict() in reviewer.py.
    # Maps file path → {reason, tier, line_count_at_registration, registered_at}.
    # Counterpart: file_size_registry.py owns the registry; stop.py Phase 1 gates on it.
    file_size_reasons: dict[str, Any] = field(default_factory=dict)


# ── Packet Formatter ──────────────────────────────────────────────────

def format_packet_for_prompt(packet: ReviewPacket) -> str:
    """Convert ReviewPacket into structured text for the LLM prompt."""
    sections = []

    # ── TASK CONTEXT (scope boundary for this review) ──
    sections.append("## TASK CONTEXT")
    sections.append(f"task_id:         {packet.task_id or '(unknown)'}")
    sections.append(f"prompt_id:       {packet.prompt_id or '(unknown)'}")
    sections.append(f"agent_id:        {packet.agent_id or '(unknown)'}")
    sections.append(f"task_started_at: {packet.task_started_at or '(unknown)'}")
    sections.append(f"session_id:      {packet.session_id}")
    sections.append(
        "\n> SCOPE: Only requests and commits since task_started_at are included below. "
        "Do NOT flag issues from prior tasks or sessions."
    )

    # ── MOST RECENT USER REQUEST (top of packet — primary review target) ──
    sections.append("\n## ⚠ MOST RECENT USER REQUEST (PRIMARY REVIEW TARGET)")
    if packet.user_requests:
        last_req = packet.user_requests[-1]
        last_ts = last_req.get("timestamp", "?")
        last_prompt = last_req.get("prompt", "(empty)")
        sections.append(f"Timestamp: {last_ts}")
        sections.append(f"\n{last_prompt}")
        preceding = last_req.get("preceding_context", "")
        if preceding:
            sections.append(
                f"\n> **This was a short confirmation. The user was responding to:**\n"
                f"> {preceding}"
            )
    else:
        sections.append("(No user requests captured — cannot verify completion)")
    sections.append(
        "\n> CRITICAL: Your verdict MUST explicitly state whether this specific request "
        "was completed fully (PASS) or not (FAIL). If it was not addressed, that alone "
        "is grounds for FINDINGS regardless of other criteria. "
        "NOTE: Short user messages like 'do these', 'yes', 'go ahead' are confirmations "
        "of the FULL preceding assistant proposal — not just a subset."
    )

    sections.append("\n## LAST ASSISTANT MESSAGE")
    if packet.last_assistant_message:
        sections.append(packet.last_assistant_message)
    else:
        sections.append("(Not captured)")

    sections.append("\n## AGENT COMMENTARY SUMMARY (all assistant messages, summarized by local model)")
    if packet.agent_commentary_summary:
        sections.append(packet.agent_commentary_summary)
    else:
        sections.append("(Not available — Ollama may be offline or transcript empty)")

    sections.append("\n## ALL USER REQUESTS (current task only — filtered by task_id)")
    if packet.user_requests:
        for i, req in enumerate(packet.user_requests, 1):
            ts = req.get("timestamp", "?")
            prompt = req.get("prompt", "(empty)")
            marker = " ← MOST RECENT" if i == len(packet.user_requests) else ""
            sections.append(f"### Message {i} [{ts}]{marker}")
            sections.append(prompt)
            preceding = req.get("preceding_context", "")
            if preceding:
                sections.append(
                    f"\n> **Preceding assistant message (user was responding to this):**\n"
                    f"> {preceding}"
                )
    else:
        sections.append("(No user requests captured)")

    sections.append("\n## SPEC STATUS")
    if packet.spec_status:
        for spec in packet.spec_status:
            sections.append(
                f"- {spec['file']}: \"{spec['title']}\" "
                f"[{spec['status']}] — {spec['checked']}/{spec['total']} criteria checked"
            )
            body = spec.get("body", "").strip()
            if body:
                sections.append(f"\n```\n{body}\n```")
    else:
        sections.append("(No active specs found)")

    sections.append("\n## APPROVED PLAN (pre-implementation)")
    if packet.plan_content:
        sections.append(
            "> This plan was approved BEFORE implementation began. "
            "It authorizes the features and approach described within."
        )
        sections.append(f"\n{packet.plan_content}")
    else:
        sections.append("(No plan file found — task may not have required a plan)")

    sections.append("\n## PROJECT CONFIG")
    sections.append(json.dumps(packet.project_config, indent=2))

    sections.append("\n## SANDBOX CHECK RESULTS (independently executed)")
    for key, result in packet.sandbox_results.items():
        if key.startswith("_git_"):
            continue
        sections.append(f"\n### {key.upper()}")
        sections.append(f"Command: `{result.get('command', 'N/A')}`")
        if result.get("skipped"):
            sections.append(f"SKIPPED: {result.get('skip_reason', 'unknown')}")
            continue
        if result.get("timed_out"):
            sections.append("TIMED OUT — check did not complete")
            continue
        sections.append(f"Exit code: {result.get('exit_code', '?')}")
        sections.append(f"Passed: {result.get('passed', False)}")
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        if stdout.strip():
            sections.append(f"stdout:\n```\n{stdout}\n```")
        if stderr.strip():
            sections.append(f"stderr:\n```\n{stderr}\n```")

    sections.append("\n## VERIFICATION ARTIFACTS (committed to output/)")
    if packet.verification_artifacts:
        for name, content in packet.verification_artifacts.items():
            sections.append(f"\n### {name}")
            sections.append(f"```\n{content}\n```")
    else:
        sections.append("(No artifacts found in output/)")

    sections.append("\n## GIT STATE")
    sections.append(f"### git status --porcelain\n```\n{packet.git_status or '(clean)'}\n```")
    sections.append(f"### git diff --stat\n```\n{packet.git_diff or '(no changes)'}\n```")
    sections.append(f"### git log --oneline -5\n```\n{packet.git_log or '(no commits)'}\n```")
    if packet.git_show_stat:
        sections.append(f"### git show HEAD --stat\n```\n{packet.git_show_stat}\n```")

    # Priority: uncommitted working-tree changes > all task commits > last commit only.
    # session_diff_content covers the common case where the agent committed before review ran.
    sections.append("\n## GIT DIFF CONTENT (for code quality review)")
    diff_content = (
        packet.git_diff_content
        or packet.session_diff_content
        or packet.git_show_content
    )
    if diff_content:
        if packet.git_diff_content:
            label = "working tree diff (uncommitted changes)"
        elif packet.session_diff_content:
            label = "session diff (all commits since task start)"
        else:
            label = "HEAD commit diff (last commit only — session_diff unavailable)"
        sections.append(f"({label})")
        sections.append(f"```diff\n{diff_content}\n```")
    else:
        sections.append("(No diff content available — skip categories 9-13, 19)")

    sections.append("\n## OVERSIZED FILES — justification required (Category 19)")
    if packet.oversized_files:
        missing: list[tuple[str, int]] = []
        for path, count in packet.oversized_files:
            tier = "800+" if count >= 800 else "400-799"
            record = packet.file_size_reasons.get(path)
            if record:
                reason = record.get("reason", "")
                registered_tier = record.get("tier", tier)
                tier_mismatch = (tier == "800+" and registered_tier == "400-799")
                mismatch_note = " ⚠ FILE GREW INTO 800+ TIER — RE-REGISTRATION REQUIRED" if tier_mismatch else ""
                sections.append(
                    f"  {path}: {count} lines [{tier}]{mismatch_note}\n"
                    f"    Justification: \"{reason}\""
                )
            else:
                sections.append(
                    f"  {path}: {count} lines [{tier}]\n"
                    f"    *** NO JUSTIFICATION REGISTERED ***"
                )
                missing.append((path, count))
        if missing:
            sections.append("\nTo register justifications (run from project root):")
            for path, _ in missing:
                sections.append(
                    f'  python3 ~/.claude/hooks/utils/file_size_registry.py'
                    f' register {path} "<why this file is large>"'
                )
    else:
        sections.append("None — all files under threshold")

    sections.append("\n## ROOT CLEANLINESS")
    if packet.root_clean:
        sections.append("Clean — no violations")
    else:
        sections.append("VIOLATIONS:")
        for v in packet.root_violations:
            sections.append(f"  {v}")

    return "\n".join(sections)


# ── LLM Client ────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    """Extract JSON from a response that may be wrapped in markdown code blocks."""
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0).strip()
    return text.strip()


def call_reviewer(
    messages: list[dict],  # type: ignore[type-arg]
    config: ReviewerConfig,
) -> dict:  # type: ignore[type-arg]
    """Call the reviewer LLM with conversation history.

    Returns parsed response: {"verdict": "APPROVED"|"FINDINGS", ...}
    On failure: returns {"verdict": "ERROR", "detail": "..."}.
    Never raises — callers depend on the ERROR dict for graceful degradation.

    # EXTENSION POINT: add new providers by extending the if/elif chain below.
    """
    # @stable: ERROR dict shape — callers check verdict=="ERROR" then read "detail"
    if config.provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return {"verdict": "ERROR", "detail": "DEEPSEEK_API_KEY not set"}
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"verdict": "ERROR", "detail": "OPENAI_API_KEY not set"}

    try:
        from openai import OpenAI

        client = (
            OpenAI(api_key=api_key, base_url="https://api.deepseek.com/v1")
            if config.provider == "deepseek"
            else OpenAI(api_key=api_key)
        )

        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            max_completion_tokens=config.max_tokens,
            response_format={"type": "json_object"},
            timeout=config.timeout_per_round,
        )
        content = (response.choices[0].message.content or "").strip()

        if not content:
            return {"verdict": "ERROR", "detail": f"Model '{config.model}' returned empty response"}

        json_str = _extract_json(content)
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            # Ask the model to fix its output rather than failing immediately
            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": (
                "Your response was not valid JSON. Please respond with EXACTLY "
                "one JSON object matching the verdict format specified in your "
                "instructions. No markdown, no explanation — just the JSON."
            )})
            retry_response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                max_completion_tokens=config.max_tokens,
                response_format={"type": "json_object"},
                timeout=config.timeout_per_round,
            )
            retry_content = (retry_response.choices[0].message.content or "").strip()
            if not retry_content:
                return {"verdict": "ERROR", "detail": f"Model '{config.model}' returned empty response on retry"}
            parsed = json.loads(_extract_json(retry_content))

        if parsed.get("verdict") not in ("APPROVED", "FINDINGS"):
            return {"verdict": "ERROR", "detail": f"Invalid verdict: {parsed.get('verdict')}"}

        return parsed  # type: ignore[no-any-return]

    except json.JSONDecodeError as e:
        return {"verdict": "ERROR", "detail": f"JSON parse error: {e}"}
    except Exception as e:
        return {"verdict": "ERROR", "detail": f"{type(e).__name__}: {str(e)[:200]}"}


async def async_call_reviewer(messages: list[dict], config: ReviewerConfig) -> dict:  # type: ignore[type-arg]
    """Async wrapper for callers in async contexts.

    Runs call_reviewer in a thread pool so the blocking HTTP call doesn't stall
    the event loop. Returns the same dict shape as call_reviewer.

    # EXTENSION POINT: replace asyncio.to_thread with a native async OpenAI client
    # if DeepSeek adds streaming support.
    """
    import asyncio
    return await asyncio.to_thread(call_reviewer, messages, config)
