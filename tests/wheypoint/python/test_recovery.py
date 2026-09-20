"""Regression tests for transactional nonterminal recovery persistence."""

from __future__ import annotations

import errno
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
from easy_cheese_schemas import (
    ArtifactLink,
    CheckpointIntent,
    NextMove,
    WheypointDelta,
)

from easy_cheese.shared import paths
from easy_cheese.shared.wheypoint import recovery, storage


def _intent() -> CheckpointIntent:
    return CheckpointIntent(
        work_id="work-0001",
        orientation="Resume the writer.",
        working_context=["src/workflow.py"],
        notes="Writer budget checkpoint.",
        next=NextMove.COOK,
        artifact="cook/checkpoint.md",
        artifact_links=[ArtifactLink(path="cook/checkpoint.md")],
    )


def _roots(root: Path) -> tuple[Path, Path, str]:
    (root / "src").mkdir()
    _ = (root / "src" / "workflow.py").write_text("def workflow():\n    pass\n")
    corpus_root = root / "corpus"
    return corpus_root, corpus_root, paths.project_key(root)


def test_same_path_with_changed_payload_cannot_reuse_checkpoint(
    tmp_path: Path,
) -> None:
    corpus_root, _, project_key = _roots(tmp_path)
    intent = _intent()
    artifact_path = tmp_path / "cook" / "checkpoint.md"
    _ = recovery.persist_checkpoint(
        intent,
        artifact_path=artifact_path,
        artifact_payload=b"first payload",
        repository_root=tmp_path,
        corpus_root=corpus_root,
        project_key=project_key,
    )

    with pytest.raises(recovery.RecoveryError, match="already referenced"):
        _ = recovery.persist_checkpoint(
            intent,
            artifact_path=artifact_path,
            artifact_payload=b"changed payload",
            repository_root=tmp_path,
            corpus_root=corpus_root,
            project_key=project_key,
        )

    assert artifact_path.read_bytes() == b"first payload"


def test_committed_artifact_survives_lost_commit_response(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_root, _, project_key = _roots(tmp_path)
    intent = _intent()
    artifact_path = tmp_path / "cook" / "checkpoint.md"
    real_commit = cast(Callable[..., object], recovery.commit.commit)

    def promote_then_lose_response(delta: WheypointDelta, **kwargs: object) -> object:
        _ = real_commit(delta, **kwargs)
        raise RuntimeError("commit response lost")

    monkeypatch.setattr(recovery.commit, "commit", promote_then_lose_response)

    with pytest.raises(RuntimeError, match="response lost"):
        _ = recovery.persist_checkpoint(
            intent,
            artifact_path=artifact_path,
            artifact_payload=b"committed payload",
            repository_root=tmp_path,
            corpus_root=corpus_root,
            project_key=project_key,
        )

    record = storage.WorkStore.open(intent.work_id, corpus_root=corpus_root).read_record()
    assert artifact_path.read_bytes() == b"committed payload"
    assert record is not None


def test_parent_directory_closes_fds_when_setup_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = iter((41, 42))
    closed: list[int] = []

    def fake_open(*_args: object, **_kwargs: object) -> int:
        try:
            return next(opened)
        except StopIteration as exc:
            raise OSError(errno.EIO, "setup failed") from exc

    monkeypatch.setattr(os, "open", fake_open)
    monkeypatch.setattr(os, "close", closed.append)

    with pytest.raises(recovery.RecoveryError, match="not writable"):
        with recovery._parent_directory(  # pyright: ignore[reportPrivateUsage]
            tmp_path, ("nested", "deeper", "checkpoint.md")
        ):
            pytest.fail("setup should fail before yielding")

    assert closed == [42, 41]


def test_concurrent_writers_serialize_same_artifact(
    tmp_path: Path,
) -> None:
    corpus_root, _, project_key = _roots(tmp_path)
    intent = _intent()
    artifact_path = tmp_path / "cook" / "checkpoint.md"
    barrier = threading.Barrier(2)
    outcomes: list[object] = []

    def write(payload: bytes) -> None:
        _ = barrier.wait()
        try:
            outcomes.append(
                recovery.persist_checkpoint(
                    intent,
                    artifact_path=artifact_path,
                    artifact_payload=payload,
                    repository_root=tmp_path,
                    corpus_root=corpus_root,
                    project_key=project_key,
                )
            )
        except Exception as exc:
            outcomes.append(exc)

    threads = [
        threading.Thread(target=write, args=(b"writer one",)),
        threading.Thread(target=write, args=(b"writer two",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(isinstance(item, recovery.RecoveryResult) for item in outcomes) == 1
    assert sum(isinstance(item, recovery.RecoveryError) for item in outcomes) == 1
    assert artifact_path.read_bytes() in {b"writer one", b"writer two"}


def test_cleanup_read_failure_preserves_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus_root, _, project_key = _roots(tmp_path)
    intent = _intent()
    artifact_path = tmp_path / "cook" / "checkpoint.md"
    real_read = storage.WorkStore.read_record
    read_calls = 0

    def fail_after_first_read(store: storage.WorkStore) -> object:
        nonlocal read_calls
        read_calls += 1
        if read_calls > 1:
            raise OSError("record read failed")
        return real_read(store)

    def fail_commit(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(storage.WorkStore, "read_record", fail_after_first_read)
    monkeypatch.setattr(recovery.commit, "commit", fail_commit)

    with pytest.raises(recovery.RecoveryError, match="authority could not be read"):
        _ = recovery.persist_checkpoint(
            intent,
            artifact_path=artifact_path,
            artifact_payload=b"preserve this artifact",
            repository_root=tmp_path,
            corpus_root=corpus_root,
            project_key=project_key,
        )

    assert artifact_path.read_bytes() == b"preserve this artifact"
