"""Compute per-finding severity and fix-cost-now buckets for /age.

Encodes the rubric documented in skills/age/references/dimensions.md so the
reviewer LLM does not re-derive the formula on every finding.

Severity formula:

    sev = base(dimension, finding)
    if location == "contract" and dimension in LOCATION_SENSITIVE:
        sev = bump(sev)
    if fix_cost_later == "structural":
        sev = bump(sev)
    sev = cap(sev, "blocker")

Fix-cost-now bucketing:

    contained  : 1-2 files, single module
    moderate   : 3-10 files, single module
    sprawling  : 11+ files, OR multiple modules

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
import sys

SEVERITY_LADDER: tuple[str, ...] = ("low", "medium", "high", "blocker")
_SEV_INDEX = {sev: i for i, sev in enumerate(SEVERITY_LADDER)}

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
FIX_COST_NOW: tuple[str, ...] = ("contained", "moderate", "sprawling")


class RubricError(ValueError):
    """Raised when a rubric input is outside the allowed vocabulary."""


def bump(sev: str) -> str:
    """Promote one tier; blocker is the cap."""
    if sev not in _SEV_INDEX:
        raise RubricError(f"unknown severity {sev!r}; expected one of {SEVERITY_LADDER}")
    return SEVERITY_LADDER[min(_SEV_INDEX[sev] + 1, len(SEVERITY_LADDER) - 1)]


def compute_severity(
    *,
    dimension: str,
    base: str,
    location: str,
    fix_cost_later: str,
) -> str:
    """Apply contract + structural bumps to a base severity, capped at blocker."""
    if dimension not in DIMENSIONS:
        raise RubricError(f"unknown dimension {dimension!r}")
    if base not in _SEV_INDEX:
        raise RubricError(f"unknown base {base!r}; expected one of {SEVERITY_LADDER}")
    if location not in LOCATIONS:
        raise RubricError(f"unknown location {location!r}; expected one of {sorted(LOCATIONS)}")
    if fix_cost_later not in FIX_COST_LATER:
        raise RubricError(
            f"unknown fix-cost-later {fix_cost_later!r}; expected one of {sorted(FIX_COST_LATER)}"
        )

    sev = base
    if location == "contract" and dimension in LOCATION_SENSITIVE:
        sev = bump(sev)
    if fix_cost_later == "structural":
        sev = bump(sev)
    return sev


def bucket_fix_cost_now(*, file_count: int, module_count: int = 1) -> str:
    """Bucket a blast-radius file/module count into contained / moderate / sprawling."""
    if file_count < 0:
        raise RubricError(f"file_count must be >= 0, got {file_count}")
    if module_count < 1:
        raise RubricError(f"module_count must be >= 1, got {module_count}")
    if module_count >= 2 or file_count >= 11:
        return "sprawling"
    if file_count >= 3:
        return "moderate"
    return "contained"


def _cmd_compute(args: argparse.Namespace) -> int:
    try:
        print(
            compute_severity(
                dimension=args.dimension,
                base=args.base,
                location=args.location,
                fix_cost_later=args.fix_cost_later,
            )
        )
    except RubricError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def _cmd_bucket(args: argparse.Namespace) -> int:
    try:
        print(bucket_fix_cost_now(file_count=args.files, module_count=args.modules))
    except RubricError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compute /age rubric severity and fix-cost buckets.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    compute = sub.add_parser("compute", help="compute severity from rubric inputs")
    compute.add_argument("--dimension", required=True, choices=sorted(DIMENSIONS))
    compute.add_argument("--base", required=True, choices=SEVERITY_LADDER)
    compute.add_argument("--location", required=True, choices=sorted(LOCATIONS))
    compute.add_argument("--fix-cost-later", required=True, choices=sorted(FIX_COST_LATER))
    compute.set_defaults(func=_cmd_compute)

    bucket = sub.add_parser("bucket", help="bucket fix-cost-now from blast-radius counts")
    bucket.add_argument("--files", type=int, required=True, help="file count from tilth_deps")
    bucket.add_argument("--modules", type=int, default=1, help="distinct module count (default 1)")
    bucket.set_defaults(func=_cmd_bucket)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
