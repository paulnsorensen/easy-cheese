"""Shared pytest config for hard-cheese tests."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def bundle(skill_archive: Callable[[str], Path]) -> Path:
    """The built hard-cheese archive (see scripts/skill_archives.py)."""
    return skill_archive("hard-cheese")


@pytest.fixture(scope="session")
def append_attempt() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.append_attempt")


@pytest.fixture(scope="session")
def freshness_check() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.freshness_check")


@pytest.fixture(scope="session")
def rank_hunks() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.rank_hunks")
