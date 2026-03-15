#!/usr/bin/env python3
"""
Custom promptfoo provider for DeepSeek reviewer tests.

Imports _SYSTEM_PROMPT directly from deepseek_verifier.py so tests always
reflect the current system prompt without any manual sync step.

Usage in yaml:
  providers:
    - id: file://deepseek_review_provider.py
"""

import json
import os
import sys
from pathlib import Path


def _get_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    env_file = Path.home() / ".claude" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                if key:
                    return key
    return None


def _get_system_prompt():
    hooks_dir = Path.home() / ".claude" / "hooks" / "utils"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    from deepseek_verifier import _SYSTEM_PROMPT  # noqa: PLC0415
    return _SYSTEM_PROMPT


def call_api(prompt, options, context):
    """Entry point called by promptfoo for each test case.

    Expects context['vars']['evidence_record'] — a pre-formatted string
    containing the WORK CONTEXT + step evidence to feed the reviewer.
    """
    api_key = _get_api_key()
    if not api_key:
        return {
            "error": (
                "DEEPSEEK_API_KEY not found. Set it via:\n"
                "  export DEEPSEEK_API_KEY=sk-...\n"
                "  OR add DEEPSEEK_API_KEY=sk-... to ~/.claude/.env"
            )
        }

    vars_ = (context or {}).get("vars", {})
    evidence_record = vars_.get("evidence_record") or str(prompt)

    try:
        system_prompt = _get_system_prompt()
    except Exception as exc:
        return {"error": f"Failed to load system prompt: {exc}"}

    try:
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": evidence_record},
            ],
            max_tokens=900,
            temperature=0.1,
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

    except Exception as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    input_data = json.loads(sys.stdin.read())
    result = call_api(
        input_data.get("prompt", ""),
        input_data.get("options", {}),
        input_data.get("context", {}),
    )
    print(json.dumps(result))
