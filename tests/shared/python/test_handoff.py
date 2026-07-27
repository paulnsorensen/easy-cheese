"""Versioned handoff envelope tests."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "shared" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import handoff  # noqa: E402


def _envelope(**changes):
    value = {
        "contract_version": handoff.CONTRACT_VERSION,
        "work_id": "work", "attempt_id": "attempt", "operation_id": "op",
        "phase": "age", "status": "ok", "next": "done", "artifact": "artifact.md",
        "payload": {}, "provenance": {},
    }
    value.update(changes)
    return handoff.HandoffEnvelope.from_mapping(value)


def test_parse_requires_declared_artifact_to_match_loaded_path(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.md"
    envelope = _envelope(artifact=str(artifact))
    contract = tmp_path / "age.yaml"
    contract.write_text("phase: age\nnext: [done]\npayload: {}\n")
    registry = handoff.assemble_transition_registry([contract])
    text = handoff.render_handoff(envelope, "# report", contracts=registry)
    assert handoff.parse_handoff(text, artifact) == envelope
    with pytest.raises(handoff.HandoffParseError, match="artifact path mismatch"):
        handoff.parse_handoff(text, tmp_path / "other.md")


def test_parse_rejects_invalid_yaml(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.md"
    text = "---\n[unterminated\n---\n"
    with pytest.raises(handoff.HandoffParseError, match="invalid handoff YAML"):
        handoff.parse_handoff(text, artifact)


@pytest.mark.parametrize(
    ("field", "value"),
    [("phase", 1), ("halt_reason", 1), ("payload", [])],
)
def test_envelope_boundary_rejects_coercible_values(field: str, value: object) -> None:
    with pytest.raises(
        handoff.HandoffParseError,
        match=rf"invalid value.*@ \$.{field}",
    ):
        _envelope(**{field: value})


def test_envelope_boundary_rejects_unknown_fields() -> None:
    with pytest.raises(
        handoff.HandoffParseError,
        match=r"extra fields found \(extra\) @ \$",
    ):
        _envelope(extra=True)


def test_status_rules_are_mutually_exclusive() -> None:
    assert "halt requires a non-empty halt_reason" in handoff.validate_handoff(_envelope(status="halt"))
    assert "ok forbids halt_reason" in handoff.validate_handoff(_envelope(halt_reason="no"))


def test_registry_enforces_source_transition_and_schema(tmp_path: Path) -> None:
    contract = tmp_path / "age.yaml"
    contract.write_text("phase: age\nnext: [done]\npayload:\n  title:\n    type: string\n    required: true\n")
    registry = handoff.assemble_transition_registry([contract])
    assert handoff.validate_handoff(_envelope(payload={"title": "review"}), registry) == []
    assert handoff.validate_handoff(_envelope(payload={}), registry) == ["payload.title is required"]
    assert handoff.validate_handoff(
        _envelope(next="hold", payload={"title": "review"}), registry
    ) == ["disallowed transition: age -> hold"]


def test_resolve_next_reports_unavailable_without_rewriting_destination(tmp_path: Path) -> None:
    contract = tmp_path / "cook.yaml"
    destination = tmp_path / "press.yaml"
    contract.write_text("phase: cook\nnext: [press, done, hold]\npayload: {}\n")
    destination.write_text("phase: press\nnext: []\npayload: {}\n")
    registry = handoff.assemble_transition_registry([contract, destination])
    envelope = _envelope(phase="cook", next="press")

    assert handoff.resolve_next(envelope, [], registry) == {
        "action": "unavailable",
        "phase": "press",
    }
    assert envelope.next == "press"
    assert handoff.resolve_next(envelope, ["press"], registry) == {
        "action": "dispatch",
        "phase": "press",
    }
    assert handoff.resolve_next(_envelope(phase="cook", next="done"), [], registry) == {
        "action": "done"
    }


def test_resolve_next_never_dispatches_a_halt(tmp_path: Path) -> None:
    contract = tmp_path / "cook.yaml"
    destination = tmp_path / "press.yaml"
    contract.write_text("phase: cook\nnext: [press]\npayload: {}\n")
    destination.write_text("phase: press\nnext: []\npayload: {}\n")
    registry = handoff.assemble_transition_registry([contract, destination])

    assert handoff.resolve_next(
        _envelope(phase="cook", status="halt", halt_reason="tests failed", next="press"),
        ["press"],
        registry,
    ) == {"action": "halt", "reason": "tests failed", "next": "press"}


def test_resolve_next_holds(tmp_path: Path) -> None:
    contract = tmp_path / "cook.yaml"
    contract.write_text("phase: cook\nnext: [hold]\npayload: {}\n")
    registry = handoff.assemble_transition_registry([contract])

    assert handoff.resolve_next(_envelope(phase="cook", next="hold"), [], registry) == {
        "action": "hold"
    }


def test_resolve_next_returns_tasks_payload(tmp_path: Path) -> None:
    contract = tmp_path / "wheypoint.yaml"
    contract.write_text(
        "phase: wheypoint\n"
        "next: [tasks]\n"
        "payload:\n"
        "  tasks:\n"
        "    type: list\n"
        "    required: false\n"
        "    items:\n"
        "      type: mapping\n"
        "      fields:\n"
        "        phase:\n"
        "          type: string\n"
        "          required: true\n"
        "        subject:\n"
        "          type: string\n"
        "          required: true\n"
    )
    destination = tmp_path / "cook.yaml"
    destination.write_text("phase: cook\nnext: []\npayload: {}\n")
    registry = handoff.assemble_transition_registry([contract, destination])
    tasks = [{"phase": "cook", "subject": "do work"}]
    envelope = _envelope(phase="wheypoint", next="tasks", payload={"tasks": tasks})

    assert handoff.resolve_next(envelope, [], registry) == {"action": "tasks", "tasks": tasks}


_MALFORMED_CONTRACT_CASES = [
    pytest.param("missing.yaml", None, "phase contract not found", id="missing-file"),
    pytest.param("a.yaml", "phase: cook-\nnext: [done]\npayload: {}\n", "malformed phase declaration", id="bad-phase-trailing-hyphen"),
    pytest.param("a.yaml", "phase: phases\nnext: [done]\npayload: {}\n", "duplicate or reserved phase declaration: phases", id="bad-phase-reserved-collision"),
    pytest.param("a.yaml", "phase: done\nnext: [hold]\npayload: {}\n", "duplicate or reserved phase declaration: done", id="reserved-name-as-phase"),
    pytest.param("a.yaml", "phase: cook\nnext:\n  - [x]\npayload: {}\n", "malformed outgoing transitions", id="malformed-outgoing-unhashable-item"),
    pytest.param("a.yaml", "phase: cook\nnext: [nowhere]\npayload: {}\n", "cook names unknown destinations: nowhere", id="unknown-destination"),
    pytest.param("a.yaml", "phase: cook\nnext: [done]\npayload:\n  type: bogus\n", "malformed payload schema", id="malformed-payload-schema"),
    pytest.param("a.yaml", "phase: cook\nnext: [done]\npayload:\n  type:\n    type: string\n", "malformed payload schema", id="malformed-payload-schema-unhashable-type"),
]


@pytest.mark.parametrize("filename, content, expected_message", _MALFORMED_CONTRACT_CASES)
def test_assemble_transition_registry_rejects_malformed_contracts(
    tmp_path: Path, filename: str, content: str | None, expected_message: str
) -> None:
    path = tmp_path / filename
    if content is not None:
        path.write_text(content)
    with pytest.raises(ValueError, match=re.escape(expected_message)):
        handoff.assemble_transition_registry([path])


def test_assemble_transition_registry_rejects_duplicate_phase_across_files(tmp_path: Path) -> None:
    first = tmp_path / "a.yaml"
    second = tmp_path / "b.yaml"
    first.write_text("phase: cook\nnext: [done]\npayload: {}\n")
    second.write_text("phase: cook\nnext: [done]\npayload: {}\n")
    with pytest.raises(ValueError, match="duplicate or reserved phase declaration: cook"):
        handoff.assemble_transition_registry([first, second])


def test_propagate_flags_pins_always_vs_chain_only_precedence() -> None:
    """--hard always propagates; --auto propagates only inside an auto chain."""
    assert handoff.propagate_flags(["--hard"], in_auto_chain=False) == ["--hard"]
    assert handoff.propagate_flags(["--auto"], in_auto_chain=False) == []
    assert handoff.propagate_flags(["--auto"], in_auto_chain=True) == ["--auto"]
    assert handoff.propagate_flags(["--hard", "--auto"], in_auto_chain=False) == ["--hard"]
    assert handoff.propagate_flags(["--unknown"], in_auto_chain=True) == []