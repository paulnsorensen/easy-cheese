#!/usr/bin/env python3
"""Canonical thresholds and the two mode selectors for /cook's fan-out gate.

Two selectors, chosen by whether a curd block exists:

- A curd block exists: `select_mode(curds)` reads `PARALLEL_THRESHOLD` (2) --
  "parallel" at `len(curds) >= PARALLEL_THRESHOLD`, else "linear". Both the
  fan-out engine (`validate_decomposition`) and the mold pre-dispatch hint
  (`curd-count`) import this constant, so exactly one number governs the
  split.
- No curd block exists (a PR or fresh branch with no handoff):
  `select_mode_from_score(score)` reads `DECOMPOSE_FIRST_THRESHOLD` (250) --
  "decompose-first" above it, else "linear". It never returns "parallel":
  score alone proves nothing about file-disjointness, so blind parallel
  fan-out is never safe at any size -- a large no-handoff branch routes to
  the decomposer instead.

The decomposer stays the authoritative mode gate at run time for the
curd-block path -- `select_mode` is the deterministic function it (and the
mold hint) call to turn a curd count into a mode name.
"""
from __future__ import annotations

import math
from collections.abc import Sized

import fromargs

LEAVES = ("select",)

PARALLEL_THRESHOLD = 2

# No curd-block proof of file-disjointness exists without a curd block, so
# fanning coders in parallel is never safe purely on size. A big un-curded
# spec routes to the decomposer instead of blind parallelism.
DECOMPOSE_FIRST_THRESHOLD = 250


def select_mode(curds: Sized) -> str:
    """Return "parallel" when the decomposition has at least
    `PARALLEL_THRESHOLD` curds, else "linear". `curds` is any sized
    collection — only its length is consulted."""
    return "parallel" if len(curds) >= PARALLEL_THRESHOLD else "linear"


def select_mode_from_score(score: float) -> str:
    """Return "decompose-first" above DECOMPOSE_FIRST_THRESHOLD, else "linear".
    Never returns "parallel" -- score alone proves nothing about file
    disjointness, so blind parallel fan-out is never safe at any size."""
    return (
        "decompose-first"
        if score > DECOMPOSE_FIRST_THRESHOLD
        else "linear"
    )


def select_cmd(*, count: int | None = None, score: float | None = None) -> str:
    """Pick /ultracook's mode (linear|parallel|decompose-first) from a curd
    count (curd block present) or a score (no curd block).

    Parameters
    ----------
    count
        Number of curds in the decomposition.
    score
        Fan-out score for the no-curd-block fallback.
    """
    if count is not None and score is not None:
        raise fromargs.CliError("--count and --score are mutually exclusive")
    if count is None and score is None:
        raise fromargs.CliError("one of --count or --score is required")
    if count is not None:
        # The decomposer knows the curd count; the count is all select_mode reads.
        if count < 0:
            raise fromargs.CliError(f"invalid --count {count}: must be zero or greater")
        return select_mode(range(count))
    assert score is not None
    if not math.isfinite(score) or score < 0:
        raise fromargs.CliError(f"invalid --score {score}: must be zero or greater and finite")
    return select_mode_from_score(score)


def build_app() -> fromargs.App:
    return fromargs.App(
        "mode",
        help=(
            "Pick /ultracook's mode (linear|parallel|decompose-first) from a "
            "curd count (curd block present) or a score (no curd block)."
        ),
        help_formatter="plain",
        default_command=select_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
