"""Behavioral coverage for Mold's command entrypoints."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.skills.mold import commands
from easy_cheese_schemas.contracts import (
    AgentWriterView,
    BoundedScope,
    CriterionWriterView,
    CurdPlanWriterView,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResultWriterView,
    SemanticCurdWriterView,
    WriterViewKind,
    canonical_bytes,
)
from easy_cheese_schemas.schema_runtime import supported_version_for


def _planner_request() -> PlannerRequest:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    return cast(Callable[..., PlannerRequest], PlannerRequest)(
        contract_version=version,
        request_id="command-normalization-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Materialize the command planner result",
    )


def _planner_writer() -> AgentWriterView:
    writer = cast(Callable[..., PlannerResultWriterView], PlannerResultWriterView)(
        disposition=PlannerDisposition.COMPLETE,
        plan=cast(Callable[..., CurdPlanWriterView], CurdPlanWriterView)(
            objective="Materialize the command planner result",
            curds=[
                cast(Callable[..., SemanticCurdWriterView], SemanticCurdWriterView)(
                    key="command",
                    outcome="Materialized planner output",
                    scope=cast(Callable[..., BoundedScope], BoundedScope)(
                        paths=["src/command.py"]
                    ),
                    outputs=["A canonical planner result"],
                    criteria=[
                        cast(Callable[..., CriterionWriterView], CriterionWriterView)(
                            description="The planner result has canonical identity",
                            check="pytest tests/python/test_mold_commands.py",
                        )
                    ],
                )
            ],
        ),
    )
    return cast(Callable[..., AgentWriterView], AgentWriterView)(
        kind=WriterViewKind.PLANNER_RESULT,
        payload=writer,
    )


def _write_json(path: Path, value: object) -> None:
    _ = path.write_bytes(canonical_bytes(value))


def test_normalize_planner_entrypoint_materializes_canonical_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    writer_path = tmp_path / "writer.json"
    request_path = tmp_path / "request.json"
    invocation_path = tmp_path / "invocation.json"
    _write_json(writer_path, _planner_writer())
    _write_json(request_path, _planner_request())
    _write_json(
        invocation_path,
        {"planner": {"plan_id": "command-plan-1", "curd_ids": {"command": "command-curd-1"}}},
    )

    exit_code = commands.main(
        [
            "normalize-planner",
            str(writer_path),
            "--request",
            str(request_path),
            "--invocation",
            str(invocation_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    output = cast(dict[str, object], json.loads(captured.out))
    plan = cast(dict[str, object], output["plan"])
    assert plan["plan_id"] == "command-plan-1"
    assert cast(list[dict[str, object]], plan["curds"])[0]["curd_id"] == "command-curd-1"


def test_finalize_entrypoint_saves_invalid_taste_as_not_ready(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "spec_format" / "valid_spec.md"
    spec_path = tmp_path / "spec.md"
    _ = spec_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    approval_path = tmp_path / "approval.json"
    taste_path = tmp_path / "taste.json"
    _ = approval_path.write_text("{}", encoding="utf-8")
    _ = taste_path.write_text(json.dumps({"not": "a taste verdict"}), encoding="utf-8")

    exit_code = commands.main(
        [
            "finalize",
            str(spec_path),
            "--approval",
            str(approval_path),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--operation-id",
            "invalid-taste",
            "--request-id",
            "invalid-taste-request",
            "--taste-result",
            str(taste_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.err == ""
    output = cast(dict[str, object], json.loads(captured.out))
    assert output["status"] == "saved-not-ready"
    requirements = cast(list[dict[str, object]], output["requirements"])
    assert any(
        item["requirement_id"] == "taste-verdict"
        and "taste verdict is invalid" in cast(str, item["description"])
        for item in requirements
    )
