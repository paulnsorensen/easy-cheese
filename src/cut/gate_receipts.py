# ships-as: press.pyz (module)
"""Shared public types for the Cut red-gate helper.

The receipt records themselves live in :mod:`easy_cheese_schemas.gates`.  This
module only re-exports that phase-neutral surface and provides the result type
returned by the read-only validator.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from easy_cheese_schemas import (
    BaselineCheck,
    EvidenceOrigin,
    GateDisposition,
    GateMode,
    GateProducer,
    GateReceipt,
    ProtectedFile,
    RedCase,
    RedKind,
    TestContract,
)


@dataclass(frozen=True)
class ValidationResult:
    """A deterministic validation verdict and its accumulated diagnostics."""

    ok: bool
    problems: tuple[str, ...] = ()
    receipt: GateReceipt | None = None

    @property
    def diagnostics(self) -> tuple[str, ...]:
        """Return problems under the command-facing diagnostics name."""
        return self.problems

    def to_dict(self) -> dict[str, Any]:
        """Return the stable JSON shape used by the CLI."""
        return {
            "ok": self.ok,
            "problems": list(self.problems),
        }


class GateValidationError(ValueError):
    """Raised by the receipt-writing seam when validation did not pass."""

    def __init__(self, problems: tuple[str, ...] | list[str]) -> None:
        self.problems = tuple(dict.fromkeys(problems))
        super().__init__("; ".join(self.problems) or "gate validation failed")


__all__ = [
    "BaselineCheck",
    "EvidenceOrigin",
    "GateDisposition",
    "GateMode",
    "GateProducer",
    "GateReceipt",
    "GateValidationError",
    "ProtectedFile",
    "RedCase",
    "RedKind",
    "TestContract",
    "ValidationResult",
]
