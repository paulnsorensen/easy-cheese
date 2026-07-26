"""Cross-family interaction gate with deterministic failure bisect."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class InteractionResult:
    passed: bool
    failing_families: tuple[str, ...]


def bisect_interaction(
    families: Sequence[str],
    gate: Callable[[tuple[str, ...]], bool],
) -> tuple[str, ...]:
    """Return a deterministic one-minimal subset that still fails the gate."""
    current = tuple(families)
    if not current or gate(current):
        return ()
    partitions = 2
    while len(current) >= 2:
        size = (len(current) + partitions - 1) // partitions
        chunks = [current[index : index + size] for index in range(0, len(current), size)]
        reduced = False
        for chunk in chunks:
            if not gate(chunk):
                current = chunk
                partitions = 2
                reduced = True
                break
        if reduced:
            continue
        for chunk in chunks:
            chunk_members = set(chunk)
            complement = tuple(member for member in current if member not in chunk_members)
            if complement and not gate(complement):
                current = complement
                partitions = max(2, partitions - 1)
                reduced = True
                break
        if reduced:
            continue
        if partitions >= len(current):
            break
        partitions = min(len(current), partitions * 2)
    return current


def gate_interactions(
    families: Sequence[str],
    gate: Callable[[tuple[str, ...]], bool],
) -> InteractionResult:
    """Run the combined gate once, then bisect only a failing combination."""
    ordered = tuple(families)
    if len(set(ordered)) != len(ordered):
        raise ValueError("family ids must be unique")
    if gate(ordered):
        return InteractionResult(True, ())
    return InteractionResult(False, bisect_interaction(ordered, gate))
