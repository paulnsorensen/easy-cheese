"""Shared pytest config for pasteurize tests."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def bundle(skill_archive: Callable[[str], Path]) -> Path:
    """The built pasteurize archive (see scripts/skill_archives.py)."""
    return skill_archive("pasteurize")


@pytest.fixture(scope="session")
def debug_tag_sweep() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.pasteurize.debug_tag_sweep")


@pytest.fixture(scope="session")
def repro_rerun() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.pasteurize.repro_rerun")
