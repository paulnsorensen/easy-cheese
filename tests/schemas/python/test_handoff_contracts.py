from __future__ import annotations

import hashlib
import json
import pytest
from attrs import evolve

from easy_cheese_schemas.contracts import (
    AgentWriterView,
    ArtifactRef,
    BoundedScope,
    ContractVersion,
    CriterionWriterView,
    CurdPlanWriterView,
    SemanticCurdWriterView,
    WriterViewKind,
)
from easy_cheese.shared.handoffs import (
    CURD_PLAN_SCHEMA_URI,
    HandoffError,
    InvocationContext,
    accept,
    canonical_bytes,
    pointer_from_mapping,
    publish,
    publish_writer_text,
)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def writer_and_invocation(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    artifact = ArtifactRef(
        artifact_id="source",
        role="source",
        uri="repo://source.txt",
        digest=_digest(source.read_bytes()),
        size_bytes=source.stat().st_size,
        media_type="text/plain",
    )
    curd = SemanticCurdWriterView(
        key="core",
        outcome="Ship the behavior",
        scope=BoundedScope(paths=["src/core.py"]),
        outputs=["Behavior is shipped"],
        criteria=[CriterionWriterView("observable", "The behavior is observable")],
        input_keys=["source"],
    )
    writer = AgentWriterView(
        WriterViewKind.CURD_PLAN,
        CurdPlanWriterView(objective="Ship the behavior", curds=[curd]),
    )
    invocation = InvocationContext(
        root=tmp_path,
        contract_version=ContractVersion(CURD_PLAN_SCHEMA_URI, "1", "0"),
        plan_id="plan-1",
        revision=1,
        request_digest=_digest(b"request"),
        artifacts={"source": artifact},
    )
    return writer, invocation


def repaired_writer_text(writer: AgentWriterView) -> str:
    raw = canonical_bytes(writer).decode().strip()
    return "// planner output\n" + raw.replace('"kind":', "kind:", 1)[:-1] + ",}"


def test_schema_or_route_mismatch_rejected(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    with pytest.raises(HandoffError, match="route"):
        publish(writer, invocation, "press", "op")

    published = publish(writer, invocation, "cook", "op")
    with pytest.raises(ValueError):
        evolve(published.pointer, destination_phase="press")
    with pytest.raises(HandoffError, match="version"):
        accept(
            evolve(
                published.pointer,
                contract_version=ContractVersion(
                    "https://schemas.easy-cheese.dev/handoff", "2", "0"
                ),
            )
        )


def test_strict_writer_path_has_no_receipt(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish(writer, invocation, "cook", "op")
    assert published.normalization_receipt is None
    assert published.pointer.normalization_receipt is None
    assert not (tmp_path / "receipts" / "op.json").exists()


def test_receipt_binding_for_non_strict_writer_repair_and_digests(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish_writer_text(
        repaired_writer_text(writer), invocation, "cook", "op"
    )
    receipt = published.normalization_receipt
    assert receipt is not None
    assert {action.kind for action in receipt.actions} == {
        "comment",
        "trailing_comma",
        "unquoted_key",
    }
    assert receipt.source_digest == _digest(repaired_writer_text(writer).encode())
    assert receipt.canonical_digest == published.pointer.payload.digest

    receipt_path = tmp_path / "receipts" / "op.json"
    tampered = evolve(receipt, canonical_digest=_digest(b"other"))
    tampered_bytes = canonical_bytes(tampered)
    receipt_path.write_bytes(tampered_bytes)
    receipt_ref = evolve(
        published.pointer.normalization_receipt,
        digest=_digest(tampered_bytes),
        size_bytes=len(tampered_bytes),
    )
    with pytest.raises(HandoffError, match="receipt digest"):
        accept(evolve(published.pointer, normalization_receipt=receipt_ref))


def test_writer_recovery_rejects_ambiguous_candidates(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    raw = canonical_bytes(writer).decode()
    text = f"first\n```json\n{raw}\n```\nsecond\n```json\n{raw}\n```"
    with pytest.raises(HandoffError, match="exactly one"):
        publish_writer_text(text, invocation, "cook", "op")


def test_pointer_last_atomic(tmp_path, monkeypatch):
    writer, invocation = writer_and_invocation(tmp_path)
    import easy_cheese.shared.handoffs as module

    original = module._write_atomic

    def fail_pointer(path, data):
        if path.parent.name == "pointers":
            raise OSError("interrupted")
        original(path, data)

    monkeypatch.setattr(module, "_write_atomic", fail_pointer)
    with pytest.raises(OSError):
        publish_writer_text(repaired_writer_text(writer), invocation, "cook", "op")
    assert not (tmp_path / "pointers" / "op.json").exists()
    assert (tmp_path / "payloads" / "op.json").exists()
    assert (tmp_path / "receipts" / "op.json").exists()


def test_idempotency_or_corruption_revalidates_every_published_artifact(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish(writer, invocation, "cook", "op")
    assert publish(writer, invocation, "cook", "op").pointer == published.pointer

    payload = tmp_path / "payloads" / "op.json"
    payload.write_text("{}", encoding="utf-8")
    with pytest.raises(HandoffError, match="corrupt"):
        publish(writer, invocation, "cook", "op")


def test_idempotency_rejects_conflicting_receipt_provenance(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    publish_writer_text(repaired_writer_text(writer), invocation, "cook", "op")
    with pytest.raises(HandoffError, match="normalization receipt"):
        publish(writer, invocation, "cook", "op")


def test_accept_rejects_reference_outside_operation_root(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish(writer, invocation, "cook", "op")
    outside = tmp_path.parent / "outside.json"
    outside.write_bytes((tmp_path / "payloads" / "op.json").read_bytes())
    external_ref = evolve(published.pointer.payload, uri=outside.resolve().as_uri())
    with pytest.raises(HandoffError, match="operation root"):
        accept(evolve(published.pointer, payload=external_ref))


def test_plan_artifacts_must_resolve_at_publish_and_accept(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    (tmp_path / "source.txt").unlink()
    with pytest.raises(HandoffError, match="unresolved plan artifact"):
        publish(writer, invocation, "cook", "op")

    (tmp_path / "source.txt").write_text("source", encoding="utf-8")
    published = publish(writer, invocation, "cook", "op")
    (tmp_path / "source.txt").unlink()
    with pytest.raises(HandoffError, match="unresolved plan artifact"):
        accept(published.pointer)


def test_pointer_mapping_accepts_optional_receipt(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish(writer, invocation, "cook", "op")
    mapping = json.loads(canonical_bytes(published.pointer))
    assert pointer_from_mapping(mapping) == published.pointer
