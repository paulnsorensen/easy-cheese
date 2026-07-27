"""Pure /pasteurize fan-out sizing policy.

Spec: deterministic-fanout-sizing.md `### 5. /pasteurize -- the signal is
inverted`. A reviewer (age_route.route) reads a diff that exists: more diff
-> more agents. A debugger fans over a SEARCH SPACE: less evidence -> more
agents. size_pasteurize_fanout reads the review_surface score DESCENDING,
over the suspect range (last-known-good..HEAD), not over a diff under
review -- a distinct function, not another mode of age_route.route or
mode.select_mode.

EVERY THRESHOLD BELOW IS A REASONED GUESS, NOT A MEASUREMENT. /pasteurize
fans zero agents today, so unlike every age_route threshold (each checked
against 30 commits of real history) these four numbers have no historical
validation. They are named module-level constants specifically so a future
reader can revise them in one place once real runs exist.

Pure function -- no I/O, no network, no file reads, same AST-banned-import
contract as age_route.py.
"""
from __future__ import annotations

# Boundary between a tight and a wide suspect range, in review_surface score
# units. Reasoned, not measured -- see module docstring.
WIDE_RANGE_THRESHOLD = 250

# Fan width for a regression with a deterministic repro, tight range.
_REGRESSION_TIGHT_N = 1

# Fan width for a regression with a deterministic repro, wide range.
_REGRESSION_WIDE_N = 2

# Fan width for heisenbug/race/perf-regression shapes, any range.
_UNSTABLE_REPRO_N = 3

# Fan width range for a cold bug with no diff to anchor to (score is None).
_COLD_BUG_MIN_N = 3
_COLD_BUG_MAX_N = 5

BUG_SHAPES = frozenset({"regression", "heisenbug", "race", "perf_regression", "cold"})


def size_pasteurize_fanout(bug_shape: str, score: float | None, deterministic_repro: bool) -> int:
    """Pure decision -- no I/O. Returns the agent fan width for /pasteurize.

    regression, tight range (score < WIDE_RANGE_THRESHOLD), deterministic repro -> 1
    regression, wide range (score > WIDE_RANGE_THRESHOLD), deterministic repro  -> 2
    heisenbug / race / perf_regression, any range                             -> 3
    cold bug, no diff to anchor to (score is None)                            -> 3..5
    """
    if bug_shape not in BUG_SHAPES:
        raise ValueError(f"invalid bug_shape {bug_shape!r}: must be one of {sorted(BUG_SHAPES)}")

    if bug_shape == "cold" or score is None:
        return _COLD_BUG_MAX_N if not deterministic_repro else _COLD_BUG_MIN_N

    if bug_shape in ("heisenbug", "race", "perf_regression"):
        return _UNSTABLE_REPRO_N

    # regression
    if score > WIDE_RANGE_THRESHOLD:
        return _REGRESSION_WIDE_N
    return _REGRESSION_TIGHT_N
