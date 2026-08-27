"""Shared pytest config for the packaged fan-out runtime."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
UC_DIR = REPO_ROOT / "skills" / "ultracook"
REFERENCES_DIR = UC_DIR / "references"
_BUNDLE = REPO_ROOT / "skills" / "ultracook" / "scripts" / "ultracook.pyz"


@pytest.fixture(scope="session")
def bundle() -> Path:
    return _BUNDLE


@pytest.fixture(scope="session")
def validate_decomposition() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.validate_decomposition")


@pytest.fixture(scope="session")
def validate_manifest() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.validate_manifest")


@pytest.fixture(scope="session")
def validate_pr_plan() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.validate_pr_plan")


@pytest.fixture(scope="session")
def curd() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.curd")


@pytest.fixture(scope="session")
def wiring() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.wiring")


@pytest.fixture(scope="session")
def manifest_update() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.manifest_update")


@pytest.fixture(scope="session")
def mode() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.mode")


@pytest.fixture(scope="session")
def worktree() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.worktree")


@pytest.fixture(scope="session")
def milknado() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.milknado")


@pytest.fixture(scope="session")
def phase_decision() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.fanout.phase_decision")


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
