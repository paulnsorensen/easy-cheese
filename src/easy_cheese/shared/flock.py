"""Cross-platform advisory file locking (fcntl on POSIX, msvcrt on Windows).

Shared by scripts that serialise concurrent read-modify-write cycles on a
file (e.g. hard-cheese's attempt log, ultracook's fan-out manifest) via a
lock sidecar.
"""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

try:
    import fcntl  # POSIX advisory file locks
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None

try:
    import msvcrt  # Windows advisory file locks
except ImportError:  # pragma: no cover - exercised only on POSIX
    msvcrt = None


def lock(fd: int, *, exclusive: bool) -> None:
    """Acquire (exclusive=True) or release an advisory lock on fd, cross-platform."""
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_UN)
    else:  # pragma: no cover - Windows only
        assert msvcrt is not None
        msvcrt.locking(fd, msvcrt.LK_LOCK if exclusive else msvcrt.LK_UNLCK, 1)


def with_flock(lock_path: Path, fn: Callable[[], None]) -> None:
    """Run fn() while holding an exclusive advisory lock on lock_path.

    Uses POSIX ``fcntl.flock`` where available and falls back to
    ``msvcrt.locking`` on Windows so the concurrency guard is not silently lost.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # O_CREAT so concurrent processes share the same lockfile inode. 0o600
    # so the lockfile is not world-readable (CodeQL py/overly-permissive-file).
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        lock(fd, exclusive=True)
        fn()
    finally:
        try:
            lock(fd, exclusive=False)
        finally:
            os.close(fd)
