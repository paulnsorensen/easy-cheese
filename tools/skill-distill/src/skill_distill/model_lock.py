"""Strict local model lock verification; this module never fetches artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable, Generic, TypeVar

from .contracts import ModelLock

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")


def model_profile_digest(locks: tuple[ModelLock, ...]) -> str:
    """Hash the complete immutable model identities used for one scoring run."""
    payload = [
        {
            "model_id": lock.model_id,
            "artifact_revision": lock.artifact_revision,
            "artifact_digest": lock.artifact_digest,
            "runtime": lock.runtime,
            "runtime_digest": lock.runtime_digest,
        }
        for lock in locks
    ]
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class VerifiedSnapshot:
    lock: ModelLock
    path: Path


class ModelLockError(ValueError):
    """A local model cannot be used as declared."""


def _snapshot_files(root: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ModelLockError(f"symlinked snapshot entry: {path.relative_to(root)}")
        if path.is_file():
            files.append(path)
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def snapshot_digest(snapshot: Path) -> str:
    """Return the digest of the complete, non-symlinked local artifact set."""
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise ModelLockError(f"local snapshot directory is missing: {snapshot}")
    root = snapshot.resolve()
    artifacts = [
        (path.relative_to(root).as_posix(), sha256(path.read_bytes()).hexdigest())
        for path in _snapshot_files(root)
    ]
    return sha256(json.dumps(artifacts, separators=(",", ":")).encode()).hexdigest()


def validate_model_lock(lock: ModelLock) -> None:
    """Reject incomplete immutable identities before touching a model snapshot."""
    if not lock.model_id:
        raise ModelLockError("model_id is required")
    if not _FULL_REVISION.fullmatch(lock.artifact_revision):
        raise ModelLockError("artifact_revision must be a full 40-character immutable revision")
    if not _SHA256.fullmatch(lock.artifact_digest):
        raise ModelLockError("artifact_digest must be a SHA-256")
    if not lock.runtime:
        raise ModelLockError("runtime is required")
    if not _SHA256.fullmatch(lock.runtime_digest):
        raise ModelLockError("runtime_digest must be a SHA-256")


def verify_local_snapshot(lock: ModelLock, snapshot: Path) -> VerifiedSnapshot:
    """Verify that the complete local artifact snapshot is exactly the locked set."""
    validate_model_lock(lock)
    digest = snapshot_digest(snapshot)
    if digest != lock.artifact_digest:
        raise ModelLockError("local snapshot contains undeclared files or drifted artifacts")
    return VerifiedSnapshot(lock=lock, path=snapshot.resolve())


T = TypeVar("T")


class LocalModelLoader(Generic[T]):
    """Calls a loader only after the immutable local snapshot is verified."""

    def __init__(self, factory: Callable[[Path], T]) -> None:
        self._factory = factory

    def load(self, lock: ModelLock, snapshot: Path) -> T:
        verified = verify_local_snapshot(lock, snapshot)
        return self._factory(verified.path)