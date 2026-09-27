"""Shared pytest config for hard-cheese tests."""

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
    """The built hard-cheese archive (see scripts/skill_archives.py)."""
    return cast(Callable[[str], Path], _skill_archives().archive_path)("hard-cheese")


@pytest.fixture(scope="session")
def append_attempt() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.append_attempt")


@pytest.fixture(scope="session")
def freshness_check() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.freshness_check")


@pytest.fixture(scope="session")
def rank_hunks() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.rank_hunks")
