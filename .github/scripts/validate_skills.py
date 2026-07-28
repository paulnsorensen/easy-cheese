#!/usr/bin/env python3
"""Validate every SKILL.md in the repository. Exit 0 on success, 1 on any failure."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
SHARED_SCRIPTS = SCRIPT_DIR.parents[1] / "shared" / "scripts"
if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))

from paths import KEBAB_SLUG  # noqa: E402

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

FRONTMATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\s*(\r?\n|\Z)", re.DOTALL)

# Codex rejects skills whose description exceeds 1024 characters.
DESCRIPTION_MAX_LEN = 1024

# This repo's own SKILL.md body budget: tighter than Anthropic's published
# Level-2 ceiling (500 lines / under 5k tokens). 150 lines at this repo's
# measured ~95 bytes/line median density is ~3,560 tokens; 3600 rounds that.
# bytes // 4 is deliberate, not lazy: Claude's tokenizer isn't public and
# tiktoken is OpenAI's BPE.
TARGET_TOKENS = 3600
BUDGET_FILE = Path(".github/skill-budgets.json")

# Reporting-only aspirational body-size goal (main()'s Body-size goal block
# below) -- never gates, never affects exit code. 1800 approximates the
# measured median body size of the skills Anthropic ships (1,888 tokens) --
# an observed fact about their shipped skills, NOT a published Anthropic
# recommendation.
GOAL_TOKENS = 1800

# Gated cap on everything in frontmatter that is NOT `description` --
# description is separately bounded by DESCRIPTION_MAX_LEN (1024 chars =~
# 256 tokens), so capping the remainder at 96 provably bounds total
# frontmatter at ~320 tokens/skill from one constant, without a long
# description competing with metadata/hooks for budget. Flat cap, not a
# ratchet: no grandfathering, no allowlist.
FRONTMATTER_EXTRA_MAX = 96

# A reference file must not markdown-link to another path containing
# "references/" — Anthropic's one-level-deep rule; a partial `head -100` read
# silently misses the tail of a nested reference.
NESTED_LINK_RE = re.compile(r"\]\(([^)]+)\)")

# A path mention of the form "references/<basename>", markdown link or plain
# backtick-quoted path, counts as "linked" for the orphan check.
REFERENCE_MENTION_RE = re.compile(r"references/([A-Za-z0-9_.\-]+)")


def _under_agents_skills(path: Path) -> bool:
    """True for any path rooted at .agents/skills/ (any depth) — the narrow
    allowance that lets repo-local skills opt into discovery despite the
    dot-prefix skip below; validate_path_shape still rejects the wrong depth.
    """
    parts = path.parts
    return len(parts) >= 2 and parts[0] == ".agents" and parts[1] == "skills"


def validate_path_shape(path: Path) -> str | None:
    parts = path.parts
    if len(parts) == 3 and parts[0] == "skills" and parts[2] == "SKILL.md":
        return None
    if (
        len(parts) == 4
        and parts[0] == ".agents"
        and parts[1] == "skills"
        and parts[3] == "SKILL.md"
    ):
        return None
    return (
        f"{path}: file is not at the documented path skills/<name>/SKILL.md "
        f"(nested sub-skills are not supported)"
    )


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
        if not KEBAB_SLUG.match(name):
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
    elif len(description) > DESCRIPTION_MAX_LEN:
        errors.append(
            f"{path}: 'description' is {len(description)} chars, exceeds "
            f"{DESCRIPTION_MAX_LEN}-char limit (codex rejects longer descriptions)"
        )

    extra = set(fm) - ALLOWED_KEYS
    if extra:
        errors.append(f"{path}: disallowed frontmatter keys: {sorted(extra)}")

    description_tokens = estimate_tokens(description) if isinstance(description, str) else 0
    frontmatter_tokens = estimate_tokens(match.group(0))
    extra_tokens = frontmatter_tokens - description_tokens
    if extra_tokens > FRONTMATTER_EXTRA_MAX:
        offending = sorted(k for k in fm if k != "description")
        errors.append(
            f"{path}: non-description frontmatter (keys: {offending}) is ~{extra_tokens} "
            f"estimated tokens, exceeds the {FRONTMATTER_EXTRA_MAX}-token cap on frontmatter "
            f"outside 'description'; trim these keys"
        )

    return errors


def estimate_tokens(body: str) -> int:
    """len(body_bytes) // 4 — no tokenizer dependency, deliberately coarse."""
    return len(body.encode("utf-8")) // 4


def skill_body(text: str) -> str:
    """Everything after the closing frontmatter '---'. Only description length
    (DESCRIPTION_MAX_LEN) is capped separately; the rest of the frontmatter is not.
    """
    match = FRONTMATTER_RE.match(text)
    return text[match.end():] if match else text


def frontmatter_text(text: str) -> str:
    r"""The raw '---\n...\n---' frontmatter block, reporting-only surface for
    whole-frontmatter token estimates (never gated — frontmatter is excluded
    from the size budget; this is a context-cost report only).
    """
    match = FRONTMATTER_RE.match(text)
    return match.group(0) if match else ""


def load_budgets() -> dict:
    if not BUDGET_FILE.exists():
        return {
            "target": TARGET_TOKENS,
            "skills": {},
            "nested_references_allowlist": [],
            "orphaned_references_allowlist": [],
        }
    return json.loads(BUDGET_FILE.read_text(encoding="utf-8"))


def validate_size(path: Path, budgets: dict) -> list[str]:
    tokens = estimate_tokens(skill_body(path.read_text(encoding="utf-8")))
    recorded = budgets.get("skills", {}).get(path.parent.name)
    grandfathered = recorded is not None and recorded > TARGET_TOKENS
    cap = recorded if grandfathered else TARGET_TOKENS

    if tokens <= cap:
        return []

    fix = (
        f"grandfathered at {cap} tokens and may only shrink"
        if grandfathered
        else (
            f"this repo's own policy ceiling of {TARGET_TOKENS} tokens, tighter than "
            f"Anthropic's published 'under 5k tokens' guidance"
        )
    )
    return [
        f"{path}: SKILL.md body is ~{tokens} estimated tokens, exceeds budget of {cap} "
        f"({fix}); trim the body or move content to references/, then run "
        f"`just update-skill-budgets` after shrinking"
    ]


def validate(path: Path, budgets: dict) -> list[str]:
    shape_error = validate_path_shape(path)
    if shape_error:
        return [shape_error]
    errors = validate_frontmatter(path)
    errors.extend(validate_size(path, budgets))
    return errors


def reference_files() -> list[Path]:
    return sorted(p for p in Path("skills").glob("*/references/**/*") if p.is_file())


def has_nested_reference_link(path: Path, linked: set[str]) -> bool:
    """True when this reference file links a references/ target whose basename
    is NOT itself reachable (linked by basename) from any skills/*/SKILL.md.
    A lateral link to a target that IS reachable is not a hidden second hop —
    `linked` is the same reachability set the orphan check below uses, so both
    structure checks share one definition of "reachable".
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    for link in NESTED_LINK_RE.findall(text):
        target = link.split("#", 1)[0].split(" ", 1)[0].strip()
        if target.startswith("http"):
            continue
        if "references/" in target:
            basename = target.rsplit("/", 1)[-1]
            if basename not in linked:
                return True
    return False


def linked_reference_basenames() -> set[str]:
    basenames: set[str] = set()
    for sf in sorted(Path("skills").glob("*/SKILL.md")):
        text = sf.read_text(encoding="utf-8", errors="ignore")
        basenames.update(REFERENCE_MENTION_RE.findall(text))
    return basenames


def validate_structure(budgets: dict) -> list[str]:
    errors: list[str] = []
    nested_allow = set(budgets.get("nested_references_allowlist", []))
    orphan_allow = set(budgets.get("orphaned_references_allowlist", []))
    ref_files = reference_files()
    linked = linked_reference_basenames()

    for rf in ref_files:
        rel = rf.as_posix()
        if has_nested_reference_link(rf, linked) and rel not in nested_allow:
            errors.append(
                f"{rel}: markdown-links to a path containing 'references/' — keep references "
                f"one level deep from SKILL.md (a partial head -100 read silently misses the "
                f"tail); move or inline the target, or add this path to "
                f"nested_references_allowlist in {BUDGET_FILE} if pre-existing"
            )

    for rf in ref_files:
        rel = rf.as_posix()
        if rf.name not in linked and rel not in orphan_allow:
            errors.append(
                f"{rel}: not linked (by basename) from any SKILL.md in skills/ — orphaned "
                f"reference file; link it from the owning or a consuming SKILL.md, delete it "
                f"if unused, or add it to orphaned_references_allowlist in {BUDGET_FILE} if "
                f"pre-existing"
            )

    return errors


def compute_budgets() -> dict:
    prior = load_budgets().get("skills", {})
    skills = {}
    sources = sorted(Path("skills").glob("*/SKILL.md")) + sorted(
        Path(".agents/skills").glob("*/SKILL.md")
    )
    for sf in sources:
        name = sf.parent.name
        measured = estimate_tokens(skill_body(sf.read_text(encoding="utf-8")))
        prior_recorded = prior.get(name)
        skills[name] = min(measured, prior_recorded) if prior_recorded is not None else measured
    ref_files = reference_files()
    linked = linked_reference_basenames()
    nested = sorted(rf.as_posix() for rf in ref_files if has_nested_reference_link(rf, linked))
    orphaned = sorted(rf.as_posix() for rf in ref_files if rf.name not in linked)
    return {
        "target": TARGET_TOKENS,
        "skills": skills,
        "nested_references_allowlist": nested,
        "orphaned_references_allowlist": orphaned,
    }


def write_budgets() -> None:
    budgets = compute_budgets()
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(budgets, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    if not Path("skills").is_dir():
        print("ERROR: skills/ directory not found", file=sys.stderr)
        return 1

    if len(sys.argv) > 1 and sys.argv[1] == "--write-budgets":
        write_budgets()
        print(f"OK: wrote {BUDGET_FILE}")
        return 0

    skill_files = sorted(
        p for p in Path().rglob("SKILL.md")
        if not any(part.startswith(".") for part in p.parts) or _under_agents_skills(p)
    )
    if not skill_files:
        print("ERROR: no SKILL.md files found in repository", file=sys.stderr)
        return 1

    budgets = load_budgets()
    all_errors: list[str] = []
    for sf in skill_files:
        all_errors.extend(validate(sf, budgets))
    all_errors.extend(validate_structure(budgets))

    if all_errors:
        for e in all_errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print(
            f"\nFAIL: {len(all_errors)} error(s) across {len(skill_files)} SKILL.md file(s)",
            file=sys.stderr,
        )
        return 1

    frontmatter_rows = sorted(
        (sf.as_posix(), estimate_tokens(frontmatter_text(sf.read_text(encoding="utf-8"))))
        for sf in skill_files
    )
    aggregate = sum(tokens for _, tokens in frontmatter_rows)
    shipped_count = sum(1 for sf in skill_files if sf.parts[0] == "skills")
    local_count = len(skill_files) - shipped_count

    print(f"OK: validated {len(skill_files)} SKILL.md file(s)")
    print(
        f"Frontmatter tokens (reporting only, not gated): aggregate {aggregate} "
        f"across {len(skill_files)} skill(s) ({shipped_count} shipped + {local_count} "
        f"repo-local under .agents/skills/)"
    )
    for rel, tokens in frontmatter_rows:
        print(f"  {rel}: {tokens}")

    goal_rows = sorted(
        (
            sf.as_posix(),
            estimate_tokens(skill_body(sf.read_text(encoding="utf-8"))) - GOAL_TOKENS,
        )
        for sf in skill_files
    )
    meeting_goal = sum(1 for _, excess in goal_rows if excess <= 0)
    goal_excess_total = sum(excess for _, excess in goal_rows if excess > 0)
    print(
        f"\nBody-size goal (reporting only, not gated; {GOAL_TOKENS} tokens approximates the "
        f"measured median body size of Anthropic's own shipped skills, not a published "
        f"Anthropic recommendation): {meeting_goal}/{len(skill_files)} skill(s) at or under "
        f"goal today; aggregate excess {goal_excess_total} tokens — a direction-of-travel "
        f"number expected to shrink over time, not a failure count"
    )
    for rel, excess in goal_rows:
        if excess > 0:
            print(f"  {rel}: +{excess} over goal")
    return 0


if __name__ == "__main__":
    sys.exit(main())