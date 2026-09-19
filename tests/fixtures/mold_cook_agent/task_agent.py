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
    response_decision,
)


def _call(
    bundle: Path,
    repository: Path,
    *args: str,
    check: bool = True,
) -> tuple[dict[str, object], int]:
    result = subprocess.run(
        [sys.executable, str(bundle), *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if check:
            raise SystemExit(f"{bundle.name} failed: {result.stderr}")
        return {}, result.returncode
    decoded = cast(object, json.loads(result.stdout))
    if not isinstance(decoded, Mapping):
        raise SystemExit(f"{bundle.name} did not return an object")
    return dict(cast(Mapping[str, object], decoded)), result.returncode


def _retain(payload: bytes, artifact_root: Path) -> Path:
    """Retain approval bytes under the digest name Cook demands."""
    artifact_root.mkdir(parents=True, exist_ok=True)
    retained = artifact_root / f"sha256-{hashlib.sha256(payload).hexdigest()}"
    _ = retained.write_bytes(payload)
    return retained


responses = cast(object, json.loads(os.environ["MOLD_COOK_HARNESS_RESPONSES"]))
if not isinstance(responses, Mapping):
    raise SystemExit("missing harness approval responses")
response_map = cast(Mapping[str, object], responses)
if not all(isinstance(response_map.get(name), str) for name in ("scope", "plan")):
    raise SystemExit("missing harness approval responses")
scope_response = cast(str, response_map["scope"])
plan_response = cast(str, response_map["plan"])
scope_decision = response_decision(scope_response)
plan_decision = response_decision(plan_response)

repository = Path(os.environ["MOLD_COOK_FIXTURE_REPOSITORY"])
mold = Path(os.environ["MOLD_COOK_MOLD_BUNDLE"])
cook = Path(os.environ["MOLD_COOK_COOK_BUNDLE"])
artifacts = repository / "artifacts"
spec = make_spec(repository)
planner = make_planner_result()

prepare, prepare_code = _call(
    cook,
    repository,
    "prepare",
    "--spec",
    str(spec),
    "--mode",
    "full",
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
request_id = prepare.get("request_id")
if not isinstance(request_id, str):
    raise SystemExit("Cook preparation did not name a request id")

scope_approval = make_approval(
    repository,
    spec,
    plan=None,
    kind=MoldCookApprovalKind.SCOPE,
    response=f"{scope_response}\n".encode(),
    request_id=request_id,
)
prepare_path = repository / "prepare.json"
_ = prepare_path.write_text(json.dumps(prepare), encoding="utf-8")
scope_approval_path = _retain(canonical_bytes(scope_approval), artifacts)
resubmitted, resubmit_code = _call(
    cook,
    repository,
    "resubmit",
    str(prepare_path),
    "--source",
    str(spec),
    "--repository-root",
    str(repository),
    "--artifact-root",
    str(artifacts),
    "--scope-approval",
    str(scope_approval_path),
    check=False,
)
resubmit_outcome = str(resubmitted.get("outcome", "refused"))
events: list[dict[str, object]] = [
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
        "decision": scope_decision.value,
        "response": scope_response,
    },
    {
        "type": "prepare",
        "mode": "full",
        "outcome": resubmit_outcome,
        "tool": "cook.pyz resubmit",
        "returncode": resubmit_code,
    },
]

if scope_decision is not MoldCookApprovalDecision.APPROVED:
    if resubmit_code != 0 or resubmit_outcome not in {"blocked", "invalid"}:
        raise SystemExit(
            f"Cook did not hold a refused scope approval: {resubmit_outcome}",
        )
    print(json.dumps({"scenario": "fixture-agent", "events": events}))
    raise SystemExit(0)

if resubmit_code != 0:
    raise SystemExit("Cook refused the approved scope approval")

plan_approval = make_approval(
    repository,
    spec,
    plan=planner,
    response=f"{plan_response}\n".encode(),
)
planner_path = repository / "planner.json"
plan_path = repository / "plan.json"
approval_path = repository / "approval.json"
taste_path = repository / "taste.json"
ledger_path = repository / "ledger.json"
_ = planner_path.write_bytes(canonical_bytes(planner))
_ = plan_path.write_bytes(canonical_bytes(planner.plan))
_ = approval_path.write_bytes(canonical_bytes(plan_approval))
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

finalized, finalize_code = _call(
    mold,
    repository,
    "finalize",
    str(spec),
    "--approval",
    str(approval_path),
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
if finalized.get("status") != "ready":
    raise SystemExit(f"Mold finalization did not publish a ready handoff: {finalized}")

pointer = artifacts / "pointers" / "agent.json"
if not pointer.is_file() or finalized.get("ready") is not True:
    raise SystemExit("Mold did not publish the accepted pointer")
accepted, accept_code = _call(
    cook,
    repository,
    "accept",
    str(pointer),
    "--artifact-root",
    str(artifacts),
)

events.extend(
    [
        {"type": "approval_requested", "kind": "plan"},
        {
            "type": "approval_recorded",
            "kind": "plan",
            "source": "harness",
            "decision": plan_decision.value,
            "response": plan_response,
        },
        {
            "type": "plan_materialized",
            "outcome": finalized.get("status"),
            "tool": "mold.pyz finalize",
            "returncode": finalize_code,
        },
        {
            "type": "handoff_published",
            "ready": finalized.get("ready"),
            "artifact_ref": "artifacts/pointers/agent.json",
        },
        {
            "type": "consumer_accept",
            "ready": accept_code == 0 and bool(accepted),
            "artifact_ref": "artifacts/pointers/agent.json",
            "tool": "cook.pyz accept",
        },
    ]
)
print(json.dumps({"scenario": "fixture-agent", "events": events}))
