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

Lopsided-split guard (issue #273 ask 2): count alone misjudges a dominant curd
plus a trivial one (e.g. a one-line config allowlist entry) as worth
parallelizing. When `select_mode` receives curd dicts carrying a size signal
(the manifest's `weight` field, or its `files[]` list — see
references/manifest-schema.json), a 2-curd split where exactly one curd is
trivial (weight <= TRIVIAL_FILE_COUNT) routes linear instead of parallel.

Design decisions (spec left these open; resolved here, see
specs/ultracook-lopsided-split-guard.md):
  - Weight metric: estimated file count per curd. Curds are already
    file-disjoint sets, so `len(files)` is a free, truthful proxy — no LOC
    estimate or separate trivial/substantial flag needed.
  - Dominance rule: only an exact 2-curd split, one trivial (<=1 file) plus
    one substantial, counts as "lopsided". Balanced multi-curd splits
    (>=2 substantial curds) are unaffected — no regression to the common case.
  - Fold vs linear: the guard only changes mode selection (routes linear); it
    does not mutate the manifest to fold the trivial curd into a sibling.
    Folding trivial curds at decomposition time is the decomposer's job (see
    decomposer-prompt.md); this guard is the runtime backstop for a trivial
    curd that still makes it into the manifest standalone.

Curds with no size signal (plain ints, `range()` elements — the CLI's
`--count`-only entry point) are unaffected: the guard requires a weight on
both curds to fire, so count-only callers keep the old pure count-based
behavior.
"""
from __future__ import annotations

import cli

PARALLEL_THRESHOLD = 2

# A curd touching this many files or fewer is "trivial" for the
# lopsided-split guard (e.g. a one-line config/allowlist entry).
TRIVIAL_FILE_COUNT = 1


def _curd_weight(curd: object) -> int | None:
    """Return `curd`'s file-count weight, or None if it carries no size
    signal. Accepts a manifest curd dict (`weight`, falling back to
    `len(files)`); any other shape (int, range element, ...) has no signal."""
    if not isinstance(curd, dict):
        return None
    weight = curd.get("weight")
    if isinstance(weight, int):
        return weight
    files = curd.get("files")
    if isinstance(files, list):
        return len(files)
    return None


def _is_lopsided_split(curds) -> bool:
    """A 2-curd split where one curd is trivial and the other substantial.
    Only fires when both curds carry a weight signal and there are exactly
    PARALLEL_THRESHOLD curds — balanced splits of >=2 substantial curds, and
    splits of more than 2 curds, are never considered lopsided here."""
    if len(curds) != PARALLEL_THRESHOLD:
        return False
    weights = [_curd_weight(c) for c in curds]
    if any(w is None for w in weights):
        return False
    trivial = [w <= TRIVIAL_FILE_COUNT for w in weights]
    return trivial.count(True) == 1 and trivial.count(False) == 1


def select_mode(curds) -> str:
    """Return "parallel" when the decomposition has at least
    `PARALLEL_THRESHOLD` curds and is not a lopsided dominant+trivial split,
    else "linear". `curds` is any sized collection; when its elements are
    manifest curd dicts carrying a size signal, the lopsided-split guard
    weighs size too, not count alone."""
    if len(curds) < PARALLEL_THRESHOLD:
        return "linear"
    if _is_lopsided_split(curds):
        return "linear"
    return "parallel"


def _cmd_select(args: object) -> None:
    # The decomposer knows the curd count; the count is all select_mode reads.
    if args.count < 0:
        raise cli.CliError(f"invalid --count {args.count}: must be zero or greater")
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
