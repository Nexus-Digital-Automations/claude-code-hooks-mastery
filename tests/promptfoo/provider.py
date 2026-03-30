#!/usr/bin/env python3
"""
Custom promptfoo provider using OpenAI API.
Reads OPENAI_API_KEY from env or ~/.claude/.env.

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

    cfg = options.get("config", {})
    model = cfg.get("model", "gpt-4o-mini")
    max_tokens = cfg.get("max_tokens", 400)
    temperature = cfg.get("temperature", 0.0)

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        # Parse prompt into messages list
        if isinstance(prompt, list):
            messages = prompt
        else:
            try:
                parsed = json.loads(prompt)
                messages = parsed if isinstance(parsed, list) else [{"role": "user", "content": prompt}]
            except (json.JSONDecodeError, TypeError):
                messages = [{"role": "user", "content": str(prompt)}]

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
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
