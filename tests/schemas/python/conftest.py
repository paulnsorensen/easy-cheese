"""Pytest config for the schema conformance suite (src/easy_cheese_schemas/).

v0.1 ships two live descriptions of the same four artifact contracts: the
hand-rolled validators in src/fanout/ and the attrs types in
src/easy_cheese_schemas/. This suite is the only thing standing between them
and silent drift, so it wires each side to the copy that actually matters:

* the validators come from the built ultracook .pyz, the artifact /ultracook
  runs (same pattern as tests/fanout/python/conftest.py);
* the attrs types come from src/, the source of truth the package publishes --
  imported here *before* the bundle joins sys.path, because the bundle vendors
  its own copy of easy_cheese_schemas and would otherwise shadow it.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# Import order is the contract: src/ and vendor/ are already on sys.path from
# the repo-root conftest, so this binds easy_cheese_schemas to src/ for the
# whole session.
import easy_cheese_schemas  # noqa: E402, F401

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

_BUNDLE = build_pyz.cached_bundle("ultracook")
sys.path.insert(0, str(_BUNDLE))

Validator = Callable[[dict[str, Any]], list[str]]


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def run_manifest_validator() -> Validator:
    return importlib.import_module("validate_manifest").validate_run_manifest


@pytest.fixture(scope="session")
def decomposition_validator() -> Validator:
    return importlib.import_module("validate_decomposition").validate_manifest


@pytest.fixture(scope="session")
def pr_plan_validator() -> Validator:
    return importlib.import_module("validate_pr_plan").validate_pr_plan


@pytest.fixture(scope="session")
def curd_block_validator() -> Validator:
    # curd_block was demoted to a direct src/ module: its dead ultracook
    # registration was pruned (spec pyz-pipeline-contracts), so the bundle no
    # longer stages it. Load it straight from source, isolated from sys.path.
    spec = importlib.util.spec_from_file_location(
        "curd_block_src", REPO_ROOT / "src" / "fanout" / "curd_block.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_curd_block
