"""This module handles the ``remediate-plan`` command for Cure.

The command accepts the age ``HandoffPointer`` published on the age -> cure
route, resolves its canonical ``ReviewResult``, checks the selected finding
ids against that result, and builds a ``remediate`` ``PlannerRequest`` whose
evidence cites the ReviewResult artifact. It dispatches that request through
the existing ``easy_cheese.shared.workflow.plan`` seam, validates the returned
``PlannerResult``, and persists the child ``CurdPlan`` -- all before any coder
runs. A selected finding id absent from the ReviewResult halts the command and
dispatches nothing.

Standalone reviews have no plan under review, so the command synthesizes a
one-curd source plan (the spec's default for the ad hoc case) and derives the
remediate child from it, keeping the ``remediate`` request strict.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import cast

from easy_cheese_schemas import (
    SCHEMA_ROOT,
    BoundedScope,
    ContractValidationError,
    ContractVersion,
    CriterionWriterView,
    CurdPlan,
    CurdPlanWriterView,
    EvidenceKind,
    EvidenceRef,
    HandoffPointer,
    IdentityAction,
    IdentityLineage,
    PlannerDisposition,
    PlannerRequest,
    PlannerRequestKind,
    PlannerResultWriterView,
    ReviewResult,
    SemanticCurdWriterView,
    SourcePlanRef,
    TransitionError,
    canonical_bytes,
    supported_version_for,
    validate_contract,
    validate_curd_plan,
)

from easy_cheese.shared import workflow
from easy_cheese.shared.publication import (
    PointerNotFoundError,
    PublicationError,
    accept,
)

__all__ = ["remediate_plan_main"]

REVIEW_RESULT_SCHEMA_URI = f"{SCHEMA_ROOT}/review-result"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="remediate-plan.py")
    _ = parser.add_argument("--pointer", required=True, type=Path)
    _ = parser.add_argument("--finding-ids", required=True)
    return parser.parse_args(argv)


def _planner_version() -> ContractVersion:
    version = supported_version_for(PlannerRequest)
    assert version is not None
    return version


def _source_plan(review_id: str) -> CurdPlan:
    """Synthesize a one-curd source plan for the review under repair."""
    request = PlannerRequest(
        contract_version=_planner_version(),
        request_id=f"{review_id}/source",
        kind=PlannerRequestKind.DECOMPOSE,
        objective=f"Source plan for review {review_id}",
        evidence=(),
        source_plan_ref=None,
    )
    view = PlannerResultWriterView(
        disposition=PlannerDisposition.COMPLETE,
        plan=CurdPlanWriterView(
            objective=f"Source plan for review {review_id}",
            curds=[
                SemanticCurdWriterView(
                    key="source",
                    outcome=f"The review {review_id} names the diff under repair",
                    scope=BoundedScope(paths=[f"reviews/{review_id}"]),
                    outputs=["The reviewed diff is identified"],
                    criteria=[
                        CriterionWriterView(
                            description="The reviewed diff is identified",
                            check=f"review {review_id} names its subject",
                        )
                    ],
                )
            ],
        ),
    )
    result = workflow.plan(request, lambda _request: view)
    assert result.plan is not None
    return result.plan


def remediate_plan_main(argv: list[str]) -> int:
    args = _parse_args(argv)
    pointer_path = cast(Path, args.pointer)
    selection = [fid.strip() for fid in cast(str, args.finding_ids).split(",") if fid.strip()]
    if not selection:
        print("ERROR: --finding-ids selected no finding", file=sys.stderr)
        return 1

    try:
        accepted = accept(
            pointer_path,
            destination_phase="cure",
            payload_schema_uri=REVIEW_RESULT_SCHEMA_URI,
        )
    except (
        PointerNotFoundError,
        PublicationError,
        ContractValidationError,
        TransitionError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    review = accepted.canonical.value
    if not isinstance(review, ReviewResult):
        print("ERROR: pointer does not resolve to a ReviewResult", file=sys.stderr)
        return 1

    known = {finding.finding_id: finding for finding in review.findings}
    for fid in selection:
        if fid not in known:
            print(f"ERROR: unknown finding id {fid}", file=sys.stderr)
            return 1

    pointer_version = supported_version_for(HandoffPointer)
    pointer_doc = validate_contract(
        pointer_path.read_text(encoding="utf-8"), HandoffPointer, pointer_version
    ).value
    assert isinstance(pointer_doc, HandoffPointer)
    review_artifact = pointer_doc.payload

    review_id = review.review_id
    source_plan = _source_plan(review_id)
    source_curd_id = source_plan.curds[0].curd_id

    evidence_ref = EvidenceRef(
        evidence_id=f"review-{review_id}",
        kind=EvidenceKind.REVIEW,
        artifact=review_artifact,
        summary=f"Review {review_id} findings under repair",
    )
    remediate_objective = (
        f"Remediate {len(selection)} selected findings from review {review_id}"
    )
    remediate_request = PlannerRequest(
        contract_version=_planner_version(),
        request_id=f"{review_id}/remediate",
        kind=PlannerRequestKind.REMEDIATE,
        objective=remediate_objective,
        evidence=(evidence_ref,),
        source_plan_ref=SourcePlanRef(
            source_plan.plan_id,
            source_plan.revision,
            source_plan.digest,
        ),
    )
    paths: list[str] = []
    for fid in selection:
        location = known[fid].location
        if location is not None and location.path not in paths:
            paths.append(location.path)
    if not paths:
        paths = [f"reviews/{review_id}"]
    remediate_curd = SemanticCurdWriterView(
        key="remediate",
        outcome=f"Resolve {len(selection)} selected findings from review {review_id}",
        scope=BoundedScope(paths=paths),
        outputs=[f"Finding {fid} is resolved" for fid in selection],
        criteria=[
            CriterionWriterView(
                description=f"Finding {fid} is resolved",
                check=f"review finding {fid} is addressed",
            )
            for fid in selection
        ],
    )
    remediate_view = PlannerResultWriterView(
        disposition=PlannerDisposition.COMPLETE,
        plan=CurdPlanWriterView(
            objective=remediate_objective,
            curds=[remediate_curd],
        ),
    )
    lineages = {
        "remediate": IdentityLineage(
            IdentityAction.DERIVE, source_curd_ids=(source_curd_id,)
        )
    }
    try:
        result = workflow.plan(
            remediate_request,
            lambda _request: remediate_view,
            lineages=lineages,
            source_plan=source_plan,
        )
    except (ContractValidationError, TransitionError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    child = result.plan
    if child is None:
        print("ERROR: planner returned no child plan", file=sys.stderr)
        return 1
    _ = validate_curd_plan(child)

    root = pointer_path.resolve().parent.parent
    out_path = root / "plans" / f"{review_id}-remediate.curd-plan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _ = out_path.write_bytes(canonical_bytes(child))
    print(str(out_path))
    return 0
