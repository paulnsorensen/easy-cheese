"""The checked-in phase declarations compile as one registry."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[3] / "shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import handoff  # noqa: E402


def test_phase_contracts_compile() -> None:
    root = Path(__file__).resolve().parents[3]
    contracts = sorted(root.glob("skills/*/references/handoff-contract.yaml"))
    registry = handoff.assemble_transition_registry(contracts)
    assert set(registry["phases"]) >= {"age", "cook", "cure", "mold", "wheypoint"}
    assert not (handoff.RESERVED_NEXT & set(registry["phases"]))
