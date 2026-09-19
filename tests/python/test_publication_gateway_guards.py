"""Adversarial guards of the shared publication gateway.

These cases exercise the hostile-input and crash-safety invariants of the
surviving gateway entry points: ``publish_canonical`` (through
``publish_mold_cook_handoff``), ``accept`` (through
``accept_mold_cook_handoff``), the ``operation_id`` containment rule, the
``file://``-only artifact rule, the bounded pointer read, and the
pointer-last reveal.
"""

from __future__ import annotations

import errno
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas import MAX_CONTRACT_BYTES, PublishedArtifact
from easy_cheese_schemas.mold_cook import MOLD_COOK_HANDOFF_SCHEMA_URI, MoldCookHandoff
from easy_cheese_schemas.schema_runtime import ContractValidationError

from easy_cheese.shared import mold_cook_handoff, publication
from tests.python.test_mold_cook_publication import _published_handoff  # pyright: ignore[reportPrivateUsage]


def _prepared_handoff(root: Path) -> MoldCookHandoff:
    """Materialize the shared fixture artifacts and return its handoff.

    The fixture also publishes one pointer under its own ``operation_id``;
    every test below publishes under a distinct ``operation_id``, so that
    first pointer never collides with the operation under test.
    """
    _, handoff = _published_handoff(root)
    return handoff


def _digest_for(
    handoff: MoldCookHandoff, invocation: Mapping[str, object] | None = None
) -> str:
    return publication.request_digest(
        "raw",
        invocation if invocation is not None else {"request_id": handoff.request_id},
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=MOLD_COOK_HANDOFF_SCHEMA_URI,
    )


def _publish(
    root: Path,
    handoff: MoldCookHandoff,
    *,
    operation_id: str,
    request_digest: str | None = None,
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    return mold_cook_handoff.publish_mold_cook_handoff(
        handoff,
        request_digest=request_digest
        if request_digest is not None
        else _digest_for(handoff),
        operation_id=operation_id,
        artifact_root=root,
        _before_reveal=_before_reveal,
    )


def _read_pointer_json(pointer_path: Path) -> dict[str, object]:
    return cast(
        "dict[str, object]", json.loads(pointer_path.read_text(encoding="utf-8"))
    )


def _flip_first_byte(path: Path) -> None:
    content = path.read_bytes()
    _ = path.write_bytes(bytes([content[0] ^ 1]) + content[1:])


@pytest.mark.parametrize("operation_id", ["", ".", "..", "a/b", r"a\b", "a/../b"])
def test_publish_rejects_unsafe_operation_id(
    tmp_path: Path, operation_id: str
) -> None:
    """An ``operation_id`` that could escape ``pointers/`` is rejected before
    the gateway touches the filesystem, so no artifact root appears."""
    handoff = _prepared_handoff(tmp_path / "fixture")
    unwritten_root = tmp_path / "unwritten"

    with pytest.raises(publication.PublicationError, match="invalid operation_id"):
        _ = _publish(unwritten_root, handoff, operation_id=operation_id)

    assert not unwritten_root.exists()


def test_publish_accepts_safe_operation_id(tmp_path: Path) -> None:
    handoff = _prepared_handoff(tmp_path)

    artifact = _publish(tmp_path, handoff, operation_id="safe_ID-1.0")

    assert artifact.pointer.operation_id == "safe_ID-1.0"
    assert (tmp_path / "pointers" / "safe_ID-1.0.json").is_file()


def test_accept_rejects_non_file_artifact_uri(tmp_path: Path) -> None:
    """A pointer that names a remote payload is refused: the gateway never
    fetches a publication payload over the network."""
    handoff = _prepared_handoff(tmp_path)
    published = _publish(tmp_path, handoff, operation_id="op-remote")
    assert published.pointer.payload.uri.startswith("file://")

    pointer_path = tmp_path / "pointers" / "op-remote.json"
    pointer = _read_pointer_json(pointer_path)
    payload = cast("dict[str, object]", pointer["payload"])
    payload["uri"] = "https://example.com/payload.json"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="is not a file:// uri"):
        _ = mold_cook_handoff.accept_mold_cook_handoff(
            pointer_path, artifact_root=tmp_path
        )


def test_accept_rejects_oversized_pointer_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller-supplied pointer larger than ``MAX_CONTRACT_BYTES`` is
    rejected by the bounded read, so an unbounded read never happens."""
    handoff = _prepared_handoff(tmp_path)
    _ = _publish(tmp_path, handoff, operation_id="op-oversized")
    pointer_path = tmp_path / "pointers" / "op-oversized.json"
    padding = " " * (MAX_CONTRACT_BYTES + 1)
    _ = pointer_path.write_text(
        pointer_path.read_text(encoding="utf-8") + padding, encoding="utf-8"
    )

    def _forbidden(_self: Path) -> bytes:
        raise AssertionError("pointer was read without a size bound")

    monkeypatch.setattr(Path, "read_bytes", _forbidden)

    with pytest.raises(ContractValidationError, match="MAX_CONTRACT_BYTES"):
        _ = mold_cook_handoff.accept_mold_cook_handoff(
            pointer_path, artifact_root=tmp_path
        )


def test_read_bounded_raises_overflow_for_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "oversized.json"
    _ = path.write_bytes(b"x" * (MAX_CONTRACT_BYTES + 1))

    with pytest.raises(publication.BoundedReadOverflow):
        _ = publication.read_bounded(path, MAX_CONTRACT_BYTES)


def test_publish_reveals_pointer_without_hard_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filesystem without hard links must fail before exposing a pointer."""
    handoff = _prepared_handoff(tmp_path)

    def _no_links(_source: object, _target: object) -> None:
        raise OSError(errno.EPERM, "hard links are unsupported")

    monkeypatch.setattr(os, "link", _no_links)
    with pytest.raises(
        publication.PublicationError,
        match="exclusive atomic reveal primitive",
    ):
        _ = _publish(tmp_path, handoff, operation_id="op-nolink")

    assert not (tmp_path / "pointers" / "op-nolink.json").exists()
    assert list((tmp_path / "pointers").glob(".*")) == []



def test_publish_tolerates_directory_open_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handoff = _prepared_handoff(tmp_path)
    real_open = os.open
    pointer_dir = tmp_path / "pointers"

    def _open(
        path: str, flags: int, mode: int = 0o600, *, dir_fd: int | None = None
    ) -> int:
        if Path(path) == pointer_dir:
            raise OSError(errno.EACCES, "directory handles are unsupported")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", _open)
    published = _publish(tmp_path, handoff, operation_id="op-dir-open")

    assert published.pointer.operation_id == "op-dir-open"
    assert (pointer_dir / "op-dir-open.json").is_file()


def test_publish_tolerates_directory_fsync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handoff = _prepared_handoff(tmp_path)
    real_open = os.open
    real_fsync = os.fsync
    pointer_fds: set[int] = set()
    pointer_dir = tmp_path / "pointers"

    def _open(
        path: str, flags: int, mode: int = 0o600, *, dir_fd: int | None = None
    ) -> int:
        descriptor = real_open(path, flags, mode, dir_fd=dir_fd)
        if Path(path) == pointer_dir:
            pointer_fds.add(descriptor)
        return descriptor

    def _fsync(descriptor: int) -> None:
        if descriptor in pointer_fds:
            raise OSError(errno.EIO, "directory sync is unsupported")
        real_fsync(descriptor)

    monkeypatch.setattr(os, "open", _open)
    monkeypatch.setattr(os, "fsync", _fsync)
    published = _publish(tmp_path, handoff, operation_id="op-dir-fsync")

    assert published.pointer.operation_id == "op-dir-fsync"
    assert (pointer_dir / "op-dir-fsync.json").is_file()



def test_concurrent_same_request_rehydrates_one_reveal(tmp_path: Path) -> None:
    handoff = _prepared_handoff(tmp_path)
    barrier = threading.Barrier(2)

    def _wait_for_reveal() -> None:
        _ = barrier.wait(timeout=5)

    def _publish_once() -> PublishedArtifact:
        return _publish(
            tmp_path,
            handoff,
            operation_id="op-concurrent-same",
            _before_reveal=_wait_for_reveal,
        )

    def _run(_unused: object) -> PublishedArtifact:
        return _publish_once()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(_run, (None, None))

    assert first.pointer == second.pointer
    assert first.canonical.value == second.canonical.value
    assert list((tmp_path / "pointers").glob(".*")) == []


def test_concurrent_conflicting_request_has_one_winner(
    tmp_path: Path,
) -> None:
    handoff = _prepared_handoff(tmp_path)
    barrier = threading.Barrier(2)
    digests = (
        _digest_for(handoff),
        _digest_for(handoff, {"request_id": "a-different-request"}),
    )

    def _wait_for_reveal() -> None:
        _ = barrier.wait(timeout=5)

    def _publish_once(request_digest: str) -> PublishedArtifact:
        return _publish(
            tmp_path,
            handoff,
            operation_id="op-concurrent-conflict",
            request_digest=request_digest,
            _before_reveal=_wait_for_reveal,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_publish_once, digest) for digest in digests]
        outcomes = [future.exception() or future.result() for future in futures]

    assert sum(isinstance(outcome, PublishedArtifact) for outcome in outcomes) == 1
    conflicts = [outcome for outcome in outcomes if isinstance(outcome, Exception)]
    assert len(conflicts) == 1
    assert isinstance(conflicts[0], publication.IdempotencyConflictError)
def test_publish_is_idempotent_on_replay(tmp_path: Path) -> None:
    handoff = _prepared_handoff(tmp_path)

    first = _publish(tmp_path, handoff, operation_id="op-replay")
    second = _publish(tmp_path, handoff, operation_id="op-replay")

    assert second.pointer == first.pointer
    assert second.canonical.value == first.canonical.value


def test_publish_rejects_conflicting_replay(tmp_path: Path) -> None:
    """A replayed ``operation_id`` that carries a different request digest is
    a conflict, never a silent overwrite of the published pointer."""
    handoff = _prepared_handoff(tmp_path)
    _ = _publish(tmp_path, handoff, operation_id="op-conflict")

    with pytest.raises(publication.IdempotencyConflictError):
        _ = _publish(
            tmp_path,
            handoff,
            operation_id="op-conflict",
            request_digest=_digest_for(handoff, {"request_id": "a-different-request"}),
        )


def test_publish_rejects_replay_with_tampered_operation_id(tmp_path: Path) -> None:
    """The persisted pointer's own ``operation_id`` is part of the replay
    identity, so a rewritten one is a conflict rather than a match."""
    handoff = _prepared_handoff(tmp_path)
    _ = _publish(tmp_path, handoff, operation_id="op-identity")
    pointer_path = tmp_path / "pointers" / "op-identity.json"
    pointer = _read_pointer_json(pointer_path)
    pointer["operation_id"] = "other"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(publication.IdempotencyConflictError, match="different request"):
        _ = _publish(tmp_path, handoff, operation_id="op-identity")


def test_publish_rejects_tampered_payload_on_replay(tmp_path: Path) -> None:
    """A replay revalidates the persisted payload digest instead of trusting
    the pointer that names it."""
    handoff = _prepared_handoff(tmp_path)
    first = _publish(tmp_path, handoff, operation_id="op-tamper")
    _flip_first_byte(Path(first.pointer.payload.uri.removeprefix("file://")))

    with pytest.raises(publication.PayloadDigestMismatchError):
        _ = _publish(tmp_path, handoff, operation_id="op-tamper")


def test_publish_revalidates_payload_before_pointer_reveal(tmp_path: Path) -> None:
    """A payload corrupted after it is persisted but before the pointer is
    revealed blocks the reveal, so no pointer ever names a corrupt payload."""
    handoff = _prepared_handoff(tmp_path)

    def _tamper() -> None:
        _flip_first_byte(next((tmp_path / "payloads").glob("*.json")))

    with pytest.raises(publication.PayloadDigestMismatchError):
        _ = _publish(
            tmp_path,
            handoff,
            operation_id="op-revalidate",
            _before_reveal=_tamper,
        )

    assert not (tmp_path / "pointers" / "op-revalidate.json").exists()


def test_publish_pointer_last_survives_crash_before_reveal(tmp_path: Path) -> None:
    """A crash after the payload is persisted leaves no pointer, and the
    retry completes the publication."""
    handoff = _prepared_handoff(tmp_path)

    def _boom() -> None:
        raise RuntimeError("simulated crash before pointer reveal")

    with pytest.raises(RuntimeError, match="simulated crash"):
        _ = _publish(tmp_path, handoff, operation_id="op-crash", _before_reveal=_boom)

    pointer_path = tmp_path / "pointers" / "op-crash.json"
    assert not pointer_path.exists()
    assert any((tmp_path / "payloads").glob("*.json"))

    artifact = _publish(tmp_path, handoff, operation_id="op-crash")

    assert pointer_path.is_file()
    assert artifact.pointer.operation_id == "op-crash"
    assert list((tmp_path / "pointers").glob(".*")) == []
