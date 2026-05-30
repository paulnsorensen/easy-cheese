"""Pytest config for the shared/scripts library, tested from source.

These modules are the shared library. Each is vendored into a per-skill bundle
only where that skill imports it, so several (severity, paths) are used only by
skills not bundled here. The library itself is the unit under test, so it is
loaded from source rather than from any one skill's bundle.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "shared" / "scripts"))


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
def severity() -> ModuleType:
    return importlib.import_module("severity")
