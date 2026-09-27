"""Shared pytest fixtures for canonical skill packages."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]



def _skill_archives() -> ModuleType:
    """Import skill_archives lazily so a break there cannot fail whole-suite collection."""
    entry = str(REPO_ROOT / "scripts")
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return importlib.import_module("skill_archives")


@pytest.fixture(scope="session")
def skill_archive() -> Callable[[str], Path]:
    """Factory: the archive to execute for a skill (see scripts/skill_archives.py).

    The ``test`` recipe and CI build every archive once through the pinned
    wedge and export ``EASY_CHEESE_PREBUILT_PYZ`` so every suite reuses one
    build. A direct pytest run without the variable builds each archive on
    first use, so coverage is unchanged.
    """
    return cast(Callable[[str], Path], getattr(_skill_archives(), "archive_path"))


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
