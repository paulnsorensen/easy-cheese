"""Compute per-finding severity and fix-cost-now buckets for /age.

Encodes the rubric documented in skills/age/references/dimensions.md so the
reviewer LLM does not re-derive the formula on every finding.

CLI:

    python3 shared/scripts/severity.py compute \\
        --dimension correctness --base high \\
        --location contract --fix-cost-later spreading
    -> blocker

    python3 shared/scripts/severity.py bucket --files 7 --modules 1
    -> moderate
"""

from __future__ import annotations

import argparse
from enum import IntEnum
from typing import Self, TextIO, cast

from typing_extensions import override

from easy_cheese.shared import cli


class RubricError(ValueError):
    """Raised when a rubric input is outside the allowed vocabulary."""


class _OrderedRubricTier(IntEnum):
    """Base for the rubric's ordered vocabularies: member order IS the ladder.

    Members ascend from least to most severe/costly, so `<` and `max()` express
    the rubric's ordering directly. `str()` yields the wire spelling the /age
    report and the CLI use (lowercase member name).
    """

    @override
    def __str__(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, value: str, *, field: str) -> Self:
        """Parse a wire spelling at the trust boundary, or raise `RubricError`."""
        try:
            return cls[value.upper()]
        except KeyError:
            expected = ", ".join(str(tier) for tier in cls)
            raise RubricError(f"unknown {field} {value!r}; expected one of {expected}") from None


class Severity(_OrderedRubricTier):
    """The /age severity ladder, least → most severe; `BLOCKER` is the cap."""

    LOW = 0
    MEDIUM = 1
    HIGH = 2
    BLOCKER = 3


class FixCostNow(_OrderedRubricTier):
    """Blast-radius bucket for fixing now, least → most costly."""

    CONTAINED = 0
    MODERATE = 1
    SPRAWLING = 2


DIMENSIONS: frozenset[str] = frozenset(
    {
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
    }
)

LOCATION_SENSITIVE: frozenset[str] = frozenset(
    {
        "correctness",
        "security",
        "encapsulation",
        "spec",
        "nih",
        "efficiency",
        "telemetry",
    }
)

LOCATIONS: frozenset[str] = frozenset({"class", "module", "cross-module", "contract"})
FIX_COST_LATER: frozenset[str] = frozenset({"contained", "spreading", "structural"})


def bump(sev: Severity) -> Severity:
    """Promote one tier; `Severity.BLOCKER` is the cap."""
    return Severity.BLOCKER if sev is Severity.BLOCKER else Severity(sev + 1)


def compute_severity(
    *,
    dimension: str,
    base: str,
    location: str,
    fix_cost_later: str,
) -> Severity:
    """Apply contract + structural bumps to a base severity, capped at blocker."""
    if dimension not in DIMENSIONS:
        raise RubricError(f"unknown dimension {dimension!r}")
    sev = Severity.parse(base, field="base")
    if location not in LOCATIONS:
        raise RubricError(f"unknown location {location!r}; expected one of {sorted(LOCATIONS)}")
    if fix_cost_later not in FIX_COST_LATER:
        raise RubricError(
            f"unknown fix-cost-later {fix_cost_later!r}; expected one of {sorted(FIX_COST_LATER)}"
        )

    if location == "contract" and dimension in LOCATION_SENSITIVE:
        sev = bump(sev)
    if fix_cost_later == "structural":
        sev = bump(sev)
    return sev


def bucket_fix_cost_now(*, file_count: int, module_count: int = 1) -> FixCostNow:
    """Bucket a blast-radius file/module count into contained / moderate / sprawling."""
    if file_count < 0:
        raise RubricError(f"file_count must be >= 0, got {file_count}")
    if module_count < 1:
        raise RubricError(f"module_count must be >= 1, got {module_count}")
    if module_count >= 2 or file_count >= 11:
        return FixCostNow.SPRAWLING
    if file_count >= 3:
        return FixCostNow.MODERATE
    return FixCostNow.CONTAINED


def _cmd_compute(args: argparse.Namespace) -> None:
    try:
        result = compute_severity(
            dimension=cast(str, args.dimension),
            base=cast(str, args.base),
            location=cast(str, args.location),
            fix_cost_later=cast(str, args.fix_cost_later),
        )
    except RubricError as exc:
        raise cli.CliError(str(exc)) from exc
    cli.emit(result, stdout=cast("TextIO", args.stdout))


def _cmd_bucket(args: argparse.Namespace) -> None:
    try:
        result = bucket_fix_cost_now(
            file_count=cast(int, args.files), module_count=cast(int, args.modules)
        )
    except RubricError as exc:
        raise cli.CliError(str(exc)) from exc
    cli.emit(result, stdout=cast("TextIO", args.stdout))


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Compute /age rubric severity and fix-cost buckets."
    sub = parser.add_subparsers(dest="cmd", required=True)

    compute = sub.add_parser("compute", help="compute severity from rubric inputs")
    _ = compute.add_argument("--dimension", required=True)
    _ = compute.add_argument("--base", required=True)
    _ = compute.add_argument("--location", required=True)
    _ = compute.add_argument("--fix-cost-later", required=True)
    compute.set_defaults(func=_cmd_compute)

    bucket = sub.add_parser("bucket", help="bucket fix-cost-now from blast-radius counts")
    _ = bucket.add_argument("--files", type=int, required=True, help="file count from tilth_deps")
    _ = bucket.add_argument("--modules", type=int, default=1, help="distinct module count (default 1)")
    bucket.set_defaults(func=_cmd_bucket)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
