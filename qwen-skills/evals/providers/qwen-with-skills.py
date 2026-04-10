"""Custom promptfoo provider that injects deepseek-skills like server.py does.

Reads index.json, matches keywords against the prompt, prepends matched skill
content, then sends to DeepSeek-V3 via OpenAI-compatible API.
"""

import json
import os
import re
from pathlib import Path


SKILLS_DIR = Path.home() / ".claude" / "deepseek-skills"
INDEX_PATH = SKILLS_DIR / "index.json"

# DeepSeek API config — set DEEPSEEK_API_KEY env var
API_BASE = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")


def _load_index():
    """Load and return skills index."""
    if not INDEX_PATH.exists():
        return {"skills": []}
    return json.loads(INDEX_PATH.read_text())


def _strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter (--- ... ---) from skill content."""
    if content.startswith("---"):
        end = content.find("---", 3)
        if end != -1:
            return content[end + 3:].strip()
    return content


def _resolve_skills(task: str) -> tuple[str, list[str]]:
    """Match task against index.json keywords and return (injected_content, skill_names)."""
    index = _load_index()
    task_lower = task.lower()
    matched = []

    for skill in index.get("skills", []):
        if skill.get("always_include"):
            matched.append(skill)
            continue
        keywords = skill.get("keywords", [])
        if any(kw in task_lower for kw in keywords):
            matched.append(skill)

    if not matched:
        return "", []

    sections = []
    names = []
    for skill in matched:
        skill_path = SKILLS_DIR / skill["path"]
        if skill_path.exists():
            content = _strip_frontmatter(skill_path.read_text().strip())
            sections.append(content)
            names.append(skill["name"])

    return "\n\n---\n\n".join(sections), names


def call_api(prompt, options, context):
    """Promptfoo provider entry point.

    Returns dict with 'output' key (the model response text).
    Also attaches metadata about which skills were injected.
    """
    # Resolve skills based on the prompt
    skill_content, skill_names = _resolve_skills(prompt)

    # Build the full prompt with skills injected
    if skill_content:
        full_prompt = prompt + "\n\n" + skill_content
    else:
        full_prompt = prompt

    # Token count metadata (approximate: chars / 4)
    skill_token_estimate = len(skill_content) // 4

    # If no API key, return skill injection metadata only (dry-run mode)
    if not API_KEY:
        return {
            "output": f"[DRY RUN — no DEEPSEEK_API_KEY set]\n\nSkills injected: {', '.join(skill_names)}\nEst. skill tokens: {skill_token_estimate}\n\nFull prompt ({len(full_prompt)} chars) would be sent to {MODEL}.",
            "tokenUsage": {"total": 0, "prompt": skill_token_estimate, "completion": 0},
            "metadata": {
                "skills_injected": skill_names,
                "skill_token_estimate": skill_token_estimate,
            },
        }

    # Call DeepSeek API
    try:
        import openai

        client = openai.OpenAI(api_key=API_KEY, base_url=API_BASE)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            max_tokens=options.get("config", {}).get("max_tokens", 2048),
            temperature=options.get("config", {}).get("temperature", 0.0),
        )
        output_text = response.choices[0].message.content or ""
        usage = response.usage
        return {
            "output": output_text,
            "tokenUsage": {
                "total": usage.total_tokens if usage else 0,
                "prompt": usage.prompt_tokens if usage else 0,
                "completion": usage.completion_tokens if usage else 0,
            },
            "metadata": {
                "skills_injected": skill_names,
                "skill_token_estimate": skill_token_estimate,
            },
        }
    except Exception as e:
        return {"error": str(e)}
