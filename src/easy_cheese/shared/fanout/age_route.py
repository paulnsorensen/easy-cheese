"""Pure age/affinage sizing router.

Spec: deterministic-fanout-sizing.md `### 2. Reviewer ladder` and
`### 3. Overrides promote`. Replaces the raw diff-stat N in {1,4,10} ladder
with a single git-derived `score` (see review_surface.py), a reviewer ladder
capped at 5 via a strict refinement tree, and turns OVERRIDE_FLAGS hits into
per-dimension solo-lens promotions instead of a blanket escalation to the
top tier.

Pure function -- no I/O, no network, no file reads. Callers compute `score`
from their own diff stats (via review_surface.score()) and pass it in; this
module only turns a score plus risk flags into a routing decision.
"""
from __future__ import annotations

import math

# The ten age dimensions, in the order /age's SKILL.md lists them.
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

# The five-lens refinement tree (spec `### 2. Reviewer ladder` table). Each
# rung of the ladder subdivides this same tree -- n=1 merges it into one
# lens, n=2 merges it into two, n=5 is the tree itself, verbatim.
_LENS_TREE: tuple[tuple[str, ...], ...] = (
    ("correctness", "spec", "assertions"),
    ("security", "telemetry"),
    ("encapsulation", "complexity"),
    ("deslop", "nih"),
    ("efficiency",),
)

# Risk-override flags (spec `### 3. Overrides promote`) -- a match pulls its
# mapped dimension out of its base-partition group into a solo lens; the
# group's remaining members survive as one lens. Canonical flag strings;
# callers' grep passes must emit these exact tokens for the override to
# register.
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

# Flag -> promoted dimension (spec's override-promotion table).
_PROMOTIONS: dict[str, str] = {
    "auth": "security",
    "secrets": "security",
    "crypto": "security",
    "tenant-isolation": "security",
    "payments": "correctness",
    "ledgers": "correctness",
    "irreversible-effects": "correctness",
    "production-destructive": "correctness",
    "concurrency": "correctness",
    "idempotency": "correctness",
    "ordering": "correctness",
    "retries": "correctness",
    "schema-migration": "encapsulation",
    "protocol-change": "encapsulation",
    "public-api-change": "encapsulation",
    "weak-integration-coverage": "assertions",
}

# Score cut points for the base ladder (spec `### 2. Reviewer ladder`).
_SCORE_N2_FLOOR = 60
_SCORE_N5_FLOOR = 250
_HIGH_EFFORT_SCORE = 900

# Affinage-only escalation: a high comment count or a red/failing CI class
# bumps the score-based tier by one step, never past the top of the ladder.
_AFFINAGE_COMMENT_BUMP = 10
_AFFINAGE_CI_BUMP_CLASSES = frozenset({"failing", "red", "flaky"})

_TIER_ORDER = (1, 2, 5)


def _bump(n: int) -> int:
    idx = _TIER_ORDER.index(n)
    return _TIER_ORDER[min(idx + 1, len(_TIER_ORDER) - 1)]


def _raw_groups_for(n: int) -> list[list[str]]:
    """The base-partition groups for tier `n`, before any override promotion."""
    if n == 1:
        return [list(DIMENSIONS)]
    if n == 2:
        return [
            [dim for lens in _LENS_TREE[:2] for dim in lens],
            [dim for lens in _LENS_TREE[2:] for dim in lens],
        ]
    return [list(lens) for lens in _LENS_TREE]


def _tier_for_score(score: float) -> int:
    if score < _SCORE_N2_FLOOR:
        return 1
    if score <= _SCORE_N5_FLOOR:
        return 2
    return 5


def _promote(base_groups: list[list[str]], promoted_dims: set[str]) -> list[list[str]]:
    """Pull `promoted_dims` out of their base group into solo lenses; each
    group's remaining members survive together as one lens."""
    solos: list[list[str]] = []
    remainders: list[list[str]] = []
    for group in base_groups:
        remainder = [dim for dim in group if dim not in promoted_dims]
        solos.extend([dim] for dim in group if dim in promoted_dims)
        if remainder:
            remainders.append(remainder)
    return solos + remainders


def route(
    *,
    score: float,
    risk_flags: list[str] | None = None,
    entry: str = "age",
    comments: int | None = None,
    ci_class: str | None = None,
) -> dict:
    """Pure decision -- no I/O. Returns the locked age-router output shape:
    {n, lenses, effort, overrides_hit, rationale}."""
    if entry not in ("age", "affinage"):
        raise ValueError(f"invalid entry {entry!r}: must be 'age' or 'affinage'")
    if not math.isfinite(score) or score < 0:
        raise ValueError(f"invalid score {score!r}: must be a non-negative finite number")
    if entry == "age" and (comments is not None or ci_class is not None):
        raise ValueError("comments/ci_class require entry='affinage'")
    risk_flags = risk_flags or []

    # Score -> base tier, with the affinage comment/CI escalation folded in
    # *before* override promotion so promotion composes on top of the
    # escalated tier rather than replacing it (ADR-001).
    base_n = _tier_for_score(score)
    bump_reason = None
    if entry == "affinage":
        if comments is not None and comments >= _AFFINAGE_COMMENT_BUMP:
            bumped = _bump(base_n)
            if bumped != base_n:
                bump_reason = f"{comments} comments"
            base_n = bumped
        if ci_class in _AFFINAGE_CI_BUMP_CLASSES:
            bumped = _bump(base_n)
            if bumped != base_n:
                bump_reason = (
                    f"{bump_reason} + ci_class={ci_class}" if bump_reason else f"ci_class={ci_class}"
                )
            base_n = bumped

    overrides_hit = sorted({flag for flag in risk_flags if flag in OVERRIDE_FLAGS})

    if overrides_hit:
        promoted_dims = {_PROMOTIONS[flag] for flag in overrides_hit}
        lenses = _promote(_raw_groups_for(base_n), promoted_dims)
        n = len(lenses)
        effort = "high"
    else:
        lenses = _raw_groups_for(base_n)
        n = base_n
        effort = "high" if score > _HIGH_EFFORT_SCORE else ("low" if n == 1 else "medium")

    rationale = f"score={score:g}, entry={entry}"
    if entry == "affinage":
        rationale += f", comments={comments}, ci_class={ci_class!r}"
    if bump_reason:
        rationale += f", {bump_reason} escalation"
    if overrides_hit:
        rationale += (
            f", override(s) {', '.join(overrides_hit)} promote "
            f"{', '.join(sorted(promoted_dims))}"
        )
    rationale += f" -> n={n}/effort={effort}"

    return {
        "n": n,
        "lenses": lenses,
        "effort": effort,
        "overrides_hit": overrides_hit,
        "rationale": rationale,
    }