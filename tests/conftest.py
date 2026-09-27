"""Fixtures every suite under tests/ shares."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from skill_archives import archive_path  # noqa: E402  (scripts/ is not a package)


@pytest.fixture(scope="session")
def skill_archive() -> Callable[[str], Path]:
    """Factory: the archive to execute for a skill (see scripts/skill_archives.py).

    The ``test`` recipe and CI build every archive once through the pinned
    wedge and export ``EASY_CHEESE_PREBUILT_PYZ`` so every suite reuses one
    build. A direct pytest run without the variable builds the set on first
    use, so coverage is unchanged.
    """
    return archive_path
