"""Hermetic coverage for the browser fixture's Cook writer.

The opt-in browser regression needs Chromium. This module drives the same
``outer_workflow.py`` entry point against direct finalized inputs, so the
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

import attrs
import pytest

from easy_cheese_schemas.contracts import PlannerDisposition, PlannerUncertainty, UncertaintyScope
from tests.python.test_mold_cook_producer import finalize_fixture, make_planner_result, make_spec


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
    result_path = cast(str, finalized.payload["result_path"])

    module = _load_outer_workflow()
    main = cast("Callable[[Sequence[str]], int]", module.main)
    exit_code = main([result_path, str(repository), str(artifact_root)])

    assert exit_code == 0
    produced = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert produced == {
        "feature": "index.html",
        "results": 1,
        "disposition": "passed",
        "whole_task_complete": True,
        "remainder": [],
    }
    document = repository / "index.html"
    assert document.is_file()
    assert "Feature executed" in document.read_text(encoding="utf-8")


def test_outer_workflow_preserves_partial_remainder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    remainder = (
        PlannerUncertainty(
            description="unselected parent work remains",
            scope=UncertaintyScope.OMITTED_WORK,
        ),
    )
    planner = attrs.evolve(
        make_planner_result(),
        disposition=PlannerDisposition.PARTIAL,
        unresolved_work=remainder,
    )
    finalized = finalize_fixture(repository, planner=planner)
    assert finalized.status == "ready"
    result_path = cast(str, finalized.payload["result_path"])
    module = _load_outer_workflow()
    main = cast("Callable[[Sequence[str]], int]", module.main)
    assert main([result_path, str(repository), str(repository / "artifacts")]) == 0
    produced = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert produced["disposition"] == "passed"
    assert produced["whole_task_complete"] is False
    assert produced["remainder"] == ["unselected parent work remains"]
    assert (repository / "index.html").is_file()
