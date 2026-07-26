"""Baseline propagation stays explicit in phase contracts and consumer prose.

Contract-aware phases declare `payload.baseline` in their phase-owned YAML.
Consumers treat an inherited baseline as settled state: identical failures are
not re-flagged, re-halted, or re-asked about.
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


CONTRACT_CONSUMERS = {
    "skills/press/SKILL.md": "skills/press/references/handoff-contract.yaml",
    "skills/age/SKILL.md": "skills/age/references/handoff-contract.yaml",
    "skills/cure/SKILL.md": "skills/cure/references/handoff-contract.yaml",
}


@pytest.mark.parametrize(("rel_path", "contract_path"), CONTRACT_CONSUMERS.items())
def test_consumer_phase_contract_carries_baseline_field(
    rel_path: str, contract_path: str
) -> None:
    contract = read(contract_path)
    assert "payload:" in contract, rel_path
    assert "baseline:" in contract, rel_path


@pytest.mark.parametrize("rel_path", CONSUMERS)
def test_consumer_states_settled_state_rule(rel_path: str) -> None:
    body = read(rel_path)
    assert any(marker in body for marker in SETTLED_STATE_MARKERS), (
        f"{rel_path} must state the no-re-flag/no-re-halt settled-state rule"
    )
    assert "quality-gates.md" in body, (
        f"{rel_path} must link to the shared baseline policy doc"
    )
