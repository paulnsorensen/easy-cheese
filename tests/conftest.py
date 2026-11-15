"""Fixtures every suite under tests/ shares."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def skill_archive() -> Callable[[str], Path]:
    """Return the built archive path for a skill (`just wedge-build`)."""
    return lambda skill: ROOT / "skills" / skill / "scripts" / f"{skill}.pyz"
