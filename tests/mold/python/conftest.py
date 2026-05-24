"""Shared pytest config for mold tests.

Modules are imported from mold's built .pyz, and the CLI subprocess tests
invoke that same bundle, so the suite verifies the bundled artifact.
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

_BUNDLE = build_pyz.cached_bundle("mold")
sys.path.insert(0, str(_BUNDLE))


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def agent_scope_diff() -> ModuleType:
    return importlib.import_module("agent_scope_diff")
