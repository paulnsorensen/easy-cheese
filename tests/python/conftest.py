"""Shared pytest fixtures for canonical skill packages."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

PREBUILT_PYZ_ENV = "EASY_CHEESE_PREBUILT_PYZ"


def _skill_names() -> tuple[str, ...]:
    """Import build_pyz lazily so a break there cannot fail whole-suite collection."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import build_pyz

    return build_pyz.SKILLS


@pytest.fixture(scope="session")
def prebuilt_bundle_dir() -> Path | None:
    """Directory of pre-built `.pyz` bundles, or None to build fresh.

    The ``test`` recipe builds every bundle once and exports
    ``EASY_CHEESE_PREBUILT_PYZ`` so xdist workers reuse one build instead of
    each rebuilding the whole set. A direct pytest run without the variable
    builds fresh, so coverage is unchanged. This fixture lives in
    ``tests/python``; suites outside it still build their own bundles even
    while the variable is set.

    A present but unusable value is a configuration error, not a reason to
    rebuild silently: a typo would otherwise cost every worker a full build
    while the run still reported success.
    """
    value = os.environ.get(PREBUILT_PYZ_ENV)
    if not value:
        return None
    candidate = Path(value)
    hint = "rebuild the set, or unset the variable to build bundles fresh"
    if not candidate.is_dir():
        raise pytest.UsageError(
            f"{PREBUILT_PYZ_ENV}={value!r} is not a directory; {hint}"
        )
    missing = sorted(
        f"{skill}.pyz"
        for skill in _skill_names()
        if not (candidate / f"{skill}.pyz").is_file()
    )
    if missing:
        names = ", ".join(missing)
        raise pytest.UsageError(
            f"{PREBUILT_PYZ_ENV}={value!r} is missing bundles ({names}); {hint}"
        )
    return candidate


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
