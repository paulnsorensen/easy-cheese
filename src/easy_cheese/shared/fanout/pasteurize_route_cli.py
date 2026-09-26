"""CLI entry point for pasteurize_route.size_pasteurize_fanout -- JSON in
(arg path or stdin), JSON out.

Split from pasteurize_route.py so that module stays a pure function with
zero I/O imports (see pasteurize_route.py's module docstring); all I/O for
pyz dispatch lives here instead.
"""
from __future__ import annotations

import fromargs

from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin

from .pasteurize_route import size_pasteurize_fanout

_USAGE = "usage: pasteurize_route_cli.py [<request.json>]"


def pasteurize_route(path: str | None = None) -> int:
    """Size a /pasteurize investigation into agents from JSON input.

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
        return size_pasteurize_fanout(**payload)  # pyright: ignore[reportArgumentType]
    except (TypeError, ValueError) as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc


def build_app() -> fromargs.App:
    return fromargs.App(
        "pasteurize-route",
        help="Size a /pasteurize investigation into agents from JSON input.",
        help_formatter="plain",
        default_command=pasteurize_route,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
