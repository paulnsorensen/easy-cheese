"""CLI entry point for age_route.route -- contextual JSON in, JSON out.

The request is read from an optional JSON path or stdin and passed to the pure
contextual planner.  This wrapper owns only argument and stream I/O.
"""
from __future__ import annotations

import fromargs

from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin

from .age_route import route

_USAGE = "usage: age_route_cli.py [<request.json>]"


def age_route(path: str | None = None) -> dict[str, object]:
    """Size an /age review from contextual JSON input.

    Parameters
    ----------
    path
        Path to the request JSON; reads stdin when omitted.
    """
    argv = [path] if path else []
    try:
        payload = read_mapping_arg_or_stdin(argv, _USAGE)
    except ManifestLoadError as exc:
        raise fromargs.CliError(str(exc), exit_code=2) from exc
    try:
        return route(**payload)  # pyright: ignore[reportArgumentType]
    except (TypeError, ValueError) as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc


def build_app() -> fromargs.App:
    return fromargs.App(
        "age-route",
        help="Size an /age review from contextual JSON input.",
        help_formatter="plain",
        default_command=age_route,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
