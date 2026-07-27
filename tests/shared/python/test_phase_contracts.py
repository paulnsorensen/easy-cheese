"""The checked-in phase declarations compile as one registry, and each
phase's minimal envelope round-trips through validate_handoff cleanly."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import handoff  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = sorted(ROOT.glob("skills/*/references/handoff-contract.yaml"))

ALL_PHASES = {
    "affinage", "age", "briesearch", "cook", "culture", "cure",
    "mold", "pasteurize", "press", "ultracook", "wheypoint",
}

# One valid outgoing `next` per phase, taken from that phase's own contract.
# `culture` is excluded: it declares `next: []` by design (see the dedicated
# test below) and so has no valid outgoing transition to round-trip.
VALID_NEXT = {
    "affinage": "done",
    "age": "done",
    "briesearch": "hold",
    "cook": "done",
    "cure": "done",
    "mold": "hold",
    "pasteurize": "done",
    "press": "done",
    "ultracook": "done",
    "wheypoint": "done",
}


def _envelope(phase: str, next_value: str) -> handoff.HandoffEnvelope:
    return handoff.HandoffEnvelope.from_mapping({
        "contract_version": handoff.CONTRACT_VERSION,
        "work_id": "work", "attempt_id": "attempt", "operation_id": "op",
        "phase": phase, "status": "ok", "next": next_value,
        "artifact": "artifact.md", "payload": {}, "provenance": {},
    })


def test_phase_contracts_compile_to_typed_exact_phase_set() -> None:
    registry = handoff.assemble_transition_registry(CONTRACTS)
    assert isinstance(registry, handoff.TransitionRegistry)
    assert set(registry.phases) == ALL_PHASES
    assert not (handoff.RESERVED_NEXT & set(registry.phases))
    assert all(isinstance(contract, handoff.PhaseContract) for contract in registry.phases.values())
    tasks = registry.phases["wheypoint"].payload.fields["tasks"]
    assert isinstance(tasks.items, handoff.PayloadSchema)


@pytest.mark.parametrize("phase", sorted(VALID_NEXT))
def test_minimal_envelope_round_trips_per_phase(phase: str) -> None:
    registry = handoff.assemble_transition_registry(CONTRACTS)
    envelope = _envelope(phase, VALID_NEXT[phase])
    assert handoff.validate_handoff(envelope, registry) == []


def test_culture_is_destination_only_no_next_value_validates() -> None:
    """culture delegates its artifact to /wheypoint — it is destination-only
    and never emits an envelope of its own
    (.hallouminate/wiki/adr/culture-wheypoint-collaboration-001.md:15) — so
    its contract declares `next: []` by design. That must hold for every
    candidate `next`, including the reserved values: neither `done` nor
    `hold` is a legitimate exit for culture any more than an ordinary phase
    name is.
    """
    registry = handoff.assemble_transition_registry(CONTRACTS)
    for candidate in ("done", "hold", "cook"):
        envelope = _envelope("culture", candidate)
        assert handoff.validate_handoff(envelope, registry) == [
            f"disallowed transition: culture -> {candidate}"
        ]
