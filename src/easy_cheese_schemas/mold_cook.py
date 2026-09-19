"""Pure contracts for the Mold-to-Cook preparation boundary.

The phase payload deliberately contains references rather than copies of plans,
proposals, or continuity records. Hosts resolve those references and validate
that every identity still denotes the bytes that were approved before they
publish or execute a handoff.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol, TypeVar, cast

from attrs import Attribute, define, field, validators

from ._schema_catalog import SCHEMA_ROOT
from .contracts import (
    ArtifactRef,
    ContractVersion,
    PlannerRequest,
    PlannerUncertainty,
    _bounded_string,  # pyright: ignore[reportPrivateUsage]
    _digest,  # pyright: ignore[reportPrivateUsage]
    _identifier,  # pyright: ignore[reportPrivateUsage]
    _identifier_list,  # pyright: ignore[reportPrivateUsage]
    _if_equals,  # pyright: ignore[reportPrivateUsage]
    _list_of,  # pyright: ignore[reportPrivateUsage]
    _optional_string,  # pyright: ignore[reportPrivateUsage]
    _string_list,  # pyright: ignore[reportPrivateUsage]
    _tuple_sequence,  # pyright: ignore[reportPrivateUsage]
    contract,
    schema_constraints,
)


MOLD_COOK_HANDOFF_SCHEMA_URI = f"{SCHEMA_ROOT}/mold-cook-handoff"
MOLD_COOK_APPROVAL_SCHEMA_URI = f"{SCHEMA_ROOT}/mold-cook-approval"
COOK_PREPARATION_RESULT_SCHEMA_URI = f"{SCHEMA_ROOT}/cook-preparation-result"


class MoldCookMode(str, Enum):
    """The planning ceremony required by a handoff."""

    LIGHT = "light"
    FULL = "full"


class MoldCookInputKind(str, Enum):
    """The classified Cook ingress that created a request."""

    DIRECT_SPEC = "direct_spec"
    SLUG = "slug"
    TASK = "task"
    CANONICAL_POINTER = "canonical_pointer"
    CONTINUATION = "continuation"


class MoldCookApprovalKind(str, Enum):
    """The bounded decision represented by an approval record."""

    SCOPE = "scope"
    PLAN = "plan"
    PARTIAL_PLAN = "partial_plan"
    RUNNER = "runner"


class MoldCookApprovalDecision(str, Enum):
    """An explicit user response; only ``APPROVED`` can authorize a handoff."""

    APPROVED = "approved"
    REJECTED = "rejected"
    CLARIFICATION = "clarification"


class MoldCookApprovalSource(str, Enum):
    """Where the host obtained the explicit response."""

    USER_RESPONSE = "user_response"
    LOCAL_DIALOGUE = "local_dialogue"


class CookPreparationOutcome(str, Enum):
    """Closed preparation result vocabulary."""

    READY = "ready"
    NEEDS_PLANNING = "needs-planning"
    NEEDS_APPROVAL = "needs-approval"
    NEEDS_PREPARATION = "needs-preparation"
    BLOCKED = "blocked"
    INVALID = "invalid"


class CookHoldKind(str, Enum):
    """Why a Cook request cannot authorize feature writes."""

    USER_INTENT = "user_intent"
    PREPARATION = "preparation"
    INTEGRITY = "integrity"
    BLOCKED = "blocked"


class CookRequirementKind(str, Enum):
    """A typed requirement that must be evidenced before preparation advances."""

    SCOPE = "scope"
    PLAN = "plan"
    APPROVAL = "approval"
    RUNNER = "runner"
    EVIDENCE = "evidence"
    INTEGRITY = "integrity"


_T = TypeVar("_T")


class _Validator(Protocol[_T]):
    def __call__(  # noqa: V103
        self, instance: object, attribute: Attribute[_T], value: _T, /
    ) -> None: ...


def _all_of(*checks: _Validator[_T]) -> _Validator[_T]:
    def validate(instance: object, attribute: Attribute[_T], value: _T) -> None:
        for check in checks:
            check(instance, attribute, value)

    return validate


def _artifact_role(expected: str) -> _Validator[ArtifactRef]:
    def validate(
        _instance: object,
        attribute: Attribute[ArtifactRef],
        value: ArtifactRef,
    ) -> None:
        if value.role != expected:
            raise ValueError(f"{attribute.name} must use artifact role {expected!r}")

    return validate


def _typed_artifact_role(expected: str) -> _Validator[ArtifactRef]:
    role_validator = _artifact_role(expected)

    def validate(
        instance: object,
        attribute: Attribute[ArtifactRef],
        value: ArtifactRef,
    ) -> None:
        role_validator(instance, attribute, value)
        if value.schema_uri is None:
            raise ValueError(f"{attribute.name} must carry a schema_uri")

    return validate


def _artifact_roles(*expected: str) -> _Validator[ArtifactRef]:
    allowed = frozenset(expected)

    def validate(
        _instance: object, attribute: Attribute[object], value: object
    ) -> None:
        if not isinstance(value, ArtifactRef):
            raise TypeError(f"{attribute.name} must be an ArtifactRef")
        if value.role not in allowed:
            options = ", ".join(sorted(allowed))
            raise ValueError(f"{attribute.name} must use one of these roles: {options}")

    return cast(_Validator[ArtifactRef], validate)


def _schema_uri(expected: str) -> _Validator[ArtifactRef]:
    def validate(
        _instance: object, attribute: Attribute[object], value: object
    ) -> None:
        if not isinstance(value, ArtifactRef):
            raise TypeError(f"{attribute.name} must be an ArtifactRef")
        if value.schema_uri != expected:
            raise ValueError(f"{attribute.name} must use schema_uri {expected!r}")

    return cast(_Validator[ArtifactRef], validate)


def _optional_schema_uri(expected: str) -> _Validator[ArtifactRef | None]:
    schema_validator = _schema_uri(expected)

    def validate(
        instance: object,
        attribute: Attribute[ArtifactRef | None],
        value: ArtifactRef | None,
    ) -> None:
        if value is not None:
            schema_validator(instance, cast("Attribute[ArtifactRef]", attribute), value)

    return validate


def _optional_artifact_schema(
    expected: str, role: str
) -> _Validator[ArtifactRef | None]:
    optional_role = validators.optional(_artifact_role(role))
    return _all_of(optional_role, _optional_schema_uri(expected))


def _digest_matches(reference_name: str) -> _Validator[str]:
    def validate(instance: object, attribute: Attribute[str], value: str) -> None:
        _digest(instance, attribute, value)
        approval = cast("MoldCookApproval", instance)
        if reference_name == "proposal_ref":
            reference = approval.proposal_ref
        elif reference_name == "response_ref":
            reference = approval.response_ref
        else:
            raise ValueError(f"unsupported approval reference {reference_name!r}")
        if value != reference.digest:
            raise ValueError(f"{attribute.name} must match {reference_name}.digest")

    return validate


def _forbid(*field_names: str) -> dict[str, object]:
    empty_or_null: dict[str, object] = {
        "anyOf": [
            {"type": "null"},
            {"type": "array", "maxItems": 0},
        ]
    }
    return {
        "not": {
            "anyOf": [
                {
                    "required": [name],
                    "properties": {name: {"not": empty_or_null}},
                }
                for name in field_names
            ]
        }
    }


@define(frozen=True)
class MoldCookCoverage:
    """Exact runnable IDs and the acknowledged PlannerResult remainder."""

    curd_ids: tuple[str, ...] = field(
        converter=_tuple_sequence,
        validator=_identifier_list(non_empty=True),
    )
    unresolved_work: tuple[PlannerUncertainty, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(PlannerUncertainty),
    )


@define(frozen=True)
class CookExecutionHold:
    """An explicit hold that prevents feature execution."""

    hold_id: str = field(validator=_identifier)
    kind: CookHoldKind = field(validator=validators.instance_of(CookHoldKind))
    reason: str = field(validator=_bounded_string)
    evidence: tuple[ArtifactRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(ArtifactRef),
    )


@define(frozen=True)
class CookSetupAuthorization:
    """Setup-only authority for one named prerequisite curd."""

    prerequisite_curd_id: str = field(validator=_identifier)
    allowed_paths: tuple[str, ...] = field(
        converter=_tuple_sequence,
        validator=_string_list(non_empty=True, path=True),
    )
    allowed_commands: tuple[str, ...] = field(
        converter=_tuple_sequence,
        validator=_string_list(non_empty=True),
    )


@define(frozen=True)
class CookUnmetRequirement:
    """A blocked preparation requirement and the evidence needed to clear it."""

    requirement_id: str = field(validator=_identifier)
    kind: CookRequirementKind = field(
        validator=validators.instance_of(CookRequirementKind)
    )
    description: str = field(validator=_bounded_string)
    evidence: tuple[ArtifactRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(ArtifactRef),
    )


@define(frozen=True)
class CookValidationFinding:
    """A typed, non-recoverable validation finding."""

    code: str = field(validator=_identifier)
    message: str = field(validator=_bounded_string)
    path: str | None = field(default=None, validator=_optional_string)


@contract("mold-cook-approval")
@schema_constraints(
    _if_equals("kind", MoldCookApprovalKind.PLAN.value, {"required": ["plan_digest"]}),
    _if_equals(
        "kind",
        MoldCookApprovalKind.PARTIAL_PLAN.value,
        {"required": ["plan_digest"]},
    ),
    _if_equals(
        "kind",
        MoldCookApprovalKind.RUNNER.value,
        {"required": ["setup_authorization"]},
    ),
)
@define(frozen=True)
class MoldCookApproval:
    """Durable, exact approval evidence for one Mold-to-Cook request."""

    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    request_id: str = field(validator=_identifier)
    kind: MoldCookApprovalKind = field(
        validator=validators.instance_of(MoldCookApprovalKind)
    )
    decision: MoldCookApprovalDecision = field(
        validator=validators.instance_of(MoldCookApprovalDecision)
    )
    source: MoldCookApprovalSource = field(
        validator=validators.instance_of(MoldCookApprovalSource)
    )
    spec_digest: str = field(validator=_digest)
    proposal_ref: ArtifactRef = field(validator=_artifact_role("proposal"))
    proposal_digest: str = field(validator=_digest_matches("proposal_ref"))
    response_ref: ArtifactRef = field(validator=_artifact_roles("response", "dialogue"))
    response_digest: str = field(validator=_digest_matches("response_ref"))
    response_text: str = field(validator=_bounded_string)
    response_source: str = field(validator=_bounded_string)
    coverage: MoldCookCoverage = field(
        validator=validators.instance_of(MoldCookCoverage)
    )
    plan_digest: str | None = field(default=None, validator=_optional_string)
    setup_authorization: CookSetupAuthorization | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(CookSetupAuthorization)),
    )

    def __attrs_post_init__(self) -> None:
        if self.proposal_ref.schema_uri == MOLD_COOK_APPROVAL_SCHEMA_URI:
            raise ValueError("approval proposal must not be an approval artifact")
        expected_role = (
            "dialogue"
            if self.source is MoldCookApprovalSource.LOCAL_DIALOGUE
            else "response"
        )
        if self.response_ref.role != expected_role:
            raise ValueError(
                f"{self.source.value} approval requires a {expected_role} artifact"
            )
        requires_plan = self.kind in {
            MoldCookApprovalKind.PLAN,
            MoldCookApprovalKind.PARTIAL_PLAN,
        }
        if requires_plan and self.plan_digest is None:
            raise ValueError(f"{self.kind.value} approval requires plan_digest")
        if not requires_plan and self.plan_digest is not None:
            raise ValueError(f"{self.kind.value} approval must not carry plan_digest")
        if (
            self.kind is MoldCookApprovalKind.RUNNER
            and self.setup_authorization is None
        ):
            raise ValueError("runner approval requires setup_authorization")
        if (
            self.kind is not MoldCookApprovalKind.RUNNER
            and self.setup_authorization is not None
        ):
            raise ValueError(
                f"{self.kind.value} approval must not carry setup_authorization"
            )


@contract("mold-cook-handoff")
@schema_constraints(
    _if_equals(
        "mode",
        MoldCookMode.LIGHT.value,
        {
            "properties": {
                "planner_result_ref": {"type": "null"},
                "plan_ref": {"type": "null"},
            }
        },
    ),
    _if_equals(
        "mode",
        MoldCookMode.FULL.value,
        {"required": ["planner_result_ref", "plan_ref"]},
    ),
)
@define(frozen=True)
class MoldCookHandoff:
    """Canonical phase payload consumed by Cook after approval."""

    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    request_id: str = field(validator=_identifier)
    input_kind: MoldCookInputKind = field(
        validator=validators.instance_of(MoldCookInputKind)
    )
    mode: MoldCookMode = field(validator=validators.instance_of(MoldCookMode))
    spec_ref: ArtifactRef = field(validator=_artifact_role("spec"))
    approval_ref: ArtifactRef = field(
        validator=_all_of(
            _artifact_role("approval"),
            _schema_uri(MOLD_COOK_APPROVAL_SCHEMA_URI),
        )
    )
    coverage: MoldCookCoverage = field(
        validator=validators.instance_of(MoldCookCoverage)
    )
    planner_result_ref: ArtifactRef | None = field(
        default=None,
        validator=_optional_artifact_schema(
            f"{SCHEMA_ROOT}/planner-result", "planner_result"
        ),
    )
    plan_ref: ArtifactRef | None = field(
        default=None,
        validator=_optional_artifact_schema(f"{SCHEMA_ROOT}/curd-plan", "curd_plan"),
    )
    taste_verdict_ref: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(_typed_artifact_role("taste_verdict")),
    )
    taste_ledger_ref: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(_typed_artifact_role("taste_ledger")),
    )
    runner_approval_ref: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(
            _all_of(
                _artifact_role("runner_approval"),
                _schema_uri(MOLD_COOK_APPROVAL_SCHEMA_URI),
            )
        ),
    )
    setup_evidence_refs: tuple[ArtifactRef, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(ArtifactRef),
    )

    def __attrs_post_init__(self) -> None:
        for reference in self.setup_evidence_refs:
            if reference.role != "setup_evidence":
                raise ValueError(
                    "setup_evidence_refs must use artifact role 'setup_evidence'"
                )
            if reference.schema_uri is None:
                raise ValueError("setup_evidence_refs must carry a schema_uri")
        if self.mode is MoldCookMode.FULL:
            if self.planner_result_ref is None or self.plan_ref is None:
                raise ValueError(
                    "full handoff requires planner_result_ref and plan_ref"
                )
        else:
            if self.planner_result_ref is not None or self.plan_ref is not None:
                raise ValueError(
                    "light handoff must not carry planner or plan references"
                )
            if len(self.coverage.curd_ids) != 1:
                raise ValueError("light handoff coverage must contain exactly one curd")
        if (self.taste_verdict_ref is None) != (self.taste_ledger_ref is None):
            raise ValueError(
                "taste_verdict_ref and taste_ledger_ref must be supplied together"
            )


@contract("cook-preparation-result")
@schema_constraints(
    _if_equals(
        "outcome",
        CookPreparationOutcome.READY.value,
        {
            "required": ["handoff_ref", "coverage"],
            "properties": {"holds": {"maxItems": 0}},
            **_forbid(
                "approved_scope_ref",
                "planner_request",
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
                "approved_plan_ref",
                "setup_authorization",
                "requirements",
                "findings",
            ),
        },
    ),
    _if_equals(
        "outcome",
        CookPreparationOutcome.NEEDS_PLANNING.value,
        {
            "required": ["approved_scope_ref", "planner_request"],
            **_forbid(
                "handoff_ref",
                "coverage",
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
                "approved_plan_ref",
                "setup_authorization",
                "requirements",
                "findings",
            ),
        },
    ),
    _if_equals(
        "outcome",
        CookPreparationOutcome.NEEDS_APPROVAL.value,
        {
            "required": [
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
            ],
            **_forbid(
                "handoff_ref",
                "coverage",
                "approved_scope_ref",
                "planner_request",
                "approved_plan_ref",
                "setup_authorization",
                "requirements",
                "findings",
            ),
        },
    ),
    _if_equals(
        "outcome",
        CookPreparationOutcome.NEEDS_PREPARATION.value,
        {
            "required": ["approved_plan_ref", "coverage", "setup_authorization"],
            **_forbid(
                "handoff_ref",
                "approved_scope_ref",
                "planner_request",
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
                "requirements",
                "findings",
            ),
        },
    ),
    _if_equals(
        "outcome",
        CookPreparationOutcome.BLOCKED.value,
        {
            "anyOf": [
                {"properties": {"requirements": {"minItems": 1}}},
                {"properties": {"holds": {"minItems": 1}}},
            ],
            **_forbid(
                "handoff_ref",
                "coverage",
                "approved_scope_ref",
                "planner_request",
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
                "approved_plan_ref",
                "setup_authorization",
                "findings",
            ),
        },
    ),
    _if_equals(
        "outcome",
        CookPreparationOutcome.INVALID.value,
        {
            "properties": {"findings": {"minItems": 1}},
            **_forbid(
                "handoff_ref",
                "coverage",
                "approved_scope_ref",
                "planner_request",
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
                "approved_plan_ref",
                "setup_authorization",
                "requirements",
            ),
        },
    ),
)
@define(frozen=True)
class CookPreparationResult:
    """Closed, non-executing preparation outcomes."""

    contract_version: ContractVersion = field(
        validator=validators.instance_of(ContractVersion)
    )
    request_id: str = field(validator=_identifier)
    input_kind: MoldCookInputKind = field(
        validator=validators.instance_of(MoldCookInputKind)
    )
    outcome: CookPreparationOutcome = field(
        validator=validators.instance_of(CookPreparationOutcome)
    )
    references: tuple[ArtifactRef, ...] = field(
        converter=_tuple_sequence,
        validator=_list_of(ArtifactRef, non_empty=True),
    )
    holds: tuple[CookExecutionHold, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(CookExecutionHold),
    )
    handoff_ref: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(_artifact_role("handoff")),
    )
    coverage: MoldCookCoverage | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(MoldCookCoverage)),
    )
    approved_scope_ref: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(_artifact_role("approved_scope")),
    )
    planner_request: PlannerRequest | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(PlannerRequest)),
    )
    approval_kind: MoldCookApprovalKind | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(MoldCookApprovalKind)),
    )
    proposal_ref: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(_artifact_role("proposal")),
    )
    proposal_digest: str | None = field(default=None, validator=_optional_string)
    missing_decision: str | None = field(default=None, validator=_optional_string)
    approved_plan_ref: ArtifactRef | None = field(
        default=None,
        validator=validators.optional(_artifact_role("curd_plan")),
    )
    setup_authorization: CookSetupAuthorization | None = field(
        default=None,
        validator=validators.optional(validators.instance_of(CookSetupAuthorization)),
    )
    requirements: tuple[CookUnmetRequirement, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(CookUnmetRequirement),
    )
    findings: tuple[CookValidationFinding, ...] = field(
        factory=tuple,
        converter=_tuple_sequence,
        validator=_list_of(CookValidationFinding),
    )

    def __attrs_post_init__(self) -> None:
        payload_fields = (
            "handoff_ref",
            "coverage",
            "approved_scope_ref",
            "planner_request",
            "approval_kind",
            "proposal_ref",
            "proposal_digest",
            "missing_decision",
            "approved_plan_ref",
            "setup_authorization",
        )
        populated = {name for name in payload_fields if getattr(self, name) is not None}
        allowed: set[str]
        if self.outcome is CookPreparationOutcome.READY:
            if self.handoff_ref is None or self.coverage is None:
                raise ValueError("ready preparation requires handoff_ref and coverage")
            if self.holds or self.requirements or self.findings:
                raise ValueError("ready preparation must not carry holds or findings")
            allowed = {"handoff_ref", "coverage"}
        elif self.outcome is CookPreparationOutcome.NEEDS_PLANNING:
            if self.approved_scope_ref is None or self.planner_request is None:
                raise ValueError(
                    "needs-planning preparation requires approved_scope_ref and planner_request"
                )
            allowed = {"approved_scope_ref", "planner_request"}
        elif self.outcome is CookPreparationOutcome.NEEDS_APPROVAL:
            if (
                self.approval_kind is None
                or self.proposal_ref is None
                or self.proposal_digest is None
                or self.missing_decision is None
            ):
                raise ValueError(
                    "needs-approval preparation requires approval kind, proposal, digest, and decision"
                )
            if self.proposal_digest != self.proposal_ref.digest:
                raise ValueError("proposal_digest must match proposal_ref.digest")
            allowed = {
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
            }
        elif self.outcome is CookPreparationOutcome.NEEDS_PREPARATION:
            if (
                self.approved_plan_ref is None
                or self.coverage is None
                or self.setup_authorization is None
            ):
                raise ValueError(
                    "needs-preparation requires approved_plan_ref, coverage, and setup authorization"
                )
            allowed = {"approved_plan_ref", "coverage", "setup_authorization"}
        elif self.outcome is CookPreparationOutcome.BLOCKED:
            if not self.requirements and not self.holds:
                raise ValueError("blocked preparation requires requirements or holds")
            allowed = set()
        else:
            if not self.findings:
                raise ValueError("invalid preparation requires validation findings")
            if self.holds or self.requirements:
                raise ValueError("invalid preparation must not carry execution holds")
            allowed = set()
        unexpected = populated - allowed
        if unexpected:
            names = ", ".join(sorted(unexpected))
            raise ValueError(
                f"{self.outcome.value} preparation carries fields for another outcome: {names}"
            )


MOLD_COOK_CONTRACTS: tuple[tuple[str, type], ...] = (
    ("cook-preparation-result", CookPreparationResult),
    ("mold-cook-approval", MoldCookApproval),
    ("mold-cook-handoff", MoldCookHandoff),
)


def registered_contracts() -> tuple[tuple[str, type], ...]:
    """Return Mold-to-Cook contracts for package-wide schema discovery."""
    return MOLD_COOK_CONTRACTS


__all__ = [
    "COOK_PREPARATION_RESULT_SCHEMA_URI",
    "MOLD_COOK_APPROVAL_SCHEMA_URI",
    "MOLD_COOK_CONTRACTS",
    "MOLD_COOK_HANDOFF_SCHEMA_URI",
    "CookExecutionHold",
    "CookHoldKind",
    "CookPreparationOutcome",
    "CookPreparationResult",
    "CookRequirementKind",
    "CookSetupAuthorization",
    "CookUnmetRequirement",
    "CookValidationFinding",
    "MoldCookApproval",
    "MoldCookApprovalDecision",
    "MoldCookApprovalKind",
    "MoldCookApprovalSource",
    "MoldCookCoverage",
    "MoldCookHandoff",
    "MoldCookInputKind",
    "MoldCookMode",
    "registered_contracts",
]
