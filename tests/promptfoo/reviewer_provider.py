#!/usr/bin/env python3
"""
Custom promptfoo provider for the stop-hook reviewer.
Reads protocol-compliance-reference.md as the system prompt,
then calls gpt-4o-mini with the evidence record as the user message.

Model: gpt-4o-mini
"""

import json
import os
import sys
from pathlib import Path


def get_api_key():
    # 1. Environment variable
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key

    # 2. ~/.claude/.env file
    env_file = Path.home() / ".claude" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key

    return None


def get_system_prompt():
    """Read the protocol compliance reference as the reviewer system prompt."""
    ref_file = Path.home() / ".claude" / "docs" / "protocol-compliance-reference.md"
    if ref_file.exists():
        return ref_file.read_text()
    return (
        "You are a protocol compliance reviewer. "
        "Review the evidence record and determine if the submission should be approved. "
        "Output JSON with 'approved' (boolean) and 'reason' (string)."
    )


def call_api(prompt, options, context):
    """Entry point called by promptfoo for each test case."""
    api_key = get_api_key()
    if not api_key:
        return {
            "error": (
                "OPENAI_API_KEY not found. Set it via:\n"
                "  export OPENAI_API_KEY=sk-...\n"
                "  OR add OPENAI_API_KEY=sk-... to ~/.claude/.env"
            )
        }

    system_prompt = get_system_prompt()

    # The prompt is the evidence_record passed directly
    if isinstance(prompt, str):
        user_message = prompt
    elif isinstance(prompt, list):
        # Extract content from messages list
        user_message = " ".join(
            m.get("content", "") for m in prompt if isinstance(m, dict)
        )
    else:
        user_message = str(prompt)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1500,
            temperature=0.2,
        )

        text = response.choices[0].message.content

        return {
            "output": text,
            "tokenUsage": {
                "prompt": response.usage.prompt_tokens,
                "completion": response.usage.completion_tokens,
                "total": response.usage.total_tokens,
            },
        }

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    input_data = json.loads(sys.stdin.read())
    result = call_api(
        input_data.get("prompt", ""),
        input_data.get("options", {}),
        input_data.get("context", {}),
    )
    print(json.dumps(result))
