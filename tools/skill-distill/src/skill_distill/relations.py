"""Typed relation validation and rewrite eligibility."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import RelationKind


REWRITE_RELATIONS = frozenset(
    {RelationKind.EQUIVALENT, RelationKind.SHARED_SHELL}
)


def parse_relation(value: str | RelationKind) -> RelationKind:
    """Return one of the seven approved relation names."""
    try:
        return RelationKind(value)
    except ValueError as error:
        raise ValueError(f"unsupported semantic relation: {value}") from error


@dataclass(frozen=True)
class CompressionEligibility:
    pair_id: str
    relation: RelationKind
    complete: bool

    @property
    def eligible(self) -> bool:
        return self.complete and self.relation in REWRITE_RELATIONS

    def require_eligible(self) -> None:
        if not self.eligible:
            raise ValueError(
                f"{self.pair_id} cannot form a rewrite family: "
                f"relation={self.relation}, complete={self.complete}"
            )


def eligible_for_rewrite(
    pair_id: str, relation: str | RelationKind, *, complete: bool
) -> CompressionEligibility:
    return CompressionEligibility(pair_id, parse_relation(relation), complete)
