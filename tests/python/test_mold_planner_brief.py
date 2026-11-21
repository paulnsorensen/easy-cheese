"""The planner brief must provide writer examples accepted by the real Mold command."""
from __future__ import annotations

import copy
import re
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from easy_cheese_schemas.contracts import PlannerRequest, PlannerRequestKind, canonical_bytes
from easy_cheese_schemas.schema_runtime import supported_version_for

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "skills/mold/scripts/mold.pyz"


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ARCHIVE), *args],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": ""},
        capture_output=True,
        text=True,
        check=False,
    )


def test_planner_brief_examples_normalize_through_archive(tmp_path: Path) -> None:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    request = PlannerRequest(
        contract_version=version,
        request_id="brief-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Preserve this exact objective",
    )
    request_path = tmp_path / "request.json"
    _ = request_path.write_bytes(canonical_bytes(request))
    invocation_path = tmp_path / "invocation.json"
    _ = invocation_path.write_text(json.dumps({"planner": {"plan_id": "brief-plan", "curd_ids": {"work": "brief-curd"}}}))
    brief_run = _run(tmp_path, "planner-brief", str(request_path))
    assert brief_run.returncode == 0, brief_run.stderr
    brief = cast(dict[str, object], json.loads(brief_run.stdout))
    assert cast(dict[str, object], brief["schema"])["title"] == "AgentWriterView"
    assert brief["objective"] == request.objective
    rules = cast(dict[str, str], brief["rules"])
    assert "kind" in rules["envelope"]
    assert "serial" in rules["ownership"].lower()
    examples = cast(dict[str, dict[str, object]], brief["examples"])
    for disposition in ("complete", "partial", "blocked"):
        writer = examples[disposition]
        assert writer["kind"] == "planner_result"
        assert cast(dict[str, object], writer["payload"])["disposition"] == disposition
        writer_path = tmp_path / f"{disposition}.json"
        _ = writer_path.write_text(json.dumps(writer))
        if disposition == "blocked":
            _ = invocation_path.write_text(json.dumps({"planner": {"plan_id": None, "curd_ids": {}}}))
        normalized = _run(tmp_path, "normalize-planner", str(writer_path), "--request", str(request_path), "--invocation", str(invocation_path))
        assert normalized.returncode == 0, (disposition, normalized.stderr)
        result = cast(dict[str, object], json.loads(normalized.stdout))
        assert result["disposition"] == disposition
        if disposition == "blocked":
            assert result["plan"] is None
        else:
            assert cast(dict[str, object], result["plan"])["objective"] == request.objective


def _refs(node: object) -> set[str]:
    return set(re.findall(r'"\$ref": "(#/\$defs/[^"]+)"', json.dumps(node)))


def test_planner_brief_schema_admits_only_the_planner_branch(tmp_path: Path) -> None:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    request = PlannerRequest(contract_version=version, request_id="brief-request", kind=PlannerRequestKind.DECOMPOSE, objective="Scope")
    request_path = tmp_path / "request.json"
    _ = request_path.write_bytes(canonical_bytes(request))
    brief_run = _run(tmp_path, "planner-brief", str(request_path))
    assert brief_run.returncode == 0, brief_run.stderr
    schema = cast(dict[str, object], json.loads(brief_run.stdout)["schema"])
    text = json.dumps(schema)
    for kind in ("curd_plan", "review_result", "diagnosis_result", "curd_result"):
        assert f'"{kind}"' not in text
    for name in ("ReviewResultWriterView", "DiagnosisResultWriterView", "CurdResultWriterView"):
        assert name not in text
    assert "planner_result" in text
    defs = cast(dict[str, object], schema["$defs"])
    refs = _refs(schema)
    assert refs
    for ref in refs:
        assert ref.startswith("#/$defs/") and ref.removeprefix("#/$defs/") in defs, ref
    assert set(defs) <= {r.removeprefix("#/$defs/") for r in refs}


def test_planner_brief_rejects_invalid_request(tmp_path: Path) -> None:
    request_path = tmp_path / "bad.json"
    _ = request_path.write_text("{}")
    result = _run(tmp_path, "planner-brief", str(request_path))
    assert result.returncode == 2


@pytest.mark.parametrize(
    ("fault", "message"),
    [
        ("complete_reason", "must not include a reason"),
        ("complete_unresolved", "must not carry unresolved work"),
        ("objective_mismatch", "must match the planner request objective"),
        ("trailing_slash", "must be normalized"),
        ("serial_overlap", "unresolved ownership"),
        ("collection_shape", "scope.paths"),
        ("bare_payload", "planner writer envelope"),
        ("partial_shared", "uncertainty must concern omitted work only"),
    ],
)
def test_planner_brief_rejects_contract_faults_through_archive(
    tmp_path: Path, fault: str, message: str
) -> None:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    request = PlannerRequest(
        contract_version=version,
        request_id="negative-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Preserve this exact objective",
    )
    request_path = tmp_path / "request.json"
    _ = request_path.write_bytes(canonical_bytes(request))
    brief_run = _run(tmp_path, "planner-brief", str(request_path))
    assert brief_run.returncode == 0, brief_run.stderr
    brief = cast(dict[str, object], json.loads(brief_run.stdout))
    examples = cast(dict[str, dict[str, object]], brief["examples"])
    writer = copy.deepcopy(examples["partial" if fault == "partial_shared" else "complete"])
    payload = cast(dict[str, object], writer["payload"])
    plan = cast(dict[str, object], payload["plan"])
    curds = cast(list[dict[str, object]], plan["curds"])
    scope = cast(dict[str, object], curds[0]["scope"])
    curd_ids = {"work": "negative-curd"}
    if fault == "complete_reason":
        payload["reason"] = "A split rationale is not a blocked reason"
    elif fault == "complete_unresolved":
        payload["unresolved_work"] = [{"description": "Uncertainty in emitted work", "scope": "emitted_work"}]
    elif fault == "objective_mismatch":
        plan["objective"] = "A paraphrased objective"
    elif fault == "trailing_slash":
        scope["paths"] = ["src/example.py/"]
    elif fault == "serial_overlap":
        other = copy.deepcopy(curds[0])
        other["key"] = "other"
        other["dependencies"] = ["work"]
        curds.append(other)
        curd_ids["other"] = "negative-other"
    elif fault == "collection_shape":
        scope["paths"] = "src/example.py"
    elif fault == "bare_payload":
        writer = payload
    elif fault == "partial_shared":
        payload["unresolved_work"] = [{"description": "Uncertainty in shared work", "scope": "shared_constraint"}]
    writer_path = tmp_path / "writer.json"
    _ = writer_path.write_text(json.dumps(writer))
    invocation_path = tmp_path / "invocation.json"
    _ = invocation_path.write_text(json.dumps({"planner": {"plan_id": "negative-plan", "curd_ids": curd_ids}}))
    normalized = _run(tmp_path, "normalize-planner", str(writer_path), "--request", str(request_path), "--invocation", str(invocation_path))
    assert normalized.returncode == 2
    assert message in normalized.stderr
    if fault == "complete_reason":
        script = "set -o pipefail; " + " ".join(
            shlex.quote(value) for value in (
                sys.executable,
                str(ARCHIVE),
                "normalize-planner",
                str(writer_path),
                "--request",
                str(request_path),
                "--invocation",
                str(invocation_path),
            )
        ) + " | tail -n 1; exit $?"
        filtered = subprocess.run(
            ["bash", "-c", script],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": ""},
            capture_output=True,
            text=True,
            check=False,
        )
        assert filtered.returncode == 2


@pytest.mark.parametrize("disposition", ["complete", "partial"])
@pytest.mark.parametrize("plan_id", ["missing", None, "", 42])
def test_runnable_plan_rejects_missing_or_invalid_identity(
    tmp_path: Path, disposition: str, plan_id: object
) -> None:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    request = PlannerRequest(
        contract_version=version,
        request_id="identity-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Preserve this exact objective",
    )
    request_path = tmp_path / "request.json"
    _ = request_path.write_bytes(canonical_bytes(request))
    brief_run = _run(tmp_path, "planner-brief", str(request_path))
    assert brief_run.returncode == 0, brief_run.stderr
    brief = cast(dict[str, object], json.loads(brief_run.stdout))
    examples = cast(dict[str, dict[str, object]], brief["examples"])
    writer_path = tmp_path / "writer.json"
    _ = writer_path.write_text(json.dumps(examples[disposition]))
    planner: dict[str, object] = {"curd_ids": {"work": "identity-curd"}}
    if plan_id != "missing":
        planner["plan_id"] = plan_id
    invocation_path = tmp_path / "invocation.json"
    _ = invocation_path.write_text(json.dumps({"planner": planner}))
    normalized = _run(
        tmp_path,
        "normalize-planner",
        str(writer_path),
        "--request",
        str(request_path),
        "--invocation",
        str(invocation_path),
    )
    assert normalized.returncode == 2
    assert "plan_id" in normalized.stderr


@pytest.mark.parametrize("disposition", ["blocked", "no_work", "invalid", "executor_failure"])
@pytest.mark.parametrize("plan_id", [None, "wrong-plan"])
def test_non_runnable_plan_identity_rules(tmp_path: Path, disposition: str, plan_id: str | None) -> None:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    request = PlannerRequest(
        contract_version=version,
        request_id="non-runnable-request",
        kind=PlannerRequestKind.DECOMPOSE,
        objective="Preserve this exact objective",
    )
    request_path = tmp_path / "request.json"
    _ = request_path.write_bytes(canonical_bytes(request))
    brief_run = _run(tmp_path, "planner-brief", str(request_path))
    assert brief_run.returncode == 0, brief_run.stderr
    brief = cast(dict[str, object], json.loads(brief_run.stdout))
    examples = cast(dict[str, dict[str, object]], brief["examples"])
    writer = copy.deepcopy(examples["blocked"])
    payload = cast(dict[str, object], writer["payload"])
    payload["disposition"] = disposition
    if disposition != "blocked":
        del payload["unresolved_work"]
    writer_path = tmp_path / "writer.json"
    _ = writer_path.write_text(json.dumps(writer))
    invocation_path = tmp_path / "invocation.json"
    _ = invocation_path.write_text(json.dumps({"planner": {"plan_id": plan_id, "curd_ids": {}}}))
    normalized = _run(
        tmp_path,
        "normalize-planner",
        str(writer_path),
        "--request",
        str(request_path),
        "--invocation",
        str(invocation_path),
    )
    if plan_id is None:
        assert normalized.returncode == 0, normalized.stderr
        result = cast(dict[str, object], json.loads(normalized.stdout))
        assert result["disposition"] == disposition
        assert result["plan"] is None
    else:
        assert normalized.returncode == 2
        assert "must not receive plan identity" in normalized.stderr
