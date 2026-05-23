"""Pytest config for the shared/scripts library, exercised through the bundle.

Modules are imported from the freshly-built easy-cheese.pyz (not the source tree)
so the tests verify the bundled artifact. import_module registers each module in
sys.modules before its body runs, so @dataclass resolves cls.__module__ natively.
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

sys.path.insert(0, str(build_pyz.cached_bundle()))


@pytest.fixture(scope="session")
def git_utils() -> ModuleType:
    return importlib.import_module("git_utils")


@pytest.fixture(scope="session")
def manifest_io() -> ModuleType:
    return importlib.import_module("manifest_io")


@pytest.fixture(scope="session")
def schema() -> ModuleType:
    return importlib.import_module("schema")


@pytest.fixture(scope="session")
def paths() -> ModuleType:
    return importlib.import_module("paths")


@pytest.fixture(scope="session")
def handoff() -> ModuleType:
    return importlib.import_module("handoff")


@pytest.fixture(scope="session")
def findings() -> ModuleType:
    return importlib.import_module("findings")


@pytest.fixture(scope="session")
def gates() -> ModuleType:
    return importlib.import_module("gates")


@pytest.fixture(scope="session")
def severity() -> ModuleType:
    return importlib.import_module("severity")
