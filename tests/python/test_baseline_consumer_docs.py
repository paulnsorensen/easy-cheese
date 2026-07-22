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

SETTLED_STATE_MARKERS = ("re-flag", "re-halt", "re-ask", "raise a finding")


def read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text()


def test_quality_gates_policy_doc_exists() -> None:
    assert QUALITY_GATES_DOC.is_file()
    body = QUALITY_GATES_DOC.read_text()
    assert "no re-halt, no re-flag of identical entries" in body


SCHEMA_CONSUMERS = tuple(c for c in CONSUMERS if c != "skills/cheese/SKILL.md")


def _handoff_schema_fence(body: str) -> str:
    """Return the first ```markdown fenced block (the handoff-slug schema)."""
    marker = "```markdown"
    start = body.index(marker) + len(marker)
    end = body.index("```", start)
    return body[start:end]


@pytest.mark.parametrize("rel_path", SCHEMA_CONSUMERS)
def test_consumer_handoff_schema_carries_baseline_field(rel_path: str) -> None:
    # cheese/SKILL.md has no handoff-slug schema (router doc, prose-only
    # baseline mention) so it is excluded from SCHEMA_CONSUMERS above.
    body = read(rel_path)
    schema_fence = _handoff_schema_fence(body)
    assert any(
        line.strip().startswith("baseline:") for line in schema_fence.splitlines()
    ), f"{rel_path} handoff-slug schema fence must carry a `baseline:` line"


@pytest.mark.parametrize("rel_path", CONSUMERS)
def test_consumer_states_settled_state_rule(rel_path: str) -> None:
    body = read(rel_path)
    assert any(marker in body for marker in SETTLED_STATE_MARKERS), (
        f"{rel_path} must state the no-re-flag/no-re-halt settled-state rule"
    )
    assert "quality-gates.md" in body, (
        f"{rel_path} must link to the shared baseline policy doc"
    )
