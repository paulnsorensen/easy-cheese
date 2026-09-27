"""Pytest config for schema and packaged-validator conformance."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

import easy_cheese_schemas  # noqa: E402, F401  # pyright: ignore[reportUnusedImport]

Validator = Callable[[dict[str, object]], list[str]]


def _skill_archives() -> ModuleType:
    """Import skill_archives lazily so a break there cannot fail whole-suite collection."""
    entry = str(REPO_ROOT / "scripts")
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return importlib.import_module("skill_archives")


@pytest.fixture(scope="session")
def bundle() -> Path:
    """The built cook archive (see scripts/skill_archives.py)."""
    return cast(Callable[[str], Path], _skill_archives().archive_path)("cook")


@pytest.fixture(scope="session")
def run_manifest_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.validate_manifest")
    return cast(Validator, module.validate_run_manifest)


@pytest.fixture(scope="session")
def pr_plan_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.validate_pr_plan")
    return cast(Validator, module.validate_pr_plan)

