"""Family-atomic filesystem rewrite transactions."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TransactionResult:
    family_id: str
    applied_paths: tuple[Path, ...]


def _replace(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        if os.path.exists(temporary):
            os.unlink(temporary)
        raise


def apply_family(
    family_id: str,
    changes: Mapping[Path, bytes],
    gate: Callable[[], bool],
) -> TransactionResult:
    """Apply all family members and restore every snapshot on any failure."""
    if not family_id or not changes:
        raise ValueError("family id and changes are required")
    ordered = tuple(sorted((Path(path) for path in changes), key=lambda path: path.as_posix()))
    if len(set(ordered)) != len(ordered):
        raise ValueError("family changes contain duplicate paths")
    snapshots = {path: path.read_bytes() if path.exists() else None for path in ordered}
    try:
        for path in ordered:
            _replace(path, changes[path])
        if not gate():
            raise RuntimeError(f"family gate failed: {family_id}")
    except BaseException:
        for path in ordered:
            previous = snapshots[path]
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                _replace(path, previous)
        raise
    return TransactionResult(family_id, ordered)
