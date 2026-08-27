"""Shared pytest config for hard-cheese tests."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_BUNDLE = REPO_ROOT / "skills" / "hard-cheese" / "scripts" / "hard-cheese.pyz"


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def append_attempt() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.append_attempt")


@pytest.fixture(scope="session")
def freshness_check() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.hard_cheese.freshness_check")
