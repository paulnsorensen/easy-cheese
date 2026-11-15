"""Host-owned acceptance-check result and stop-record types for fan remediation.

These types carry the integrated acceptance check's outcome from the host dispatch seam into the
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
class AcceptanceCheckResult:
    """Host-validated result from one integrated acceptance check on the merged tip."""

    passed: bool
    baseline_id: str
    new_failures: tuple[str, ...] = attrs.field(
        default=(), converter=normalize_gate_failures
    )
    evidence: tuple[EvidenceRef, ...] = ()
    scope: RemediationScopeKey | None = None
    gate_round: int | None = None


class AcceptanceStopClassification(str, Enum):
    """Reason the initial acceptance check stopped post-merge execution."""

    ABSENT = "absent"
    FAILED = "failed"
    ERROR = "error"


@attrs.frozen
class AcceptanceStopRecord:
    """Typed host record for an absent or failed initial acceptance check."""

    scope: RemediationScopeKey
    gate_round: int
    baseline_id: str | None
    classification: AcceptanceStopClassification
    failure_reason: str
    evidence: tuple[EvidenceRef, ...] = ()


class PressOutcome(str, Enum):
    """Outcome of one per-curd Press round; see `skills/cook/references/press-loop.md`."""

    GREEN = "green"
    FINDING = "finding"
    COVERAGE_GAP = "coverage_gap"
    INVALID_EVIDENCE = "invalid_evidence"
    PRODUCTION_CHANGED = "production_changed"
    EXEMPT = "exempt"


@attrs.frozen
class PressRequest:
    """Round identity Cook passes to a fresh Press dispatch.

    Cook is the single round counter. ``attack_id`` is ``None`` until a finding
    names the attack that Press must replay.
    """

    round_number: int
    attack_id: str | None = None


@attrs.frozen
class PressRoundResult:
    """Host-validated outcome of one Press round for one curd."""

    outcome: PressOutcome
    attack_id: str | None = None
    summary: str = ""
    evidence: tuple[EvidenceRef, ...] = ()


@attrs.frozen
class PressRoundRecord:
    """Persisted typed record of one Press round, with any halt it caused."""

    curd_id: str
    round_number: int
    outcome: PressOutcome
    attack_id: str | None
    summary: str
    halt: str | None = None
    evidence: tuple[EvidenceRef, ...] = ()
