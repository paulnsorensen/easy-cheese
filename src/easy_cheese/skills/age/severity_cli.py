"""The /age `severity` command: rubric severity and fix-cost-now buckets.

The rubric lives in `easy_cheese_review.severity`. This module only adapts it
to the bundle command surface.

    age.pyz severity compute --dimension correctness --base high \\
        --location contract --fix-cost-later spreading
    -> blocker

    age.pyz severity bucket --files 7 --modules 1
    -> moderate
"""

from __future__ import annotations

import fromargs

from easy_cheese_review.severity import RubricError, bucket_fix_cost_now, compute_severity


def compute(*, dimension: str, base: str, location: str, fix_cost_later: str) -> str:
    """Compute severity from rubric inputs.

    Parameters
    ----------
    dimension
        Review dimension name.
    base
        Base severity tier (low/medium/high/blocker).
    location
        Finding location (class/module/cross-module/contract).
    fix_cost_later
        Fix-cost-later bucket (contained/spreading/structural).
    """
    try:
        result = compute_severity(
            dimension=dimension,
            base=base,
            location=location,
            fix_cost_later=fix_cost_later,
        )
    except RubricError as exc:
        raise fromargs.CliError(str(exc)) from exc
    return str(result)


def bucket(*, files: int, modules: int = 1) -> str:
    """Bucket fix-cost-now from blast-radius counts.

    Parameters
    ----------
    files
        File count from tilth_deps.
    modules
        Distinct module count (default 1).
    """
    try:
        result = bucket_fix_cost_now(file_count=files, module_count=modules)
    except RubricError as exc:
        raise fromargs.CliError(str(exc)) from exc
    return str(result)


def build_app() -> fromargs.App:
    app = fromargs.App(
        "severity",
        help="Compute /age rubric severity and fix-cost buckets.",
        help_formatter="plain",
    )
    _ = app.command(compute, name="compute")
    _ = app.command(bucket, name="bucket")
    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
