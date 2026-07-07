"""Handoff slug preamble: parse, render, and validate the four-line block.

Schema (see shared/formatting.md § Required preamble):

    status: ok | halt: <one-line reason>
    next: <skill-name> | done
    artifact: <path-to-prior-report-if-any>
    <one-line orientation: what changed or what was reviewed>

The block sits at the top of every findings report so downstream skills
(`/ultracook`, `/cheese --continue`) can chain without re-parsing the body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Flag propagation rules — see shared/handoff-gate.md § Flag propagation.
ALWAYS_PROPAGATE: frozenset[str] = frozenset({"--hard"})
CHAIN_ONLY: frozenset[str] = frozenset({"--auto"})


@dataclass(frozen=True)
class HandoffSlug:
    status: str  # "ok" or "halt"
    halt_reason: str | None
    next_skill: str  # bare skill name (no leading slash) or "done"
    artifact: str | None
    orientation: str

    def is_halt(self) -> bool:
        return self.status == "halt"


_STATUS_RE = re.compile(r"^status:\s*(?P<rest>.+?)\s*$")
_NEXT_RE = re.compile(r"^next:\s*(?P<value>\S.*?)\s*$")
_ARTIFACT_RE = re.compile(r"^artifact:\s*(?P<value>.*?)\s*$")


class HandoffParseError(ValueError):
    """Raised when a handoff preamble cannot be parsed."""


def _parse_status(line: str) -> tuple[str, str | None]:
    match = _STATUS_RE.match(line)
    if not match:
        raise HandoffParseError(f"expected 'status:' line, got {line!r}")
    rest = match.group("rest")
    if rest == "ok":
        return "ok", None
    if rest.startswith("halt:"):
        reason = rest[len("halt:") :].strip()
        if not reason:
            raise HandoffParseError("halt status requires a reason after 'halt:'")
        return "halt", reason
    raise HandoffParseError(f"status must be 'ok' or 'halt: <reason>', got {rest!r}")


def parse_handoff_slug(text: str) -> HandoffSlug:
    """Parse the four-line preamble from the top of an artifact body.

    The preamble is strictly the first four *physical* lines: status, next,
    artifact (value may be empty), orientation. Treating blank lines as
    skippable would let a missing orientation silently consume the first
    body line (e.g. a `# Press Report` heading) as the orientation.
    """
    raw_lines = text.splitlines()
    if len(raw_lines) < 4:
        raise HandoffParseError(
            f"handoff preamble needs status / next / artifact / orientation; got {len(raw_lines)} lines"
        )
    status, halt_reason = _parse_status(raw_lines[0])

    next_match = _NEXT_RE.match(raw_lines[1])
    if not next_match:
        raise HandoffParseError(f"expected 'next:' line, got {raw_lines[1]!r}")
    next_skill = next_match.group("value").lstrip("/")

    artifact_match = _ARTIFACT_RE.match(raw_lines[2])
    if not artifact_match:
        raise HandoffParseError(f"expected 'artifact:' line, got {raw_lines[2]!r}")
    artifact_value = artifact_match.group("value") or None

    orientation = raw_lines[3].strip()
    if not orientation:
        raise HandoffParseError("orientation line must be non-empty")

    return HandoffSlug(
        status=status,
        halt_reason=halt_reason,
        next_skill=next_skill,
        artifact=artifact_value,
        orientation=orientation,
    )


def render_handoff_slug(slug: HandoffSlug) -> str:
    """Render a HandoffSlug back to its canonical four-line preamble."""
    if slug.status == "halt":
        if not slug.halt_reason:
            raise ValueError("halt status requires halt_reason")
        status_line = f"status: halt: {slug.halt_reason}"
    elif slug.status == "ok":
        status_line = "status: ok"
    else:
        raise ValueError(f"unknown status {slug.status!r}")
    artifact_line = f"artifact: {slug.artifact or ''}"
    return "\n".join(
        [status_line, f"next: {slug.next_skill}", artifact_line, slug.orientation]
    )


# ----- skill dispatch + flag propagation -----------------------------------

_DISPATCH_RE = re.compile(r"^/(?P<skill>[a-z][a-z-]*)\b\s*(?P<args>.*)$")


def parse_skill_dispatch(dispatch: str) -> tuple[str, list[str]]:
    """Split '/age <slug> --hard' into ('age', ['<slug>', '--hard'])."""
    match = _DISPATCH_RE.match(dispatch.strip())
    if not match:
        raise ValueError(f"not a skill dispatch: {dispatch!r}")
    args = match.group("args").split()
    return match.group("skill"), args


def propagate_flags(source_flags: list[str], *, in_auto_chain: bool) -> list[str]:
    """Return the subset of source flags that survive the propagation rules."""
    result: list[str] = []
    for flag in source_flags:
        bare = flag.split("=", 1)[0]
        if bare in ALWAYS_PROPAGATE:
            result.append(flag)
        elif bare in CHAIN_ONLY and in_auto_chain:
            result.append(flag)
    return result
