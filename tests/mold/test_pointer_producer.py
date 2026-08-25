from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from easy_cheese.shared.handoffs import HandoffError, canonical_bytes
from easy_cheese_schemas.contracts import MAX_CONTRACT_BYTES
from easy_cheese.skills.mold.commands import _read_writer_view, contract_publish, validate_spec
from scripts import build_pyz
from tests.schemas.python.test_handoff_contracts import (
    repaired_writer_text,
    writer_and_invocation,
)


def _run_isolated(archive: Path, cwd: Path, *arguments: str):
    return subprocess.run(
        [sys.executable, "-I", "-S", str(archive.resolve()), *arguments],
        cwd=cwd,
        env={"PATH": "", "PYTHONPATH": "/does/not/exist"},
        capture_output=True,
        text=True,
    )


def test_closed_syntax_recovery_and_receipt_pointer_publication(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    archive = build_pyz.build_layout_bundle("mold", tmp_path / "mold.pyz")
    writer_path = tmp_path / "writer.jsonish"
    invocation_path = tmp_path / "invocation.json"
    writer_path.write_text(repaired_writer_text(writer), encoding="utf-8")
    invocation_path.write_bytes(canonical_bytes(invocation.to_mapping()))

    completed = _run_isolated(
        archive,
        tmp_path,
        "contract",
        "publish",
        "--writer-view",
        str(writer_path),
        "--invocation",
        str(invocation_path),
        "--operation-id",
        "mold-op",
    )
    assert completed.returncode == 0, completed.stderr
    pointer = json.loads(completed.stdout)
    assert pointer["destination_phase"] == "cook"
    assert pointer["normalization_receipt"] is not None
    assert (tmp_path / "pointers" / "mold-op.json").is_file()


def test_typed_api_uses_strict_receipt_free_path(tmp_path):
    writer, invocation = writer_and_invocation(tmp_path)
    result = contract_publish(writer, invocation, "cook", "mold-op")
    assert result.normalization_receipt is None
    assert result.pointer.payload.digest.startswith("sha256:")


def test_validate_spec_preserves_real_behavior():
    valid = Path("tests/python/fixtures/spec_format/valid_spec.md")
    assert validate_spec(valid) == 0


def test_isolated_mold_archive_exposes_every_declared_command(tmp_path):
    archive = build_pyz.build_layout_bundle("mold", tmp_path / "mold.pyz")
    completed = _run_isolated(archive, tmp_path, "--help")
    assert completed.returncode == 0, completed.stderr
    for command in (
        "artifact-path",
        "contract",
        "curd-count",
        "gate-graph",
        "render_html",
        "taste-test",
        "validate-spec",
    ):
        assert command in completed.stdout


def test_writer_view_read_is_bounded(tmp_path):
    path = tmp_path / "writer.json"
    path.write_bytes(b"x" * (MAX_CONTRACT_BYTES + 1))
    with pytest.raises(HandoffError, match="MAX_CONTRACT_BYTES"):
        _read_writer_view(path)
