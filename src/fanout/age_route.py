"""Pure age/affinage sizing router.

Spec: subagent-routing-overhaul.md `## Seam schemas (locked)` (age-router
block) and the `## The four sizing functions` table's "age router" row.
Replaces the size-only spawn gate in skills/age/SKILL.md (>15 files OR
>25KB) with a three-tier N dial (1 / 4 / 10) plus a hard-override list that
forces N=10 regardless of size.

Pure function -- no I/O, no network, no file reads. The /age and /affinage
skill paths already have files_changed/insertions/deletions from their own
diff stat and risk_flags from their own grep pass; this module only turns
those numbers into a routing decision.
"""
from __future__ import annotations

# The ten age dimensions, in the order /age's SKILL.md lists them. N=10
# gives each its own single-element lens; N=1 folds them into one lens.
DIMENSIONS: tuple[str, ...] = (
    "correctness",
    "security",
    "encapsulation",
    "spec",
    "complexity",
    "deslop",
    "assertions",
    "nih",
    "efficiency",
    "telemetry",
)

# N=4 grouping, verbatim from the spec's locked lens-grouping line.
LENS_GROUPS_N4: tuple[tuple[str, ...], ...] = (
    ("correctness", "spec", "assertions"),
    ("security",),
    ("complexity", "deslop", "nih"),
    ("efficiency", "telemetry", "encapsulation"),
)

# Hard risk-overrides (spec: "Hard risk-overrides" paragraph below the
# sizing-functions table) -- any match forces N=10/effort=high regardless
# of diff size. Canonical flag strings; callers' grep passes must emit
# these exact tokens for the override to register.
OVERRIDE_FLAGS: frozenset[str] = frozenset(
    {
        "auth",
        "secrets",
        "crypto",
        "tenant-isolation",
        "payments",
        "ledgers",
        "irreversible-effects",
        "concurrency",
        "idempotency",
        "ordering",
        "retries",
        "schema-migration",
        "protocol-change",
        "public-api-change",
        "production-destructive",
        "weak-integration-coverage",
    }
)

# Size thresholds mirror the prior size-only gate in skills/age/SKILL.md
# (>15 files OR >25KB, ~800 lines at ~30 bytes/line) for the N=10 boundary;
# N=4 sits at roughly a tenth of that magnitude -- a diff too big for one
# lens to cover but not yet needing per-dimension workers.
_N4_FILES = 3
_N4_LINES = 80
_N10_FILES = 15
_N10_LINES = 800

# Affinage-only escalation: a high comment count or a red/failing CI class
# bumps the size-based tier by one step (1 -> 4 -> 10), never past N=10.
_AFFINAGE_COMMENT_BUMP = 10
_AFFINAGE_CI_BUMP_CLASSES = frozenset({"failing", "red", "flaky"})

_TIER_ORDER = (1, 4, 10)


def _bump(n: int) -> int:
    idx = _TIER_ORDER.index(n)
    return _TIER_ORDER[min(idx + 1, len(_TIER_ORDER) - 1)]


def _lenses_for(n: int) -> list[list[str]]:
    if n == 1:
        return [list(DIMENSIONS)]
    if n == 4:
        return [list(group) for group in LENS_GROUPS_N4]
    return [[dim] for dim in DIMENSIONS]


def route(
    files_changed: int,
    insertions: int,
    deletions: int,
    risk_flags: list[str] | None = None,
    entry: str = "age",
    comments: int | None = None,
    ci_class: str | None = None,
) -> dict:
    """Pure decision -- no I/O. Returns the locked age-router output shape:
    {n, lenses, effort, overrides_hit, rationale}."""
    if entry not in ("age", "affinage"):
        raise ValueError(f"invalid entry {entry!r}: must be 'age' or 'affinage'")
    risk_flags = risk_flags or []

    overrides_hit = sorted({flag for flag in risk_flags if flag in OVERRIDE_FLAGS})
    if overrides_hit:
        return {
            "n": 10,
            "lenses": _lenses_for(10),
            "effort": "high",
            "overrides_hit": overrides_hit,
            "rationale": f"hard override(s) {', '.join(overrides_hit)} -> n=10/effort=high",
        }

    diff_lines = insertions + deletions
    if files_changed > _N10_FILES or diff_lines > _N10_LINES:
        n = 10
    elif files_changed > _N4_FILES or diff_lines > _N4_LINES:
        n = 4
    else:
        n = 1

    bump_reason = None
    if entry == "affinage":
        if comments is not None and comments >= _AFFINAGE_COMMENT_BUMP:
            bumped = _bump(n)
            if bumped != n:
                bump_reason = f"{comments} comments"
            n = bumped
        if ci_class in _AFFINAGE_CI_BUMP_CLASSES:
            bumped = _bump(n)
            if bumped != n:
                bump_reason = (
                    f"{bump_reason} + ci_class={ci_class}" if bump_reason else f"ci_class={ci_class}"
                )
            n = bumped

    effort = "high" if n == 10 else "medium"
    rationale = (
        f"{files_changed} files, {diff_lines} lines, no risk flags"
        + (f", {bump_reason} escalation" if bump_reason else "")
        + f" -> n={n}/effort={effort}"
    )
    return {
        "n": n,
        "lenses": _lenses_for(n),
        "effort": effort,
        "overrides_hit": [],
        "rationale": rationale,
    }