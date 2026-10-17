"""Guards for the blocking-question rationale contract.

The old `## Required body sections by state` table and its `## Document`
chapter were prose the runtime never enforced; the spec retired them. The
wheypoint-contract-simplify spec retired the decision dossier too. What must
survive in the docs is the *semantic* contract: a blocking question needs a
rationale, and a parked fork is a question.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WHEYPOINT_SKILL = REPO_ROOT / "skills" / "wheypoint" / "SKILL.md"
INTENT_CONTRACT = REPO_ROOT / "skills" / "wheypoint" / "references" / "intent-contract.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_wheypoint_skill_exists() -> None:
    assert WHEYPOINT_SKILL.exists(), f"wheypoint SKILL.md moved or renamed: {WHEYPOINT_SKILL}"
    assert INTENT_CONTRACT.exists(), f"intent contract moved or renamed: {INTENT_CONTRACT}"


def test_a_blocking_question_requires_a_rationale_and_the_runtime_enforces_it() -> None:
    body = _read(WHEYPOINT_SKILL)
    assert re.search(r"requires a rationale for each blocking question", body), (
        "SKILL.md must state that the runtime requires a rationale for each blocking question"
    )
    assert "The runtime refuses an intent instead of dropping data." in body


def test_a_parked_fork_is_a_question_and_no_dossier_remains() -> None:
    body = _read(WHEYPOINT_SKILL) + _read(INTENT_CONTRACT)
    assert "Record a parked fork as a `question`" in body
    assert "dossier" not in body.lower().replace("no dossier", "")
    assert "decision_dossier" not in body


def test_the_blocking_question_contract_spells_out_the_rationale() -> None:
    contract = _read(INTENT_CONTRACT)
    line = next(
        row for row in contract.splitlines() if "A `question` with `blocks_continuation: true`" in row
    )
    for element in ("rationale", "options", "evidence", "prior leaning"):
        assert element in line, f"blocking-question line must name {element!r}: {line}"


def test_notes_replaced_the_document_chapter() -> None:
    body = _read(WHEYPOINT_SKILL)
    assert "## Document" not in body and "Required body sections by state" not in body
    assert "Put the report a cold reader needs in `notes`." in body


def test_skill_md_points_at_the_work_graph_reference() -> None:
    body = _read(WHEYPOINT_SKILL)
    assert "(references/work-graph.md)" in body
    assert (WHEYPOINT_SKILL.parent / "references" / "work-graph.md").is_file()
