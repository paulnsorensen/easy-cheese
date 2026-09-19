"""Hermetic coverage for the browser fixture's Cook writer.

The opt-in browser regression needs Chromium. This module drives the same
``outer_workflow.py`` entry point against a real accepted handoff, so the
curd disposition the fixture produces stays verified without a browser.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

from tests.python.test_mold_cook_producer import finalize_fixture, make_spec


FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "mold_cook_browser"
    / "outer_workflow.py"
)


def _load_outer_workflow() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mold_cook_outer_workflow", FIXTURE)
    if spec is None or spec.loader is None:
        raise AssertionError(f"browser fixture is not importable: {FIXTURE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_outer_workflow_records_a_passed_curd(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The fixture must publish evidence, not a silently blocked curd."""
    repository = tmp_path / "repository"
    _ = repository.mkdir()
    spec = make_spec(repository)
    finalized = finalize_fixture(repository, spec_path=spec)
    assert finalized.status == "ready"
    artifact_root = repository / "artifacts"
    pointer = artifact_root / "pointers" / "operation-1.json"

    module = _load_outer_workflow()
    main = cast("Callable[[Sequence[str]], int]", module.main)
    exit_code = main([str(pointer), str(repository), str(artifact_root)])

    assert exit_code == 0
    produced = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert produced == {
        "feature": "index.html",
        "results": 1,
        "disposition": "passed",
    }
    document = repository / "index.html"
    assert document.is_file()
    assert "Feature executed" in document.read_text(encoding="utf-8")
