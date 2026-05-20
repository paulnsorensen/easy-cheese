"""Parse, group, and render review findings for /age and /cure.

Finding bullet shape (see shared/formatting.md § Findings format):

    - **[<dimension>]** `path/to/file.ext:42-50` — <what is wrong>. <recommendation>.

Stake comes from the surrounding section heading (`### High` or `### Medium`).
Findings are assigned ids in render order so the cure selection verbs (`1,3,5`,
`all-high`, `skip N`) resolve to the same set both sides of the handoff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

STAKES: tuple[str, ...] = ("high", "medium")
STAKE_ORDER = {stake: index for index, stake in enumerate(STAKES)}


@dataclass(frozen=True)
class Finding:
    id: int
    stake: str  # "high" or "medium"
    dimension: str
    location: str  # "path/to/file.ext:42-50" or similar
    summary: str
    recommendation: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


# Matches: - **[<dimension>]** `<location>` — <body>
# The separator accepts both em-dash (—) and hyphen (-) to tolerate
# both careful markdown and auto-converted variants from plain text.
_BULLET_RE = re.compile(
    r"^-\s+\*\*\[(?P<dim>[^\]]+)\]\*\*\s+`(?P<loc>[^`]+)`\s*[—-]\s*(?P<body>.+?)\s*$"
)
_STAKE_HEADING_RE = re.compile(r"^#{2,4}\s*(?P<stake>high|medium)\b", re.IGNORECASE)


def _split_summary_recommendation(body: str) -> tuple[str, str | None]:
    """Split the bullet body into (summary, recommendation) on the first period
    that closes a sentence. Returns (body, None) if there's no clean split."""
    body = body.rstrip()
    if body.endswith("."):
        body = body[:-1]
    parts = re.split(r"\.\s+", body, maxsplit=1)
    if len(parts) == 2 and parts[1]:
        return parts[0].strip() + ".", parts[1].strip() + "."
    return body.strip() + ".", None


def parse_findings_report(text: str) -> list[Finding]:
    """Walk the report. Each bullet inherits the stake from the prior heading.

    Bullets outside a stake heading are silently skipped — the report shape
    requires findings to live under a stake section.
    """
    current_stake: str | None = None
    findings: list[Finding] = []
    for raw in text.splitlines():
        heading = _STAKE_HEADING_RE.match(raw.strip())
        if heading:
            current_stake = heading.group("stake").lower()
            continue
        if current_stake is None:
            continue
        bullet = _BULLET_RE.match(raw)
        if not bullet:
            continue
        summary, recommendation = _split_summary_recommendation(bullet.group("body"))
        findings.append(
            Finding(
                id=len(findings) + 1,
                stake=current_stake,
                dimension=bullet.group("dim").strip(),
                location=bullet.group("loc").strip(),
                summary=summary,
                recommendation=recommendation,
            )
        )
    return findings


def group_by_stake(findings: list[Finding]) -> list[Finding]:
    """Return findings sorted high → medium, preserving in-stake order."""
    return sorted(findings, key=lambda f: (STAKE_ORDER.get(f.stake, 99), f.id))


def render_selection_table(findings: list[Finding]) -> str:
    """Render the | # | stake | dim | location | summary | table for /cure."""
    header = (
        "| # | stake  | dim          | location                  | summary |\n"
        "|---|--------|--------------|---------------------------|---------|"
    )
    rows = [
        f"| {f.id} | {f.stake:6s} | {f.dimension:12s} | {f.location:25s} | {f.summary} |"
        for f in group_by_stake(findings)
    ]
    return "\n".join([header, *rows])


# ----- selection-verb interpreter ------------------------------------------

_NUM_LIST_RE = re.compile(r"^\d+(?:\s*,\s*\d+)*$")
_SKIP_RE = re.compile(r"^skip\s+(\d+)$", re.IGNORECASE)
_RANGE_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


class SelectionError(ValueError):
    """Raised when a selection verb references unknown ids or is unparseable."""


def parse_selection(verb: str, findings: list[Finding]) -> list[int]:
    """Expand a selection verb to a sorted list of finding ids.

    Recognized verbs (cure/references/selection.md § Recognized selection verbs):

        1,3,5         specific item ids
        1-3           inclusive range
        all-high      every blocker- or high-severity finding (floor semantics;
                      under the legacy two-tier stake model this collapses to
                      every high-stake finding because no blocker tier exists)
        all           every finding
        none          empty selection (default)
        skip N        every finding *except* N

    The runtime below still filters on the legacy `stake` field — once the
    severity migration lands on `Finding`, the `all-high` branch widens to
    include blocker-severity findings without changing this docstring.
    """
    verb = verb.strip().lower()
    ids = {f.id for f in findings}

    if verb in ("", "none"):
        return []
    if verb == "all":
        return sorted(ids)
    if verb == "all-high":
        return sorted(f.id for f in findings if f.stake == "high")

    skip = _SKIP_RE.match(verb)
    if skip:
        target = int(skip.group(1))
        if target not in ids:
            raise SelectionError(f"skip target {target} not in findings")
        return sorted(ids - {target})

    range_match = _RANGE_RE.match(verb)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        if lo > hi:
            raise SelectionError(f"range {lo}-{hi} is reversed")
        selected = set(range(lo, hi + 1)) & ids
        missing = set(range(lo, hi + 1)) - ids
        if missing:
            raise SelectionError(f"range references unknown ids: {sorted(missing)}")
        return sorted(selected)

    if _NUM_LIST_RE.match(verb):
        wanted = {int(token.strip()) for token in verb.split(",")}
        unknown = wanted - ids
        if unknown:
            raise SelectionError(f"unknown finding ids: {sorted(unknown)}")
        return sorted(wanted)

    raise SelectionError(f"unrecognized selection verb: {verb!r}")
