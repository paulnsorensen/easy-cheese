"""Independent canonical-center validation for rewrite families."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .contracts import DistillationFamily, RelationKind
from .relations import REWRITE_RELATIONS


@dataclass(frozen=True)
class MemberValidation:
    member_id: str
    preserved: bool


@dataclass(frozen=True)
class FamilyValidation:
    family_id: str
    relation: RelationKind
    members: tuple[MemberValidation, ...]

    @property
    def eligible(self) -> bool:
        return all(member.preserved for member in self.members)


def _semantic_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _semantic_value(item)
            for key, item in value.items()
            if key not in {"source_span", "schema_version"}
        }
    if isinstance(value, (tuple, list)):
        return [_semantic_value(item) for item in value]
    return value


def _obligations(values: Sequence[Mapping[str, Any]]) -> Counter[str]:
    return Counter(
        json.dumps(_semantic_value(value), sort_keys=True, separators=(",", ":"))
        for value in values
    )


def validate_family(
    family: DistillationFamily,
    original_obligations: Mapping[str, Sequence[Mapping[str, Any]]],
) -> FamilyValidation:
    """Require each explicit member to equal the same center plus its residual."""
    if family.relation not in REWRITE_RELATIONS:
        raise ValueError(f"relation {family.relation} is not rewrite-eligible")
    if family.family_id != family.canonical_center.family_id:
        raise ValueError("family and canonical center ids differ")
    if len(family.members) < 2 or len(set(family.members)) != len(family.members):
        raise ValueError("a rewrite family requires at least two distinct members")

    residuals = family.canonical_center.member_residuals
    missing_residuals = set(family.members) - set(residuals)
    if missing_residuals:
        member_id = sorted(missing_residuals)[0]
        raise ValueError(f"member {member_id} lacks an explicit residual")
    validations = []
    for member_id in family.members:
        if member_id not in original_obligations:
            raise ValueError(f"member {member_id} lacks independent original evidence")
        rewritten = family.canonical_center.clauses + tuple(residuals[member_id])
        preserved = _obligations(original_obligations[member_id]) == _obligations(rewritten)
        if not preserved:
            raise ValueError(f"member {member_id} obligations differ from center plus residual")
        validations.append(MemberValidation(member_id, True))

    extra_residuals = set(residuals) - set(family.members)
    if extra_residuals:
        raise ValueError(f"residuals name non-members: {sorted(extra_residuals)}")
    return FamilyValidation(family.family_id, family.relation, tuple(validations))
