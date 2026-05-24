"""Shared pytest config for pasteurize tests.

Modules are imported from pasteurize's built .pyz, and the CLI subprocess
tests invoke that same bundle, so the suite verifies the bundled artifact.
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

_BUNDLE = build_pyz.cached_bundle("pasteurize")
sys.path.insert(0, str(_BUNDLE))


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def debug_tag_sweep() -> ModuleType:
    return importlib.import_module("debug_tag_sweep")


@pytest.fixture(scope="session")
def repro_rerun() -> ModuleType:
    return importlib.import_module("repro_rerun")
