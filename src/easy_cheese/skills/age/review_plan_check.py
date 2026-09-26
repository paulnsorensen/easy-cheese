"""Check supplied dispatch observations against an Age review plan."""

from __future__ import annotations

import fromargs

from easy_cheese.shared.fanout.age_route import check_execution
from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin
from easy_cheese_schemas.validate import require_exact_keys

_USAGE = "usage: review-plan-check [<request.json>]"
_KEYS = ("plan", "observations")


def review_plan_check(path: str | None = None) -> dict[str, object]:
    """Check supplied dispatch observations against an Age review plan.

    Parameters
    ----------
    path
        Path to the request JSON (plan, observations); reads stdin when omitted.
    """
    argv = [path] if path else []
    try:
        payload = read_mapping_arg_or_stdin(argv, _USAGE)
    except ManifestLoadError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    try:
        require_exact_keys(payload, _KEYS, "request")
        return check_execution(**payload)  # pyright: ignore[reportArgumentType]
    except (TypeError, ValueError) as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc


def build_app() -> fromargs.App:
    return fromargs.App(
        "review-plan-check",
        help="Check supplied dispatch observations against an Age review plan.",
        help_formatter="plain",
        default_command=review_plan_check,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
