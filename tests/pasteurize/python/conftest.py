"""Shared pytest config for pasteurize tests."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _skill_archives() -> ModuleType:
    """Import skill_archives lazily so a break there cannot fail whole-suite collection."""
    entry = str(REPO_ROOT / "scripts")
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return importlib.import_module("skill_archives")


@pytest.fixture(scope="session")
def bundle() -> Path:
    """The built pasteurize archive (see scripts/skill_archives.py)."""
    return cast(Callable[[str], Path], _skill_archives().archive_path)("pasteurize")


@pytest.fixture(scope="session")
def debug_tag_sweep() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.pasteurize.debug_tag_sweep")


@pytest.fixture(scope="session")
def repro_rerun() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.pasteurize.repro_rerun")
