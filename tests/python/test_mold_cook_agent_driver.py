"""Bounded live-agent driver checks with a deterministic fixture agent."""

from __future__ import annotations

import json
import os
import subprocess
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
        "prepare",
        "prepare",
        "approval_requested",
        "approval_recorded",
        "plan_materialized",
        "handoff_published",
        "consumer_accept",
    ]
    assert report.mode == "full"
    assert events[1]["outcome"] == "needs-approval"
    assert events[1]["approval_kind"] == "scope"
    assert events[3]["decision"] == "approved"
    assert events[4]["outcome"] == "needs-planning"
    assert events[5]["outcome"] == "needs-approval"
    assert events[8]["outcome"] == "ready"
    assert events[10]["ready"] is True
    assert all(
        event.get("tool") or event["type"] not in {"prepare", "plan_materialized"}
        for event in events
    )
    assert output.is_file()
    pointer = repository / "artifacts" / "pointers" / "agent.json"
    assert pointer.is_file()
    pointer_value = cast(dict[str, object], json.loads(pointer.read_text(encoding="utf-8")))
    assert pointer_value["operation_id"] == "agent"
    assert pointer_value["destination_phase"] == "cook"


def test_fixture_agent_scope_decline_stops_before_publication_and_acceptance(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    responses = tmp_path / "responses.json"
    _ = responses.write_text(
        json.dumps({"scope": "declined", "plan": "approved"}), encoding="utf-8"
    )
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(Path.home())),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "MOLD_COOK_FIXTURE_REPOSITORY": str(repository),
        "MOLD_COOK_MOLD_BUNDLE": str(MOLD_PYZ.resolve()),
        "MOLD_COOK_COOK_BUNDLE": str(COOK_PYZ.resolve()),
        "MOLD_COOK_TEST_ROOT": str(ROOT),
        "MOLD_COOK_HARNESS_RESPONSES": responses.read_text(encoding="utf-8"),
    }
    result = subprocess.run(
        [sys.executable, str(FIXTURE / "task_agent.py")],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode != 0
    trace = cast(dict[str, object], json.loads(result.stdout))
    events = cast(list[dict[str, object]], trace["events"])
    assert events[3]["decision"] == "rejected"
    assert events[4]["outcome"] != "ready"
    pointer = repository / "artifacts" / "pointers" / "agent.json"
    assert not pointer.exists()
    accepted = subprocess.run(
        [
            sys.executable,
            str(COOK_PYZ),
            "accept",
            str(pointer),
            "--artifact-root",
            str(repository / "artifacts"),
        ],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert accepted.returncode != 0
