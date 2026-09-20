"""Closed records and typed failures shared by every preparation stage.

This module sits at the bottom of the package import graph: it depends on the
contract schemas alone, so any other preparation module can import it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TypeAlias, cast

import attrs

from easy_cheese_schemas import (
    ArtifactRef,
    CurdPlan,
    PlannerRequest,
    PlannerResult,
    PlannerResultWriterView,
    PlannerUncertainty,
)
from easy_cheese_schemas.mold_cook import (
    CookExecutionHold,
    CookPreparationResult,
    CookSetupAuthorization,
    MoldCookApproval,
    MoldCookCoverage,
    MoldCookInputKind,
    MoldCookMode,
)
from easy_cheese_schemas.validate import (
    require_exact_keys,
    require_int,
    require_mapping,
    require_relative_path,
    require_str,
)
from easy_cheese.shared import workflow
from easy_cheese.shared.fanout.run_fan import ScopeRemediationSummary
from easy_cheese.shared.mold_cook_handoff import MoldCookSpecReadiness


class CookInputError(ValueError):
    """A request could not be classified as one supported Cook input."""


class CookEvidenceError(ValueError):
    """Evidence is absent, stale, detached, or outside its authority."""


class DependencyClosureError(CookEvidenceError):
    """A partial approval names a curd without its approved dependencies."""


class SetupExecutionFailed(CookEvidenceError):
    """The authorized setup command ran but did not pass."""


class PreparationFailure(Exception):
    """Internal typed failure converted into an invalid preparation result."""

    def __init__(self, code: str, message: str, *, path: str | None = None) -> None:
        super().__init__(message)
        self.code: str = code
        self.path: str | None = path


@attrs.define(frozen=True)
class ClassifiedCookInput:
    """The input contract selected before any format-specific resolution."""

    kind: MoldCookInputKind
    source: str
    path: Path | None = None
    explicit: bool = False
    declared_kind: MoldCookInputKind | None = None
    snapshot: bytes | None = None


@attrs.define(frozen=True)
class CookPreparationRequest:
    """Host-owned context for one recomputable preparation transition."""

    request_id: str
    source: str | Path | ClassifiedCookInput
    repository_root: Path = attrs.field(converter=Path)
    artifact_root: Path = attrs.field(converter=Path)
    mode: MoldCookMode = MoldCookMode.FULL
    explicit_kind: MoldCookInputKind | None = None
    holds: tuple[CookExecutionHold, ...] = attrs.field(factory=tuple)


@attrs.define(frozen=True)
class SetupEvidence:
    """The bounded host-runner proof accepted by Cook before feature execution."""

    prerequisite_curd_id: str
    plan_digest: str
    authorization_digest: str
    runner_command: str
    fixture_path: str
    environment_id: str
    exit_code: int
    captured_output_digest: str

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "SetupEvidence":
        values = require_mapping(raw, "setup evidence")
        required = (
            "prerequisite_curd_id",
            "plan_digest",
            "authorization_digest",
            "runner_command",
            "fixture_path",
            "environment_id",
            "exit_code",
            "captured_output_digest",
        )
        try:
            require_exact_keys(values, required, "setup evidence")
            return cls(
                prerequisite_curd_id=require_str(
                    values["prerequisite_curd_id"],
                    "setup evidence prerequisite_curd_id",
                ),
                plan_digest=require_str(
                    values["plan_digest"], "setup evidence plan_digest"
                ),
                authorization_digest=require_str(
                    values["authorization_digest"],
                    "setup evidence authorization_digest",
                ),
                runner_command=require_str(
                    values["runner_command"], "setup evidence runner_command"
                ),
                fixture_path=require_relative_path(
                    values["fixture_path"], "setup evidence fixture_path"
                ),
                environment_id=require_str(
                    values["environment_id"], "setup evidence environment_id"
                ),
                exit_code=require_int(values["exit_code"], "setup evidence exit_code"),
                captured_output_digest=require_str(
                    values["captured_output_digest"],
                    "setup evidence captured_output_digest",
                ),
            )
        except ValueError as exc:
            raise CookEvidenceError(str(exc)) from exc


@attrs.define(frozen=True)
class CookHoldClearance:
    """One explicit user response that clears a named execution hold."""

    hold_id: str
    response_ref: ArtifactRef = attrs.field(
        validator=attrs.validators.instance_of(ArtifactRef)
    )
    response_text: str

    def __attrs_post_init__(self) -> None:
        if not self.hold_id or not self.response_text.strip():
            raise ValueError("hold clearance requires a hold ID and response text")


@attrs.define(frozen=True)
class CookExecutionOutcome:
    """Durable binding for one accepted handoff execution."""

    request_id: str
    handoff_ref: ArtifactRef
    planner_result_ref: ArtifactRef
    plan_ref: ArtifactRef
    coverage: MoldCookCoverage
    completed_curds: tuple[str, ...]
    remainder: tuple[PlannerUncertainty, ...]
    whole_task_complete: bool
    resumable_ref: ArtifactRef
    execution_results: workflow.ExecutionResults = attrs.field(repr=False)
    outcome_ref: ArtifactRef | None = None
    fan_next_step: str | None = None
    remediation_state_refs: tuple[ArtifactRef, ...] = attrs.field(factory=tuple)
    stop_evidence_refs: tuple[ArtifactRef, ...] = attrs.field(factory=tuple)
    remediation_request_ref: ArtifactRef | None = None
    execution_result_refs: tuple[ArtifactRef, ...] = attrs.field(factory=tuple)
    scope_summaries: Mapping[str, ScopeRemediationSummary] = attrs.field(
        factory=lambda: cast(dict[str, ScopeRemediationSummary], {})
    )


@attrs.define(frozen=True)
class LegacyPlanMigration:
    """Typed read-only bridge from an intact historical CurdPlan pointer."""

    plan: CurdPlan
    plan_ref: ArtifactRef
    normalization_receipt_ref: ArtifactRef | None = None


@attrs.define(frozen=True)
class RunnerSetup:
    runner_approval_ref: ArtifactRef | None
    setup_evidence_refs: tuple[ArtifactRef, ...]


ApprovalSource: TypeAlias = (
    MoldCookApproval | ArtifactRef | str | Path | Mapping[str, object]
)
SetupAuthorizationSource: TypeAlias = (
    CookSetupAuthorization | ArtifactRef | Mapping[str, object] | str | Path
)
SetupEvidenceSource: TypeAlias = (
    SetupEvidence | Mapping[str, object] | ArtifactRef | str | Path
)


@attrs.define(frozen=True, kw_only=True)
class PreparationEvidence:
    """Every host-owned input one preparation round reads, declared once.

    ``prepare`` and ``resubmit`` take this record instead of forwarding each
    field, so the two entry points cannot drift apart. ``clearances`` is read
    by ``resubmit`` alone; every other field reaches ``prepare``.
    """

    scope_approval: ApprovalSource | None = None
    plan_approval: ApprovalSource | None = None
    runner_approval: ApprovalSource | None = None
    planner_result: PlannerResult | ArtifactRef | str | Path | None = None
    planner_view: PlannerResultWriterView | None = None
    planner_dispatch: Callable[[PlannerRequest], object] | None = None
    setup_authorization: SetupAuthorizationSource | None = None
    setup_evidence: SetupEvidenceSource | None = None
    spec_binding: ArtifactRef | str | Path | None = None
    holds: Sequence[CookExecutionHold] = ()
    clearances: Sequence[CookHoldClearance] = ()
    previous: CookPreparationResult | None = None


@attrs.define(frozen=True)
class PreparationContext:
    """Every value one preparation round shares across its stages."""

    request: CookPreparationRequest
    classified: ClassifiedCookInput
    refs: list[ArtifactRef]
    evidence: PreparationEvidence
    root: Path
    artifacts: Path
    previous: CookPreparationResult | None = None


@attrs.define(frozen=True)
class ResolvedPreparationSource:
    processing_source: ClassifiedCookInput
    objective: str
    planner_value: PlannerResult | None = None
    planner_ref: ArtifactRef | None = None
    plan_ref: ArtifactRef | None = None
    spec_ref: ArtifactRef | None = None
    readiness: MoldCookSpecReadiness | None = None
    legacy_mode: bool = False


@attrs.define(frozen=True)
class SpecStage:
    """The canonical spec this round reads, with the source it processes."""

    processing_source: ClassifiedCookInput
    objective: str
    spec_ref: ArtifactRef
    spec_raw: bytes
    readiness: MoldCookSpecReadiness | None


@attrs.define(frozen=True)
class MaterializedPlan:
    """The persisted planner result and the plan it carries."""

    planner_ref: ArtifactRef
    plan: CurdPlan
    plan_ref: ArtifactRef
    candidate_coverage: MoldCookCoverage


@attrs.define(frozen=True)
class ApprovedPlan:
    """The bound plan approval and the coverage it authorizes."""

    approval_ref: ArtifactRef
    coverage: MoldCookCoverage
