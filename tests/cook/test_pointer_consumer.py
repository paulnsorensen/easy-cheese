from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from attrs import evolve

from easy_cheese.shared.handoffs import HandoffError, canonical_bytes, pointer_from_mapping, publish
from easy_cheese.skills.cook.commands import _read_pointer, contract_accept, execute
from scripts import build_pyz
from tests.schemas.python.test_handoff_contracts import writer_and_invocation


def _run_isolated(archive: Path, cwd: Path, *arguments: str):
    return subprocess.run(
        [sys.executable, "-I", "-S", str(archive.resolve()), *arguments],
        cwd=cwd,
        env={"PATH": "", "PYTHONPATH": "/does/not/exist"},
        capture_output=True,
        text=True,
    )


def test_pointer_only_rejects_bare_payload():
    with pytest.raises(HandoffError, match="HandoffPointer"):
        contract_accept({"spec": "bare"}, Path("."))


def test_route_schema_receipt_and_normalization_strict_equality(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish(writer, invocation, "cook", "cook-op")
    accepted = contract_accept(published.pointer, tmp_path)
    assert accepted.canonical.plan_id == "plan-1"
    assert execute(published.pointer, tmp_path).plan_id == "plan-1"


def test_isolated_cook_archive_accepts_pointer_and_rejects_payload(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    publish(writer, invocation, "cook", "cook-op")
    archive = build_pyz.build_layout_bundle("cook", tmp_path / "cook.pyz")
    pointer_path = tmp_path / "pointers" / "cook-op.json"

    accepted = _run_isolated(
        archive,
        tmp_path,
        "contract",
        "accept",
        "--pointer",
        str(pointer_path),
    )
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout)["plan_id"] == "plan-1"

    payload_path = tmp_path / "payloads" / "cook-op.json"
    rejected = _run_isolated(
        archive,
        tmp_path,
        "contract",
        "accept",
        "--pointer",
        str(payload_path),
    )
    assert rejected.returncode != 0
    assert "pointer" in rejected.stderr.lower()


def test_isolated_archive_has_no_repository_import_fallback(tmp_path):
    archive = build_pyz.build_layout_bundle("cook", tmp_path / "cook.pyz")
    completed = _run_isolated(archive, tmp_path, "--help")
    assert completed.returncode == 0, completed.stderr
    assert "contract" in completed.stdout


def test_pointer_ingress_requires_canonical_bytes(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    publish(writer, invocation, "cook", "cook-op")
    pointer_path = tmp_path / "pointers" / "cook-op.json"
    pointer_path.write_bytes(b"\n" + json.dumps(json.loads(pointer_path.read_bytes())).encode())
    with pytest.raises(HandoffError, match="canonical"):
        _read_pointer(pointer_path)


def test_pointer_ingress_rejects_payload_from_another_operation_root(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    publish(writer, invocation, "cook", "cook-op")
    other = tmp_path / "other"
    other.mkdir()
    pointer_path = tmp_path / "pointers" / "cook-op.json"
    pointer = pointer_from_mapping(json.loads(pointer_path.read_bytes()))
    payload = evolve(pointer.payload, uri=(other / "payload.json").resolve().as_uri())
    pointer_path.write_bytes(canonical_bytes(evolve(pointer, payload=payload)))
    with pytest.raises(HandoffError, match="escapes"):
        _read_pointer(pointer_path)


def test_pointer_file_symlink_is_rejected(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    publish(writer, invocation, "cook", "cook-op")
    real = tmp_path / "pointers" / "cook-op.json"
    link = tmp_path / "pointer-link.json"
    link.symlink_to(real)
    with pytest.raises(HandoffError, match="symlink"):
        _read_pointer(link)


def test_contract_accept_binds_expected_operation_root(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish(writer, invocation, "cook", "cook-op")
    with pytest.raises(HandoffError, match="expected root"):
        contract_accept(published.pointer, tmp_path / "other-root")


def test_pointer_read_rejects_parent_symlink_swap(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    publish(writer, invocation, "cook", "cook-op")
    pointers = tmp_path / "pointers"
    outside = tmp_path / "outside"
    outside.mkdir()
    real = pointers / "cook-op.json"
    pointers.rename(tmp_path / "pointers-original")
    pointers.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(HandoffError, match="symlink|without following"):
            _read_pointer(real)
    finally:
        pointers.unlink()
        (tmp_path / "pointers-original").rename(pointers)
