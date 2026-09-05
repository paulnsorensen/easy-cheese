"""Guards for the dossier contract after the wheypoint-ergonomics spec.

The old `## Required body sections by state` table and its `## Document`
chapter were prose the runtime never enforced; the spec retired them (S7
notes body, dossier rule in the schema). What must survive in the docs is the
*semantic* contract: a gating entry needs a dossier fork, a fork carries four
elements, and a parked fork may exist without gating (ADR
wheypoint-ergonomics-001).
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


def test_a_gating_entry_requires_a_dossier_fork_and_the_runtime_enforces_it() -> None:
    body = _read(WHEYPOINT_SKILL)
    assert re.search(r"requires a dossier fork for each gating entry", body), (
        "SKILL.md must state that the runtime requires a dossier fork for each gating entry"
    )
    assert "The runtime refuses an intent instead of dropping data." in body


def test_a_parked_fork_may_exist_without_gating() -> None:
    body = _read(WHEYPOINT_SKILL) + _read(INTENT_CONTRACT)
    assert re.search(r"A fork may describe any active question", body), (
        "the docs must allow a dossier fork on a non-gating question (ADR wheypoint-ergonomics-001)"
    )
    assert "Record a parked fork in `decision_dossier`" in body


def test_the_dossier_contract_spells_out_all_four_elements() -> None:
    contract = _read(INTENT_CONTRACT)
    line = next(row for row in contract.splitlines() if "**`decision_dossier`**" in row)
    for element in ("fork", "option", "evidence", "breaks", "prior_leaning"):
        assert element in line, f"dossier contract line must name {element!r}: {line}"


def test_notes_replaced_the_document_chapter() -> None:
    body = _read(WHEYPOINT_SKILL)
    assert "## Document" not in body and "Required body sections by state" not in body
    assert "Put the report a cold reader needs in `notes`." in body
