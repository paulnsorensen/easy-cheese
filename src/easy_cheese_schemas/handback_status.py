"""The handback status vocabulary: what a phase may return in its `status:` field.

`HandbackStatus` (a `StrEnum`) is the single source of truth for the wire
grammar (`requires_reason`) and the routing rule (`disposition`). Adding a
status never requires editing a consumer -- only branching on `disposition`
does.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

MAX_REASON_LENGTH = 512


class StatusError(ValueError):
    """Raised when a handback `status:` field is outside the declared vocabulary."""


class Disposition(StrEnum):
    """What an orchestrator does with a handback: proceed, retry, or stop."""

    PROCEED = "proceed"
    RETRY = "retry"
    STOP = "stop"


class HandbackStatus(StrEnum):
    """One `status:` value a phase may hand back.

    `requires_reason` decides the wire grammar: `ok` stands alone, every other
    status is `"<name>: <one-line reason>"`. `disposition` is what the
    orchestrator does with it, and is the only field a consumer should branch
    on -- adding a status must not require editing every consumer.
    """

    OK = "ok"
    OK_WITH_CONCERNS = "ok-with-concerns"
    NEEDS_CONTEXT = "needs-context"
    GATED = "gated"
    HALT = "halt"

    @property
    def requires_reason(self) -> bool:
        return _STATUS_RULES[self][0]

    @property
    def disposition(self) -> Disposition:
        return _STATUS_RULES[self][1]


_STATUS_RULES: Mapping[HandbackStatus, tuple[bool, Disposition]] = MappingProxyType(
    {
        HandbackStatus.OK: (False, Disposition.PROCEED),
        HandbackStatus.OK_WITH_CONCERNS: (True, Disposition.PROCEED),
        HandbackStatus.NEEDS_CONTEXT: (True, Disposition.RETRY),
        HandbackStatus.GATED: (True, Disposition.STOP),
        HandbackStatus.HALT: (True, Disposition.STOP),
    }
)

PROCEED = Disposition.PROCEED
RETRY = Disposition.RETRY
STOP = Disposition.STOP
DISPOSITIONS = (PROCEED, RETRY, STOP)

HANDBACK_STATUSES: Mapping[str, HandbackStatus] = MappingProxyType(
    {status.value: status for status in HandbackStatus}
)
REGISTERED_STATUSES = tuple(HANDBACK_STATUSES)


def status_vocabulary() -> str:
    """Render the full `status:` grammar, e.g. for a CLI `--status` help string."""
    return " | ".join(
        status.value if not status.requires_reason else f"{status.value}: <reason>"
        for status in HANDBACK_STATUSES.values()
    )


# Every Unicode line/paragraph separator str.splitlines() treats as a break;
# kept as an explicit tuple because splitlines() has no public boundary list.
_LINE_SEPARATORS = (
    "\n", "\r", "\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", " ", " "
)


def require_single_line(field: str, value: str) -> None:
    if any(separator in value for separator in _LINE_SEPARATORS):
        raise StatusError(f"{field} must fit on one physical line")


def _resolve_status(name: str) -> HandbackStatus:
    """Normalise a status name (strip + lowercase) and look it up.

    Shared by parse, render, and disposition lookup so a name that resolves
    in one path resolves identically in all three. Rejects non-ASCII names
    before lookup so a homoglyph (e.g. U+212A KELVIN SIGN) cannot widen the
    accepted set beyond `REGISTERED_STATUSES`.
    """
    require_single_line("status name", name)
    candidate = name.strip()
    if not candidate.isascii():
        raise StatusError(f"status must be one of {status_vocabulary()}, got {name!r}")
    status = HANDBACK_STATUSES.get(candidate.lower())
    if status is None:
        raise StatusError(f"status must be one of {status_vocabulary()}, got {name!r}")
    return status


def _clean_reason(status: HandbackStatus, reason: str, *, require_reason: bool) -> str | None:
    """Strip and enforce a reason against `status`; shared by parse and render.

    Stripping before the emptiness check is what makes a whitespace-only
    reason (`render_status_field("halt", "   ")`) behave identically to a
    missing one, instead of rendering a value `parse_status_field` rejects.
    """
    require_single_line("status reason", reason)
    cleaned = reason.strip()
    if not status.requires_reason:
        if cleaned:
            raise StatusError(f"{status.value} status takes no reason")
        return None
    if not cleaned:
        if require_reason:
            raise StatusError(
                f"{status.value} status requires a reason after '{status.value}:'"
            )
        return None
    if len(cleaned) > MAX_REASON_LENGTH:
        raise StatusError(
            f"{status.value} status reason exceeds {MAX_REASON_LENGTH} characters"
        )
    return cleaned


def parse_status_field(
    value: str, *, require_reason: bool = True
) -> tuple[str, str | None]:
    """Split a `status:` field value into `(status name, reason or None)`.

    This is the single grammar for every producer and consumer of the handoff
    preamble; callers translate `StatusError` into their own error type. The
    name is matched case-insensitively after stripping, because the field is
    read back out of agent-authored prose.

    `require_reason=False` is for readers of an already-emitted field -- the
    phase router and the legacy note reader. A reason-carrying status that
    arrived bare (`halt` with no colon) must still route by its declared
    disposition rather than be rejected into some caller's fallback; the
    vocabulary itself is never forked.
    """
    require_single_line("status field", value)
    name, separator, reason_text = value.strip().partition(":")
    status = _resolve_status(name)
    if not status.requires_reason:
        if separator or reason_text.strip():
            raise StatusError(f"{status.value} status takes no reason")
        return status.value, None
    return status.value, _clean_reason(status, reason_text, require_reason=require_reason)


def render_status_field(name: str, reason: str | None) -> str:
    """Render `(status name, reason)` back to its canonical field value."""
    status = _resolve_status(name)
    if not status.requires_reason:
        if reason:
            raise StatusError(f"{status.value} status takes no reason")
        return status.value
    cleaned = _clean_reason(status, reason or "", require_reason=True)
    return f"{status.value}: {cleaned}"


def status_disposition(name: str) -> Disposition:
    """Return what an orchestrator must do with `name`: proceed, retry, or stop."""
    return _resolve_status(name).disposition


__all__ = [
    "DISPOSITIONS",
    "HANDBACK_STATUSES",
    "MAX_REASON_LENGTH",
    "PROCEED",
    "REGISTERED_STATUSES",
    "RETRY",
    "STOP",
    "Disposition",
    "HandbackStatus",
    "StatusError",
    "parse_status_field",
    "render_status_field",
    "require_single_line",
    "status_disposition",
    "status_vocabulary",
]
