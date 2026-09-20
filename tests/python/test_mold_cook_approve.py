"""Tests for the `approve` bundle command and its documented flows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared.mold_cook_approve import ApprovalRecordError, approve
from easy_cheese.shared.mold_cook_handoff import validate_mold_cook_approval
from easy_cheese.skills.cook import commands as cook_commands
from easy_cheese.skills.mold import commands as mold_commands
from easy_cheese_schemas import canonical_bytes
from easy_cheese_schemas.mold_cook import (
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
    MoldCookCoverage,
)
from tests.python.test_mold_cook_producer import (
    make_planner_result,
    make_spec,
    taste_fixture,
)


_ONE_CURD = MoldCookCoverage(curd_ids=("curd-1",))


def _run(
    main: Callable[[list[str]], int],
    argv: list[str],
    capsys: pytest.CaptureFixture[str],
) -> tuple[int, dict[str, object], str]:
    code = main(argv)
    captured = capsys.readouterr()
    output = (
        cast("dict[str, object]", json.loads(captured.out)) if captured.out else {}
    )
    return code, output, captured.err


def test_approve_retains_an_approved_record_under_its_digest(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    artifacts = tmp_path / "artifacts"

    approval, path = approve(
        spec,
        artifact_root=artifacts,
        request_id="request-1",
        kind=MoldCookApprovalKind.SCOPE,
        response_text="approved",
        coverage=_ONE_CURD,
    )

    assert approval.decision is MoldCookApprovalDecision.APPROVED
    assert approval.request_id == "request-1"
    assert approval.spec_digest == (
        "sha256:" + hashlib.sha256(spec.read_bytes()).hexdigest()
    )
    assert approval.response_text == "approved"
    assert path.parent == artifacts
    assert path.name == "sha256-" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert path.read_bytes() == canonical_bytes(approval)
    _ = validate_mold_cook_approval(approval, artifacts)


def test_approve_records_a_non_affirmative_response_as_rejected(
    tmp_path: Path,
) -> None:
    approval, _ = approve(
        make_spec(tmp_path),
        artifact_root=tmp_path / "artifacts",
        request_id="request-1",
        kind=MoldCookApprovalKind.SCOPE,
        response_text="not yet, change the scope",
        coverage=_ONE_CURD,
    )

    assert approval.decision is MoldCookApprovalDecision.REJECTED


@pytest.mark.parametrize("response", ["", "   \n"])
def test_approve_refuses_an_empty_response(tmp_path: Path, response: str) -> None:
    with pytest.raises(ApprovalRecordError):
        _ = approve(
            make_spec(tmp_path),
            artifact_root=tmp_path / "artifacts",
            request_id="request-1",
            kind=MoldCookApprovalKind.SCOPE,
            response_text=response,
            coverage=_ONE_CURD,
        )


def test_approve_refuses_a_scope_with_no_declared_coverage(tmp_path: Path) -> None:
    with pytest.raises(ApprovalRecordError, match="--curd-id"):
        _ = approve(
            make_spec(tmp_path),
            artifact_root=tmp_path / "artifacts",
            request_id="request-1",
            kind=MoldCookApprovalKind.SCOPE,
            response_text="approved",
        )


def test_approve_refuses_a_plan_kind_without_a_plan(tmp_path: Path) -> None:
    with pytest.raises(ApprovalRecordError):
        _ = approve(
            make_spec(tmp_path),
            artifact_root=tmp_path / "artifacts",
            request_id="request-1",
            kind=MoldCookApprovalKind.PLAN,
            response_text="approved",
        )


def test_approve_refuses_the_runner_kind(tmp_path: Path) -> None:
    with pytest.raises(ApprovalRecordError):
        _ = approve(
            make_spec(tmp_path),
            artifact_root=tmp_path / "artifacts",
            request_id="request-1",
            kind=MoldCookApprovalKind.RUNNER,
            response_text="approved",
        )


def test_approve_command_reports_bad_input_on_stderr(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, output, err = _run(
        mold_commands.main,
        [
            "approve",
            str(tmp_path / "missing.md"),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--request-id",
            "request-1",
            "--kind",
            "scope",
            "--response",
            "approved",
        ],
        capsys,
    )

    assert code == 1
    assert output == {}
    assert err.startswith("ERROR:")


def test_documented_finalize_flow_reaches_cook_accept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = make_spec(tmp_path)
    artifacts = tmp_path / "artifacts"
    planner = make_planner_result()
    planner_path = tmp_path / "planner-result.json"
    taste_path = tmp_path / "taste.json"
    ledger_path = tmp_path / "ledger.json"
    _ = planner_path.write_bytes(canonical_bytes(planner))
    _ = taste_path.write_text(json.dumps(taste_fixture(spec).to_dict()))
    _ = ledger_path.write_text("[]")

    code, approved, err = _run(
        mold_commands.main,
        [
            "approve",
            str(spec),
            "--artifact-root",
            str(artifacts),
            "--request-id",
            "request-1",
            "--kind",
            "plan",
            "--response",
            "ship it",
            "--planner-result",
            str(planner_path),
        ],
        capsys,
    )
    assert (code, err) == (0, "")
    assert approved["decision"] == "approved"

    code, finalized, err = _run(
        mold_commands.main,
        [
            "finalize",
            str(spec),
            "--approval",
            cast(str, approved["approval_path"]),
            "--artifact-root",
            str(artifacts),
            "--operation-id",
            "documented-1",
            "--request-id",
            "request-1",
            "--mode",
            "full",
            "--planner-result",
            str(planner_path),
            "--taste-result",
            str(taste_path),
            "--ledger",
            str(ledger_path),
        ],
        capsys,
    )
    assert (code, err) == (0, "")
    assert finalized["status"] == "ready", finalized
    pointer = str(artifacts / "pointers" / "documented-1.json")
    assert finalized["command"] == ["/cook", "--auto", pointer, "--spec", str(spec)]

    code, _, err = _run(
        cook_commands.main,
        ["accept", pointer, "--artifact-root", str(artifacts), "--spec", str(spec)],
        capsys,
    )
    assert (code, err) == (0, "")


def test_direct_spec_scope_approval_advances_cook_preparation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = make_spec(tmp_path)
    artifacts = tmp_path / "artifacts"
    roots = ["--repository-root", str(tmp_path), "--artifact-root", str(artifacts)]

    code, prepared, err = _run(
        cook_commands.main, ["prepare", "--spec", str(spec), *roots], capsys
    )
    assert (code, err) == (0, "")
    assert prepared["outcome"] == "needs-approval"
    assert prepared["approval_kind"] == "scope"
    prepared_path = tmp_path / "prepare.json"
    _ = prepared_path.write_text(json.dumps(prepared))

    code, approved, err = _run(
        cook_commands.main,
        [
            "approve",
            str(spec),
            "--artifact-root",
            str(artifacts),
            "--request-id",
            cast(str, prepared["request_id"]),
            "--kind",
            "scope",
            "--response",
            "yes",
            "--curd-id",
            "curd-1",
        ],
        capsys,
    )
    assert (code, err) == (0, "")

    code, resubmitted, err = _run(
        cook_commands.main,
        [
            "resubmit",
            str(prepared_path),
            "--source",
            str(spec),
            *roots,
            "--scope-approval",
            cast(str, approved["approval_path"]),
        ],
        capsys,
    )
    assert (code, err) == (0, "")
    assert resubmitted["approved_scope_ref"] is not None
    assert resubmitted["outcome"] == "needs-planning", resubmitted

    planner_path = tmp_path / "planner-result.json"
    _ = planner_path.write_bytes(canonical_bytes(make_planner_result()))
    evidence = [
        "--scope-approval",
        cast(str, approved["approval_path"]),
        "--planner-result",
        str(planner_path),
    ]
    _ = prepared_path.write_text(json.dumps(resubmitted))
    code, planned, err = _run(
        cook_commands.main,
        ["resubmit", str(prepared_path), "--source", str(spec), *roots, *evidence],
        capsys,
    )
    assert (code, err) == (0, "")
    assert (planned["outcome"], planned["approval_kind"]) == ("needs-approval", "plan")

    code, plan_approved, err = _run(
        cook_commands.main,
        [
            "approve",
            str(spec),
            "--artifact-root",
            str(artifacts),
            "--request-id",
            cast(str, prepared["request_id"]),
            "--kind",
            "plan",
            "--response",
            "approved",
            "--planner-result",
            str(planner_path),
        ],
        capsys,
    )
    assert (code, err) == (0, "")
    _ = prepared_path.write_text(json.dumps(planned))
    code, ready, err = _run(
        cook_commands.main,
        [
            "resubmit",
            str(prepared_path),
            "--source",
            str(spec),
            *roots,
            *evidence,
            "--plan-approval",
            cast(str, plan_approved["approval_path"]),
        ],
        capsys,
    )
    assert (code, err) == (0, "")
    assert ready["outcome"] == "ready", ready


def test_a_rejected_scope_response_does_not_advance_preparation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = make_spec(tmp_path)
    artifacts = tmp_path / "artifacts"
    roots = ["--repository-root", str(tmp_path), "--artifact-root", str(artifacts)]
    _, prepared, _ = _run(
        cook_commands.main, ["prepare", "--spec", str(spec), *roots], capsys
    )
    prepared_path = tmp_path / "prepare.json"
    _ = prepared_path.write_text(json.dumps(prepared))
    _, rejected, _ = _run(
        cook_commands.main,
        [
            "approve",
            str(spec),
            "--artifact-root",
            str(artifacts),
            "--request-id",
            cast(str, prepared["request_id"]),
            "--kind",
            "scope",
            "--response=--auto",
            "--curd-id",
            "curd-1",
        ],
        capsys,
    )
    assert rejected["decision"] == "rejected"

    code, resubmitted, _ = _run(
        cook_commands.main,
        [
            "resubmit",
            str(prepared_path),
            "--source",
            str(spec),
            *roots,
            "--scope-approval",
            cast(str, rejected["approval_path"]),
        ],
        capsys,
    )
    assert code != 0 or resubmitted.get("outcome") in {"blocked", "invalid"}
