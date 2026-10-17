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
from typing import TypedDict

# A touched file costs about eight lines of reviewer attention regardless of
# its line delta -- context-switch cost, not content cost.
FILE_COST: int = 8

# First-match-wins glob -> weight pairs. The table is inverted: default is
# full weight (1.0) for anything unmatched, so an unlisted extension is
# never silently under-reviewed. Only identified non-review surface is
# subtracted from that default.
DEFAULT_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("*.lock", 0.0),
    ("*-lock.json", 0.0),
    ("*-lock.yaml", 0.0),
    ("*.pyc", 0.0),
    ("*.pyz", 0.0),
    ("go.sum", 0.0),
    ("fixtures/**", 0.0),
    ("snapshots/**", 0.0),
    ("vendor/**", 0.0),
    ("README*", 0.25),
    ("CHANGELOG*", 0.25),
    ("docs/**", 0.25),
    ("src/content/**", 0.25),
    (".hallouminate/**", 0.25),
)

# The hyphen in "*-lock.json"/"*-lock.yaml" is required: a real lockfile is
# "package-lock.json" / "pnpm-lock.yaml", always hyphenated before "lock".
# A bare "*lock.json" also matches "unlock.json" or "mylock.yaml" -- ordinary
# source whose basename merely ends in the substring "lock" -- and silently
# zeroes it out of review sizing.

_DEFAULT_WEIGHT = 1.0


class ReviewScore(TypedDict):
    score: float
    weighted_files: float
    weighted_lines: float
    zeroed: list[str]
    weights_source: str
    rows: int


def weigh(path: str, weights: tuple[tuple[str, float], ...] | None = None) -> float:
    """First-match-wins glob weight for a single path.

    A pattern with no "/" is basename-anchored -- it matches only the
    path's final segment (path.rsplit("/", 1)[-1]). It still matches at any
    depth ("a/b/README.md" -> 0.25, "deep/dir/go.sum" -> 0.0), but because
    fnmatch's "*" crosses "/", the nested form "**/README*" would also match
    a *directory* component and quarter real source underneath it:
    "src/READMEs/code.py" scored 0.25 that way, and is 1.0 here.

    Basename anchoring does not by itself stop a pattern from over-matching
    within the filename -- "*lock.json" still swallows "src/unlock.json" on
    its basename alone. That is why the lockfile globs are hyphenated
    ("*-lock.json", "*-lock.yaml"); see ADR-002. One residual over-match is
    accepted: "src/READMEparser.py" weighs 0.25, since its basename really
    does start with "README".

    A pattern containing "/" keeps the anchored-or-nested match
    (fnmatchcase(path, pat) or fnmatchcase(path, "**/" + pat)) so a
    directory name means that directory anywhere in the tree.

    Uses fnmatchcase (not fnmatch) -- fnmatch applies os.path.normcase,
    which would make this determinism-critical module platform-dependent.

    Falls through to _DEFAULT_WEIGHT (1.0) when nothing matches.
    """
    table = weights if weights is not None else DEFAULT_WEIGHTS
    basename = path.rsplit("/", 1)[-1]
    for pattern, weight in table:
        if "/" in pattern:
            if fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, "**/" + pattern):
                return weight
        elif fnmatch.fnmatchcase(basename, pattern):
            return weight
    return _DEFAULT_WEIGHT


def score(
    rows: list[tuple[str, int, int]],
    weights: tuple[tuple[str, float], ...] | None = None,
    weights_source: str = "defaults",
) -> ReviewScore:
    """rows are (path, insertions, deletions) numstat tuples. Returns
    {score, weighted_files, weighted_lines, zeroed, weights_source, rows}.

    weights_source is provenance only (the CLI's knowledge of whether
    DEFAULT_WEIGHTS or a --config override was used) -- it does not affect
    scoring. The weights table is resolved once here and passed down to
    every weigh() call rather than re-resolving the None sentinel per row.
    """
    table = weights if weights is not None else DEFAULT_WEIGHTS
    weighted_lines = 0.0
    weighted_files = 0.0
    zeroed: list[str] = []
    for path, insertions, deletions in rows:
        w = weigh(path, weights=table)
        weighted_lines += w * (insertions + deletions)
        weighted_files += w
        if w == 0.0:
            zeroed.append(path)
    return {
        "score": weighted_lines + FILE_COST * weighted_files,
        "weighted_files": weighted_files,
        "weighted_lines": weighted_lines,
        "zeroed": zeroed,
        "weights_source": weights_source,
        "rows": len(rows),
    }
