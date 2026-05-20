"""Shared pytest config.

The melt scripts use hyphenated filenames that can't be imported by the
normal `import` machinery, so we load them by path with importlib.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "melt" / "scripts"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def conflict_pick() -> ModuleType:
    return _load("conflict_pick", SCRIPTS_DIR / "conflict-pick.py")


@pytest.fixture(scope="session")
def conflict_summary() -> ModuleType:
    return _load("conflict_summary", SCRIPTS_DIR / "conflict-summary.py")


@pytest.fixture(scope="session")
def lockfile_resolve() -> ModuleType:
    return _load("lockfile_resolve", SCRIPTS_DIR / "lockfile-resolve.py")


@pytest.fixture(scope="session")
def batch_resolve() -> ModuleType:
    return _load("batch_resolve", SCRIPTS_DIR / "batch-resolve.py")


@pytest.fixture(scope="session")
def detect_squash_residue() -> ModuleType:
    return _load("detect_squash_residue", SCRIPTS_DIR / "detect-squash-residue.py")
