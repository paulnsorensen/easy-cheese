"""Adversarial guards for the shared publication gateway."""

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

from easy_cheese_schemas import (
    MAX_CONTRACT_BYTES,
    CurdPlan,
    PublishedArtifact,
    canonical_bytes,
    supported_version_for,
    validate_contract,
)
from easy_cheese_schemas.schema_runtime import ContractValidationError
from easy_cheese.shared import publication
from tests.python.test_mold_cook_publication import (
    CURD_PLAN_SCHEMA_URI,
    _published_plan,  # pyright: ignore[reportPrivateUsage]
)


def _prepared_plan(root: Path) -> CurdPlan:
    """Publish fixture artifacts before each guard uses another operation ID."""
    _, plan = _published_plan(root)
    return plan


def _digest_for(plan: CurdPlan, invocation: Mapping[str, object] | None = None) -> str:
    return publication.request_digest(
        "raw",
        invocation if invocation is not None else {"plan_id": plan.plan_id},
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
    )


def _publish(
    root: Path,
    plan: CurdPlan,
    *,
    operation_id: str,
    request_digest: str | None = None,
    _before_reveal: Callable[[], None] | None = None,
) -> PublishedArtifact:
    return publication.publish_canonical(
        request_digest=request_digest
        if request_digest is not None
        else _digest_for(plan),
        source_phase="mold",
        destination_phase="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        operation_id=operation_id,
        artifact_root=root,
        prepare=lambda: validate_contract(
            canonical_bytes(plan), CurdPlan, supported_version_for(CurdPlan)
        ),
        _before_reveal=_before_reveal,
    )


def _accept(pointer_path: Path, *, artifact_root: Path):
    return publication.accept(
        pointer_path,
        destination_phase="cook",
        payload_schema_uri=CURD_PLAN_SCHEMA_URI,
        artifact_root=artifact_root,
    )


def _read_pointer_json(pointer_path: Path) -> dict[str, object]:
    return cast(
        "dict[str, object]", json.loads(pointer_path.read_text(encoding="utf-8"))
    )


def _flip_first_byte(path: Path) -> None:
    content = path.read_bytes()
    _ = path.write_bytes(bytes([content[0] ^ 1]) + content[1:])


@pytest.mark.parametrize("operation_id", ["", ".", "..", "a/b", r"a\b", "a/../b"])
def test_publish_rejects_unsafe_operation_id(tmp_path: Path, operation_id: str) -> None:
    """An ``operation_id`` that could escape ``pointers/`` is rejected before
    the gateway touches the filesystem, so no artifact root appears."""
    plan = _prepared_plan(tmp_path / "fixture")
    unwritten_root = tmp_path / "unwritten"

    with pytest.raises(publication.PublicationError, match="invalid operation_id"):
        _ = _publish(unwritten_root, plan, operation_id=operation_id)

    assert not unwritten_root.exists()


@pytest.mark.parametrize(
    "request_digest",
    ["", "sha256:0", "sha256:" + "G" * 64, "sha256:" + "A" * 64, "sha512:" + "0" * 64],
)
def test_publish_rejects_invalid_request_digest_before_writes(
    tmp_path: Path, request_digest: str
) -> None:
    plan = _prepared_plan(tmp_path / "fixture")
    unwritten_root = tmp_path / "unwritten"

    with pytest.raises(publication.PublicationError, match="invalid request_digest"):
        _ = _publish(
            unwritten_root,
            plan,
            operation_id="invalid-digest",
            request_digest=request_digest,
        )

    assert not unwritten_root.exists()


def test_publish_accepts_safe_operation_id(tmp_path: Path) -> None:
    plan = _prepared_plan(tmp_path)

    artifact = _publish(tmp_path, plan, operation_id="safe_ID-1.0")

    assert artifact.pointer_path == tmp_path / "pointers" / "safe_ID-1.0.json"
    assert (tmp_path / "pointers" / "safe_ID-1.0.json").is_file()


def test_accept_rejects_non_file_artifact_uri(tmp_path: Path) -> None:
    """A pointer that names a remote payload is refused: the gateway never
    fetches a publication payload over the network."""
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-remote")

    pointer_path = tmp_path / "pointers" / "op-remote.json"
    pointer = _read_pointer_json(pointer_path)
    payload = cast("dict[str, object]", pointer["payload"])
    assert cast(str, payload["uri"]).startswith("file://")
    payload["uri"] = "https://example.com/payload.json"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="is not a file:// uri"):
        _ = _accept(pointer_path, artifact_root=tmp_path)


def test_accept_rejects_unknown_index_field(tmp_path: Path) -> None:
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-unknown")
    path = tmp_path / "pointers" / "op-unknown.json"
    index = _read_pointer_json(path)
    index["unexpected"] = "untrusted"
    _ = path.write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="invalid publication index"):
        _ = _accept(path, artifact_root=tmp_path)


def test_accept_rejects_payload_outside_artifact_root(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    plan = _prepared_plan(root)
    _ = _publish(root, plan, operation_id="op-outside")
    path = root / "pointers" / "op-outside.json"
    index = _read_pointer_json(path)
    payload = cast("dict[str, object]", index["payload"])
    outside = tmp_path / "outside.json"
    _ = outside.write_bytes(b"not trusted")
    payload["uri"] = outside.as_uri()
    _ = path.write_text(json.dumps(index), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="escapes allowed root"):
        _ = _accept(path, artifact_root=root)


def test_accept_rejects_oversized_pointer_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller-supplied pointer larger than ``MAX_CONTRACT_BYTES`` is
    rejected by the bounded read, so an unbounded read never happens."""
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-oversized")
    pointer_path = tmp_path / "pointers" / "op-oversized.json"
    padding = " " * (MAX_CONTRACT_BYTES + 1)
    _ = pointer_path.write_text(
        pointer_path.read_text(encoding="utf-8") + padding, encoding="utf-8"
    )

    def _forbidden(_self: Path) -> bytes:
        raise AssertionError("pointer was read without a size bound")

    monkeypatch.setattr(Path, "read_bytes", _forbidden)

    with pytest.raises(ContractValidationError, match="MAX_CONTRACT_BYTES"):
        _ = _accept(pointer_path, artifact_root=tmp_path)


def test_read_bounded_raises_overflow_for_oversized_file(tmp_path: Path) -> None:
    path = tmp_path / "oversized.json"
    _ = path.write_bytes(b"x" * (MAX_CONTRACT_BYTES + 1))

    with pytest.raises(publication.BoundedReadOverflow):
        _ = publication.read_bounded(path, MAX_CONTRACT_BYTES)


def test_publish_reveals_pointer_without_hard_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A filesystem without hard links must fail before exposing a pointer."""
    plan = _prepared_plan(tmp_path)

    def _no_links(_source: object, _target: object) -> None:
        raise OSError(errno.EPERM, "hard links are unsupported")

    monkeypatch.setattr(os, "link", _no_links)
    with pytest.raises(
        publication.PublicationError,
        match="exclusive atomic reveal primitive",
    ):
        _ = _publish(tmp_path, plan, operation_id="op-nolink")

    assert not (tmp_path / "pointers" / "op-nolink.json").exists()
    assert list((tmp_path / "pointers").glob(".*")) == []


def test_publish_tolerates_directory_open_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _prepared_plan(tmp_path)
    real_open = os.open
    pointer_dir = tmp_path / "pointers"

    def _open(
        path: str, flags: int, mode: int = 0o600, *, dir_fd: int | None = None
    ) -> int:
        if Path(path) == pointer_dir:
            raise OSError(errno.EACCES, "directory handles are unsupported")
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", _open)
    published = _publish(tmp_path, plan, operation_id="op-dir-open")

    assert published.pointer_path == pointer_dir / "op-dir-open.json"
    assert (pointer_dir / "op-dir-open.json").is_file()


def test_publish_tolerates_directory_fsync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _prepared_plan(tmp_path)
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
    published = _publish(tmp_path, plan, operation_id="op-dir-fsync")

    assert published.pointer_path == pointer_dir / "op-dir-fsync.json"
    assert (pointer_dir / "op-dir-fsync.json").is_file()


def test_concurrent_same_request_rehydrates_one_reveal(tmp_path: Path) -> None:
    plan = _prepared_plan(tmp_path)
    barrier = threading.Barrier(2)

    def _wait_for_reveal() -> None:
        _ = barrier.wait(timeout=5)

    def _publish_once() -> PublishedArtifact:
        return _publish(
            tmp_path,
            plan,
            operation_id="op-concurrent-same",
            _before_reveal=_wait_for_reveal,
        )

    def _run(_unused: object) -> PublishedArtifact:
        return _publish_once()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.map(_run, (None, None))

    assert first.pointer_path == second.pointer_path
    assert first.canonical.value == second.canonical.value
    assert list((tmp_path / "pointers").glob(".*")) == []


def test_concurrent_conflicting_request_has_one_winner(
    tmp_path: Path,
) -> None:
    plan = _prepared_plan(tmp_path)
    barrier = threading.Barrier(2)
    digests = (
        _digest_for(plan),
        _digest_for(plan, {"request_id": "a-different-request"}),
    )

    def _wait_for_reveal() -> None:
        _ = barrier.wait(timeout=5)

    def _publish_once(request_digest: str) -> PublishedArtifact:
        return _publish(
            tmp_path,
            plan,
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
    plan = _prepared_plan(tmp_path)

    first = _publish(tmp_path, plan, operation_id="op-replay")
    second = _publish(tmp_path, plan, operation_id="op-replay")

    assert second.pointer_path == first.pointer_path
    assert second.canonical.value == first.canonical.value


def test_publish_rejects_conflicting_replay(tmp_path: Path) -> None:
    """A replayed ``operation_id`` that carries a different request digest is
    a conflict, never a silent overwrite of the published pointer."""
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-conflict")

    with pytest.raises(publication.IdempotencyConflictError):
        _ = _publish(
            tmp_path,
            plan,
            operation_id="op-conflict",
            request_digest=_digest_for(plan, {"request_id": "a-different-request"}),
        )


def test_publish_rejects_replay_with_tampered_operation_id(tmp_path: Path) -> None:
    """The persisted pointer's own ``operation_id`` is part of the replay
    identity, so a rewritten one is a conflict rather than a match."""
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-identity")
    pointer_path = tmp_path / "pointers" / "op-identity.json"
    pointer = _read_pointer_json(pointer_path)
    cast(dict[str, object], pointer["request"])["operation_id"] = "other"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="path does not match operation_id"):
        _ = _publish(tmp_path, plan, operation_id="op-identity")


def test_publish_rejects_tampered_payload_on_replay(tmp_path: Path) -> None:
    """A replay revalidates the persisted payload digest instead of trusting
    the pointer that names it."""
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-tamper")
    _flip_first_byte(next((tmp_path / "payloads").glob("*.json")))

    with pytest.raises(publication.PayloadDigestMismatchError):
        _ = _publish(tmp_path, plan, operation_id="op-tamper")


def test_publish_revalidates_payload_before_pointer_reveal(tmp_path: Path) -> None:
    """A payload corrupted after it is persisted but before the pointer is
    revealed blocks the reveal, so no pointer ever names a corrupt payload."""
    plan = _prepared_plan(tmp_path)

    def _tamper() -> None:
        _flip_first_byte(next((tmp_path / "payloads").glob("*.json")))

    with pytest.raises(publication.PayloadDigestMismatchError):
        _ = _publish(
            tmp_path,
            plan,
            operation_id="op-revalidate",
            _before_reveal=_tamper,
        )

    assert not (tmp_path / "pointers" / "op-revalidate.json").exists()


def test_publish_pointer_last_survives_crash_before_reveal(tmp_path: Path) -> None:
    """A crash after the payload is persisted leaves no pointer, and the
    retry completes the publication."""
    plan = _prepared_plan(tmp_path)

    def _boom() -> None:
        raise RuntimeError("simulated crash before pointer reveal")

    with pytest.raises(RuntimeError, match="simulated crash"):
        _ = _publish(tmp_path, plan, operation_id="op-crash", _before_reveal=_boom)

    pointer_path = tmp_path / "pointers" / "op-crash.json"
    assert not pointer_path.exists()
    assert any((tmp_path / "payloads").glob("*.json"))

    artifact = _publish(tmp_path, plan, operation_id="op-crash")

    assert pointer_path.is_file()
    assert artifact.pointer_path == pointer_path
    assert list((tmp_path / "pointers").glob(".*")) == []


def test_accept_rejects_pointer_with_old_plan_schema(tmp_path: Path) -> None:
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-old-plan")
    pointer_path = tmp_path / "pointers" / "op-old-plan.json"
    pointer = _read_pointer_json(pointer_path)
    payload = cast("dict[str, object]", pointer["payload"])
    payload["schema_uri"] = CURD_PLAN_SCHEMA_URI + "-old"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(
        ContractValidationError,
        match="payload schema does not match publication request",
    ):
        _ = _accept(pointer_path, artifact_root=tmp_path)


def test_accept_rejects_pointer_with_wrong_destination_route(tmp_path: Path) -> None:
    plan = _prepared_plan(tmp_path)
    _ = _publish(tmp_path, plan, operation_id="op-route")
    pointer_path = tmp_path / "pointers" / "op-route.json"
    pointer = _read_pointer_json(pointer_path)
    cast("dict[str, object]", pointer["request"])["destination_phase"] = "age"
    _ = pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="'age'.*'cook'"):
        _ = _accept(pointer_path, artifact_root=tmp_path)
