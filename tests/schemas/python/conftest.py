"""Pytest config for schema and packaged-validator conformance."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

import easy_cheese_schemas  # noqa: E402, F401
_BUNDLE = REPO_ROOT / "skills" / "ultracook" / "scripts" / "ultracook.pyz"

Validator = Callable[[dict[str, Any]], list[str]]


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def run_manifest_validator() -> Validator:
    return importlib.import_module(
        "easy_cheese.shared.fanout.validate_manifest"
    ).validate_run_manifest


@pytest.fixture(scope="session")
def decomposition_validator() -> Validator:
    return importlib.import_module(
        "easy_cheese.shared.fanout.validate_decomposition"
    ).validate_manifest


@pytest.fixture(scope="session")
def pr_plan_validator() -> Validator:
    return importlib.import_module(
        "easy_cheese.shared.fanout.validate_pr_plan"
    ).validate_pr_plan


@pytest.fixture(scope="session")
def curd_block_validator() -> Validator:
    return importlib.import_module(
        "easy_cheese.shared.fanout.curd_block"
    ).validate_curd_block
