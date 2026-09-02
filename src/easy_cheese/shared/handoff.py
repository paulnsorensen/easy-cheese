"""Handoff slug preamble: parse, render, and validate the preamble block.

Schema (canonical rules: skills/cheese/references/handback-contract.md):

    status: <one of easy_cheese_schemas.phase_contracts.HANDBACK_STATUSES>
    next: <skill-name> | done
    artifact: <path-to-prior-report-if-any>
    taste_test: <verdict>                     (optional keyed line)
    durable_flags: none | <flag lines>        (optional keyed line)
    baseline: none | <block>                  (optional keyed line)
    <one-line orientation: what changed or what was reviewed>

The keyed lines between `artifact:` and the orientation are optional: a
plain four-line preamble parses identically, with both fields None.

The block sits at the top of every findings report so downstream skills
(`/ultracook`, `/cheese --continue`) can chain without re-parsing the body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from easy_cheese_schemas.handback_status import require_single_line
from easy_cheese_schemas.phase_contracts import (
    StatusError,
    parse_status_field,
    render_status_field,
    status_disposition,
)

# Flag propagation rules — see skills/cheese/references/handoff-gate.md § Flag propagation.
ALWAYS_PROPAGATE: frozenset[str] = frozenset({"--hard"})
CHAIN_ONLY: frozenset[str] = frozenset({"--auto"})


@dataclass(frozen=True, init=False)
class HandoffSlug:
    status: str  # a name from phase_contracts.HANDBACK_STATUSES
    reason: str | None  # the one-line reason every non-`ok` status carries
    next_skill: str  # bare skill name (no leading slash) or "done"
    artifact: str | None
    orientation: str
    taste_test: str | None = None
    durable_flags: str | None = None
    baseline: str | None = None

    def __init__(
        self,
        *,
        status: str,
        next_skill: str,
        artifact: str | None,
        orientation: str,
        reason: str | None = None,
        halt_reason: str | None = None,
        taste_test: str | None = None,
        durable_flags: str | None = None,
        baseline: str | None = None,
    ) -> None:
        """Accept `reason=` (current) or `halt_reason=` (deprecated alias)."""
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason if reason is not None else halt_reason)
        object.__setattr__(self, "next_skill", next_skill)
        object.__setattr__(self, "artifact", artifact)
        object.__setattr__(self, "orientation", orientation)
        object.__setattr__(self, "taste_test", taste_test)
        object.__setattr__(self, "durable_flags", durable_flags)
        object.__setattr__(self, "baseline", baseline)

    @property
    def halt_reason(self) -> str | None:
        """Deprecated read-only alias for `reason`; kept for pre-rename readers."""
        return self.reason

    @property
    def disposition(self) -> str:
        """What the orchestrator must do next: proceed, retry, or stop."""
        return status_disposition(self.status)


_STATUS_RE = re.compile(r"^status:\s*(?P<rest>.+?)\s*$")
_NEXT_RE = re.compile(r"^next:\s*(?P<value>\S.*?)\s*$")
_ARTIFACT_RE = re.compile(r"^artifact:\s*(?P<value>.*?)\s*$")
# Optional keyed lines allowed between `artifact:` and the orientation.
_OPTIONAL_KEY_RE = re.compile(r"^(?P<key>taste_test|durable_flags|baseline):\s*(?P<value>.*?)\s*$")


class HandoffParseError(ValueError):
    """Raised when a handoff preamble cannot be parsed."""


def _parse_status(line: str) -> tuple[str, str | None]:
    match = _STATUS_RE.match(line)
    if not match:
        raise HandoffParseError(f"expected 'status:' line, got {line!r}")
    rest = match.group("rest")
    try:
        return parse_status_field(rest)
    except StatusError as exc:
        raise HandoffParseError(str(exc)) from exc


def parse_handoff_slug(text: str) -> HandoffSlug:
    """Parse the preamble from the top of an artifact body.

    The preamble is strictly the first *physical* lines: status, next,
    artifact (value may be empty), zero or more optional keyed lines
    (`taste_test:`, `durable_flags:`, `baseline:`), orientation. Treating blank lines as
    skippable would let a missing orientation silently consume the first
    body line (e.g. a `# Press Report` heading) as the orientation.
    """
    raw_lines = text.splitlines()
    if len(raw_lines) < 4:
        raise HandoffParseError(
            f"handoff preamble needs status / next / artifact / orientation; got {len(raw_lines)} lines"
        )
    status, reason = _parse_status(raw_lines[0])

    next_match = _NEXT_RE.match(raw_lines[1])
    if not next_match:
        raise HandoffParseError(f"expected 'next:' line, got {raw_lines[1]!r}")
    next_skill = next_match.group("value").lstrip("/")

    artifact_match = _ARTIFACT_RE.match(raw_lines[2])
    if not artifact_match:
        raise HandoffParseError(f"expected 'artifact:' line, got {raw_lines[2]!r}")
    artifact_value = artifact_match.group("value") or None

    optional: dict[str, str] = {}
    index = 3
    while index < len(raw_lines):
        keyed_match = _OPTIONAL_KEY_RE.match(raw_lines[index])
        if not keyed_match:
            break
        key = keyed_match.group("key")
        value = keyed_match.group("value")
        if key in optional:
            raise HandoffParseError(f"duplicate '{key}:' line in handoff preamble")
        if not value:
            raise HandoffParseError(f"'{key}:' line requires a value")
        optional[key] = value
        index += 1

    if index >= len(raw_lines):
        raise HandoffParseError("orientation line missing after keyed preamble lines")
    orientation = raw_lines[index].strip()
    if not orientation:
        raise HandoffParseError("orientation line must be non-empty")

    return HandoffSlug(
        status=status,
        reason=reason,
        next_skill=next_skill,
        artifact=artifact_value,
        orientation=orientation,
        taste_test=optional.get("taste_test"),
        durable_flags=optional.get("durable_flags"),
        baseline=optional.get("baseline"),
    )


def render_handoff_slug(slug: HandoffSlug) -> str:
    """Render a HandoffSlug back to its canonical preamble."""
    for field_name, value in (
        ("artifact", slug.artifact),
        ("orientation", slug.orientation),
        ("taste_test", slug.taste_test),
        ("durable_flags", slug.durable_flags),
        ("baseline", slug.baseline),
    ):
        if value is not None:
            require_single_line(field_name, value)
    status_line = "status: " + render_status_field(slug.status, slug.reason)
    lines = [status_line, f"next: {slug.next_skill}", f"artifact: {slug.artifact or ''}"]
    if slug.taste_test is not None:
        lines.append(f"taste_test: {slug.taste_test}")
    if slug.durable_flags is not None:
        lines.append(f"durable_flags: {slug.durable_flags}")
    if slug.baseline is not None:
        lines.append(f"baseline: {slug.baseline}")
    lines.append(slug.orientation)
    return "\n".join(lines)


# ----- skill dispatch + flag propagation -----------------------------------

_DISPATCH_RE = re.compile(r"^/(?P<skill>[a-z][a-z-]*)\b\s*(?P<args>.*)$")


def parse_skill_dispatch(dispatch: str) -> tuple[str, list[str]]:
    """Split '/age <slug> --hard' into ('age', ['<slug>', '--hard'])."""
    match = _DISPATCH_RE.match(dispatch.strip())
    if not match:
        raise ValueError(f"not a skill dispatch: {dispatch!r}")
    args = match.group("args").split()
    return match.group("skill"), args


def propagate_flags(source_flags: list[str], *, in_auto_chain: bool) -> list[str]:  # noqa: V103
    """Return the subset of source flags that survive the propagation rules."""
    result: list[str] = []
    for flag in source_flags:
        bare = flag.split("=", 1)[0]
        if bare in ALWAYS_PROPAGATE or bare in CHAIN_ONLY and in_auto_chain:
            result.append(flag)
    return result
