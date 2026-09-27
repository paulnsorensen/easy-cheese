"""Pytest config for schema and packaged-validator conformance."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

import easy_cheese_schemas  # noqa: E402, F401  # pyright: ignore[reportUnusedImport]

Validator = Callable[[dict[str, object]], list[str]]


@pytest.fixture(scope="session")
def bundle(skill_archive: Callable[[str], Path]) -> Path:
    """The built cook archive (see scripts/skill_archives.py)."""
    return skill_archive("cook")


@pytest.fixture(scope="session")
def run_manifest_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.validate_manifest")
    return cast(Validator, module.validate_run_manifest)


@pytest.fixture(scope="session")
def pr_plan_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.validate_pr_plan")
    return cast(Validator, module.validate_pr_plan)

