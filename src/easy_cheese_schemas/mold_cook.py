"""Shared values for Mold scope, holds, and retained runner limits."""

from __future__ import annotations

import sys
from enum import Enum

from attrs import define, field, validators

from .contracts import (
    ArtifactRef,
    PlannerUncertainty,
    _bounded_string,  # pyright: ignore[reportPrivateUsage]
    _identifier,  # pyright: ignore[reportPrivateUsage]
    _identifier_list,  # pyright: ignore[reportPrivateUsage]
    _list_of,  # pyright: ignore[reportPrivateUsage]
    _string_list,  # pyright: ignore[reportPrivateUsage]
    _tuple_sequence,  # pyright: ignore[reportPrivateUsage]
    marked_contracts_in,
)


class CookHoldKind(str, Enum):
    """Why one selected scope cannot execute."""

    USER_INTENT = "user_intent"
    PREPARATION = "preparation"
    INTEGRITY = "integrity"
    BLOCKED = "blocked"


class CookRequirementKind(str, Enum):
    """Evidence needed before selected work can execute."""

    SCOPE = "scope"
    PLAN = "plan"
    APPROVAL = "approval"
    RUNNER = "runner"
    EVIDENCE = "evidence"
    INTEGRITY = "integrity"


@define(frozen=True)
class MoldCookCoverage:
    """Selected curd IDs and the exact unresolved PlannerResult work."""

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
    """A reason that Mold work remains saved but cannot execute."""

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


def registered_contracts() -> tuple[tuple[str, type], ...]:
    """Return registered roots; these value types are not contract roots."""
    return marked_contracts_in(sys.modules[__name__])


MOLD_COOK_CONTRACTS: tuple[tuple[str, type], ...] = registered_contracts()

__all__ = [
    "MOLD_COOK_CONTRACTS",
    "CookExecutionHold",
    "CookHoldKind",
    "CookRequirementKind",
    "CookSetupAuthorization",
    "CookUnmetRequirement",
    "MoldCookCoverage",
    "registered_contracts",
]
