"""Fixture OMP task agent that drives real Mold and Cook bundle calls."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

test_root = Path(os.environ["MOLD_COOK_TEST_ROOT"])
sys.path.insert(0, str(test_root))
sys.path.insert(0, str(test_root / "src"))

from easy_cheese_schemas import canonical_bytes  # noqa: E402
from easy_cheese_schemas.mold_cook import (  # noqa: E402
    MoldCookApprovalDecision,
    MoldCookApprovalKind,
)
from tests.python.test_mold_cook_producer import (  # noqa: E402
    taste_fixture,
    make_approval,
    make_planner_result,
    make_spec,
)


def _call(bundle: Path, repository: Path, *args: str) -> tuple[dict[str, object], int]:
    result = subprocess.run(
        [sys.executable, str(bundle), *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{bundle.name} failed: {result.stderr}")
    decoded = cast(object, json.loads(result.stdout))
    if not isinstance(decoded, Mapping):
        raise SystemExit(f"{bundle.name} did not return an object")
    return dict(cast(Mapping[str, object], decoded)), result.returncode


responses = cast(object, json.loads(os.environ["MOLD_COOK_HARNESS_RESPONSES"]))
if not isinstance(responses, Mapping):
    raise SystemExit("missing harness approval responses")
response_map = cast(Mapping[str, object], responses)
if not all(isinstance(response_map.get(name), str) for name in ("scope", "plan")):
    raise SystemExit("missing harness approval responses")


def _decision(response: str) -> MoldCookApprovalDecision:
    token = response.strip().casefold().rstrip(" \t.,!?;:")
    if token in {"approved", "approve", "yes", "y", "ok", "lgtm", "confirmed"}:
        return MoldCookApprovalDecision.APPROVED
    return MoldCookApprovalDecision.REJECTED


repository = Path(os.environ["MOLD_COOK_FIXTURE_REPOSITORY"])
mold = Path(os.environ["MOLD_COOK_MOLD_BUNDLE"])
cook = Path(os.environ["MOLD_COOK_COOK_BUNDLE"])
artifacts = repository / "artifacts"
spec = make_spec(repository)
planner = make_planner_result()
scope_response = cast(str, response_map["scope"])
plan_response = cast(str, response_map["plan"])
scope_approval = make_approval(
    repository,
    spec,
    plan=None,
    response=scope_response,
    kind=MoldCookApprovalKind.SCOPE,
    decision=_decision(scope_response),
    artifact_prefix="scope",
)
plan_approval = make_approval(
    repository,
    spec,
    plan=planner,
    response=plan_response,
    kind=MoldCookApprovalKind.PLAN,
    artifact_prefix="plan",
)
def _retain(value: object) -> Path:
    content = canonical_bytes(value)
    path = artifacts / f"sha256-{hashlib.sha256(content).hexdigest()}"
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_bytes(content)
    return path


planner_path = _retain(planner)
plan_path = _retain(planner.plan)
scope_approval_path = _retain(scope_approval)
plan_approval_path = _retain(plan_approval)
taste_path = repository / "taste.json"
ledger_path = repository / "ledger.json"
taste = taste_fixture(spec)
_ = taste_path.write_text(
    json.dumps(
        {
            "draft_sha256": taste.draft_sha256,
            "verdict": taste.verdict,
            "forks": [],
            "contradictions": [],
            "orphaned_decisions": [],
            "unsupported_assumptions": [],
            "acceptance_gaps": [],
        }
    ),
    encoding="utf-8",
)
_ = ledger_path.write_text("[]\n", encoding="utf-8")

prepare, prepare_code = _call(
    cook,
    repository,
    "prepare",
    "--spec",
    str(spec),
    "--mode",
    "full",
    "--request-id",
    "request-1",
    "--repository-root",
    str(repository),
    "--artifact-root",
    str(artifacts),
)
if (
    prepare.get("outcome") != "needs-approval"
    or prepare.get("approval_kind") != "scope"
):
    raise SystemExit(f"Cook preparation did not request scope approval: {prepare}")

scope_prepare, scope_prepare_code = _call(
    cook,
    repository,
    "prepare",
    "--spec",
    str(spec),
    "--mode",
    "full",
    "--request-id",
    "request-1",
    "--repository-root",
    str(repository),
    "--artifact-root",
    str(artifacts),
    "--scope-approval",
    str(scope_approval_path),
)
base_events = [
    {"type": "input_classified", "input_kind": "direct_spec"},
    {
        "type": "prepare",
        "mode": "full",
        "outcome": prepare["outcome"],
        "approval_kind": prepare["approval_kind"],
        "tool": "cook.pyz prepare",
        "returncode": prepare_code,
    },
    {"type": "approval_requested", "kind": "scope"},
    {
        "type": "approval_recorded",
        "kind": "scope",
        "source": "harness",
        "decision": scope_approval.decision.value,
        "response": scope_approval.response_text,
    },
    {
        "type": "prepare",
        "mode": "full",
        "outcome": scope_prepare["outcome"],
        "approval_kind": scope_prepare.get("approval_kind"),
        "tool": "cook.pyz prepare",
        "returncode": scope_prepare_code,
    },
]
if scope_approval.decision is not MoldCookApprovalDecision.APPROVED:
    print(json.dumps({"scenario": "fixture-agent", "events": base_events}))
    raise SystemExit(2)

planned, planned_code = _call(
    cook,
    repository,
    "prepare",
    "--spec",
    str(spec),
    "--mode",
    "full",
    "--request-id",
    "request-1",
    "--repository-root",
    str(repository),
    "--artifact-root",
    str(artifacts),
    "--scope-approval",
    str(scope_approval_path),
    "--planner-result",
    str(planner_path),
)
finalized, _ = _call(
    cook,
    repository,
    "prepare",
    "--spec",
    str(spec),
    "--mode",
    "full",
    "--request-id",
    "request-1",
    "--repository-root",
    str(repository),
    "--artifact-root",
    str(artifacts),
    "--scope-approval",
    str(scope_approval_path),
    "--planner-result",
    str(planner_path),
    "--plan-approval",
    str(plan_approval_path),
)
if finalized.get("outcome") != "ready":
    raise SystemExit(f"Cook preparation did not produce a ready handoff: {finalized}")

finalized_mold, mold_finalize_code = _call(
    mold,
    repository,
    "finalize",
    str(spec),
    "--approval",
    str(plan_approval_path),
    "--planner-result",
    str(planner_path),
    "--plan",
    str(plan_path),
    "--taste-result",
    str(taste_path),
    "--ledger",
    str(ledger_path),
    "--artifact-root",
    str(artifacts),
    "--operation-id",
    "agent",
    "--request-id",
    "request-1",
)
if finalized_mold.get("status") != "ready":
    raise SystemExit(f"Mold finalization did not publish a ready handoff: {finalized_mold}")

pointer = artifacts / "pointers" / "agent.json"
if not pointer.is_file() or finalized_mold.get("ready") is not True:
    raise SystemExit("Mold did not publish the accepted pointer")
accepted, accept_code = _call(
    cook,
    repository,
    "accept",
    str(pointer),
    "--artifact-root",
    str(artifacts),
)

print(
    json.dumps(
        {
            "scenario": "fixture-agent",
            "events": [
                *base_events,
                {
                    "type": "prepare",
                    "mode": "full",
                    "outcome": planned["outcome"],
                    "approval_kind": planned.get("approval_kind"),
                    "tool": "cook.pyz prepare",
                    "returncode": planned_code,
                },
                {"type": "approval_requested", "kind": "plan"},
                {
                    "type": "approval_recorded",
                    "kind": "plan",
                    "source": "harness",
                    "decision": plan_approval.decision.value,
                    "response": plan_approval.response_text,
                },
                {
                    "type": "plan_materialized",
                    "outcome": finalized_mold.get("status"),
                    "tool": "mold.pyz finalize",
                    "returncode": mold_finalize_code,
                },
                {
                    "type": "handoff_published",
                    "ready": finalized_mold.get("ready"),
                    "artifact_ref": "artifacts/pointers/agent.json",
                },
                {
                    "type": "consumer_accept",
                    "ready": accept_code == 0 and bool(accepted),
                    "artifact_ref": "artifacts/pointers/agent.json",
                },
            ],
        }
    )
)
