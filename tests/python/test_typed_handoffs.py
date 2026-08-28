from __future__ import annotations

import json
from pathlib import Path

import pytest

import easy_cheese.shared.handoffs as handoffs
from attrs import evolve
from easy_cheese.skills.mold.contract_cli import main as mold_contract_main
from easy_cheese_schemas import CurdPlan, curd_plan_digest, load


def plan() -> dict[str, object]:
    raw = {
        "contract_version": {
            "schema_uri": handoffs.CURD_PLAN_SCHEMA_URI,
            "major": "1",
            "minor": "0",
        },
        "plan_id": "plan-inner",
        "revision": 1,
        "digest": "sha256:" + "0" * 64,
        "objective": "Test the typed boundary",
        "curds": [
            {
                "curd_id": "curd-inner",
                "outcome": "Publish safely",
                "scope": {"paths": ["src/handoff.py"]},
                "inputs": [],
                "outputs": ["A pointer"],
                "dependencies": [],
                "criteria": [
                    {
                        "criterion_id": "criterion-inner",
                        "description": "The pointer validates",
                        "check": "pytest",
                    }
                ],
                "lineage": {"identity_action": "new"},
            }
        ],
    }
    loaded = load(raw, CurdPlan, strict=True).value
    assert loaded is not None
    raw["digest"] = curd_plan_digest(loaded)
    return raw


def test_normalization_is_syntax_only_and_bounded(tmp_path: Path) -> None:
    strict = json.dumps(plan())
    repaired = "// note\n" + strict.replace('"plan_id"', "plan_id", 1)
    published = handoffs.publish_writer_text(
        repaired, "cook", "op-repaired", tmp_path
    )
    assert published.normalization_receipt is not None
    assert {action.kind for action in published.normalization_receipt.actions} == {
        "comment",
        "unquoted_key",
    }
    assert published.canonical.plan_id == "plan-inner"

    with pytest.raises(handoffs.HandoffError):
        handoffs.normalize_writer_text('{"curd_plan": {{')
    with pytest.raises(handoffs.HandoffError):
        handoffs.normalize_writer_text('{"plan_id": "a", "plan_id": "b"}')


def test_publication_revalidates_idempotency_and_corruption(tmp_path: Path) -> None:
    source = json.dumps(plan())
    first = handoffs.publish_writer_text(source, "cook", "op", tmp_path)
    second = handoffs.publish_writer_text(source, "cook", "op", tmp_path)
    assert second.pointer == first.pointer

    payload = tmp_path / "payloads" / "op.json"
    payload.write_bytes(payload.read_bytes() + b"\n")
    with pytest.raises(handoffs.HandoffError, match="corrupt"):
        handoffs.publish_writer_text(source, "cook", "op", tmp_path)


def test_operation_conflict_rejects_different_request(tmp_path: Path) -> None:
    source = json.dumps(plan())
    handoffs.publish_writer_text(source, "cook", "op", tmp_path)
    changed_plan = plan()
    changed_plan["objective"] = "Different request"
    changed_loaded = load(changed_plan, CurdPlan, strict=True).value
    assert changed_loaded is not None
    changed_plan["digest"] = curd_plan_digest(changed_loaded)
    with pytest.raises(handoffs.HandoffError, match="conflicts"):
        handoffs.publish_writer_text(
            json.dumps(changed_plan), "cook", "op", tmp_path
        )


def test_accept_requires_pointer_path(tmp_path: Path) -> None:
    source = json.dumps(plan())
    published = handoffs.publish_writer_text(source, "cook", "op", tmp_path)
    assert handoffs.accept(published.pointer_path).canonical.plan_id == "plan-inner"
    with pytest.raises(handoffs.HandoffError):
        handoffs.accept(tmp_path / "payloads" / "op.json")


def test_legacy_adapter_is_exact_and_has_sunset(tmp_path: Path, monkeypatch) -> None:
    legacy = {
        "schema_uri": handoffs.LEGACY_SCHEMA_URI,
        "version": {"major": "1", "minor": "0"},
        "source_phase": "mold",
        "destination_phase": "cook",
        "payload": plan(),
    }
    published = handoffs.migrate_legacy_text(
        json.dumps(legacy), "legacy", tmp_path
    )
    assert published.normalization_receipt is not None
    assert published.normalization_receipt.remove_after == "2.0.0"

    legacy["version"] = {"major": "1", "minor": "1"}
    with pytest.raises(handoffs.HandoffError, match="unsupported"):
        handoffs.migrate_legacy_text(json.dumps(legacy), "other", tmp_path)

    legacy["version"] = {"major": "1", "minor": "0"}
    monkeypatch.setattr(handoffs, "LEGACY_REMOVE_AFTER", "1.0.0")
    with pytest.raises(handoffs.HandoffError, match="sunset"):
        handoffs.migrate_legacy_text(json.dumps(legacy), "sunset", tmp_path)


def test_all_plan_ingress_rejects_wrong_digest_and_unsupported_version(
    tmp_path: Path,
) -> None:
    invalid_digest = plan()
    invalid_digest["digest"] = "sha256:" + "f" * 64
    with pytest.raises(handoffs.HandoffError, match="digest mismatch"):
        handoffs.publish_writer_text(
            json.dumps(invalid_digest), "cook", "wrong-digest", tmp_path
        )

    unsupported = plan()
    unsupported["contract_version"]["minor"] = "1"
    with pytest.raises(handoffs.HandoffError, match="unsupported contract version"):
        handoffs.publish_writer_text(
            json.dumps(unsupported), "cook", "wrong-version", tmp_path
        )

    legacy = {
        "schema_uri": handoffs.LEGACY_SCHEMA_URI,
        "version": {"major": "1", "minor": "0"},
        "source_phase": "mold",
        "destination_phase": "cook",
        "payload": invalid_digest,
    }
    with pytest.raises(handoffs.HandoffError, match="digest mismatch"):
        handoffs.migrate_legacy_text(json.dumps(legacy), "legacy-invalid", tmp_path)


def test_accept_revalidates_plan_self_digest(tmp_path: Path) -> None:
    published = handoffs.publish_writer_text(
        json.dumps(plan()), "cook", "accept-invalid", tmp_path
    )
    payload_path = tmp_path / "payloads" / "accept-invalid.json"
    payload = json.loads(payload_path.read_bytes())
    payload["digest"] = "sha256:" + "f" * 64
    payload_bytes = handoffs.canonical_bytes(payload)
    payload_path.write_bytes(payload_bytes)
    pointer = evolve(
        published.pointer,
        payload=evolve(
            published.pointer.payload,
            digest=handoffs.digest(payload_bytes),
            size_bytes=len(payload_bytes),
        ),
    )
    published.pointer_path.write_bytes(handoffs.canonical_bytes(pointer))
    with pytest.raises(handoffs.HandoffError, match="digest mismatch"):
        handoffs.accept(published.pointer_path)


def test_accept_rejects_unsupported_plan_version(tmp_path: Path) -> None:
    published = handoffs.publish_writer_text(
        json.dumps(plan()), "cook", "accept-version", tmp_path
    )
    payload_path = tmp_path / "payloads" / "accept-version.json"
    payload = json.loads(payload_path.read_bytes())
    payload["contract_version"]["minor"] = "1"
    payload_bytes = handoffs.canonical_bytes(payload)
    payload_path.write_bytes(payload_bytes)
    pointer = evolve(
        published.pointer,
        payload=evolve(
            published.pointer.payload,
            digest=handoffs.digest(payload_bytes),
            size_bytes=len(payload_bytes),
        ),
    )
    published.pointer_path.write_bytes(handoffs.canonical_bytes(pointer))
    with pytest.raises(handoffs.HandoffError, match="unsupported contract version"):
        handoffs.accept(published.pointer_path)


def test_receipt_is_canonical_and_bound_to_request_provenance(tmp_path: Path) -> None:
    source = "// repaired\n" + json.dumps(plan())
    published = handoffs.publish_writer_text(source, "cook", "receipt", tmp_path)
    receipt_path = tmp_path / "receipts" / "receipt.json"
    assert published.normalization_receipt is not None
    assert published.normalization_receipt.source_digest == published.pointer.request_digest
    assert receipt_path.read_bytes() == handoffs.canonical_bytes(
        published.normalization_receipt
    )

    receipt = evolve(
        published.normalization_receipt,
        normalizer_id="unsupported-normalizer",
    )
    receipt_bytes = handoffs.canonical_bytes(receipt)
    receipt_path.write_bytes(receipt_bytes)
    pointer = evolve(
        published.pointer,
        normalization_receipt=evolve(
            published.pointer.normalization_receipt,
            digest=handoffs.digest(receipt_bytes),
            size_bytes=len(receipt_bytes),
        ),
    )
    published.pointer_path.write_bytes(handoffs.canonical_bytes(pointer))
    with pytest.raises(handoffs.HandoffError, match="unsupported.*provenance"):
        handoffs.accept(published.pointer_path)


def test_receipt_rejects_noncanonical_bytes_and_wrong_source_digest(
    tmp_path: Path,
) -> None:
    source = "// repaired\n" + json.dumps(plan())
    published = handoffs.publish_writer_text(source, "cook", "receipt-bytes", tmp_path)
    receipt_path = tmp_path / "receipts" / "receipt-bytes.json"
    receipt = published.normalization_receipt
    assert receipt is not None

    noncanonical = handoffs.canonical_bytes(receipt) + b"\n"
    receipt_path.write_bytes(noncanonical)
    pointer = evolve(
        published.pointer,
        normalization_receipt=evolve(
            published.pointer.normalization_receipt,
            digest=handoffs.digest(noncanonical),
            size_bytes=len(noncanonical),
        ),
    )
    published.pointer_path.write_bytes(handoffs.canonical_bytes(pointer))
    with pytest.raises(handoffs.HandoffError, match="canonical"):
        handoffs.accept(published.pointer_path)

    wrong_source = evolve(receipt, source_digest="sha256:" + "f" * 64)
    receipt_bytes = handoffs.canonical_bytes(wrong_source)
    receipt_path.write_bytes(receipt_bytes)
    pointer = evolve(
        published.pointer,
        normalization_receipt=evolve(
            published.pointer.normalization_receipt,
            digest=handoffs.digest(receipt_bytes),
            size_bytes=len(receipt_bytes),
        ),
    )
    published.pointer_path.write_bytes(handoffs.canonical_bytes(pointer))
    with pytest.raises(handoffs.HandoffError, match="source digest"):
        handoffs.accept(published.pointer_path)


def test_publication_rejects_symlinked_root_and_ancestor(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    root_link = tmp_path / "root-link"
    root_link.symlink_to(target, target_is_directory=True)
    with pytest.raises(handoffs.HandoffError, match="unsafe directory"):
        handoffs.publish_writer_text(json.dumps(plan()), "cook", "root", root_link)

    ancestor = tmp_path / "ancestor"
    ancestor.symlink_to(target, target_is_directory=True)
    with pytest.raises(handoffs.HandoffError, match="unsafe directory"):
        handoffs.publish_writer_text(
            json.dumps(plan()), "cook", "ancestor", ancestor / "handoffs"
        )


def test_publication_detects_directory_swap_without_writing_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "handoffs"
    root.mkdir()
    displaced = tmp_path / "displaced"
    original_link = handoffs.os.link
    swapped = False

    def swap_after_link(*args, **kwargs):
        nonlocal swapped
        result = original_link(*args, **kwargs)
        if not swapped:
            root.rename(displaced)
            root.mkdir()
            for name in ("payloads", "receipts", "pointers"):
                (root / name).mkdir()
            swapped = True
        return result

    monkeypatch.setattr(handoffs.os, "link", swap_after_link)
    with pytest.raises(handoffs.HandoffError, match="root changed"):
        handoffs.publish_writer_text(json.dumps(plan()), "cook", "swap", root)
    assert not any((root / "payloads").iterdir())
    assert (displaced / "payloads" / "swap.json").is_file()
    assert not (displaced / "pointers" / "swap.json").exists()



def test_pointer_is_removed_when_root_swaps_during_pointer_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "handoffs"
    root.mkdir()
    displaced = tmp_path / "displaced"
    original_link = handoffs.os.link
    swapped = False

    def swap_after_pointer_link(*args, **kwargs):
        nonlocal swapped
        result = original_link(*args, **kwargs)
        destination_fd = kwargs["dst_dir_fd"]
        pointer_directory = root / "pointers"
        if (
            not swapped
            and pointer_directory.exists()
            and handoffs.os.fstat(destination_fd).st_ino
            == pointer_directory.stat().st_ino
        ):
            root.rename(displaced)
            root.mkdir()
            for name in ("payloads", "receipts", "pointers"):
                (root / name).mkdir()
            swapped = True
        return result

    monkeypatch.setattr(handoffs.os, "link", swap_after_pointer_link)
    with pytest.raises(handoffs.HandoffError, match="root changed"):
        handoffs.publish_writer_text(json.dumps(plan()), "cook", "pointer-swap", root)
    assert swapped
    assert not (root / "pointers" / "pointer-swap.json").exists()
    assert not (displaced / "pointers" / "pointer-swap.json").exists()
    assert (displaced / "payloads" / "pointer-swap.json").is_file()


def test_reads_are_bounded_and_canonical_depth_is_enforced(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    oversized.write_bytes(b"x" * 9)
    with pytest.raises(handoffs.HandoffError, match="exceeds 8 bytes"):
        handoffs.read_nofollow(oversized, 8)

    deep: object = "bottom"
    for _ in range(70):
        deep = {"nested": deep}
    raw = plan()
    raw["context"] = {"items": [{"key": "deep", "value": deep}]}
    with pytest.raises(handoffs.HandoffError, match="MAX_CONTRACT_DEPTH"):
        handoffs.publish_writer_text(json.dumps(raw), "cook", "deep", tmp_path)


def test_cli_and_referenced_artifact_reads_stop_at_the_byte_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    oversized_input = tmp_path / "oversized-input.json"
    oversized_input.write_bytes(b"x" * (handoffs.MAX_CONTRACT_BYTES + 1))
    assert (
        mold_contract_main(
            [
                "publish",
                "--writer-view",
                str(oversized_input),
                "--destination",
                "cook",
                "--operation-id",
                "oversized",
                "--out-dir",
                str(tmp_path / "out"),
            ]
        )
        == 1
    )
    assert "exceeds" in capsys.readouterr().err

    published = handoffs.publish_writer_text(
        json.dumps(plan()), "cook", "oversized-reference", tmp_path / "references"
    )
    payload_path = tmp_path / "references" / "payloads" / "oversized-reference.json"
    payload_bytes = b"x" * (handoffs.MAX_CONTRACT_BYTES + 1)
    payload_path.write_bytes(payload_bytes)
    pointer = evolve(
        published.pointer,
        payload=evolve(
            published.pointer.payload,
            digest=handoffs.digest(payload_bytes),
            size_bytes=len(payload_bytes),
        ),
    )
    published.pointer_path.write_bytes(handoffs.canonical_bytes(pointer))
    with pytest.raises(handoffs.HandoffError, match="exceeds"):
        handoffs.accept(published.pointer_path)
