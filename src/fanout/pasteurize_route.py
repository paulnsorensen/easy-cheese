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
against 30 commits of real history) these eight numbers have no historical
validation. They are named module-level constants specifically so a future
reader can revise them in one place once real runs exist.

Pure function -- no I/O, no network, no file reads, same AST-banned-import
contract as age_route.py.
"""
from __future__ import annotations

import math

# Boundary between a tight and a wide suspect range, in review_surface score
# units. Reasoned, not measured -- see module docstring.
WIDE_RANGE_THRESHOLD = 250

# Fan width for a regression, tight range, deterministic repro.
_REGRESSION_TIGHT_DETERMINISTIC_N = 1

# Fan width for a regression, tight range, no deterministic repro (less
# evidence -> more agents).
_REGRESSION_TIGHT_NONDETERMINISTIC_N = 2

# Fan width for a regression, wide range, deterministic repro.
_REGRESSION_WIDE_DETERMINISTIC_N = 2

# Fan width for a regression, wide range, no deterministic repro.
_REGRESSION_WIDE_NONDETERMINISTIC_N = 3

# Fan width for heisenbug/race/perf-regression shapes, any range, any repro.
_UNSTABLE_REPRO_N = 3

# Fan width for a cold bug with no diff to anchor to (score is None),
# deterministic repro.
_COLD_BUG_DETERMINISTIC_N = 3

# Fan width for a cold bug with no diff to anchor to (score is None),
# no deterministic repro.
_COLD_BUG_NONDETERMINISTIC_N = 5

BUG_SHAPES = frozenset({"regression", "heisenbug", "race", "perf_regression", "cold"})


def size_pasteurize_fanout(bug_shape: str, score: float | None, deterministic_repro: bool) -> int:
    """Pure decision -- no I/O. Returns the agent fan width for /pasteurize.

    heisenbug / race / perf_regression, any range, any repro              -> 3
    cold bug, no diff to anchor to (score is None), deterministic repro   -> 3
    cold bug, no diff to anchor to (score is None), no deterministic repro -> 5
    regression, tight range (score <= WIDE_RANGE_THRESHOLD), deterministic -> 1
    regression, tight range (score <= WIDE_RANGE_THRESHOLD), non-deterministic -> 2
    regression, wide range (score > WIDE_RANGE_THRESHOLD), deterministic  -> 2
    regression, wide range (score > WIDE_RANGE_THRESHOLD), non-deterministic -> 3
    """
    if bug_shape not in BUG_SHAPES:
        raise ValueError(f"invalid bug_shape {bug_shape!r}: must be one of {sorted(BUG_SHAPES)}")
    if score is not None and (not math.isfinite(score) or score < 0):
        raise ValueError(f"invalid score {score!r}: must be a non-negative finite number")
    if not isinstance(deterministic_repro, bool):
        raise ValueError(f"invalid deterministic_repro {deterministic_repro!r}: must be a bool")

    if bug_shape in ("heisenbug", "race", "perf_regression"):
        return _UNSTABLE_REPRO_N

    if bug_shape == "cold" or score is None:
        return _COLD_BUG_DETERMINISTIC_N if deterministic_repro else _COLD_BUG_NONDETERMINISTIC_N

    # regression
    if score > WIDE_RANGE_THRESHOLD:
        return _REGRESSION_WIDE_DETERMINISTIC_N if deterministic_repro else _REGRESSION_WIDE_NONDETERMINISTIC_N
    return _REGRESSION_TIGHT_DETERMINISTIC_N if deterministic_repro else _REGRESSION_TIGHT_NONDETERMINISTIC_N