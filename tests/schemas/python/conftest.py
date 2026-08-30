"""Pytest config for schema and packaged-validator conformance."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

import easy_cheese_schemas  # noqa: E402, F401  # pyright: ignore[reportUnusedImport]
_BUNDLE = REPO_ROOT / "skills" / "cook" / "scripts" / "cook.pyz"

Validator = Callable[[dict[str, object]], list[str]]


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def run_manifest_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.validate_manifest")
    return cast(Validator, module.validate_run_manifest)


@pytest.fixture(scope="session")
def decomposition_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.validate_decomposition")
    return cast(Validator, module.validate_manifest)


@pytest.fixture(scope="session")
def pr_plan_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.validate_pr_plan")
    return cast(Validator, module.validate_pr_plan)


@pytest.fixture(scope="session")
def curd_block_validator() -> Validator:
    module = importlib.import_module("easy_cheese.shared.fanout.curd_block")
    return cast(Validator, module.validate_curd_block)
