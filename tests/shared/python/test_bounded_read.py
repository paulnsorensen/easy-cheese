"""Direct tests for the one hardened bounded reader."""

from __future__ import annotations

from pathlib import Path

import pytest

from easy_cheese.shared.bounded_read import (
    BoundedReadOverflow,
    NotRegularFileError,
    read_bounded_file,
)


def test_a_regular_file_round_trips(tmp_path: Path) -> None:
    """Finding 60: the shared reader returns the exact bytes on disk."""

    path = tmp_path / "payload.bin"
    content = bytes(range(256)) * 400
    _ = path.write_bytes(content)

    assert read_bounded_file(path, limit=len(content)) == content
    assert read_bounded_file(path, limit=len(content) + 1) == content


def test_a_symlink_is_refused(tmp_path: Path) -> None:
    """Finding 60: a caller-supplied path cannot redirect the read."""

    target = tmp_path / "target.bin"
    _ = target.write_bytes(b"redirected")
    link = tmp_path / "link.bin"
    link.symlink_to(target)

    with pytest.raises(OSError) as error:
        _ = read_bounded_file(link, limit=64)

    assert not isinstance(error.value, (BoundedReadOverflow, NotRegularFileError))


def test_a_directory_is_refused(tmp_path: Path) -> None:
    """Finding 60: only a regular file is readable."""

    with pytest.raises(NotRegularFileError):
        _ = read_bounded_file(tmp_path, limit=64)


def test_an_oversized_file_raises_overflow(tmp_path: Path) -> None:
    """Finding 60: the cap is enforced against the declared size."""

    path = tmp_path / "oversized.bin"
    _ = path.write_bytes(b"x" * 65)

    with pytest.raises(BoundedReadOverflow) as error:
        _ = read_bounded_file(path, limit=64)

    assert error.value.path == path
    assert error.value.max_bytes == 64


def test_a_negative_limit_is_refused(tmp_path: Path) -> None:
    """Finding 60: a nonsense cap is a caller error, not a silent read."""

    path = tmp_path / "payload.bin"
    _ = path.write_bytes(b"payload")

    with pytest.raises(ValueError, match="non-negative"):
        _ = read_bounded_file(path, limit=-1)
