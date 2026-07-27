"""Versioned handoff envelope tests."""
from __future__ import annotations

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
    text = handoff.render_handoff(envelope, "# report")
    assert handoff.parse_handoff(text, artifact) == envelope
    with pytest.raises(handoff.HandoffParseError, match="artifact path mismatch"):
        handoff.parse_handoff(text, tmp_path / "other.md")


def test_parse_rejects_yaml_frontmatter(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.md"
    text = f"""---
contract_version: {handoff.CONTRACT_VERSION}
work_id: work
attempt_id: attempt
operation_id: op
phase: age
status: ok
halt_reason: null
next: done
artifact: {artifact}
payload: {{}}
provenance: {{}}
---
"""
    with pytest.raises(handoff.HandoffParseError, match="invalid handoff JSON"):
        handoff.parse_handoff(text, artifact)


def test_status_rules_are_mutually_exclusive() -> None:
    assert "halt requires a non-empty halt_reason" in handoff.validate_handoff(_envelope(status="halt"))
    assert "ok forbids halt_reason" in handoff.validate_handoff(_envelope(halt_reason="no"))


def test_registry_enforces_source_transition_and_schema(tmp_path: Path) -> None:
    contract = tmp_path / "age.yaml"
    contract.write_text("phase: age\nnext: [done]\npayload:\n  title:\n    type: string\n    required: true\n")
    registry = handoff.assemble_transition_registry([contract])
    assert handoff.validate_handoff(_envelope(payload={"title": "review"}), registry) == []
    assert any("required" in error for error in handoff.validate_handoff(_envelope(payload={}), registry))
    assert any("disallowed transition" in error for error in handoff.validate_handoff(_envelope(next="hold", payload={"title": "review"}), registry))


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
