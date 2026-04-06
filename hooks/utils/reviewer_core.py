"""Shared reviewer logic — no project-specific path dependencies.

Both the Claude Code reviewer (hooks/utils/reviewer.py) and the claw-code-parity
reviewer (hooks/claw_stop.py) import from this module.

Exports:
    ReviewerConfig  — LLM + budget configuration
    ReviewPacket    — structured context passed to the LLM
    format_packet_for_prompt(packet) -> str
    call_reviewer(messages, config) -> dict
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field


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


# ── Configuration ──────────────────────────────────────────────────────

@dataclass
class ReviewerConfig:
    model: str = "gpt-5-mini"
    temperature: float = 0.2
    max_tokens: int = 2000
    max_rounds: int = 5
    timeout_per_round: int = 30
    sandbox_timeout: int = 120
    sandbox_timeout_frontend: int = 300
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
    user_requests: list[dict] = field(default_factory=list)
    spec_status: list[dict] = field(default_factory=list)
    sandbox_results: dict[str, dict] = field(default_factory=dict)
    project_config: dict = field(default_factory=dict)
    git_status: str = ""
    git_diff: str = ""
    git_diff_content: str = ""
    git_log: str = ""
    git_show_stat: str = ""
    git_show_content: str = ""
    root_clean: bool = True
    root_violations: list[str] = field(default_factory=list)
    last_assistant_message: str = ""
    agent_commentary_summary: str = ""
    plan_content: str = ""
    timestamp: str = ""
    verification_artifacts: dict[str, str] = field(default_factory=dict)


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
        # If the user message is short, show what they were approving
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

    # Last assistant message (for Execute-Don't-Recommend check)
    sections.append("\n## LAST ASSISTANT MESSAGE")
    if packet.last_assistant_message:
        sections.append(packet.last_assistant_message)
    else:
        sections.append("(Not captured)")

    # Agent commentary summary (local model summary of all assistant messages)
    sections.append("\n## AGENT COMMENTARY SUMMARY (all assistant messages, summarized by local model)")
    if packet.agent_commentary_summary:
        sections.append(packet.agent_commentary_summary)
    else:
        sections.append("(Not available — Ollama may be offline or transcript empty)")

    # All user requests (current task only)
    sections.append("\n## ALL USER REQUESTS (current task only — filtered by task_id)")
    if packet.user_requests:
        for i, req in enumerate(packet.user_requests, 1):
            ts = req.get("timestamp", "?")
            prompt = req.get("prompt", "(empty)")
            marker = " ← MOST RECENT" if i == len(packet.user_requests) else ""
            sections.append(f"### Message {i} [{ts}]{marker}")
            sections.append(prompt)
            # Show what the user was responding to (for short confirmations)
            preceding = req.get("preceding_context", "")
            if preceding:
                sections.append(
                    f"\n> **Preceding assistant message (user was responding to this):**\n"
                    f"> {preceding}"
                )
    else:
        sections.append("(No user requests captured)")

    # Spec status
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

    # Approved plan (pre-implementation — proves spec-before-code compliance)
    sections.append("\n## APPROVED PLAN (pre-implementation)")
    if packet.plan_content:
        sections.append(
            "> This plan was approved BEFORE implementation began. "
            "It authorizes the features and approach described within."
        )
        sections.append(f"\n{packet.plan_content}")
    else:
        sections.append("(No plan file found — task may not have required a plan)")

    # Project config
    sections.append("\n## PROJECT CONFIG")
    sections.append(json.dumps(packet.project_config, indent=2))

    # Sandbox check results
    sections.append("\n## SANDBOX CHECK RESULTS (independently executed)")
    for key, result in packet.sandbox_results.items():
        if key.startswith("_git_"):
            continue  # Git results shown separately
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

    # Verification artifacts (output/*.txt, output/*.diff committed to repo)
    sections.append("\n## VERIFICATION ARTIFACTS (committed to output/)")
    if packet.verification_artifacts:
        for name, content in packet.verification_artifacts.items():
            sections.append(f"\n### {name}")
            sections.append(f"```\n{content}\n```")
    else:
        sections.append("(No artifacts found in output/)")

    # Git state
    sections.append("\n## GIT STATE")
    sections.append(f"### git status --porcelain\n```\n{packet.git_status or '(clean)'}\n```")
    sections.append(f"### git diff --stat\n```\n{packet.git_diff or '(no changes)'}\n```")
    sections.append(f"### git log --oneline -5\n```\n{packet.git_log or '(no commits)'}\n```")
    if packet.git_show_stat:
        sections.append(f"### git show HEAD --stat\n```\n{packet.git_show_stat}\n```")

    # Actual diff content for code quality review (categories 9-13)
    # Use working-tree diff if available; fall back to HEAD commit diff when all changes are committed
    sections.append("\n## GIT DIFF CONTENT (for code quality review)")
    diff_content = packet.git_diff_content or packet.git_show_content
    if diff_content:
        label = "working tree diff" if packet.git_diff_content else "HEAD commit diff (all changes committed)"
        sections.append(f"({label})")
        sections.append(f"```diff\n{diff_content}\n```")
    else:
        sections.append("(No diff content available — skip categories 9-13)")

    # Root cleanliness
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
    messages: list[dict],
    config: ReviewerConfig,
) -> dict:
    """Call GPT-5 Mini with conversation history.

    Returns parsed response: {"verdict": "APPROVED"|"FINDINGS", ...}
    On failure: returns {"verdict": "ERROR", "detail": "..."}.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"verdict": "ERROR", "detail": "OPENAI_API_KEY not set"}

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=config.model,
            messages=messages,
            max_completion_tokens=config.max_tokens,
            response_format={"type": "json_object"},
            timeout=config.timeout_per_round,
        )
        content = (response.choices[0].message.content or "").strip()

        # Detect empty responses (broken model — don't silently auto-approve)
        if not content:
            return {
                "verdict": "ERROR",
                "detail": f"Model '{config.model}' returned empty response",
            }

        # Parse JSON from response
        json_str = _extract_json(content)
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            # Retry: ask for valid JSON
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
                return {
                    "verdict": "ERROR",
                    "detail": f"Model '{config.model}' returned empty response on retry",
                }
            retry_json = _extract_json(retry_content)
            parsed = json.loads(retry_json)

        if parsed.get("verdict") not in ("APPROVED", "FINDINGS"):
            return {
                "verdict": "ERROR",
                "detail": f"Invalid verdict: {parsed.get('verdict')}",
            }

        return parsed

    except json.JSONDecodeError as e:
        return {"verdict": "ERROR", "detail": f"JSON parse error: {e}"}
    except Exception as e:
        err_type = type(e).__name__
        return {"verdict": "ERROR", "detail": f"{err_type}: {str(e)[:200]}"}
