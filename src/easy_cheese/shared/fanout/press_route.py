"""Validated boundary router for the Press adversarial gate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypeAlias


class Outcome(str, Enum):
    """Closed set of outcomes that Press can expose at its boundary."""

    GREEN = "green"
    IN_CONTRACT_RED = "in_contract_red"
    INVALID_EVIDENCE = "invalid_evidence"
    PRODUCTION_CHANGED = "production_changed"


@dataclass(frozen=True)
class Continue:
    """Request one Press-owned corrective Cook continuation."""

    reason: str = "press-corrective-cook"


@dataclass(frozen=True)
class Dispatch:
    """Expose the next globally routed phase after a clean Press pass."""

    command: str = "/age"


@dataclass(frozen=True)
class Stop:
    """Stop Press, optionally preserving a valid third-RED evidence chain."""

    reason: str
    gated_evidence: bool  # noqa: V107


Action: TypeAlias = Continue | Dispatch | Stop
_MAX_REPAIR_CYCLES = 2


def _coerce_outcome(outcome: object) -> Outcome:
    if isinstance(outcome, Outcome):
        return outcome
    if not isinstance(outcome, str):
        raise TypeError(
            f"outcome must be an Outcome or string, not {type(outcome).__name__}"
        )
    try:
        return Outcome(outcome)
    except ValueError as exc:
        allowed = ", ".join(member.value for member in Outcome)
        raise ValueError(
            f"invalid outcome {outcome!r}; expected one of: {allowed}"
        ) from exc


def _check_repair_cycles(repair_cycles: int) -> None:
    if isinstance(repair_cycles, bool):
        raise TypeError("repair_cycles must be a non-negative integer")
    if repair_cycles < 0:
        raise ValueError("repair_cycles must be a non-negative integer")


def press_route(outcome: Outcome | str, repair_cycles: int) -> Action:
    """Return the only action permitted at a Press decision boundary."""
    resolved = _coerce_outcome(outcome)
    _check_repair_cycles(repair_cycles)

    if resolved is Outcome.GREEN:
        return Dispatch()
    if resolved is Outcome.IN_CONTRACT_RED:
        if repair_cycles < _MAX_REPAIR_CYCLES:
            return Continue()
        return Stop(reason="third-red", gated_evidence=True)
    if resolved is Outcome.INVALID_EVIDENCE:
        return Stop(reason="invalid-evidence", gated_evidence=False)
    return Stop(reason="production-changed", gated_evidence=False)


__all__ = [
    "Action",
    "Continue",
    "Dispatch",
    "Outcome",
    "Stop",
    "press_route",
]
