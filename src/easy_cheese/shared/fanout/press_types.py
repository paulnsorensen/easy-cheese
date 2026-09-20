"""Host-owned Press gate result and stop-record types for fan remediation.

These types carry a Press gate's outcome from the host dispatch seam into the
orchestrator and its persisted stop evidence. They hold no decision logic --
the pure decision core in `remediation.py` never reads them.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from enum import Enum

import attrs

from easy_cheese_schemas import EvidenceRef, RemediationScopeKey

_GATE_FAILURE_LIMIT = 128
_UNSAFE_RUN = re.compile(r"[^A-Za-z0-9._:/-]+")
_HYPHEN_RUN = re.compile(r"-{2,}")
_LEADING_NON_ALNUM = re.compile(r"^[^A-Za-z0-9]+")
_EMPTY_GATE_FAILURE = "gate-failure"


def normalize_gate_failures(names: Iterable[str]) -> tuple[str, ...]:
    """Return unique identifier-shaped gate failure names in first-seen order.

    A host gate reports free text such as ``pytest: 3 failed``. The Cure
    observation contract accepts only unique opaque identifiers.
    """
    slugs: dict[str, None] = {}
    for name in names:
        slug = _HYPHEN_RUN.sub("-", _UNSAFE_RUN.sub("-", str(name).strip()))
        slug = _LEADING_NON_ALNUM.sub("", slug)[:_GATE_FAILURE_LIMIT]
        slugs[slug or _EMPTY_GATE_FAILURE] = None
    return tuple(slugs)


@attrs.frozen
class PressGateResult:
    """Host-validated result from one post-merge Press gate."""

    passed: bool
    baseline_id: str
    new_failures: tuple[str, ...] = attrs.field(
        default=(), converter=normalize_gate_failures
    )
    evidence: tuple[EvidenceRef, ...] = ()
    scope: RemediationScopeKey | None = None
    gate_round: int | None = None


class PressStopClassification(str, Enum):
    """Reason an initial Press gate stopped post-merge execution."""

    ABSENT = "absent"
    FAILED = "failed"
    ERROR = "error"


@attrs.frozen
class PressStopRecord:
    """Typed host record for an absent or failed initial Press gate."""

    scope: RemediationScopeKey
    gate_round: int
    baseline_id: str | None
    classification: PressStopClassification
    failure_reason: str
    evidence: tuple[EvidenceRef, ...] = ()
