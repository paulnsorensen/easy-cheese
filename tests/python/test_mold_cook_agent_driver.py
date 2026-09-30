"""Bounded live-agent driver checks with a deterministic fixture agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest

from tests.python.mold_cook_agent_driver import AgentScenarioError, run_agent_scenario

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mold_cook_agent"
ROOT = Path(__file__).resolve().parents[2]
MOLD_ARCHIVE = ROOT / "skills" / "mold" / "scripts" / "mold.pyz"
COOK_ARCHIVE = ROOT / "skills" / "cook" / "scripts" / "cook.pyz"


def test_fixture_agent_uses_harness_responses_and_writes_trace(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "trace.json"
    report = run_agent_scenario(
        [sys.executable, str(FIXTURE / "task_agent.py")],
        fixture_repository=repository,
        mold_bundle=MOLD_ARCHIVE,
        cook_bundle=COOK_ARCHIVE,
        responses=FIXTURE / "responses.json",
        output=output,
    )
    trace = cast(dict[str, object], json.loads(output.read_text(encoding="utf-8")))
    events = cast(list[dict[str, object]], trace["events"])
    assert report.scenario == "fixture-agent"
    assert [event["type"] for event in events] == [
        "input_classified",
        "prepare",
        "approval_requested",
        "approval_recorded",
        "plan_materialized",
        "handoff_published",
        "consumer_accept",
    ]
    assert report.mode == "full"
    assert events[1]["outcome"] == "needs-planning"
    assert events[3]["response"] == "approved"
    assert events[3]["decision"] == "approved"
    assert events[4]["outcome"] == "ready"
    assert events[6]["ready"] is True
    assert [event["tool"] for event in events if "tool" in event] == [
        "scripts/cook.pyz prepare",
        "scripts/mold.pyz finalize",
        "scripts/cook.pyz accept",
    ]
    assert output.is_file()
    pointer = repository / "artifacts" / "pointers" / "agent.json"
    assert pointer.is_file()
    pointer_value = cast(
        dict[str, object], json.loads(pointer.read_text(encoding="utf-8"))
    )
    assert pointer_value["operation_id"] == "agent"
    assert pointer_value["destination_phase"] == "cook"


def test_supplied_refused_scope_response_holds_cook_and_writes_no_feature(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "trace.json"

    with pytest.raises(AgentScenarioError) as refusal:
        _ = run_agent_scenario(
            [sys.executable, str(FIXTURE / "task_agent.py")],
            fixture_repository=repository,
            mold_bundle=MOLD_ARCHIVE,
            cook_bundle=COOK_ARCHIVE,
            responses=FIXTURE / "responses-refusal.json",
            output=output,
        )

    # The agent exits 0 only when Cook holds the refused approval, so the
    # transcript check is the failure the driver reports.
    assert "recorded approval does not authorize execution" in str(refusal.value)
    assert not output.exists()
    assert not (repository / "artifacts" / "pointers").exists()
    assert not (repository / "src").exists()
