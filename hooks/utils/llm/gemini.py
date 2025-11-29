#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "google-genai",
#     "python-dotenv",
# ]
# ///

"""
Google Gemini LLM Integration

Supports both Gemini 2.5 Flash (fast, efficient) and Gemini 3 Pro (advanced).

API Key: Get from Google AI Studio (https://aistudio.google.com/)
Environment Variable: GOOGLE_API_KEY

Models:
- gemini-2.5-flash: Best for large scale, low-latency, high volume tasks
- gemini-3-pro: Most advanced Google model
"""

import os
import sys
from dotenv import load_dotenv


def prompt_llm(prompt_text, model="gemini-2.5-flash"):
    """
    Base Google Gemini LLM prompting method.

    Args:
        prompt_text (str): The prompt to send to the model
        model (str): Model to use (gemini-2.5-flash or gemini-3-pro)

    Returns:
        str: The model's response text, or None if error
    """
    load_dotenv()

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=model,
            contents=prompt_text,
        )

        return response.text.strip()

    except Exception:
        return None


def generate_completion_message(project_name=None):
    """
    Generate a completion message using Google Gemini.

    Args:
        project_name (str): Optional project name to include in message

    Returns:
        str: A natural language completion message, or None if error
    """
    engineer_name = os.getenv("ENGINEER_NAME", "").strip()

    # Build requirements based on available context
    if project_name and engineer_name:
        name_instruction = f"MUST include the project name '{project_name}' in EVERY message. Sometimes (about 30% of the time) also include the engineer's name '{engineer_name}' in a natural way."
        examples = f"""Examples of the style:
- Standard: "{project_name} is complete!", "All done on {project_name}!", "{project_name} is ready!", "Finished work on {project_name}!"
- Personalized: "{engineer_name}, {project_name} is ready!", "{project_name} is done, {engineer_name}!", "Complete on {project_name}, {engineer_name}!", "{engineer_name}, {project_name} tasks complete!" """
    elif project_name:
        name_instruction = f"MUST include the project name '{project_name}' in EVERY message."
        examples = f"""Examples of the style: "{project_name} is complete!", "All done on {project_name}!", "{project_name} is ready!", "Finished work on {project_name}!", "{project_name} tasks complete!" """
    elif engineer_name:
        name_instruction = f"Sometimes (about 30% of the time) include the engineer's name '{engineer_name}' in a natural way."
        examples = f"""Examples of the style:
- Standard: "Work complete!", "All done!", "Task finished!", "Ready for your next move!"
- Personalized: "{engineer_name}, all set!", "Ready for you, {engineer_name}!", "Complete, {engineer_name}!", "{engineer_name}, we're done!" """
    else:
        name_instruction = ""
        examples = """Examples of the style: "Work complete!", "All done!", "Task finished!", "Ready for your next move!" """

    prompt = f"""Generate a short, friendly completion message for when an AI coding assistant finishes a task.

Requirements:
- Keep it under 10 words
- Make it positive and future focused
- Use natural, conversational language
- Focus on completion/readiness
- Do NOT include quotes, formatting, or explanations
- Return ONLY the completion message text
{name_instruction}

{examples}

Generate ONE completion message:"""

    response = prompt_llm(prompt, model="gemini-2.5-flash")

    # Clean up response - remove quotes and extra formatting
    if response:
        response = response.strip().strip('"').strip("'").strip()
        # Take first line if multiple lines
        response = response.split("\n")[0].strip()

    return response


def generate_agent_name():
    """
    Generate a one-word agent name using Google Gemini.

    Returns:
        str: A single-word agent name, or fallback name if error
    """
    import random

    # Example names to guide generation
    example_names = [
        "Phoenix", "Sage", "Nova", "Echo", "Atlas", "Cipher", "Nexus",
        "Oracle", "Quantum", "Zenith", "Aurora", "Vortex", "Nebula",
        "Catalyst", "Prism", "Axiom", "Helix", "Flux", "Synth", "Vertex"
    ]

    # If no API key, return random fallback
    if not os.getenv("GOOGLE_API_KEY"):
        return random.choice(example_names)

    # Create examples string
    examples_str = ", ".join(example_names[:10])  # Use first 10 as examples

    prompt_text = f"""Generate exactly ONE unique agent/assistant name.

Requirements:
- Single word only (no spaces, hyphens, or punctuation)
- Abstract and memorable
- Professional sounding
- Easy to pronounce
- Similar style to these examples: {examples_str}

Generate a NEW name (not from the examples). Respond with ONLY the name, nothing else.

Name:"""

    try:
        # Use Gemini 2.5 Flash for fast generation
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise Exception("No API key")

        from google import genai
        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt_text,
        )

        # Extract and clean the name
        name = response.text.strip()
        # Ensure it's a single word
        name = name.split()[0] if name else "Agent"
        # Remove any punctuation
        name = ''.join(c for c in name if c.isalnum())
        # Capitalize first letter
        name = name.capitalize() if name else "Agent"

        # Validate it's not empty and reasonable length
        if name and 3 <= len(name) <= 20:
            return name
        else:
            raise Exception("Invalid name generated")

    except Exception:
        # Return random fallback name
        return random.choice(example_names)


def analyze_context(prompt_text, use_advanced=False):
    """
    Analyze context and generate guidance for prompt hooks.

    Uses Gemini 2.5 Flash (fast) or Gemini 3 Pro (advanced) based on parameter.

    Args:
        prompt_text (str): The analysis prompt
        use_advanced (bool): Use Gemini 3 Pro for more complex analysis

    Returns:
        str: Analysis result or None if error
    """
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return None

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        # Choose model based on complexity
        model = "gemini-3-pro" if use_advanced else "gemini-2.5-flash"

        response = client.models.generate_content(
            model=model,
            contents=prompt_text,
        )

        return response.text.strip()

    except Exception:
        return None


def main():
    """Command line interface for testing."""
    import json

    if len(sys.argv) > 1:
        if sys.argv[1] == "--completion":
            # Check for --project flag
            project_name = None
            if len(sys.argv) > 3 and sys.argv[2] == "--project":
                project_name = sys.argv[3]

            message = generate_completion_message(project_name)
            if message:
                print(message)
            else:
                print("Error generating completion message")
        elif sys.argv[1] == "--agent-name":
            # Generate agent name (no input needed)
            name = generate_agent_name()
            print(name)
        elif sys.argv[1] == "--analyze":
            # Context analysis for prompt hooks
            if len(sys.argv) > 2:
                # Check for --advanced flag
                use_advanced = "--advanced" in sys.argv
                prompt_parts = [arg for arg in sys.argv[2:] if arg != "--advanced"]
                prompt_text = " ".join(prompt_parts)

                result = analyze_context(prompt_text, use_advanced=use_advanced)
                if result:
                    print(result)
                else:
                    print("Error analyzing context")
            else:
                print("Usage: ./gemini.py --analyze 'analysis prompt' [--advanced]")
        elif sys.argv[1] == "--model":
            # Test with specific model
            if len(sys.argv) > 3:
                model = sys.argv[2]
                prompt_text = " ".join(sys.argv[3:])
                response = prompt_llm(prompt_text, model=model)
                if response:
                    print(response)
                else:
                    print(f"Error calling Gemini API with model {model}")
            else:
                print("Usage: ./gemini.py --model <model-name> 'your prompt'")
        else:
            prompt_text = " ".join(sys.argv[1:])
            response = prompt_llm(prompt_text)
            if response:
                print(response)
            else:
                print("Error calling Google Gemini API")
    else:
        print("Usage: ./gemini.py 'your prompt here'")
        print("       ./gemini.py --completion")
        print("       ./gemini.py --agent-name")
        print("       ./gemini.py --analyze 'prompt' [--advanced]")
        print("       ./gemini.py --model <model-name> 'prompt'")


if __name__ == "__main__":
    main()
