from __future__ import annotations

import hashlib
import json
import pytest
from attrs import evolve

from easy_cheese_schemas.contracts import MAX_CONTRACT_BYTES

import easy_cheese.shared.handoffs as handoffs

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
    invocation = handoffs.InvocationContext(
        root=tmp_path,
        contract_version=ContractVersion(handoffs.CURD_PLAN_SCHEMA_URI, "1", "0"),
        plan_id="plan-1",
        revision=1,
        request_digest=_digest(b"request"),
        artifacts={"source": artifact},
    )
    return writer, invocation


def repaired_writer_text(writer: AgentWriterView) -> str:
    raw = handoffs.canonical_bytes(writer).decode().strip()
    return "// planner output\n" + raw.replace('"kind":', "kind:", 1)[:-1] + ",}"


def test_schema_or_route_mismatch_rejected(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    with pytest.raises(handoffs.HandoffError, match="route"):
        handoffs.publish(writer, invocation, "press", "op")

    published = handoffs.publish(writer, invocation, "cook", "op")
    with pytest.raises(ValueError):
        evolve(published.pointer, destination_phase="press")
    with pytest.raises(handoffs.HandoffError, match="version"):
        handoffs.accept(
            evolve(
                published.pointer,
                contract_version=ContractVersion(
                    "https://schemas.easy-cheese.dev/handoff", "2", "0"
                ),
            ),
            invocation.root,
        )


def test_strict_writer_path_has_no_receipt(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = handoffs.publish(writer, invocation, "cook", "op")
    assert published.normalization_receipt is None
    assert published.pointer.normalization_receipt is None
    assert not (tmp_path / "receipts" / "op.json").exists()


def test_receipt_binding_for_non_strict_writer_repair_and_digests(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = handoffs.publish_writer_text(
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
    tampered_bytes = handoffs.canonical_bytes(tampered)
    receipt_path.write_bytes(tampered_bytes)
    receipt_ref = evolve(
        published.pointer.normalization_receipt,
        digest=_digest(tampered_bytes),
        size_bytes=len(tampered_bytes),
    )
    with pytest.raises(handoffs.HandoffError, match="receipt digest"):
        handoffs.accept(evolve(published.pointer, normalization_receipt=receipt_ref), tmp_path)


def test_writer_recovery_rejects_ambiguous_candidates(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    raw = handoffs.canonical_bytes(writer).decode()
    text = f"first\n```json\n{raw}\n```\nsecond\n```json\n{raw}\n```"
    with pytest.raises(handoffs.HandoffError, match="fenced"):
        handoffs.publish_writer_text(text, invocation, "cook", "op")


def test_normalize_writer_text_rejects_oversized_input():
    with pytest.raises(handoffs.HandoffError, match="MAX_CONTRACT_BYTES"):
        handoffs.normalize_writer_text("{" + "x" * MAX_CONTRACT_BYTES)


def test_writer_text_allows_fence_like_domain_content(tmp_path):
    writer, _invocation = writer_and_invocation(tmp_path)
    payload = evolve(
        writer.payload,
        curds=(
            evolve(
                writer.payload.curds[0],
                criteria=(
                    evolve(
                        writer.payload.curds[0].criteria[0],
                        check="Explain ```json example``` verbatim",
                    ),
                ),
            ),
        ),
    )
    repaired, _actions = handoffs.normalize_writer_text(
        handoffs.canonical_bytes(evolve(writer, payload=payload)).decode()
    )
    assert repaired.payload.curds[0].criteria[0].check == "Explain ```json example``` verbatim"


def test_writer_recovery_rejects_duplicate_json_keys(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    raw = handoffs.canonical_bytes(writer).decode().replace(
        '"kind":"curd_plan"', '"kind":"curd_plan","kind":"curd_plan"', 1
    )
    with pytest.raises(handoffs.HandoffError, match="exactly one"):
        handoffs.publish_writer_text(raw, invocation, "cook", "op")


def test_publish_rejects_symlinked_operation_directory(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "payloads").symlink_to(outside, target_is_directory=True)
    with pytest.raises(handoffs.HandoffError, match="symlink"):
        handoffs.publish(writer, invocation, "cook", "op")


def test_acceptance_rejects_payload_parent_symlink_swap(tmp_path, monkeypatch):
    writer, invocation = writer_and_invocation(tmp_path)
    published = handoffs.publish(writer, invocation, "cook", "op")
    payloads = tmp_path / "payloads"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = handoffs.read_nofollow_file
    swapped = False

    def swap_parent(directory, name):
        nonlocal swapped
        if directory == payloads and not swapped:
            swapped = True
            backup = tmp_path / "payloads-original"
            payloads.rename(backup)
            payloads.symlink_to(outside, target_is_directory=True)
            try:
                return original(directory, name)
            finally:
                payloads.unlink()
                backup.rename(payloads)
        return original(directory, name)

    monkeypatch.setattr(handoffs, "read_nofollow_file", swap_parent)
    with pytest.raises(handoffs.HandoffError, match="symlink|without following"):
        handoffs.accept(published.pointer, tmp_path)


def test_publication_rejects_parent_symlink_swap(tmp_path, monkeypatch):
    writer, invocation = writer_and_invocation(tmp_path)
    payloads = tmp_path / "payloads"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = handoffs._write_atomic_noclobber
    swapped = False

    def swap_parent(path, data, **kwargs):
        nonlocal swapped
        if path.parent.name == "payloads" and not swapped:
            swapped = True
            backup = tmp_path / "payloads-original"
            payloads.rename(backup)
            payloads.symlink_to(outside, target_is_directory=True)
            try:
                return original(path, data, **kwargs)
            finally:
                payloads.unlink()
                backup.rename(payloads)
        return original(path, data, **kwargs)

    monkeypatch.setattr(handoffs, "_write_atomic_noclobber", swap_parent)
    with pytest.raises(handoffs.HandoffError, match="operation path|changed"):
        handoffs.publish(writer, invocation, "cook", "op")
    assert not (outside / "op.json").exists()


def test_post_write_parent_swap_cannot_publish_pointer(tmp_path, monkeypatch):
    writer, invocation = writer_and_invocation(tmp_path)
    payloads = tmp_path / "payloads"
    outside = tmp_path / "outside"
    outside.mkdir()
    original = handoffs._write_atomic_noclobber
    swapped = False

    def swap_after_write(path, data, **kwargs):
        nonlocal swapped
        result = original(path, data, **kwargs)
        if path.parent == payloads and not swapped:
            swapped = True
            backup = tmp_path / "payloads-original"
            payloads.rename(backup)
            payloads.symlink_to(outside, target_is_directory=True)
        return result

    monkeypatch.setattr(handoffs, "_write_atomic_noclobber", swap_after_write)
    with pytest.raises(handoffs.HandoffError, match="changed during publication|must be a directory"):
        handoffs.publish(writer, invocation, "cook", "op")
    assert not (tmp_path / "pointers" / "op.json").exists()
    assert not (outside / "op.json").exists()


def test_pointer_link_cleanup_on_post_link_parent_swap(tmp_path, monkeypatch):
    writer, invocation = writer_and_invocation(tmp_path)
    payloads = tmp_path / "payloads"
    outside = tmp_path / "outside"
    outside.mkdir()
    original_link = handoffs.os.link
    link_count = 0

    def swap_after_pointer_link(source, target, *args, **kwargs):
        nonlocal link_count
        result = original_link(source, target, *args, **kwargs)
        link_count += 1
        if link_count == 2:
            backup = tmp_path / "payloads-original"
            payloads.rename(backup)
            payloads.symlink_to(outside, target_is_directory=True)
        return result

    monkeypatch.setattr(handoffs.os, "link", swap_after_pointer_link)
    with pytest.raises(handoffs.HandoffError, match="changed|must be a directory"):
        handoffs.publish(writer, invocation, "cook", "op")
    assert not (tmp_path / "pointers" / "op.json").exists()


def test_pointer_last_atomic(tmp_path, monkeypatch):
    writer, invocation = writer_and_invocation(tmp_path)
    original = handoffs._write_atomic_noclobber

    def fail_pointer(path, data, **kwargs):
        if path.parent.name == "pointers":
            raise OSError("interrupted")
        original(path, data, **kwargs)

    monkeypatch.setattr(handoffs, "_write_atomic_noclobber", fail_pointer)
    with pytest.raises(OSError):
        handoffs.publish_writer_text(repaired_writer_text(writer), invocation, "cook", "op")
    assert not (tmp_path / "pointers" / "op.json").exists()
    assert (tmp_path / "payloads" / "op.json").exists()
    assert (tmp_path / "receipts" / "op.json").exists()


def test_publish_rejects_symlinked_existing_pointer(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    handoffs.publish(writer, invocation, "cook", "op")
    pointer_path = tmp_path / "pointers" / "op.json"
    outside = tmp_path / "external-pointer.json"
    outside.write_bytes(pointer_path.read_bytes())
    pointer_path.unlink()
    pointer_path.symlink_to(outside)
    with pytest.raises(handoffs.HandoffError, match="symlink|without following"):
        handoffs.publish(writer, invocation, "cook", "op")


def test_publish_retry_rejects_symlinked_winner_pointer(tmp_path, monkeypatch):
    writer, invocation = writer_and_invocation(tmp_path)
    handoffs.publish(writer, invocation, "cook", "op")
    pointer_path = tmp_path / "pointers" / "op.json"
    external = tmp_path / "external-pointer.json"
    external.write_bytes(pointer_path.read_bytes())
    original_paths = handoffs._operation_paths
    installed = False

    def install_symlink(root, operation_id):
        nonlocal installed
        paths = original_paths(root, operation_id)
        if not installed:
            installed = True
            paths[2].unlink()
            paths[2].symlink_to(external)
        return paths

    monkeypatch.setattr(handoffs, "_operation_paths", install_symlink)
    with pytest.raises(handoffs.HandoffError, match="invalid existing handoff pointer"):
        handoffs.publish(writer, invocation, "cook", "op")


def test_idempotency_or_corruption_revalidates_every_published_artifact(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = handoffs.publish(writer, invocation, "cook", "op")
    assert handoffs.publish(writer, invocation, "cook", "op").pointer == published.pointer

    payload = tmp_path / "payloads" / "op.json"
    payload.write_text("{}", encoding="utf-8")
    with pytest.raises(handoffs.HandoffError, match="corrupt"):
        handoffs.publish(writer, invocation, "cook", "op")


def test_idempotency_rejects_conflicting_receipt_provenance(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    handoffs.publish_writer_text(repaired_writer_text(writer), invocation, "cook", "op")
    with pytest.raises(handoffs.HandoffError, match="normalization receipt"):
        handoffs.publish(writer, invocation, "cook", "op")


def test_accept_rejects_reference_outside_operation_root(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = handoffs.publish(writer, invocation, "cook", "op")
    outside = tmp_path.parent / "outside.json"
    outside.write_bytes((tmp_path / "payloads" / "op.json").read_bytes())
    external_ref = evolve(published.pointer.payload, uri=outside.resolve().as_uri())
    with pytest.raises(handoffs.HandoffError, match="operation root"):
        handoffs.accept(evolve(published.pointer, payload=external_ref), tmp_path)


def test_plan_artifacts_must_resolve_at_publish_and_accept(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    (tmp_path / "source.txt").unlink()
    with pytest.raises(handoffs.HandoffError, match="unresolved plan artifact"):
        handoffs.publish(writer, invocation, "cook", "op")

    (tmp_path / "source.txt").write_text("source", encoding="utf-8")
    published = handoffs.publish(writer, invocation, "cook", "op")
    (tmp_path / "source.txt").unlink()
    with pytest.raises(handoffs.HandoffError, match="unresolved plan artifact"):
        handoffs.accept(published.pointer, tmp_path)


def test_pointer_mapping_accepts_optional_receipt(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = handoffs.publish(writer, invocation, "cook", "op")
    mapping = json.loads(handoffs.canonical_bytes(published.pointer))
    assert handoffs.pointer_from_mapping(mapping) == published.pointer
