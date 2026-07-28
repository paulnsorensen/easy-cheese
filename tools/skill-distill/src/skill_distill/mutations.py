"""Deterministic signed-obligation mutation cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class MutationCase:
    kind: str
    member_index: int
    obligations: tuple[Mapping[str, Any], ...]


def deterministic_mutations(
    obligations: Sequence[Mapping[str, Any]],
) -> tuple[MutationCase, ...]:
    """Produce stable single-atom mutations in a fixed kind order."""
    original = tuple(dict(atom) for atom in obligations)
    cases = []
    for index, atom in enumerate(original):
        cases.append(MutationCase("drop", index, original[:index] + original[index + 1 :]))

        polarity = dict(atom)
        polarity["polarity"] = "prohibited" if atom.get("polarity") == "required" else "required"
        cases.append(MutationCase("polarity", index, original[:index] + (polarity,) + original[index + 1 :]))

        condition = dict(atom)
        condition["condition"] = f"not ({atom.get('condition', '')})"
        cases.append(MutationCase("condition", index, original[:index] + (condition,) + original[index + 1 :]))

        order = dict(atom)
        order["order"] = int(atom.get("order", 0)) + 1
        cases.append(MutationCase("order", index, original[:index] + (order,) + original[index + 1 :]))
    return tuple(cases)
