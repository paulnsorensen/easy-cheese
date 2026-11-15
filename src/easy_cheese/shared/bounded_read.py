"""One hardened bounded reader for caller-supplied local paths.

Every host-side reader that opens a path a caller chose makes the same three
refusals: it must not follow a final symlink, it must not read anything but a
regular file, and it must not allocate past the caller's limit. This module
holds that sequence once. Callers translate its errors into their own domain
types.
"""

from __future__ import annotations

import contextlib
import os
import stat
from collections.abc import Callable
from pathlib import Path

__all__ = [
    "BoundedReadOverflow",
    "NotRegularFileError",
    "read_bounded_descriptor",
    "read_bounded_file",
    "read_bounded_stream",
]

_READ_CHUNK_BYTES = 64 * 1024

_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_BINARY", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_NOFOLLOW", 0)
)


class BoundedReadOverflow(OSError):
    """A bounded read hit a file larger than its caller-supplied cap."""

    path: Path
    max_bytes: int

    def __init__(self, path: Path, max_bytes: int) -> None:
        self.path = path
        self.max_bytes = max_bytes
        super().__init__(f"{path} exceeds {max_bytes} bytes")


class NotRegularFileError(OSError):
    """A bounded read refused a path that is not a regular file."""

    path: Path

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(f"{path} is not a regular file")


def read_bounded_file(path: Path, *, limit: int) -> bytes:
    """Read at most ``limit`` bytes of ``path`` without following a symlink.

    ``O_NOFOLLOW`` makes a final symlink raise ``OSError``, so a
    caller-supplied path cannot redirect the read to another file. A file
    larger than ``limit`` raises :class:`BoundedReadOverflow` before its
    contents are allocated, and a path that is not a regular file raises
    :class:`NotRegularFileError`. Every other open or read failure surfaces
    as the raw ``OSError``, so a caller keeps ``FileNotFoundError`` and its
    siblings.
    """

    fd = os.open(path, _OPEN_FLAGS)
    try:
        return read_bounded_descriptor(fd, path, limit=limit)
    finally:
        with contextlib.suppress(OSError):
            os.close(fd)


def read_bounded_descriptor(fd: int, path: Path, *, limit: int) -> bytes:
    """Read at most ``limit`` bytes of one already open descriptor.

    A caller that opened its own descriptor -- relative to a directory
    descriptor, for example -- keeps the same refusals as
    :func:`read_bounded_file`. ``path`` names the descriptor for the error
    text only; the checks are made on the descriptor. A descriptor that is
    not a regular file raises :class:`NotRegularFileError`, and a file
    larger than ``limit`` raises :class:`BoundedReadOverflow` before its
    contents are allocated.
    """

    if limit < 0:
        raise ValueError("limit must be a non-negative integer")
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode):
        raise NotRegularFileError(path)
    if metadata.st_size > limit:
        raise BoundedReadOverflow(path, limit)
    return read_bounded_stream(lambda amount: os.read(fd, amount), path, limit=limit)


def read_bounded_stream(
    reader: Callable[[int], bytes], path: Path, *, limit: int
) -> bytes:
    """Read at most ``limit`` bytes from ``reader``, one bounded chunk at a time.

    This is the chunked loop the file and descriptor readers share, exposed
    for a caller whose source has no descriptor -- an HTTPS response body,
    for example. ``reader`` is asked for no more than one byte past the cap,
    so a source that overruns raises :class:`BoundedReadOverflow` instead of
    allocating without bound. ``path`` names the source for the error text.
    """

    if limit < 0:
        raise ValueError("limit must be a non-negative integer")
    content = bytearray()
    while True:
        chunk = reader(min(_READ_CHUNK_BYTES, limit - len(content) + 1))
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > limit:
            raise BoundedReadOverflow(path, limit)
    return bytes(content)
