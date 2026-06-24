"""Shared pytest config for cheese-factory tests.

Validators are imported from cheese-factory's built .pyz, and the CLI subprocess
tests invoke that same bundle, so the suite verifies the bundled artifact.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CF_DIR = REPO_ROOT / "skills" / "cheese-factory"
REFERENCES_DIR = CF_DIR / "references"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import build_pyz  # noqa: E402

_BUNDLE = build_pyz.cached_bundle("cheese-factory")
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
def cf_dir() -> Path:
    return CF_DIR


@pytest.fixture(scope="session")
def manifest_schema_path() -> Path:
    return REFERENCES_DIR / "manifest-schema.json"


@pytest.fixture(scope="session")
def pr_plan_schema_path() -> Path:
    return REFERENCES_DIR / "pr-plan-schema.json"


@pytest.fixture(scope="session")
def skill_md_path() -> Path:
    return CF_DIR / "SKILL.md"


@pytest.fixture(scope="session")
def skill_corpus(skill_md_path: Path) -> str:
    """SKILL.md plus every references/*.md doc — the skill's full authored surface.

    Load-bearing contract phrases may live in the SKILL body or in a reference
    file (progressive disclosure). String-shaped checks read the whole corpus so
    a phrase that was *relocated* into a reference still counts as present, while
    a genuinely *removed* phrase is still caught.
    """
    parts = [skill_md_path.read_text(encoding="utf-8")]
    for ref in sorted(REFERENCES_DIR.glob("*.md")):
        parts.append(ref.read_text(encoding="utf-8"))
    return "\n".join(parts)
