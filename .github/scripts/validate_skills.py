#!/usr/bin/env python3
"""Validate every SKILL.md under skills/.

Per-file checks:
- Lives at exactly skills/<name>/SKILL.md (no scope, no nested sub-skills).
- Begins with a YAML frontmatter block (--- ... ---). CRLF and missing
  trailing newline are tolerated.
- Frontmatter parses as a YAML mapping.
- Required keys present and non-empty: name, description.
- Only spec-allowed keys (plus Claude Code extensions) are present.
- name is kebab-case, 1-64 chars, no leading/trailing/consecutive hyphens.
- name matches the parent directory name.

Exit 0 on success, 1 on any failure.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ALLOWED_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
    "version",
    "argument-hint",
    "disable-model-invocation",
    "user-invocable",
    "model",
    "context",
    "agent",
    "hooks",
}

NAME_RE = re.compile(r"^(?!-)(?!.*--)[a-z0-9-]{1,64}(?<!-)$")
FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\s*(\r?\n|\Z)", re.DOTALL)


def validate_path_shape(path: Path) -> str | None:
    parts = path.parts
    if len(parts) != 3 or parts[0] != "skills" or parts[2] != "SKILL.md":
        return (
            f"{path}: file is not at the documented path skills/<name>/SKILL.md "
            f"(nested sub-skills are not supported)"
        )
    return None


def validate_frontmatter(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return [f"{path}: missing or malformed YAML frontmatter (expected leading --- ... ---)"]

    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return [f"{path}: invalid YAML frontmatter: {exc}"]

    if not isinstance(fm, dict):
        return [f"{path}: frontmatter must be a YAML mapping"]

    errors: list[str] = []
    name = fm.get("name")
    description = fm.get("description")

    if not name:
        errors.append(f"{path}: missing required key 'name'")
    elif not isinstance(name, str):
        errors.append(f"{path}: 'name' must be a string")
    else:
        if not NAME_RE.match(name):
            errors.append(
                f"{path}: name '{name}' is not kebab-case "
                f"(1-64 chars, lowercase a-z 0-9, no leading/trailing/consecutive hyphens)"
            )
        if name != path.parent.name:
            errors.append(
                f"{path}: name '{name}' does not match parent directory '{path.parent.name}'"
            )

    if not description:
        errors.append(f"{path}: missing required key 'description'")
    elif not isinstance(description, str) or not description.strip():
        errors.append(f"{path}: 'description' must be a non-empty string")

    extra = set(fm) - ALLOWED_KEYS
    if extra:
        errors.append(f"{path}: disallowed frontmatter keys: {sorted(extra)}")

    return errors


def validate(path: Path) -> list[str]:
    shape_error = validate_path_shape(path)
    if shape_error:
        return [shape_error]
    return validate_frontmatter(path)


def main() -> int:
    if not Path("skills").is_dir():
        print("ERROR: skills/ directory not found", file=sys.stderr)
        return 1

    skill_files = sorted(
        p for p in Path(".").rglob("SKILL.md")
        if not any(part.startswith(".") for part in p.parts)
    )
    if not skill_files:
        print("ERROR: no SKILL.md files found under skills/", file=sys.stderr)
        return 1

    all_errors: list[str] = []
    for sf in skill_files:
        all_errors.extend(validate(sf))

    if all_errors:
        for e in all_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(
            f"\nFAIL: {len(all_errors)} error(s) across {len(skill_files)} SKILL.md file(s)",
            file=sys.stderr,
        )
        return 1

    print(f"OK: validated {len(skill_files)} SKILL.md file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
