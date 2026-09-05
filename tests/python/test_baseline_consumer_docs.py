"""Curd 4 (baseline-quality-gate) hardened the five phase-consumer SKILL.md
files to honor an upstream `baseline:` handoff block as settled state: no
re-flagging and no re-halting on gate failures identical to the recorded
baseline. If a future edit strips the `baseline:` handoff-schema line or the
no-re-flag/no-re-halt prose (or its link to the shared policy doc), a slug
carrying a baseline block would again get re-asked about or re-halted on
already-recorded failures — exactly the regression this test exists to catch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
QUALITY_GATES_DOC = REPO_ROOT / "skills" / "cook" / "references" / "quality-gates.md"

CONSUMERS = (
    "skills/press/SKILL.md",
    "skills/age/SKILL.md",
    "skills/cure/SKILL.md",
    "skills/cheese/SKILL.md",
    "skills/wheypoint/SKILL.md",
)

SETTLED_STATE_MARKERS = ("re-flag", "re-halt", "re-ask", "raise a finding", "trigger a halt")


def read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text()


def _corpus(rel_path: str) -> str:
    """A skill's SKILL.md plus its references/*.md, concatenated.

    Prose that used to live in SKILL.md has been trimmed out into routed
    references/*.md files; consumer-doc checks must read the whole skill
    corpus, not just SKILL.md, or they false-negative on content that moved.
    """
    skill_path = REPO_ROOT / rel_path
    parts = [read(rel_path)]
    refs_dir = skill_path.parent / "references"
    if refs_dir.is_dir():
        parts += [p.read_text() for p in sorted(refs_dir.glob("*.md"))]
    return "\n".join(parts)


def test_quality_gates_policy_doc_exists() -> None:
    assert QUALITY_GATES_DOC.is_file()
    body = QUALITY_GATES_DOC.read_text()
    assert "no re-halt, no re-flag of identical entries" in body


# cheese/SKILL.md has no handoff-slug schema (router doc, prose-only baseline
# mention). wheypoint/SKILL.md documents the canonical projection, whose record
# carries no baseline field at all -- `checkpoint` refuses the key rather than
# drop it -- so it is covered by its own test below instead.
SCHEMA_CONSUMERS = tuple(
    c
    for c in CONSUMERS
    if c not in {"skills/cheese/SKILL.md", "skills/wheypoint/SKILL.md"}
)


def _handoff_schema_fence(rel_path: str) -> str:
    """Return the ```markdown fence carrying the handoff-slug schema.

    Searches the skill's whole corpus (SKILL.md + references/*.md) for the
    fence containing a `status:` line -- the schema itself, not just the first
    ```markdown fence in SKILL.md, which may be an unrelated worked example
    once the schema has been routed out to a references file.
    """
    skill_path = REPO_ROOT / rel_path
    candidates = [skill_path] + sorted((skill_path.parent / "references").glob("*.md"))
    marker = "```markdown"
    for path in candidates:
        if not path.is_file():
            continue
        body = path.read_text()
        pos = 0
        while True:
            idx = body.find(marker, pos)
            if idx == -1:
                break
            start = idx + len(marker)
            end = body.index("```", start)
            fence = body[start:end]
            if "status: " in fence:
                return fence
            pos = end + 3
    raise AssertionError(f"no ```markdown fence containing a 'status:' line found for {rel_path}")


@pytest.mark.parametrize("rel_path", SCHEMA_CONSUMERS)
def test_consumer_handoff_schema_carries_baseline_field(rel_path: str) -> None:
    schema_fence = _handoff_schema_fence(rel_path)
    assert any(
        line.strip().startswith("baseline: none |") for line in schema_fence.splitlines()
    ), f"{rel_path} handoff-slug schema fence must carry a `baseline: none |` sentinel line"


def test_wheypoint_refuses_a_baseline_key_rather_than_drop_it() -> None:
    """Wheypoint's canonical record has no baseline field.

    Silently dropping the key would lose settled state, so the checkpoint
    command must refuse it. The handwritten legacy note still carries a
    `baseline:` line, and the doc must say both things.
    """
    from easy_cheese.skills.wheypoint import legacy

    assert "baseline" in legacy._ALLOWED_HEADER_KEYS  # pyright: ignore[reportPrivateUsage]

    body = read("skills/wheypoint/SKILL.md")
    schema_fence = _handoff_schema_fence("skills/wheypoint/SKILL.md")
    assert not any(
        line.strip().startswith("baseline:") for line in schema_fence.splitlines()
    ), "the canonical schema must not document a baseline field"
    assert "refuses a `baseline` key rather than drop it" in body, (
        "wheypoint must state that checkpoint refuses the key, not drops it"
    )


@pytest.mark.parametrize("rel_path", CONSUMERS)
def test_consumer_states_settled_state_rule(rel_path: str) -> None:
    body = _corpus(rel_path)
    assert any(marker in body for marker in SETTLED_STATE_MARKERS), (
        f"{rel_path} must state the no-re-flag/no-re-halt settled-state rule"
    )
    assert "quality-gates.md" in body, (
        f"{rel_path} must link to the shared baseline policy doc"
    )
