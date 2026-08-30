"""Regression tests for removing the dead /cheese-factory pointer from skills/.

/cheese-factory does not exist as a dispatch target and never will; the PR
that would have shipped it was closed. These tests are the ratchet against
re-introducing the recommendation, plus content checks on the replacement
dispatch-count gate signal and the decomposer-producer / mold agent-resolution
fixes that shipped alongside it.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"

COOK_SKILL = SKILLS_DIR / "cook" / "SKILL.md"
ROUTING_POLICY = SKILLS_DIR / "cheese" / "references" / "routing-policy.md"
DECOMPOSER_DOC = SKILLS_DIR / "cheese" / "references" / "decomposer.md"
MOLD_SKILL = SKILLS_DIR / "mold" / "SKILL.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def test_cheese_factory_absent_from_all_skills() -> None:
    """Ratchet: /cheese-factory must never reappear anywhere under skills/."""
    offenders: list[str] = []
    for path in SKILLS_DIR.rglob("*"):
        if not path.is_file():
            continue
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if b"cheese-factory" in content:
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, f"/cheese-factory reintroduced under skills/: {offenders}"


def test_cook_gate_carries_dispatch_count_signal() -> None:
    """The cook-gate wave-plan phrasing must show a projected dispatch count."""
    body = _text(COOK_SKILL)
    match = re.search(r'"12 ACs -> 5 curds, 2 waves,[^"]*\bGo\?"', body)
    assert match, "cook gate phrasing missing a dispatch-count clause"
    assert re.search(r"up to \d+ agent dispatches", match.group(0)), (
        f"gate phrasing has no 'up to N agent dispatches' clause: {match.group(0)!r}"
    )


def test_routing_policy_cook_gate_matches_cook_skill_phrasing() -> None:
    """Drift guard: routing-policy's cook-gate row must carry the identical
    gate phrasing as skills/cook/SKILL.md, not a hand-copied variant."""
    cook_match = re.search(r'"12 ACs -> 5 curds, 2 waves,[^"]*\bGo\?"', _text(COOK_SKILL))
    policy_match = re.search(
        r'"12 ACs -> 5 curds, 2 waves,[^"]*\bGo\?"', _text(ROUTING_POLICY)
    )
    assert cook_match and policy_match, "gate phrasing missing from one of the two docs"
    assert cook_match.group(0) == policy_match.group(0), (
        "cook gate phrasing drifted between skills/cook/SKILL.md and "
        "skills/cheese/references/routing-policy.md"
    )


def test_routing_policy_cook_gate_row_drops_cheese_factory_recommendation() -> None:
    body = _text(ROUTING_POLICY)
    match = re.search(r"\| cook gate \|.*\|\n", body)
    assert match, "cook gate row not found in routing-policy.md"
    assert "cheese-factory" not in match.group(0)


def test_decomposer_producers_both_dispatch_fresh_context() -> None:
    """Both /mold and /cook producers must describe dispatching a fresh-context
    decomposer sub-agent -- 'inline' must no longer describe cook's producer."""
    body = _text(DECOMPOSER_DOC)
    start = body.index("## Producers")
    end = body.index("## Validator", start)
    section = body[start:end]

    assert "inline" not in section, (
        "decomposer.md still describes a producer as running the decomposer inline"
    )

    mold_bullet_start = section.index("`/mold`")
    cook_bullet_start = section.index("`/cook`")
    mold_bullet = section[mold_bullet_start:cook_bullet_start]
    cook_bullet = section[cook_bullet_start:]

    for bullet in (mold_bullet, cook_bullet):
        assert "dispatch" in bullet, f"producer bullet missing 'dispatch': {bullet!r}"
    assert "fresh-context" in cook_bullet, (
        f"cook's producer bullet missing 'fresh-context': {cook_bullet!r}"
    )


def _agent_resolution_row(body: str, work_label: str) -> str:
    match = re.search(rf"\| {re.escape(work_label)} \|.*\|", body)
    assert match, f"no agent-resolution row found for {work_label!r}"
    return match.group(0)


def test_mold_agent_resolution_table_has_decompose_row_matching_cook() -> None:
    """mold's Agent resolution table must carry a decompose row naming
    'planner', with role and fallback cells matching cook's corresponding row."""
    cook_row = _agent_resolution_row(_text(COOK_SKILL), "Decompose the spec")
    mold_body = _text(MOLD_SKILL)

    decompose_rows = [
        line
        for line in mold_body.splitlines()
        if line.startswith("|") and "planner" in line
    ]
    assert decompose_rows, "mold's Agent resolution table has no decompose/planner row"
    mold_row = decompose_rows[0]

    def _cells(row: str) -> list[str]:
        return [cell.strip() for cell in row.strip("|").split("|")]

    cook_cells = _cells(cook_row)
    mold_cells = _cells(mold_row)

    # Work | Preferred types | Permissions/isolation | Minimum power | Effort | Fallback
    assert cook_cells[1] == mold_cells[1], "preferred-types cell drifted"
    assert cook_cells[5] == mold_cells[5], "fallback cell drifted"
    assert "planner" in mold_cells[1]
