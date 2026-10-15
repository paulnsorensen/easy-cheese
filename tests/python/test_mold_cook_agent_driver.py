"""Bounded live-agent driver checks with a deterministic fixture agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest

from tests.python.mold_cook_agent_driver import (
    MAX_TRACE_BYTES,
    AgentScenarioError,
    _run_bounded,  # pyright: ignore[reportPrivateUsage]
    run_agent_scenario,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mold_cook_agent"
ROOT = Path(__file__).resolve().parents[2]
MOLD_ARCHIVE = ROOT / "skills" / "mold" / "scripts" / "mold.pyz"


def test_fixture_agent_reaches_ready_without_approval_and_writes_trace(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "trace.json"
    report = run_agent_scenario(
        [sys.executable, str(FIXTURE / "task_agent.py")],
        fixture_repository=repository,
        mold_bundle=MOLD_ARCHIVE,
        responses=FIXTURE / "responses.json",
        output=output,
    )
    trace = cast(dict[str, object], json.loads(output.read_text(encoding="utf-8")))
    events = cast(list[dict[str, object]], trace["events"])
    assert report.scenario == "fixture-agent"
    assert [event["type"] for event in events] == [
        "input_classified",
        "plan_materialized",
        "bound_inputs",
        "feature_write",
    ]
    assert events[1]["outcome"] == "complete"
    assert events[2]["ready"] is True
    assert events[3]["whole_task_complete"] is True
    assert events[3]["remainder"] == []
    assert [event["tool"] for event in events if "tool" in event] == [
        "scripts/mold.pyz finalize",
    ]
    assert output.is_file()
    result_path = repository / report.artifact_refs[0]
    assert result_path.is_file()
    finalized = cast(dict[str, object], json.loads(result_path.read_text(encoding="utf-8")))
    assert finalized["request_id"] == "request-1"
    assert (repository / "src" / "core.py").read_text(encoding="utf-8") == "FEATURE_READY = True\n"


def test_driver_rejects_oversized_agent_output(tmp_path: Path) -> None:
    with pytest.raises(AgentScenarioError, match="bounded size"):
        _ = _run_bounded(
            [sys.executable, "-c", f"print('x' * {MAX_TRACE_BYTES + 1})"],
            cwd=tmp_path, env={}, timeout=5,
        )


def test_driver_rejects_timed_out_agent(tmp_path: Path) -> None:
    with pytest.raises(AgentScenarioError, match="timeout"):
        _ = _run_bounded(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            cwd=tmp_path, env={}, timeout=0.1,
        )


def test_fixture_agent_preserves_partial_remainder(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "trace.json"
    report = run_agent_scenario(
        [sys.executable, str(FIXTURE / "task_agent.py"), "--partial"],
        fixture_repository=repository,
        mold_bundle=MOLD_ARCHIVE,
        responses=FIXTURE / "responses.json",
        output=output,
    )
    assert report.scenario == "fixture-agent"
    trace = cast(dict[str, object], json.loads(output.read_text(encoding="utf-8")))
    events = cast(list[dict[str, object]], trace["events"])
    assert events[-1] == {
        "type": "feature_write",
        "path": "src/core.py",
        "artifact_ref": report.artifact_refs[0],
        "whole_task_complete": False,
        "remainder": ["unselected parent work remains"],
    }
    assert (repository / "src" / "core.py").is_file()
