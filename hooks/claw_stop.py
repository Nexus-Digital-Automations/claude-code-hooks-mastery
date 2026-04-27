#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///
"""Protocol compliance reviewer entry point for claw-code-parity projects.

Usage:
    uv run --script claw_stop.py <working_dir> [--last-message <msg>] [--json]

Exit codes:
    0 — APPROVED
    1 — FINDINGS (blocking issues found)
    2 — ERROR (reviewer failed to run)

Conversation history is persisted to {working_dir}/.claw/data/
so that successive invocations within a session build on prior context.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Fix Python environment before any imports
for _var in ["PYTHONHOME", "PYTHONPATH"]:
    if _var in os.environ:
        del os.environ[_var]

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / ".claude" / ".env")
    load_dotenv()
except ImportError:
    pass

# Add utils dir to path
_HOOKS_DIR = Path(__file__).parent
_UTILS_DIR = _HOOKS_DIR / "utils"
sys.path.insert(0, str(_UTILS_DIR))

from review_types import (  # noqa: E402
    ReviewPacket,
    ReviewerConfig,
    call_reviewer,
    format_packet_for_prompt,
)
from packet_builder_claw import build_claw_packet  # noqa: E402

_PROTOCOL_REF = _HOOKS_DIR.parent / "docs" / "protocol-compliance-reference.md"


# ── Reviewer Config ───────────────────────────────────────────────────

def load_claw_reviewer_config(working_dir: Path) -> ReviewerConfig:
    """Load from {working_dir}/.claw/data/reviewer_config.json, else defaults."""
    config_file = working_dir / ".claw" / "data" / "reviewer_config.json"
    try:
        if config_file.exists():
            data = json.loads(config_file.read_text())
            return ReviewerConfig(**{
                k: v for k, v in data.items()
                if k in ReviewerConfig.__dataclass_fields__
            })
    except Exception:
        pass
    return ReviewerConfig()


# ── Conversation Management ───────────────────────────────────────────

def _claw_data_dir(working_dir: Path) -> Path:
    return working_dir / ".claw" / "data"


def _conv_file(working_dir: Path, session_id: str) -> Path:
    return _claw_data_dir(working_dir) / f"review_conversation_{session_id}.json"


def load_claw_conversation(working_dir: Path, session_id: str) -> list[dict]:
    """Load conversation history for a claw session."""
    try:
        f = _conv_file(working_dir, session_id)
        if not f.exists():
            return []
        raw = json.loads(f.read_text())
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict) and "messages" in raw:
            # Check project root to prevent cross-project contamination
            stored_root = raw.get("project_root", "")
            current_root = str(working_dir.resolve())
            if stored_root and stored_root != current_root:
                print(
                    f"[claw-reviewer] Clearing stale conversation — "
                    f"project root changed ({stored_root!r} → {current_root!r})",
                    file=sys.stderr,
                )
                f.unlink(missing_ok=True)
                return []
            return raw["messages"]
    except Exception:
        pass
    return []


def save_claw_conversation(
    working_dir: Path,
    session_id: str,
    messages: list[dict],
) -> None:
    """Persist conversation history."""
    try:
        data_dir = _claw_data_dir(working_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        _conv_file(working_dir, session_id).write_text(
            json.dumps(
                {
                    "project_root": str(working_dir.resolve()),
                    "messages": messages,
                },
                indent=2,
            )
        )
    except Exception:
        pass


# ── System Prompt ─────────────────────────────────────────────────────

def load_system_prompt() -> str | None:
    try:
        if _PROTOCOL_REF.exists():
            return _PROTOCOL_REF.read_text()
    except Exception:
        pass
    return None


# ── Review Result ─────────────────────────────────────────────────────

@dataclass
class ReviewResult:
    approved: bool = False
    round_count: int = 0
    findings: list[dict] = field(default_factory=list)
    summary: str = ""
    error: str = ""


# ── Main Review Loop ──────────────────────────────────────────────────

def run_claw_review(
    working_dir: Path,
    packet: ReviewPacket,
    config: ReviewerConfig,
) -> ReviewResult:
    """Run one protocol review round for a claw-code-parity session."""
    if not config.enabled:
        return ReviewResult(approved=True, summary="Reviewer disabled in config")

    if not os.getenv("OPENAI_API_KEY"):
        return ReviewResult(
            approved=True,
            summary="Reviewer skipped — OPENAI_API_KEY not set",
            error="no_api_key",
        )

    system_prompt = load_system_prompt()
    if not system_prompt:
        return ReviewResult(
            approved=True,
            summary="Reviewer skipped — protocol reference not found",
            error="no_system_prompt",
        )

    packet_text = format_packet_for_prompt(packet)
    session_id = packet.session_id

    history = load_claw_conversation(working_dir, session_id)
    round_count = len([m for m in history if m.get("role") == "user"]) + 1

    if round_count > config.max_rounds:
        return ReviewResult(
            approved=True,
            summary=f"Max review rounds ({config.max_rounds}) reached — auto-approving",
            round_count=round_count,
        )

    last_request_text = "(no request captured)"
    if packet.user_requests:
        last_request_text = packet.user_requests[-1].get("prompt", "(empty)")[:300]

    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({
        "role": "user",
        "content": (
            f"## REVIEW ROUND {round_count}\n\n"
            f"Review the following work for protocol compliance.\n\n"
            f"**MANDATORY PASS/FAIL CHECK:** The most recent user request was:\n"
            f"> {last_request_text}\n\n"
            f"Your response MUST include an explicit line:\n"
            f"  LAST REQUEST: PASS — <brief explanation>\n"
            f"  OR\n"
            f"  LAST REQUEST: FAIL — <what is missing or incomplete>\n\n"
            f"If the last request is FAIL, the overall verdict MUST be FINDINGS.\n\n"
            f"{packet_text}"
        ),
    })

    response = call_reviewer(messages, config)

    history.append({
        "role": "user",
        "content": f"[Round {round_count} review packet — {packet.timestamp}]",
    })
    history.append({
        "role": "assistant",
        "content": json.dumps(response),
    })
    save_claw_conversation(working_dir, session_id, history)

    if response.get("verdict") == "ERROR":
        return ReviewResult(
            approved=True,
            summary=f"Reviewer error (non-blocking): {response.get('detail', 'unknown')}",
            error=response.get("detail", "unknown"),
            round_count=round_count,
        )

    if response.get("verdict") == "APPROVED":
        return ReviewResult(
            approved=True,
            summary=response.get("summary", "Approved"),
            round_count=round_count,
        )

    return ReviewResult(
        approved=False,
        findings=response.get("findings", []),
        summary=response.get("summary", "Issues found"),
        round_count=round_count,
    )


# ── CLI Entry Point ───────────────────────────────────────────────────

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Protocol compliance reviewer for claw-code-parity projects"
    )
    parser.add_argument(
        "working_dir",
        help="Root of the claw-code-parity project to review",
    )
    parser.add_argument(
        "--last-message", default="",
        help="Override last assistant message (for category 14 review)",
    )
    parser.add_argument(
        "--session", default=None,
        help="Explicit session JSON file path (default: most recent in working_dir/.claude/sessions/)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output structured JSON (exit 0=APPROVED, 1=FINDINGS, 2=ERROR)",
    )
    args = parser.parse_args()

    working_dir = Path(args.working_dir).resolve()
    if not working_dir.is_dir():
        print(f"ERROR: working_dir does not exist: {working_dir}", file=sys.stderr)
        sys.exit(2)

    session_file = Path(args.session).resolve() if args.session else None
    config = load_claw_reviewer_config(working_dir)

    if not args.json:
        print(f"Running claw protocol review for: {working_dir}")
        print(f"Model: {config.model}")
        print()

    packet = build_claw_packet(
        working_dir,
        session_file=session_file,
        reviewer_config=config,
    )
    if args.last_message:
        packet.last_assistant_message = args.last_message[:3000]

    result = run_claw_review(working_dir, packet, config)

    if args.json:
        output = {
            "approved": result.approved,
            "round_count": result.round_count,
            "summary": result.summary,
            "error": result.error,
            "findings": result.findings,
        }
        print(json.dumps(output))
        if result.approved:
            sys.exit(0)
        elif result.error:
            sys.exit(2)
        else:
            sys.exit(1)
    else:
        if result.approved:
            print(f"APPROVED (round {result.round_count})")
            print(f"  {result.summary}")
            if result.error:
                print(f"  Note: {result.error}")
        else:
            print(f"FINDINGS (round {result.round_count}/{config.max_rounds})")
            print()
            for finding in result.findings:
                sev = "BLOCK" if finding.get("severity") == "blocking" else "ADVSR"
                print(f"  [{sev}] [{finding.get('category', '?')}]")
                print(f"    {finding.get('description', '')}")
                if finding.get("evidence"):
                    print(f"    Evidence: {finding['evidence'][:200]}")
                if finding.get("evidence_needed"):
                    print(f"    Needed: {finding['evidence_needed']}")
                print()
            print(f"Summary: {result.summary}")


if __name__ == "__main__":
    main()
