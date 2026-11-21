"""Compute per-finding severity and fix-cost-now buckets for /age.

This code owns the rubric. skills/age/references/dimensions.md mirrors it in
prose for reviewers, and a test compares the "Location sensitivity" table with
`LOCATION_SENSITIVITY`. The package never reads that prose at run time. /age
wraps these functions in its `severity` bundle command; affineur imports them
directly.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum
from types import MappingProxyType
from typing import Self

from typing_extensions import override

from easy_cheese_schemas import FixCostNow, ReviewDimension


class RubricError(ValueError):
    """Raised when a rubric input is outside the allowed vocabulary."""


class _OrderedRubricTier(IntEnum):
    """Base for the rubric's ordered vocabularies: member order IS the ladder.

    Members ascend from least to most severe/costly, so `<` and `max()` express
    the rubric's ordering directly. `str()` yields the wire spelling the /age
    report and the CLI use (lowercase member name).
    """

    @override
    def __str__(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, value: str, *, field: str) -> Self:
        """Parse a wire spelling at the trust boundary, or raise `RubricError`."""
        try:
            return cls[value.upper()]
        except KeyError:
            expected = ", ".join(str(tier) for tier in cls)
            raise RubricError(
                f"unknown {field} {value!r}; expected one of {expected}"
            ) from None


class Severity(_OrderedRubricTier):
    """The /age severity ladder, least → most severe; `BLOCKER` is the cap."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    BLOCKER = 3


DIMENSIONS: frozenset[str] = frozenset(dimension.value for dimension in ReviewDimension)

# Whether the `contract` location bumps a dimension. Keyed by `ReviewDimension`
# with an explicit value for every member; a test fails on a missing dimension.
LOCATION_SENSITIVITY: Mapping[ReviewDimension, bool] = MappingProxyType(
    {
        ReviewDimension.CORRECTNESS: True,
        ReviewDimension.SECURITY: True,
        ReviewDimension.ENCAPSULATION: True,
        ReviewDimension.SPEC: True,
        ReviewDimension.COMPLEXITY: False,
        ReviewDimension.DESLOP: False,
        ReviewDimension.ASSERTIONS: False,
        ReviewDimension.NIH: True,
        ReviewDimension.EFFICIENCY: True,
        ReviewDimension.TELEMETRY: True,
        ReviewDimension.CONVENTIONS: False,
        ReviewDimension.ALTITUDE: False,
        ReviewDimension.REFRAME: False,
        ReviewDimension.TESTS: False,
        ReviewDimension.COMPAT: False,
        ReviewDimension.SCOPE: False,
        ReviewDimension.DEPENDENCIES: False,
    }
)

# Kept for existing importers: the wire spellings of the sensitive dimensions.
LOCATION_SENSITIVE: frozenset[str] = frozenset(
    dimension.value for dimension, sensitive in LOCATION_SENSITIVITY.items() if sensitive
)

LOCATIONS: frozenset[str] = frozenset({"class", "module", "cross-module", "contract"})
FIX_COST_LATER: frozenset[str] = frozenset({"contained", "spreading", "structural"})


def bump(sev: Severity) -> Severity:
    """Promote one tier; `Severity.BLOCKER` is the cap."""
    return Severity.BLOCKER if sev is Severity.BLOCKER else Severity(sev + 1)


def compute_severity(
    *,
    dimension: str,
    base: str,
    location: str,
    fix_cost_later: str,
) -> Severity:
    """Apply contract + structural bumps to a base severity, capped at blocker."""
    if dimension not in DIMENSIONS:
        raise RubricError(f"unknown dimension {dimension!r}")
    sev = Severity.parse(base, field="base")
    if location not in LOCATIONS:
        raise RubricError(
            f"unknown location {location!r}; expected one of {sorted(LOCATIONS)}"
        )
    if fix_cost_later not in FIX_COST_LATER:
        raise RubricError(
            f"unknown fix-cost-later {fix_cost_later!r}; expected one of {sorted(FIX_COST_LATER)}"
        )

    if location == "contract" and dimension in LOCATION_SENSITIVE:
        sev = bump(sev)
    if fix_cost_later == "structural":
        sev = bump(sev)
    return sev


def bucket_fix_cost_now(*, file_count: int, module_count: int = 1) -> FixCostNow:
    """Bucket a blast-radius file/module count into contained / moderate / sprawling."""
    if file_count < 0:
        raise RubricError(f"file_count must be >= 0, got {file_count}")
    if module_count < 1:
        raise RubricError(f"module_count must be >= 1, got {module_count}")
    if module_count >= 2 or file_count >= 11:
        return FixCostNow.SPRAWLING
    if file_count >= 3:
        return FixCostNow.MODERATE
    return FixCostNow.CONTAINED