"""Parse, group, and render review findings for /age and /cure.

Mirrors the severity-grouped report shape emitted by /age (see
skills/age/SKILL.md § Output). A finding bullet looks like:

    ## Blocker
    - **[encapsulation:blocker]** `src/users/index.ts:42` — what is wrong
      - location: contract · fix-cost-now: sprawling · fix-cost-later: structural
      - recommendation: do X then Y

The script ships with the skill — there is no separate "legacy" format
maintained here. If /age changes its emit format, this parser must change
in lockstep.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SEVERITIES: tuple[str, ...] = ("blocker", "high", "medium", "low")
SEVERITY_ORDER = {sev: i for i, sev in enumerate(SEVERITIES)}


@dataclass(frozen=True)
class Finding:
    id: int
    severity: str  # blocker | high | medium | low
    dimension: str
    location: str  # file:line span, e.g. "src/auth.ts:42-50"
    summary: str
    location_tier: str | None = None  # class | module | cross-module | contract
    fix_cost_now: str | None = None  # contained | moderate | sprawling
    fix_cost_later: str | None = None  # contained | spreading | structural
    recommendation: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


# Heading: ## Blocker / ## High / ## Medium / ## Low (2-4 hashes, case-insensitive)
_SEVERITY_HEADING_RE = re.compile(
    r"^#{2,4}\s*(?P<severity>blocker|high|medium|low)\b", re.IGNORECASE
)

# Main bullet:
#   - **[<dimension>(:<severity>)]** `<location>` — <summary>
# Severity-after-colon is optional — the parser falls back to the surrounding
# section heading if it is absent.
_BULLET_RE = re.compile(
    r"^-\s+\*\*\[(?P<dim>[^\]:]+)(?::(?P<sev>blocker|high|medium|low))?\]\*\*"
    r"\s+`(?P<loc>[^`]+)`\s*[—-]\s*(?P<body>.+?)\s*$",
    re.IGNORECASE,
)

# Sub-field lines, indented under the main bullet:
#   - location: <tier> · fix-cost-now: <bucket> · fix-cost-later: <bucket>
#   - recommendation: <text>
_LOCATION_SUBFIELD_RE = re.compile(r"^\s+-\s*location:\s*(?P<value>.+?)\s*$", re.IGNORECASE)
_RECOMMENDATION_SUBFIELD_RE = re.compile(
    r"^\s+-\s*recommendation:\s*(?P<value>.+?)\s*$", re.IGNORECASE
)

# Middle-dot ( · ) or pipe (|) separator between key:value pairs on the
# location line. Tolerates either since markdown render can vary.
_SUBFIELD_SPLIT_RE = re.compile(r"\s*[·|]\s*")
_KEY_VALUE_RE = re.compile(r"^(?P<key>[a-z][a-z-]*):\s*(?P<value>.+?)$", re.IGNORECASE)


def _parse_location_sub_line(raw: str) -> dict[str, str]:
    """Split a `location: X · fix-cost-now: Y · fix-cost-later: Z` line into a dict."""
    pieces = _SUBFIELD_SPLIT_RE.split(raw.strip())
    parsed: dict[str, str] = {}
    for piece in pieces:
        match = _KEY_VALUE_RE.match(piece)
        if match:
            parsed[match.group("key").lower()] = match.group("value").strip()
    return parsed


def parse_findings_report(text: str) -> list[Finding]:
    """Walk the report. Each bullet inherits the severity from the prior heading
    unless its own `[dim:severity]` tag overrides it. Sub-field lines indented
    under a bullet attach to that bullet."""
    current_severity: str | None = None
    findings: list[Finding] = []
    pending: dict[str, str | None] | None = None  # accumulating sub-fields for the latest bullet

    def flush() -> None:
        nonlocal pending
        if pending is None:
            return
        findings.append(
            Finding(
                id=len(findings) + 1,
                severity=pending["severity"] or "low",
                dimension=pending["dimension"] or "",
                location=pending["location"] or "",
                summary=(pending["summary"] or "").rstrip(". ") + ".",
                location_tier=pending.get("location_tier"),
                fix_cost_now=pending.get("fix_cost_now"),
                fix_cost_later=pending.get("fix_cost_later"),
                recommendation=pending.get("recommendation"),
            )
        )
        pending = None

    for raw in text.splitlines():
        heading = _SEVERITY_HEADING_RE.match(raw.strip())
        if heading:
            flush()
            current_severity = heading.group("severity").lower()
            continue

        bullet = _BULLET_RE.match(raw)
        if bullet:
            flush()
            tag_severity = bullet.group("sev")
            severity = (tag_severity or current_severity or "").lower()
            if not severity:
                # bullet appeared before any section heading and without an inline tag — skip
                continue
            pending = {
                "severity": severity,
                "dimension": bullet.group("dim").strip().lower(),
                "location": bullet.group("loc").strip(),
                "summary": bullet.group("body").strip(),
                "location_tier": None,
                "fix_cost_now": None,
                "fix_cost_later": None,
                "recommendation": None,
            }
            continue

        if pending is None:
            continue

        loc_match = _LOCATION_SUBFIELD_RE.match(raw)
        if loc_match:
            parsed = _parse_location_sub_line(
                "location: " + loc_match.group("value")
            )
            pending["location_tier"] = parsed.get("location")
            pending["fix_cost_now"] = parsed.get("fix-cost-now")
            pending["fix_cost_later"] = parsed.get("fix-cost-later")
            continue

        rec_match = _RECOMMENDATION_SUBFIELD_RE.match(raw)
        if rec_match:
            pending["recommendation"] = rec_match.group("value").rstrip(". ") + "."
            continue

    flush()
    return findings


def group_by_severity(findings: list[Finding]) -> list[Finding]:
    """Return findings sorted blocker → high → medium → low, preserving in-tier order."""
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 99), f.id))


def render_selection_table(findings: list[Finding]) -> str:
    """Render the | # | severity | dim | location | summary | table for /cure."""
    header = (
        "| # | severity | dim           | location                  | summary |\n"
        "|---|----------|---------------|---------------------------|---------|"
    )
    rows = [
        f"| {f.id} | {f.severity:8s} | {f.dimension:13s} | {f.location:25s} | {f.summary} |"
        for f in group_by_severity(findings)
    ]
    return "\n".join([header, *rows])


# ----- selection-verb interpreter ------------------------------------------

_NUM_LIST_RE = re.compile(r"^\d+(?:\s*,\s*\d+)*$")
_SKIP_RE = re.compile(r"^skip\s+(\d+)$", re.IGNORECASE)
_RANGE_RE = re.compile(r"^(\d+)\s*-\s*(\d+)$")


class SelectionError(ValueError):
    """Raised when a selection verb references unknown ids or is unparseable."""


def _resolve_atom(atom: str, findings: list[Finding], ids: set[int]) -> tuple[set[int], int | None]:
    """Resolve one verb fragment. Returns (selected_ids, skip_target_or_None).

    `skip N` is returned separately so verb composition can apply skips after
    the union of positive selectors is built.
    """
    atom = atom.strip().lower()
    if not atom:
        return set(), None

    if atom == "all-blocker":
        return {f.id for f in findings if f.severity == "blocker"}, None
    if atom == "all-high":
        return {f.id for f in findings if f.severity in ("blocker", "high")}, None
    if atom == "cheap":
        return {f.id for f in findings if f.fix_cost_now == "contained"}, None

    skip = _SKIP_RE.match(atom)
    if skip:
        target = int(skip.group(1))
        if target not in ids:
            raise SelectionError(f"skip target {target} not in findings")
        return set(), target

    range_match = _RANGE_RE.match(atom)
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        if lo > hi:
            raise SelectionError(f"range {lo}-{hi} is reversed")
        wanted = set(range(lo, hi + 1))
        missing = wanted - ids
        if missing:
            raise SelectionError(f"range references unknown ids: {sorted(missing)}")
        return wanted, None

    if _NUM_LIST_RE.match(atom):
        wanted = {int(token.strip()) for token in atom.split(",")}
        unknown = wanted - ids
        if unknown:
            raise SelectionError(f"unknown finding ids: {sorted(unknown)}")
        return wanted, None

    raise SelectionError(f"unrecognized selection verb: {atom!r}")


def parse_selection(verb: str, findings: list[Finding]) -> list[int]:
    """Expand a selection verb to a sorted list of finding ids.

    Recognized verbs (cure/references/selection.md § Recognized selection verbs):

        1,3,5         specific item ids (commas allowed inside a numeric atom)
        1-3           inclusive range
        all-blocker   every blocker-severity finding (strict; no high included)
        all-high      every blocker- or high-severity finding (floor at high)
        cheap         every finding with fix-cost-now == contained
        all           every finding
        none          empty selection (default)
        skip N        drop finding N from the result

    Verbs compose with commas. Set algebra: positive selectors union, `skip N`
    applies last. `all` and `none` are mutually exclusive with every other verb.
    """
    verb = verb.strip().lower()
    ids = {f.id for f in findings}

    if verb in ("", "none"):
        return []
    if verb == "all":
        return sorted(ids)

    # Comma-composed verb: split into atoms, but keep bare number lists intact
    # so "1,3,5" stays a single atom (handled by _NUM_LIST_RE).
    atoms = _split_composed_verb(verb)
    if "all" in atoms or "none" in atoms:
        raise SelectionError("'all' and 'none' are mutually exclusive with other verbs")

    selected: set[int] = set()
    skip_targets: set[int] = set()
    has_positive_atom = False
    for atom in atoms:
        atom_ids, skip = _resolve_atom(atom, findings, ids)
        if skip is None:
            has_positive_atom = True
            selected |= atom_ids
        else:
            skip_targets.add(skip)

    # A bare `skip N` (no other atoms) means "all minus N" — the skip is the
    # only verb and the implicit positive set is `all`. Matches selection.md's
    # verb table where `skip N` is listed alongside positive selectors.
    if not has_positive_atom and skip_targets:
        selected = set(ids)

    return sorted(selected - skip_targets)


def _split_composed_verb(verb: str) -> list[str]:
    """Split a comma-composed verb into atoms, preserving bare numeric lists.

    `1,3,5` stays one atom (numeric list). `all-high, 7` becomes ["all-high", "7"].
    `all-blocker, cheap, skip 4` becomes ["all-blocker", "cheap", "skip 4"].
    """
    # If the whole thing is just digits and commas, it's a numeric atom.
    if _NUM_LIST_RE.match(verb.replace(" ", "")):
        return [verb]
    # Otherwise split on comma. Each piece may be a named verb, a single id,
    # a range, or a skip — _resolve_atom handles all of them.
    return [piece.strip() for piece in verb.split(",") if piece.strip()]
