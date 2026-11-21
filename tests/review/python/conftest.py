"""Fixtures for the easy-cheese-review package suites."""

from __future__ import annotations

import importlib
import shutil
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

from tests.review.python.support import WriteTree


@pytest.fixture(scope="session")
def severity() -> ModuleType:
    return importlib.import_module("easy_cheese_review.severity")


@pytest.fixture(scope="session")
def ast_grep_binary() -> str:
    """The ast-grep binary; the suites need it and fail without it."""
    binary = shutil.which("ast-grep")
    assert binary is not None, "ast-grep must be on PATH for the easy-cheese-review suites"
    return binary


@pytest.fixture
def write_tree() -> WriteTree:
    """Return a writer that creates `files` (path -> text) under a root."""

    def write(root: Path, files: Mapping[str, str]) -> Path:
        for relative, text in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _ = target.write_text(text, encoding="utf-8")
        return root

    return write
