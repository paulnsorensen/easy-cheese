"""Execute direct Cook inputs and produce the browser feature."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas.contracts import (
    Criterion,
    CriterionDisposition,
    CriterionResultWriterView,
    CurdResultWriterView,
    DeliverableWriterView,
    ReviewDisposition,
    ReviewResultWriterView,
)
from easy_cheese.skills.cook.preparation import execute_bound_plan
from easy_cheese.shared.mold_cook_handoff import (
    SETUP_EVIDENCE_SCHEMA_URI,
    materialize_artifact_ref,
)
from easy_cheese_schemas import ArtifactRef, MoldCookCoverage
from easy_cheese_schemas.schema_runtime import (
    structure_contract_value,
)


def _write_feature(
    repository: Path, context: dict[str, object]
) -> CurdResultWriterView:
    criteria = cast(tuple[Criterion, ...], context["criteria"])
    document = """<!doctype html>
<html><body>
<h1>Mold to Cook fixture</h1>
<p data-testid="feature-state">ready</p>
<button type="button" id="run">Run feature</button>
<p data-testid="feature-result">Waiting</p>
<script>
  document.querySelector('#run').addEventListener('click', () => {
    document.querySelector('[data-testid="feature-result"]').textContent = 'Feature executed';
  });
</script>
</body></html>
"""
    _ = (repository / "index.html").write_text(document, encoding="utf-8")
    return CurdResultWriterView(
        criterion_results=tuple(
            CriterionResultWriterView(
                criterion_id=criterion.criterion_id,
                disposition=CriterionDisposition.PASSED,
                evidence_keys=("index.html",),
            )
            for criterion in criteria
        ),
        deliverables=(
            DeliverableWriterView(
                role="feature",
                path="index.html",
                media_type="text/html",
            ),
        ),
    )


def _clean_review(_request: object) -> ReviewResultWriterView:
    return ReviewResultWriterView(disposition=ReviewDisposition.CLEAN, findings=())


def _unexpected_diagnosis(_request: object) -> object:
    raise AssertionError("clean feature must not dispatch diagnosis")


def main(argv: list[str]) -> int:
    if len(argv) not in {3, 6}:
        raise SystemExit(
            "usage: outer_workflow.py FINALIZATION_RESULT REPOSITORY ARTIFACT_ROOT "
            + "[RUNNER_AUTHORIZATION RUNNER_RESPONSE SETUP_EVIDENCE]"
        )
    result_path, repository, artifact_root = (Path(value) for value in argv[:3])
    finalized = cast(dict[str, object], json.loads(result_path.read_text(encoding="utf-8")))
    refs = {
        name: structure_contract_value(finalized[name], ArtifactRef, name)
        for name in ("spec_ref", "planner_result_ref", "plan_ref")
    }
    coverage = structure_contract_value(finalized["coverage"], MoldCookCoverage, "coverage")
    runner_authorization_ref: ArtifactRef | None = None
    runner_response_ref: ArtifactRef | None = None
    setup_evidence_refs: tuple[ArtifactRef, ...] = ()
    if len(argv) == 6:
        roles = ("runner_authorization", "dialogue", "setup_evidence")
        references: list[ArtifactRef] = []
        for role, raw_path in zip(roles, argv[3:], strict=True):
            path = Path(raw_path)
            references.append(
                materialize_artifact_ref(
                    path.read_bytes(), artifact_id=f"browser-{role}", role=role,
                    uri=path.as_uri(),
                    schema_uri=SETUP_EVIDENCE_SCHEMA_URI if role == "setup_evidence" else None,
                )
            )
        runner_authorization_ref = references[0]
        runner_response_ref = references[1]
        setup_evidence_refs = (references[2],)
    results = execute_bound_plan(
        request_id=cast(str, finalized["request_id"]),
        spec_ref=refs["spec_ref"],
        planner_result_ref=refs["planner_result_ref"],
        plan_ref=refs["plan_ref"],
        coverage=coverage,
        artifact_root=artifact_root,
        repository_root=repository,
        dispatch_writer=lambda context: _write_feature(
            repository, cast(dict[str, object], context)
        ),
        dispatch_review=_clean_review,
        dispatch_diagnosis=_unexpected_diagnosis,
        runner_authorization_ref=runner_authorization_ref,
        runner_response_ref=runner_response_ref,
        setup_evidence_refs=setup_evidence_refs,
    )
    curd_results = results.execution_results[1]
    print(
        json.dumps(
            {
                "feature": "index.html",
                "results": len(curd_results),
                "disposition": curd_results[0].disposition.value,
                "whole_task_complete": results.whole_task_complete,
                "remainder": [item.description for item in results.remainder],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
