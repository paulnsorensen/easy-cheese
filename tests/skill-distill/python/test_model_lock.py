from __future__ import annotations

from pathlib import Path

import pytest

from skill_distill.contracts import ModelLock
from skill_distill.model_lock import (
    LocalModelLoader,
    ModelLockError,
    snapshot_digest,
    validate_model_lock,
)


def _lock(snapshot: Path) -> ModelLock:
    return ModelLock(
        model_id="example/model",
        artifact_revision="a" * 40,
        artifact_digest=snapshot_digest(snapshot),
        runtime="fake-runtime==1.0",
        runtime_digest="b" * 64,
    )


def test_preflight_requires_full_revision_and_snapshot_digest(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    digest = snapshot_digest(snapshot)

    with pytest.raises(ModelLockError, match="full 40-character"):
        validate_model_lock(
            ModelLock("model", "short", digest, "runtime", "b" * 64)
        )
    with pytest.raises(ModelLockError, match="artifact_digest"):
        validate_model_lock(
            ModelLock("model", "a" * 40, "not-a-digest", "runtime", "b" * 64)
        )


def test_loader_only_runs_after_complete_local_snapshot_verifies(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    artifact = snapshot / "weights" / "model.bin"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"verified")
    lock = _lock(snapshot)
    calls: list[Path] = []
    loader = LocalModelLoader(lambda path: calls.append(path) or "loaded")

    assert loader.load(lock, snapshot) == "loaded"
    assert calls == [snapshot.resolve()]

    artifact.write_bytes(b"drift")
    with pytest.raises(ModelLockError, match="undeclared files or drifted artifacts"):
        loader.load(lock, snapshot)
    assert calls == [snapshot.resolve()]


def test_loader_rejects_undeclared_snapshot_files_before_factory_runs(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "model.bin").write_bytes(b"verified")
    lock = _lock(snapshot)
    calls: list[Path] = []
    loader = LocalModelLoader(lambda path: calls.append(path) or "loaded")

    (snapshot / "injected.bin").write_bytes(b"unexpected")

    with pytest.raises(ModelLockError, match="undeclared files"):
        loader.load(lock, snapshot)
    assert calls == []