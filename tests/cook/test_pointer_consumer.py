from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from easy_cheese.shared.handoffs import HandoffError, publish
from easy_cheese.skills.cook.commands import contract_accept, execute
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
        contract_accept({"spec": "bare"})


def test_route_schema_receipt_and_normalization_strict_equality(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    published = publish(writer, invocation, "cook", "cook-op")
    accepted = contract_accept(published.pointer)
    assert accepted.canonical.plan_id == "plan-1"
    assert execute(published.pointer).plan_id == "plan-1"


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
