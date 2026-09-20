"""Cross-platform advisory locks for local state transactions."""
from __future__ import annotations

import contextlib
from contextlib import contextmanager
import os
from collections.abc import Generator
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - exercised only on POSIX
    msvcrt = None


def _lock(fd: int, *, exclusive: bool) -> None:
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX if exclusive else fcntl.LOCK_UN)
    else:  # pragma: no cover - Windows only
        assert msvcrt is not None
        msvcrt.locking(fd, msvcrt.LK_LOCK if exclusive else msvcrt.LK_UNLCK, 1)


@contextmanager
def advisory_lock(path: Path) -> Generator[None, None, None]:
    """Hold an exclusive private advisory lock until the context exits."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        _lock(fd, exclusive=True)
        yield
    finally:
        try:
            _lock(fd, exclusive=False)
        finally:
            with contextlib.suppress(OSError):
                os.close(fd)
