from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas.contracts import (
    MAX_CONTRACT_BYTES,
    MAX_CONTRACT_DEPTH,
    AgentWriterView,
    PlannerRequest,
    WriterViewKind,
)
from easy_cheese_schemas import schema_runtime
from easy_cheese_schemas.schema_runtime import (
    ContractValidationError,
    load_agent_writer_view,
    normalize_agent_output,
    supported_version_for,
    validate_contract,
)

ROOT = Path(__file__).resolve().parents[3]


def writer_cases() -> list[tuple[str, dict[str, object]]]:
    return [
        (
            "curd_plan",
            {
                "objective": "Ship the change",
                "curds": [
                    {
                        "key": "core",
                        "outcome": "Update the runtime",
                        "scope": {"paths": ["src/runtime.py"]},
                        "outputs": ["Validated output"],
                        "criteria": [
                            {"description": "Check output", "check": "pytest"}
                        ],
                    }
                ],
            },
        ),
        ("planner_result", {"disposition": "no_work", "reason": "No work remains"}),
        ("review_result", {"disposition": "clean", "findings": []}),
        (
            "diagnosis_result",
            {
                "disposition": "invalid",
                "reproduction": {"status": "not_reproduced", "steps": ["Run check"]},
                "hypotheses": [],
                "reason": "Input is invalid",
            },
        ),
        (
            "curd_result",
            {
                "criterion_results": [
                    {
                        "criterion_id": "criterion-1",
                        "disposition": "skipped",
                        "reason": "Not applicable",
                    }
                ]
            },
        ),
    ]


@pytest.mark.parametrize(("kind", "payload"), writer_cases())
def test_writer_kind_selects_relevant_payload_error(
    kind: str, payload: dict[str, object]
) -> None:
    valid = load_agent_writer_view({"kind": kind, "payload": payload})
    assert valid.kind is WriterViewKind(kind)

    invalid = dict(payload, unexpected_field=True)
    with pytest.raises(
        ContractValidationError,
        match=r"^\$\.payload contains unknown fields: unexpected_field$",
    ):
        _ = load_agent_writer_view({"kind": kind, "payload": invalid})


@pytest.mark.parametrize(
    ("kind", "payload", "fragment"),
    [
        ("curd_plan", {"objective": "", "curds": []}, "objective"),
        ("planner_result", {"disposition": "complete"}, "must carry a plan"),
        (
            "review_result",
            {"disposition": "findings", "findings": []},
            "at least one finding",
        ),
        (
            "diagnosis_result",
            {
                "disposition": "invalid",
                "reproduction": {"status": "not_reproduced", "steps": ["Run check"]},
                "hypotheses": [],
            },
            "must include a reason",
        ),
        (
            "curd_result",
            {
                "criterion_results": [
                    {"criterion_id": "criterion-1", "disposition": "skipped"}
                ]
            },
            "must include a reason",
        ),
    ],
)
def test_writer_kind_rejects_invalid_semantics(
    kind: str, payload: dict[str, object], fragment: str
) -> None:
    with pytest.raises(ContractValidationError) as caught:
        _ = load_agent_writer_view({"kind": kind, "payload": payload})
    message = str(caught.value)
    assert fragment in message
    assert "does not match any allowed shape" not in message


def test_planner_reason_error_does_not_report_other_payload_shapes() -> None:
    with pytest.raises(ContractValidationError) as caught:
        _ = load_agent_writer_view(
            {
                "kind": "planner_result",
                "payload": {
                    "disposition": "complete",
                    "plan": writer_cases()[0][1],
                    "reason": "Unneeded",
                },
            }
        )
    message = str(caught.value)
    assert "complete planner writer view must not include a reason" in message
    assert "does not match any allowed shape" not in message
    assert "curd_plan" not in message


def test_validate_contract_selects_writer_payload_error() -> None:
    with pytest.raises(ContractValidationError) as caught:
        _ = validate_contract(
            {"kind": "planner_result", "payload": {"disposition": "complete"}},
            AgentWriterView,
        )
    assert (
        str(caught.value)
        == "$.payload is invalid: complete planner writer view must carry a plan"
    )


@pytest.mark.parametrize("kind", ["curd_plan", "planner_result"])
def test_malformed_scope_paths_reports_selected_array_path(kind: str) -> None:
    plan = dict(writer_cases()[0][1])
    curd = dict(cast(list[dict[str, object]], plan["curds"])[0])
    curd["scope"] = {"paths": "src/runtime.py"}
    plan["curds"] = [curd]
    payload = plan if kind == "curd_plan" else {"disposition": "complete", "plan": plan}

    with pytest.raises(ContractValidationError) as caught:
        _ = load_agent_writer_view({"kind": kind, "payload": payload})
    message = str(caught.value)
    path = "$.payload" if kind == "curd_plan" else "$.payload.plan"
    assert f"{path}.curds[0].scope.paths must be an array" in message
    assert "unknown fields" not in message
    assert "$.payload does not match any allowed shape" not in message
    if kind == "planner_result":
        assert "$.payload.plan does not match any allowed shape" in message
        assert "$.payload.plan must be null" in message


def test_writer_envelope_errors_and_budgets_still_reject() -> None:
    valid: dict[str, object] = {
        "kind": "review_result",
        "payload": {"disposition": "clean", "findings": []},
    }
    cases: list[tuple[object, str]] = [
        ({**valid, "extra": True}, "$ contains unknown fields: extra"),
        ({"payload": valid["payload"]}, "$.kind is required"),
        ({"kind": "review_result"}, "$.payload is required"),
        ({"kind": "not_a_kind", "payload": valid["payload"]}, "$.kind must be one of"),
        (
            {"kind": "planner_result", "payload": valid["payload"]},
            "planner_result writer view payload must be",
        ),
        (
            '{"kind":"review_result","kind":"review_result","payload":{}}',
            "duplicate field 'kind'",
        ),
        ("{", "invalid JSON"),
        ("x" * (MAX_CONTRACT_BYTES + 1), "MAX_CONTRACT_BYTES"),
    ]
    for raw, fragment in cases:
        with pytest.raises(ContractValidationError) as caught:
            _ = load_agent_writer_view(raw)
        assert fragment in str(caught.value)

    deep: object = None
    for _ in range(MAX_CONTRACT_DEPTH + 1):
        deep = [deep]
    with pytest.raises(ContractValidationError, match="MAX_CONTRACT_DEPTH"):
        _ = load_agent_writer_view({"kind": "review_result", "payload": deep})


def test_selection_does_not_depend_on_union_message_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reworded(_self: object) -> str:
        return "reworded union failure"

    monkeypatch.setattr(
        schema_runtime._UnionMatchError,  # pyright: ignore[reportPrivateUsage]
        "__str__",
        reworded,
    )
    payload = dict(writer_cases()[2][1], unexpected_field=True)
    with pytest.raises(
        ContractValidationError,
        match=r"^\$\.payload contains unknown fields: unexpected_field$",
    ):
        _ = load_agent_writer_view({"kind": "review_result", "payload": payload})


def test_normalizer_uses_selected_payload_error() -> None:
    with pytest.raises(ContractValidationError) as caught:
        _ = normalize_agent_output(
            {"kind": "planner_result", "payload": {"disposition": "complete"}},
            {},
        )
    assert (
        str(caught.value)
        == "$.payload is invalid: complete planner writer view must carry a plan"
    )


def test_normalizer_preserves_host_owned_field_rejection() -> None:
    with pytest.raises(ContractValidationError, match="host-owned field"):
        _ = normalize_agent_output(
            {"kind": "curd_plan", "payload": {"plan_id": "agent"}},
            {},
        )


def test_mold_archive_reports_planner_reason_error(tmp_path: Path) -> None:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    request: dict[str, object] = {
        "contract_version": {
            "schema_uri": version.schema_uri,
            "major": version.major,
            "minor": version.minor,
        },
        "request_id": "diagnostic-request",
        "kind": "decompose",
        "objective": "Check writer diagnostics",
    }
    writer: dict[str, object] = {
        "kind": "planner_result",
        "payload": {
            "disposition": "complete",
            "plan": writer_cases()[0][1],
            "reason": "Unneeded",
        },
    }
    invocation: dict[str, object] = {"plan_id": "diagnostic-plan", "curd_ids": {}}
    for name, payload in (
        ("request", request),
        ("writer", writer),
        ("invocation", invocation),
    ):
        _ = (tmp_path / f"{name}.json").write_text(json.dumps(payload))
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "skills/mold/scripts/mold.pyz"),
            "normalize-planner",
            str(tmp_path / "writer.json"),
            "--request",
            str(tmp_path / "request.json"),
            "--invocation",
            str(tmp_path / "invocation.json"),
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": "", "SHIV_ROOT": str(tmp_path / "shiv")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "complete planner writer view must not include a reason" in result.stderr
    assert "does not match any allowed shape" not in result.stderr
