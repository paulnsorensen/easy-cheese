"""Shared pytest config for pasteurize tests."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_BUNDLE = REPO_ROOT / "skills" / "pasteurize" / "scripts" / "pasteurize.pyz"


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def debug_tag_sweep() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.pasteurize.debug_tag_sweep")


@pytest.fixture(scope="session")
def repro_rerun() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.pasteurize.repro_rerun")
