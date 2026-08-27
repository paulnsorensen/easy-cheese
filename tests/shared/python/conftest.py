"""Pytest fixtures for the canonical shared runtime package."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest

@pytest.fixture(scope="session")
def git_utils() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.git_utils")


@pytest.fixture(scope="session")
def manifest_io() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.manifest_io")


@pytest.fixture(scope="session")
def schema() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.schema")


@pytest.fixture(scope="session")
def paths() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.paths")


@pytest.fixture(scope="session")
def severity() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.severity")


@pytest.fixture(scope="session")
def cli() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.cli")


@pytest.fixture(scope="session")
def handoff() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.handoff")


@pytest.fixture(scope="session")
def findings() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.findings")


@pytest.fixture(scope="session")
def gates() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.gates")


@pytest.fixture(scope="session")
def slugify_mod() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.slugify")


@pytest.fixture(scope="session")
def handoff_cli_mod() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.handoff_cli")


@pytest.fixture(scope="session")
def paths_cli_mod() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.paths_cli")


@pytest.fixture(scope="session")
def hallouminate_setup() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.hallouminate_setup")
