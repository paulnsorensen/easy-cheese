"""Assert schema conformance exercises canonical packaged sources."""

from __future__ import annotations

import importlib
import importlib.metadata
import re
from pathlib import Path

import easy_cheese_schemas

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_schema_types_come_from_src() -> None:
    assert easy_cheese_schemas.__file__ is not None
    assert Path(easy_cheese_schemas.__file__).is_relative_to(REPO_ROOT / "src")


def test_validators_come_from_canonical_packages() -> None:
    for name in (
        "validate_manifest",
        "validate_decomposition",
        "validate_pr_plan",
        "curd_block",
    ):
        module = importlib.import_module(f"easy_cheese.shared.fanout.{name}")
        assert module.__file__ is not None
        assert Path(module.__file__).is_relative_to(REPO_ROOT / "src/easy_cheese")


def test_runtime_dependencies_match_the_hash_lock() -> None:
    lock = (REPO_ROOT / "requirements/runtime.txt").read_text()
    pins = dict(re.findall(r"^([A-Za-z_]+)==([^ ]+)", lock, re.MULTILINE))
    assert importlib.metadata.version("attrs") == pins["attrs"]
    assert importlib.metadata.version("cattrs") == pins["cattrs"]
