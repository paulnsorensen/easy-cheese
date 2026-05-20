"""Pytest config for the shared/scripts library.

These modules live under repo-root/shared/scripts and are loaded by path so
the tests don't depend on the surrounding skill directories. The pattern
mirrors tests/python/conftest.py and tests/cheese-factory/python/conftest.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"

if str(SHARED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SHARED_SCRIPTS))


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    # Register in sys.modules so @dataclass can resolve cls.__module__ during
    # class body execution. Without this, dataclasses raises AttributeError
    # on sys.modules.get(cls.__module__).__dict__.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def git_utils() -> ModuleType:
    return _load("git_utils", SHARED_SCRIPTS / "git_utils.py")


@pytest.fixture(scope="session")
def manifest_io() -> ModuleType:
    return _load("manifest_io", SHARED_SCRIPTS / "manifest_io.py")


@pytest.fixture(scope="session")
def schema() -> ModuleType:
    return _load("schema", SHARED_SCRIPTS / "schema.py")


@pytest.fixture(scope="session")
def paths() -> ModuleType:
    return _load("paths", SHARED_SCRIPTS / "paths.py")


@pytest.fixture(scope="session")
def handoff() -> ModuleType:
    return _load("handoff", SHARED_SCRIPTS / "handoff.py")


@pytest.fixture(scope="session")
def findings() -> ModuleType:
    return _load("findings", SHARED_SCRIPTS / "findings.py")


@pytest.fixture(scope="session")
def gates() -> ModuleType:
    return _load("gates", SHARED_SCRIPTS / "gates.py")
