#!/usr/bin/env python3
"""
Structural analysis of all agent and skill prompt files.
Reports quality issues without LLM API calls.

Usage:
    python3 tests/promptfoo/analyze-prompts.py [--fix] [--report]
"""

import re
import sys
import json
import argparse
from pathlib import Path

ROOT = Path.home() / ".claude"
AGENTS_DIR = ROOT / "agents"
SKILLS_DIR = ROOT / "skills"

# ── Structural checks ────────────────────────────────────────────────────────

REQUIRED_FRONTMATTER = {"name", "description"}
WEAK_DESCRIPTION_PATTERNS = [
    r"^Agent\s*$", r"^TODO", r"^TBD", r"placeholder", r"replace this",
    r"^<.*>$", r"^Agent Name$", r"^generated"
]
PLACEHOLDER_PATTERNS = [
    r"\$ARGUMENTS", r"\{\{[A-Z_]+\}\}", r"<YOUR_", r"<<REPLACE",
    r"INSERT_HERE", r"TODO:", r"\[PLACEHOLDER\]",
]
WEAK_SECTIONS = ["## Instructions", "## Context", "## Purpose", "## Capabilities",
                 "## Core", "## You are", "## When to Use"]


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body. Returns (frontmatter_dict, body)."""
    if not content.startswith("---"):
        return {}, content

    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return {}, content

    fm_text = content[3:end_idx].strip()
    body = content[end_idx + 4:].strip()
    fm = {}
    for line in fm_text.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, body


def check_agent(path: Path) -> list[dict]:
    """Check a single agent file for structural issues."""
    issues = []
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"file": str(path), "severity": "error", "issue": f"Cannot read: {e}"}]

    # Skip index/contributing/license files
    if path.name in ("AGENT_INDEX.md", "PLUGINS_INDEX.md", "CONTRIBUTING.md",
                     "README.md", "LICENSE", "AGENT_INDEX.md"):
        return []

    fm, body = parse_frontmatter(content)

    def add(severity, issue, suggestion=None):
        entry = {"file": str(path.relative_to(ROOT)), "severity": severity, "issue": issue}
        if suggestion:
            entry["suggestion"] = suggestion
        issues.append(entry)

    # 1. Frontmatter presence
    if not fm:
        add("error", "Missing frontmatter (---)",
            "Add ---\\nname: <slug>\\ndescription: <what it does>\\n---")
        return issues

    # 2. Required fields
    for field in REQUIRED_FRONTMATTER:
        if field not in fm or not fm[field]:
            add("error", f"Missing required frontmatter field: '{field}'",
                f"Add {field}: <value> to frontmatter")

    # 3. Name quality
    name = fm.get("name", "")
    for pat in WEAK_DESCRIPTION_PATTERNS:
        if re.search(pat, name, re.IGNORECASE):
            add("error", f"Placeholder/template name: '{name}'",
                "Replace with a specific, descriptive agent name")

    # 4. Description quality
    desc = fm.get("description", "")
    if len(desc) < 20:
        add("warning", f"Description too short ({len(desc)} chars): '{desc}'",
            "Write a specific 1-2 sentence description explaining what this agent does")
    elif len(desc) < 50:
        add("info", f"Description is brief ({len(desc)} chars) — consider expanding")
    for pat in WEAK_DESCRIPTION_PATTERNS:
        if re.search(pat, desc, re.IGNORECASE):
            add("warning", f"Description looks generic/placeholder: '{desc[:80]}'",
                "Write a specific description with the agent's specialization")
    if "Use PROACTIVELY" not in desc and "use proactively" not in desc.lower():
        # Not all agents need this, just note it
        pass

    # 5. Body content
    if len(body.strip()) < 50:
        add("error", "System prompt body is nearly empty (< 50 chars)",
            "Add role definition, capabilities, and instructions")
    elif len(body.strip()) < 200:
        add("warning", f"Thin system prompt ({len(body.strip())} chars) — may lack guidance",
            "Consider adding more specific capabilities and instruction sections")

    # 6. Role definition check
    role_patterns = [r"You are", r"you are", r"Your role", r"your role",
                     r"^# ", r"As an expert", r"As a "]
    has_role = any(re.search(p, body[:500]) for p in role_patterns)
    if not has_role:
        add("warning", "System prompt doesn't clearly define the agent's role",
            "Start the system prompt with 'You are a...' or 'Your role is...'")

    # 7. Placeholder text in body
    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, body, re.IGNORECASE):
            add("warning", f"Placeholder text found matching '{pat}'",
                "Remove or replace placeholder text with actual content")

    # 8. Template leftover check
    if "your name here" in body.lower() or "[INSERT" in body.upper():
        add("error", "Template text left unreplaced in body")

    return issues


def check_skill(skill_dir: Path) -> list[dict]:
    """Check a skill directory for structural issues."""
    # Follow symlinks
    try:
        resolved = skill_dir.resolve()
    except Exception:
        return [{"file": str(skill_dir.relative_to(ROOT)), "severity": "error",
                 "issue": "Broken symlink"}]

    skill_md = resolved / "SKILL.md"
    if not skill_md.exists():
        # Check for other .md files
        mds = list(resolved.glob("*.md"))
        if not mds:
            return [{"file": str(skill_dir.relative_to(ROOT)), "severity": "error",
                     "issue": "No SKILL.md found and no .md files"}]
        return []  # Has content, just named differently

    return check_agent(skill_md)  # Reuse agent checks (same structure)


def scan_all() -> dict:
    """Scan all agents and skills. Return structured results."""
    results = {"agents": [], "skills": [], "summary": {}}

    # Scan all agent .md files recursively
    agent_files = [p for p in AGENTS_DIR.rglob("*.md")
                   if p.name not in ("AGENT_INDEX.md", "PLUGINS_INDEX.md",
                                     "CONTRIBUTING.md", "README.md", "LICENSE")]
    for path in sorted(agent_files):
        issues = check_agent(path)
        if issues:
            results["agents"].extend(issues)

    # Scan skill directories
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if skill_dir.name.startswith("."):
            continue
        if skill_dir.is_dir() or skill_dir.is_symlink():
            issues = check_skill(skill_dir)
            if issues:
                results["skills"].extend(issues)

    # Summary
    all_issues = results["agents"] + results["skills"]
    results["summary"] = {
        "total_issues": len(all_issues),
        "errors": sum(1 for i in all_issues if i.get("severity") == "error"),
        "warnings": sum(1 for i in all_issues if i.get("severity") == "warning"),
        "info": sum(1 for i in all_issues if i.get("severity") == "info"),
        "agent_files_scanned": len(agent_files),
        "skill_dirs_scanned": sum(1 for d in SKILLS_DIR.iterdir()
                                   if not d.name.startswith(".")),
    }
    return results


def print_report(results: dict, verbose: bool = False):
    """Print human-readable report."""
    s = results["summary"]
    print("\n" + "=" * 70)
    print("PROMPT STRUCTURAL ANALYSIS REPORT")
    print("=" * 70)
    print(f"Agent files scanned : {s['agent_files_scanned']}")
    print(f"Skill dirs scanned  : {s['skill_dirs_scanned']}")
    print(f"Total issues        : {s['total_issues']}")
    print(f"  Errors            : {s['errors']}")
    print(f"  Warnings          : {s['warnings']}")
    print(f"  Info              : {s['info']}")
    print()

    def print_section(label, issues):
        if not issues:
            print(f"✅ {label}: No issues found")
            return
        errors = [i for i in issues if i.get("severity") == "error"]
        warnings = [i for i in issues if i.get("severity") == "warning"]
        info = [i for i in issues if i.get("severity") == "info"]

        print(f"\n{'─' * 70}")
        print(f"  {label.upper()}")
        print(f"{'─' * 70}")

        for severity, items, icon in [("ERRORS", errors, "🔴"),
                                       ("WARNINGS", warnings, "⚠️ "),
                                       ("INFO", info, "ℹ️ ")]:
            if not items:
                continue
            print(f"\n{icon} {severity} ({len(items)}):")
            for issue in items:
                print(f"  {issue['file']}")
                print(f"    → {issue['issue']}")
                if verbose and issue.get("suggestion"):
                    print(f"    💡 {issue['suggestion']}")

    print_section("AGENT PROMPTS", results["agents"])
    print_section("SKILL PROMPTS", results["skills"])

    all_issues = results["agents"] + results["skills"]
    errors = [i for i in all_issues if i.get("severity") == "error"]
    print("\n" + "=" * 70)
    if errors:
        print(f"❌ FAILED: {len(errors)} errors must be fixed")
    else:
        print("✅ PASS: No structural errors found")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Analyze agent/skill prompt quality")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show suggestions")
    parser.add_argument("--errors-only", action="store_true", help="Only show errors")
    parser.add_argument("--output", help="Write JSON results to file")
    args = parser.parse_args()

    print("Scanning agent and skill prompts...", file=sys.stderr)
    results = scan_all()

    if args.errors_only:
        results["agents"] = [i for i in results["agents"] if i.get("severity") == "error"]
        results["skills"] = [i for i in results["skills"] if i.get("severity") == "error"]

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, verbose=args.verbose)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2))
        print(f"\nResults written to {args.output}", file=sys.stderr)

    # Exit code: 1 if errors, 0 if only warnings/info
    all_issues = results["agents"] + results["skills"]
    errors = [i for i in all_issues if i.get("severity") == "error"]
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
