"""Cook execution result."""

from __future__ import annotations

from collections.abc import Mapping

import attrs

from easy_cheese_schemas import ArtifactRef, PlannerUncertainty
from easy_cheese_schemas.mold_cook import MoldCookCoverage
from easy_cheese.shared import workflow
from easy_cheese.shared.fanout.run_fan import ScopeRemediationSummary


@attrs.define(frozen=True)
class CookExecutionOutcome:
    """Durable result for one bound spec and selected plan."""

    request_id: str
    planner_result_ref: ArtifactRef
    plan_ref: ArtifactRef
    coverage: MoldCookCoverage
    completed_curds: tuple[str, ...]
    remainder: tuple[PlannerUncertainty, ...]
    whole_task_complete: bool
    execution_results: workflow.ExecutionResults = attrs.field(repr=False)
    outcome_ref: ArtifactRef | None = None
    fan_next_step: str | None = None
    remediation_state_refs: tuple[ArtifactRef, ...] = attrs.field(factory=tuple)
    stop_evidence_refs: tuple[ArtifactRef, ...] = attrs.field(factory=tuple)
    remediation_request_ref: ArtifactRef | None = None
    execution_result_refs: tuple[ArtifactRef, ...] = attrs.field(factory=tuple)
    scope_summaries: Mapping[str, ScopeRemediationSummary] = attrs.field(
        factory=lambda: dict[str, ScopeRemediationSummary]()
    )
