"""Shared pytest config for cheese-factory tests.

Loads the validate_decomposition script by path (it's a hyphen-free name
already, but we keep the loader pattern consistent with the wider repo).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CF_DIR = REPO_ROOT / "skills" / "cheese-factory"
SCRIPTS_DIR = CF_DIR / "scripts"
REFERENCES_DIR = CF_DIR / "references"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def validate_decomposition() -> ModuleType:
    return _load("validate_decomposition", SCRIPTS_DIR / "validate_decomposition.py")


@pytest.fixture(scope="session")
def validate_manifest() -> ModuleType:
    return _load("validate_manifest", SCRIPTS_DIR / "validate_manifest.py")


@pytest.fixture(scope="session")
def validate_pr_plan() -> ModuleType:
    return _load("validate_pr_plan", SCRIPTS_DIR / "validate_pr_plan.py")


@pytest.fixture(scope="session")
def cf_dir() -> Path:
    return CF_DIR


@pytest.fixture(scope="session")
def manifest_schema_path() -> Path:
    return REFERENCES_DIR / "manifest-schema.json"


@pytest.fixture(scope="session")
def skill_md_path() -> Path:
    return CF_DIR / "SKILL.md"
