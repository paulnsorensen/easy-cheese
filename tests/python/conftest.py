"""Shared pytest config.

The melt, mold, and affinage script tests import their modules from each skill's
built .pyz, verifying the bundled artifacts. Every bundle carries only its own
skill's scripts plus the shared modules that skill imports.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

for _skill in ("melt", "mold", "affinage"):
    sys.path.insert(0, str(build_pyz.cached_bundle(_skill)))


@pytest.fixture(scope="session")
def conflict_pick() -> ModuleType:
    return importlib.import_module("conflict_pick")


@pytest.fixture(scope="session")
def conflict_summary() -> ModuleType:
    return importlib.import_module("conflict_summary")


@pytest.fixture(scope="session")
def lockfile_resolve() -> ModuleType:
    return importlib.import_module("lockfile_resolve")


@pytest.fixture(scope="session")
def batch_resolve() -> ModuleType:
    return importlib.import_module("batch_resolve")


@pytest.fixture(scope="session")
def detect_squash_residue() -> ModuleType:
    return importlib.import_module("detect_squash_residue")


@pytest.fixture(scope="session")
def curd_count() -> ModuleType:
    return importlib.import_module("curd_count")


@pytest.fixture(scope="session")
def gate_graph() -> ModuleType:
    return importlib.import_module("gate_graph")


@pytest.fixture(scope="session")
def pr_status() -> ModuleType:
    return importlib.import_module("pr_status")


@pytest.fixture(scope="session")
def post_reply() -> ModuleType:
    return importlib.import_module("post_reply")
