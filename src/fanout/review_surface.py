"""Pure git-derived, code-weighted review-surface scorer.

Spec: deterministic-fanout-sizing.md `### 1. review_surface` and
`## Validation evidence`. Replaces raw diff-stat sizing (age_route.py's
files_changed/insertions/deletions) with one monotone score that weighs
non-review surface (lockfiles, fixtures, vendored code) toward zero and
prose toward a quarter weight, so a touched file costs roughly
FILE_COST lines of attention:

    score = sum(weight * lines) + FILE_COST * sum(weight)

Pure function -- no I/O, no network, no file reads. A sibling CLI runs git
and hands this module numstat rows; this module only classifies and scores
them. Inherits age_route.py's AST-derived import ban (see
tests/fanout/python/test_review_surface.py::TestPurity).
"""
from __future__ import annotations

import fnmatch

# A touched file costs about eight lines of reviewer attention regardless of
# its line delta -- context-switch cost, not content cost.
FILE_COST: int = 8

# First-match-wins glob -> weight pairs. The table is inverted: default is
# full weight (1.0) for anything unmatched, so an unlisted extension is
# never silently under-reviewed. Only identified non-review surface is
# subtracted from that default.
DEFAULT_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("*.lock", 0.0),
    ("*lock.json", 0.0),
    ("*lock.yaml", 0.0),
    ("*.pyc", 0.0),
    ("*.pyz", 0.0),
    ("fixtures/**", 0.0),
    ("snapshots/**", 0.0),
    ("vendor/**", 0.0),
    ("README*", 0.25),
    ("CHANGELOG*", 0.25),
    ("docs/**", 0.25),
    ("src/content/**", 0.25),
    (".hallouminate/**", 0.25),
)

_DEFAULT_WEIGHT = 1.0


def weigh(path: str, weights: tuple[tuple[str, float], ...] | None = None) -> float:
    """First-match-wins glob weight for a single path. Falls through to
    _DEFAULT_WEIGHT (1.0) when nothing matches."""
    table = weights if weights is not None else DEFAULT_WEIGHTS
    # Patterns match anchored (at repo root) or nested ("**/" + pattern)
    # so the table reads position-independently regardless of where a
    # matching path sits in the tree.
    for pattern, weight in table:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, "**/" + pattern):
            return weight
    return _DEFAULT_WEIGHT


def score(
    rows: list[tuple[str, int, int]],
    weights: tuple[tuple[str, float], ...] | None = None,
) -> dict:
    """rows are (path, insertions, deletions) numstat tuples. Returns
    {score, weighted_files, weighted_lines, zeroed}."""
    weighted_lines = 0.0
    weighted_files = 0.0
    zeroed: list[str] = []
    for path, insertions, deletions in rows:
        w = weigh(path, weights=weights)
        weighted_lines += w * (insertions + deletions)
        weighted_files += w
        if w == 0.0:
            zeroed.append(path)
    return {
        "score": weighted_lines + FILE_COST * weighted_files,
        "weighted_files": weighted_files,
        "weighted_lines": weighted_lines,
        "zeroed": zeroed,
    }
