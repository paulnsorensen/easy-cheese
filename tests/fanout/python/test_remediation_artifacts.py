"""Tests for the shared remediation path and artifact-ref helpers."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from easy_cheese.shared.remediation_artifacts import (
    REMEDIATION_STATE_ROLE,
    RemediationPathError,
    build_artifact_ref,
    bytes_digest,
    contained_path,
    path_component,
)


def test_path_component_is_stable_sha256_hex() -> None:
    value = "run/../1"
    expected = hashlib.sha256(value.encode("utf-8")).hexdigest()
    assert path_component(value) == expected
    assert path_component(value) == path_component(value)
    assert "/" not in path_component(value)


def test_contained_path_returns_resolved_target_inside_root(tmp_path: Path) -> None:
    target = tmp_path / "remediation" / "state.json"
    assert contained_path(tmp_path, target) == target.resolve()


def test_contained_path_rejects_parent_traversal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(RemediationPathError):
        _ = contained_path(root, root / ".." / "outside.json")


def test_contained_path_rejects_absolute_path_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = (tmp_path / "elsewhere" / "state.json").resolve()
    assert outside.is_absolute()
    with pytest.raises(RemediationPathError):
        _ = contained_path(root, outside)


def test_build_artifact_ref_binds_digest_and_size(tmp_path: Path) -> None:
    raw = b'{"cursor":"awaiting_review"}'
    path = tmp_path / "state.json"
    _ = path.write_bytes(raw)
    ref = build_artifact_ref(
        path, raw, artifact_id="state-1", role=REMEDIATION_STATE_ROLE
    )
    expected = "sha256:" + hashlib.sha256(raw).hexdigest()
    assert ref.digest == expected
    assert bytes_digest(raw) == expected
    assert ref.size_bytes == len(raw)
    assert ref.uri == path.resolve().as_uri()
    assert ref.role == REMEDIATION_STATE_ROLE
    assert ref.media_type == "application/json"
