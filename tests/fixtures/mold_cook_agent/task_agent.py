"""Fixture task agent that finalizes Mold and executes direct Cook inputs."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import attrs

TEST_ROOT = Path(os.environ["MOLD_COOK_TEST_ROOT"])
sys.path.insert(0, str(TEST_ROOT))
sys.path.insert(0, str(TEST_ROOT / "src"))

from easy_cheese.skills.cook import execute_bound_plan  # noqa: E402
from easy_cheese.shared.mold_cook_handoff import validate_bound_execution  # noqa: E402
from easy_cheese_schemas import ArtifactRef, MoldCookCoverage, canonical_bytes  # noqa: E402
from easy_cheese_schemas.schema_runtime import (  # noqa: E402
    structure_contract_value,
)
from easy_cheese_schemas.contracts import (  # noqa: E402
    Criterion,
    PlannerDisposition,
    PlannerUncertainty,
    UncertaintyScope,
    CriterionDisposition,
    CriterionResultWriterView,
    CurdResultWriterView,
    DeliverableWriterView,
    ReviewDisposition,
    ReviewResultWriterView,
)
from tests.python.test_mold_cook_producer import (  # noqa: E402
    make_planner_result,
    make_spec,
)


def _call(bundle: Path, repository: Path, *args: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(bundle), *args], cwd=repository,
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"{bundle.name} failed: {result.stderr}")
    decoded = cast(object, json.loads(result.stdout))
    if not isinstance(decoded, Mapping):
        raise SystemExit(f"{bundle.name} did not return an object")
    return dict(cast(Mapping[str, object], decoded))


def _write_feature(repository: Path, context: Mapping[str, object]) -> CurdResultWriterView:
    criteria = cast(tuple[Criterion, ...], context["criteria"])
    feature = repository / "src" / "core.py"
    feature.parent.mkdir(parents=True, exist_ok=True)
    _ = feature.write_text("FEATURE_READY = True\n", encoding="utf-8")
    return CurdResultWriterView(
        criterion_results=tuple(
            CriterionResultWriterView(
                criterion_id=item.criterion_id,
                disposition=CriterionDisposition.PASSED,
                evidence_keys=("src/core.py",),
            )
            for item in criteria
        ),
        deliverables=(
            DeliverableWriterView(
                role="feature", path="src/core.py", media_type="text/x-python",
            ),
        ),
    )


def _clean_review(_request: object) -> ReviewResultWriterView:
    return ReviewResultWriterView(disposition=ReviewDisposition.CLEAN, findings=())


def _unexpected_diagnosis(_request: object) -> object:
    raise AssertionError("clean feature must not dispatch diagnosis")


repository = Path(os.environ["MOLD_COOK_FIXTURE_REPOSITORY"])
mold = Path(os.environ["MOLD_COOK_MOLD_BUNDLE"])
artifacts = repository / "artifacts"
spec = make_spec(repository)
planner = make_planner_result()
if sys.argv[1:] == ["--partial"]:
    planner = attrs.evolve(
        planner,
        disposition=PlannerDisposition.PARTIAL,
        unresolved_work=(
            PlannerUncertainty(
                description="unselected parent work remains",
                scope=UncertaintyScope.OMITTED_WORK,
            ),
        ),
    )
elif sys.argv[1:]:
    raise SystemExit("usage: task_agent.py [--partial]")
planner_path = repository / "planner.json"
plan_path = repository / "plan.json"
_ = planner_path.write_bytes(canonical_bytes(planner))
_ = plan_path.write_bytes(canonical_bytes(planner.plan))

finalized = _call(
    mold, repository, "finalize", str(spec),
    "--planner-result", str(planner_path),
    "--plan", str(plan_path),
    "--artifact-root", str(artifacts),
    "--operation-id", "agent",
    "--request-id", "request-1",
)
if finalized.get("status") != "ready":
    raise SystemExit(f"Mold did not return ready direct inputs: {finalized}")
result_path = Path(cast(str, finalized["result_path"]))
if not result_path.is_file():
    raise SystemExit("Mold did not retain its finalization result")
refs = {
    name: structure_contract_value(finalized[name], ArtifactRef, name)
    for name in ("spec_ref", "planner_result_ref", "plan_ref")
}
coverage = structure_contract_value(finalized["coverage"], MoldCookCoverage, "coverage")
_ = validate_bound_execution(
    spec_ref=refs["spec_ref"], planner_result_ref=refs["planner_result_ref"],
    plan_ref=refs["plan_ref"], coverage=coverage, artifact_root=artifacts,
)
result = execute_bound_plan(
    request_id=cast(str, finalized["request_id"]),
    spec_ref=refs["spec_ref"], planner_result_ref=refs["planner_result_ref"],
    plan_ref=refs["plan_ref"], coverage=coverage, artifact_root=artifacts,
    repository_root=repository,
    dispatch_writer=lambda context: _write_feature(repository, context),
    dispatch_review=_clean_review,
    dispatch_diagnosis=_unexpected_diagnosis,
)
if (
    result.completed_curds != coverage.curd_ids
    or result.remainder != planner.unresolved_work
    or result.whole_task_complete == bool(planner.unresolved_work)
):
    raise SystemExit("Cook did not preserve the finalized curd and remainder")
relative_result = str(result_path.relative_to(repository))
events: list[dict[str, object]] = [
    {"type": "input_classified", "input_kind": "direct_spec"},
    {
        "type": "plan_materialized",
        "outcome": planner.disposition.value,
        "tool": "scripts/mold.pyz finalize",
    },
    {"type": "bound_inputs", "ready": True, "artifact_ref": relative_result},
]
if result.remainder:
    events.append({
        "type": "remainder_preserved",
        "unresolved_work": [item.description for item in result.remainder],
    })
events.append({
    "type": "feature_write",
    "path": "src/core.py",
    "artifact_ref": relative_result,
    "whole_task_complete": result.whole_task_complete,
    "remainder": [item.description for item in result.remainder],
})
print(json.dumps({"scenario": "fixture-agent", "events": events}))