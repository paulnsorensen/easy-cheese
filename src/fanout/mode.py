#!/usr/bin/env python3
"""Canonical curd-count threshold and the authoritative mode selector.

`PARALLEL_THRESHOLD` is the single source of truth for how many curds make a
decomposition worth fanning out. A decomposition of `PARALLEL_THRESHOLD` or more
curds runs /ultracook's parallel mode; fewer stays linear. Both the fan-out
engine (`validate_decomposition`) and the mold pre-dispatch hint (`curd-count`)
import this constant, so exactly one number governs the split.

The decomposer stays the authoritative mode gate at run time — this selector is
the deterministic function it (and the mold hint) call to turn a curd count into
a mode name.
"""
from __future__ import annotations

import cli

PARALLEL_THRESHOLD = 2


def select_mode(curds) -> str:
    """Return "parallel" when the decomposition has at least
    `PARALLEL_THRESHOLD` curds, else "linear". `curds` is any sized
    collection — only its length is consulted."""
    return "parallel" if len(curds) >= PARALLEL_THRESHOLD else "linear"


def _cmd_select(args: object) -> None:
    # The decomposer knows the curd count; the count is all select_mode reads.
    cli.emit(select_mode(range(args.count)), json_mode=args.json_mode)


def _setup(parser) -> None:
    parser.description = "Pick /ultracook's mode (linear|parallel) from a curd count."
    parser.add_argument(
        "--count",
        type=int,
        required=True,
        help="Number of curds in the decomposition.",
    )
    parser.set_defaults(func=_cmd_select)


if __name__ == "__main__":
    cli.run(_setup)
