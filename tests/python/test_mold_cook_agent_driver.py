"""Bounded live-agent driver checks with a deterministic fixture agent."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

from tests.python.mold_cook_agent_driver import run_agent_scenario

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "mold_cook_agent"
ROOT = Path(__file__).resolve().parents[2]
MOLD_PYZ = ROOT / "skills" / "mold" / "scripts" / "mold.pyz"
COOK_PYZ = ROOT / "skills" / "cook" / "scripts" / "cook.pyz"


def test_fixture_agent_uses_harness_responses_and_writes_trace(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    output = tmp_path / "trace.json"
    report = run_agent_scenario(
        [sys.executable, str(FIXTURE / "task_agent.py")],
        fixture_repository=repository,
        mold_bundle=MOLD_PYZ,
        cook_bundle=COOK_PYZ,
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
        "approval_requested",
        "approval_recorded",
        "handoff_published",
        "consumer_accept",
    ]
    assert report.mode == "full"
    assert events[1]["outcome"] == "needs-approval"
    assert events[1]["approval_kind"] == "scope"
    assert events[4]["outcome"] == "ready"
    assert events[8]["ready"] is True
    assert all(event.get("tool") or event["type"] not in {"prepare", "plan_materialized"} for event in events)
    assert output.is_file()
    pointer = repository / "artifacts" / "pointers" / "agent.json"
    assert pointer.is_file()
    pointer_value = cast(dict[str, object], json.loads(pointer.read_text(encoding="utf-8")))
    assert pointer_value["operation_id"] == "agent"
    assert pointer_value["destination_phase"] == "cook"
