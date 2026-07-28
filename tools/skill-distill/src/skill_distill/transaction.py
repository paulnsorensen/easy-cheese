"""Family-atomic filesystem rewrite transactions."""

from __future__ import annotations

import os
import stat
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TransactionResult:
    family_id: str
    applied_paths: tuple[Path, ...]


def _replace(path: Path, content: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(temporary, mode)
        else:
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(temporary, 0o666 & ~umask)
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def _rollback(
    ordered: tuple[Path, ...],
    snapshots: Mapping[Path, tuple[bytes, int] | None],
    error: BaseException,
) -> None:
    unrestored = []
    for path in ordered:
        snapshot = snapshots[path]
        try:
            if snapshot is None:
                path.unlink(missing_ok=True)
            else:
                content, mode = snapshot
                _replace(path, content, mode)
        except BaseException:
            unrestored.append(path)
    if unrestored:
        names = ", ".join(str(path) for path in unrestored)
        error.add_note(f"rollback could not restore: {names}")


def apply_family(family_id: str, changes: Mapping[Path, bytes]) -> TransactionResult:
    """Apply all family members and restore every snapshot on any failure."""
    if not family_id or not changes:
        raise ValueError("family id and changes are required")
    ordered = tuple(sorted((Path(path) for path in changes), key=lambda path: path.as_posix()))
    if len(set(ordered)) != len(ordered):
        raise ValueError("family changes contain duplicate paths")
    snapshots = {
        path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode)) if path.exists() else None
        for path in ordered
    }
    try:
        for path in ordered:
            snapshot = snapshots[path]
            _replace(path, changes[path], snapshot[1] if snapshot is not None else None)
    except BaseException as error:
        _rollback(ordered, snapshots, error)
        raise
    return TransactionResult(family_id, ordered)