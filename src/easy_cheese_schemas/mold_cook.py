"""Pure contracts for the Mold-to-Cook preparation boundary.

The phase payload deliberately contains references rather than copies of plans,
proposals, or continuity records. Hosts resolve those references and validate
that every identity still denotes the bytes that were approved before they
publish or execute a handoff.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from enum import Enum
from typing import NamedTuple, cast

from attrs import define, field, validators

from ._schema_catalog import (
    COOK_PREPARATION_RESULT_SCHEMA_URI,
    MOLD_COOK_APPROVAL_SCHEMA_URI,
    MOLD_COOK_HANDOFF_SCHEMA_URI,
    SCHEMA_ROOT,
)
from .contracts import (
    ArtifactRef,
    ContractVersion,
    PlannerRequest,
    PlannerUncertainty,
    Validator,
    _bounded_string,  # pyright: ignore[reportPrivateUsage]
    _digest,  # pyright: ignore[reportPrivateUsage]
    _identifier,  # pyright: ignore[reportPrivateUsage]
    _identifier_list,  # pyright: ignore[reportPrivateUsage]
    _if_equals,  # pyright: ignore[reportPrivateUsage]
    _list_of,  # pyright: ignore[reportPrivateUsage]
    _NamedAttribute,  # pyright: ignore[reportPrivateUsage]
    _optional_string,  # pyright: ignore[reportPrivateUsage]
    _string_list,  # pyright: ignore[reportPrivateUsage]
    _tuple_sequence,  # pyright: ignore[reportPrivateUsage]
    contract,
    marked_contracts_in,
    schema_constraints,
)


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


_ARTIFACT_REF: dict[str, object] = {"$ref": "#/$defs/ArtifactRef"}
_SETUP_AUTHORIZATION: dict[str, object] = {"$ref": "#/$defs/CookSetupAuthorization"}
_STRING: dict[str, object] = {"type": "string"}
_NULL: dict[str, object] = {"type": "null"}

_RESPONSE_ROLES: frozenset[str] = frozenset({"response", "dialogue"})


def _as_artifact_ref(attribute: _NamedAttribute, value: object) -> ArtifactRef:
    if not isinstance(value, ArtifactRef):
        raise TypeError(f"{attribute.name} must be an ArtifactRef")
    return value


def _artifact_role(expected: str) -> Validator:
    def validate(_instance: object, attribute: _NamedAttribute, value: object) -> None:
        if _as_artifact_ref(attribute, value).role != expected:
            raise ValueError(f"{attribute.name} must use artifact role {expected!r}")

    return validate


def _typed_artifact_role(expected: str) -> Validator:
    def validate(_instance: object, attribute: _NamedAttribute, value: object) -> None:
        reference = _as_artifact_ref(attribute, value)
        if reference.role != expected:
            raise ValueError(f"{attribute.name} must use artifact role {expected!r}")
        if reference.schema_uri is None:
            raise ValueError(f"{attribute.name} must carry a schema_uri")

    return validate


def _response_or_dialogue_role(
    _instance: object, attribute: _NamedAttribute, value: object
) -> None:
    """Accept the two artifact roles that can carry an explicit user response."""
    if _as_artifact_ref(attribute, value).role not in _RESPONSE_ROLES:
        options = ", ".join(sorted(_RESPONSE_ROLES))
        raise ValueError(f"{attribute.name} must use one of these roles: {options}")


def _schema_uri(expected: str) -> Validator:
    def validate(_instance: object, attribute: _NamedAttribute, value: object) -> None:
        if _as_artifact_ref(attribute, value).schema_uri != expected:
            raise ValueError(f"{attribute.name} must use schema_uri {expected!r}")

    return validate


def _optional_artifact_schema(expected: str, role: str) -> Validator:
    role_check = _artifact_role(role)
    uri_check = _schema_uri(expected)

    def validate(instance: object, attribute: _NamedAttribute, value: object) -> None:
        if value is None:
            return
        role_check(instance, attribute, value)
        uri_check(instance, attribute, value)

    return validate


def _approval_of(instance: object) -> MoldCookApproval:
    if not isinstance(instance, MoldCookApproval):
        raise TypeError("approval digest validators require a MoldCookApproval")
    return instance


def _proposal_digest_matches(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    """Require ``proposal_digest`` to repeat ``proposal_ref.digest`` exactly."""
    _digest(instance, attribute, value)
    if value != _approval_of(instance).proposal_ref.digest:
        raise ValueError(f"{attribute.name} must match proposal_ref.digest")


def _response_digest_matches(
    instance: object, attribute: _NamedAttribute, value: object
) -> None:
    """Require ``response_digest`` to repeat ``response_ref.digest`` exactly."""
    _digest(instance, attribute, value)
    if value != _approval_of(instance).response_ref.digest:
        raise ValueError(f"{attribute.name} must match response_ref.digest")


def _requires(**fields: Mapping[str, object]) -> dict[str, object]:
    """Require each field and narrow it to the schema its runtime type allows.

    ``required`` alone is satisfied by an explicit ``null``, so every
    conditionally mandatory field also drops the null member of its union.
    """
    return {
        "required": list(fields),
        "properties": {name: dict(schema) for name, schema in fields.items()},
    }


def _artifact_binding(
    field_name: str, role: str, schema_uri: str | None = None
) -> dict[str, object]:
    """Publish the artifact role, and schema identity, one reference must carry."""
    identity: dict[str, object] = {"role": {"const": role}}
    if schema_uri is not None:
        identity["schema_uri"] = {"const": schema_uri}
    return {"properties": {field_name: {"properties": identity}}}


def _paired_or_absent(first: str, second: str) -> dict[str, object]:
    """Require two optional references to appear together, or not at all."""
    return {
        "anyOf": [
            {"properties": {first: _NULL, second: _NULL}},
            _requires(**{first: {"not": _NULL}, second: {"not": _NULL}}),
        ]
    }


_OUTCOME_PAYLOAD_FIELDS: frozenset[str] = frozenset(
    {
        "approval_kind",
        "approved_plan_ref",
        "approved_scope_ref",
        "coverage",
        "findings",
        "handoff_ref",
        "holds",
        "missing_decision",
        "planner_request",
        "proposal_digest",
        "proposal_ref",
        "requirements",
        "setup_authorization",
    }
)

_OUTCOME_SEQUENCE_FIELDS: frozenset[str] = frozenset(
    {"findings", "holds", "requirements"}
)

_OUTCOME_PAYLOAD_SCHEMAS: dict[str, dict[str, object]] = {
    "approval_kind": _STRING,
    "approved_plan_ref": _ARTIFACT_REF,
    "approved_scope_ref": _ARTIFACT_REF,
    "coverage": {"$ref": "#/$defs/MoldCookCoverage"},
    "handoff_ref": _ARTIFACT_REF,
    "missing_decision": _STRING,
    "planner_request": {"$ref": "#/$defs/PlannerRequest"},
    "proposal_digest": _STRING,
    "proposal_ref": _ARTIFACT_REF,
    "setup_authorization": _SETUP_AUTHORIZATION,
}


class _OutcomeFields(NamedTuple):
    """The payload fields one preparation outcome requires and permits."""

    required: frozenset[str] = frozenset()
    any_of: frozenset[str] = frozenset()
    optional: frozenset[str] = frozenset()

    @property
    def allowed(self) -> frozenset[str]:
        return self.required | self.any_of | self.optional


_OPTIONAL_HOLDS: frozenset[str] = frozenset({"holds"})

_OUTCOME_FIELDS: dict[CookPreparationOutcome, _OutcomeFields] = {
    CookPreparationOutcome.READY: _OutcomeFields(
        required=frozenset({"handoff_ref", "coverage"}),
    ),
    CookPreparationOutcome.NEEDS_PLANNING: _OutcomeFields(
        required=frozenset({"approved_scope_ref", "planner_request"}),
        optional=_OPTIONAL_HOLDS,
    ),
    CookPreparationOutcome.NEEDS_APPROVAL: _OutcomeFields(
        required=frozenset(
            {
                "approval_kind",
                "proposal_ref",
                "proposal_digest",
                "missing_decision",
            }
        ),
        optional=_OPTIONAL_HOLDS,
    ),
    CookPreparationOutcome.NEEDS_PREPARATION: _OutcomeFields(
        required=frozenset({"approved_plan_ref", "coverage", "setup_authorization"}),
        optional=_OPTIONAL_HOLDS,
    ),
    CookPreparationOutcome.BLOCKED: _OutcomeFields(
        any_of=frozenset({"requirements", "holds"}),
    ),
    CookPreparationOutcome.INVALID: _OutcomeFields(
        required=frozenset({"findings"}),
    ),
}


def _non_empty(name: str) -> dict[str, object]:
    return {"required": [name], "properties": {name: {"minItems": 1}}}


def _forbid(*field_names: str) -> dict[str, object]:
    """Reject a branch that carries any of ``field_names`` non-null and non-empty."""
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


def _outcome_constraints() -> tuple[dict[str, object], ...]:
    """Derive one ``if``/``then`` branch per outcome from ``_OUTCOME_FIELDS``."""
    branches: list[dict[str, object]] = []
    for outcome, fields in _OUTCOME_FIELDS.items():
        then: dict[str, object] = {}
        if fields.required:
            then["required"] = sorted(fields.required)
            then["properties"] = {
                name: (
                    {"minItems": 1}
                    if name in _OUTCOME_SEQUENCE_FIELDS
                    else dict(_OUTCOME_PAYLOAD_SCHEMAS[name])
                )
                for name in sorted(fields.required)
            }
        if fields.any_of:
            then["anyOf"] = [_non_empty(name) for name in sorted(fields.any_of)]
        then.update(_forbid(*sorted(_OUTCOME_PAYLOAD_FIELDS - fields.allowed)))
        branches.append(_if_equals("outcome", outcome.value, then))
    return tuple(branches)


def _is_populated(value: object) -> bool:
    if isinstance(value, tuple):
        return bool(cast("tuple[object, ...]", value))
    return value is not None


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
    _if_equals(
        "kind",
        MoldCookApprovalKind.PLAN.value,
        _requires(plan_digest=_STRING),
    ),
    _if_equals(
        "kind",
        MoldCookApprovalKind.PARTIAL_PLAN.value,
        _requires(plan_digest=_STRING),
    ),
    _if_equals(
        "kind",
        MoldCookApprovalKind.RUNNER.value,
        _requires(setup_authorization=_SETUP_AUTHORIZATION),
    ),
    _artifact_binding("proposal_ref", "proposal"),
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
    proposal_digest: str = field(validator=_proposal_digest_matches)
    response_ref: ArtifactRef = field(validator=_response_or_dialogue_role)
    response_digest: str = field(validator=_response_digest_matches)
    response_text: str = field(validator=_bounded_string)
    response_source: str = field(validator=_bounded_string)
    coverage: MoldCookCoverage = field(
        validator=validators.instance_of(MoldCookCoverage)
    )
    plan_digest: str | None = field(
        default=None, validator=validators.optional(_digest)
    )
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
                "planner_result_ref": _NULL,
                "plan_ref": _NULL,
                "coverage": {"properties": {"curd_ids": {"maxItems": 1}}},
            }
        },
    ),
    _if_equals(
        "mode",
        MoldCookMode.FULL.value,
        _requires(planner_result_ref=_ARTIFACT_REF, plan_ref=_ARTIFACT_REF),
    ),
    _artifact_binding("spec_ref", "spec"),
    _artifact_binding("approval_ref", "approval", MOLD_COOK_APPROVAL_SCHEMA_URI),
    _paired_or_absent("taste_verdict_ref", "taste_ledger_ref"),
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
        validator=validators.and_(
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
            validators.and_(
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
@schema_constraints(*_outcome_constraints())
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
    proposal_digest: str | None = field(
        default=None, validator=validators.optional(_digest)
    )
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
        fields = _OUTCOME_FIELDS[self.outcome]
        populated = {
            name
            for name in _OUTCOME_PAYLOAD_FIELDS
            if _is_populated(cast("object", getattr(self, name)))
        }
        missing = sorted(fields.required - populated)
        if missing:
            raise ValueError(
                f"{self.outcome.value} preparation requires {', '.join(missing)}"
            )
        if fields.any_of and not populated & fields.any_of:
            options = " or ".join(sorted(fields.any_of))
            raise ValueError(f"{self.outcome.value} preparation requires {options}")
        unexpected = sorted(populated - fields.allowed)
        if unexpected:
            names = ", ".join(unexpected)
            raise ValueError(
                f"{self.outcome.value} preparation carries fields for another outcome: {names}"
            )
        if (
            self.proposal_ref is not None
            and self.proposal_digest != self.proposal_ref.digest
        ):
            raise ValueError("proposal_digest must match proposal_ref.digest")


def registered_contracts() -> tuple[tuple[str, type], ...]:
    """Return marked contract classes in ``mold_cook.py`` in slug order."""
    return marked_contracts_in(sys.modules[__name__])


MOLD_COOK_CONTRACTS: tuple[tuple[str, type], ...] = registered_contracts()


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
