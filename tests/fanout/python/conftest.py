"""Shared pytest config for the fan-out engine tests (src/fanout/).

/ultracook drives the fan-out engine, so the engine modules are imported from
ultracook's built .pyz, and the CLI subprocess tests invoke that same bundle —
the suite verifies the bundled artifact.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
UC_DIR = REPO_ROOT / "skills" / "ultracook"
REFERENCES_DIR = UC_DIR / "references"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

_BUNDLE = build_pyz.cached_bundle("ultracook")
sys.path.insert(0, str(_BUNDLE))


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def validate_decomposition() -> ModuleType:
    return importlib.import_module("validate_decomposition")


@pytest.fixture(scope="session")
def validate_manifest() -> ModuleType:
    return importlib.import_module("validate_manifest")


@pytest.fixture(scope="session")
def validate_pr_plan() -> ModuleType:
    return importlib.import_module("validate_pr_plan")


@pytest.fixture(scope="session")
def curd() -> ModuleType:
    return importlib.import_module("curd")


@pytest.fixture(scope="session")
def wiring() -> ModuleType:
    return importlib.import_module("wiring")


@pytest.fixture(scope="session")
def wiring_topo_sort() -> ModuleType:
    return importlib.import_module("wiring_topo_sort")


@pytest.fixture(scope="session")
def manifest_update() -> ModuleType:
    return importlib.import_module("manifest_update")


@pytest.fixture(scope="session")
def mode() -> ModuleType:
    return importlib.import_module("mode")


@pytest.fixture(scope="session")
def worktree() -> ModuleType:
    return importlib.import_module("worktree")


@pytest.fixture(scope="session")
def milknado() -> ModuleType:
    return importlib.import_module("milknado")


@pytest.fixture(scope="session")
def phase_decision() -> ModuleType:
    return importlib.import_module("phase_decision")


@pytest.fixture(scope="session")
def uc_dir() -> Path:
    return UC_DIR


@pytest.fixture(scope="session")
def references_dir() -> Path:
    return REFERENCES_DIR


@pytest.fixture(scope="session")
def manifest_schema_path() -> Path:
    return REFERENCES_DIR / "manifest-schema.json"


@pytest.fixture(scope="session")
def pr_plan_schema_path() -> Path:
    return REFERENCES_DIR / "pr-plan-schema.json"
