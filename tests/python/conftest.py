"""Shared pytest fixtures for canonical skill packages."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def prebuilt_bundle_dir() -> Path | None:
    """Directory of pre-built `.pyz` bundles, or None to build fresh.

    The ``test`` recipe builds every bundle once and exports
    ``EASY_CHEESE_PREBUILT_PYZ`` so xdist workers reuse one build instead of
    each rebuilding the whole set. A direct pytest run without the variable
    builds fresh, so coverage is unchanged.
    """
    value = os.environ.get("EASY_CHEESE_PREBUILT_PYZ")
    if not value:
        return None
    candidate = Path(value)
    return candidate if candidate.is_dir() else None


@pytest.fixture(scope="session")
def conflict_pick() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.melt.conflict_pick")


@pytest.fixture(scope="session")
def conflict_summary() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.melt.conflict_summary")


@pytest.fixture(scope="session")
def lockfile_resolve() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.melt.lockfile_resolve")


@pytest.fixture(scope="session")
def batch_resolve() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.melt.batch_resolve")


@pytest.fixture(scope="session")
def detect_squash_residue() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.melt.detect_squash_residue")


@pytest.fixture(scope="session")
def curd_count() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.mold.curd_count")


@pytest.fixture(scope="session")
def gate_graph() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.mold.gate_graph")


@pytest.fixture(scope="session")
def pr_status() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.affinage.pr_status")


@pytest.fixture(scope="session")
def post_reply() -> ModuleType:
    return importlib.import_module("easy_cheese.skills.affinage.post_reply")
