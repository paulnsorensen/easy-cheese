"""Shared pytest config for wheypoint tests.

The ``lint`` module is imported from wheypoint's built .pyz (not from src/), so
the suite verifies the same bundled artifact the skill ships and CI diffs.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

_BUNDLE = build_pyz.cached_bundle("wheypoint")
sys.path.insert(0, str(_BUNDLE))


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def lint() -> ModuleType:
    return importlib.import_module("lint")
