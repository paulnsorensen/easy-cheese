"""JSON CLI wrapper for the Press attempt telemetry record.

The request carries only what the agent observed: slug, attempt, tool errors,
delegations, and changed files. `outcome` and `repair_cycles` are read from
the attempt's route artifact, `.cheese/press/<slug>.attempt-N.route.json`,
the same document `press-route` routed on, so the record can never disagree
with the route it audits (#611). This module owns that one file read;
`press_telemetry` stays pure.
"""

from __future__ import annotations

from pathlib import Path

import fromargs

from easy_cheese.shared import paths
from easy_cheese.shared.manifest_io import (
    ManifestLoadError,
    read_mapping_arg_or_stdin,
    read_mapping_file,
)
from easy_cheese_schemas.validate import require_exact_keys

from .press_telemetry import require_attempt_number, telemetry_record

_REQUEST_KEYS = ("slug", "attempt", "tool_errors", "delegations", "changed_files")
_ROUTE_KEYS = ("outcome", "repair_cycles")


def _route_artifact_path(slug: str, attempt: int) -> Path:
    """The route request `press-route` read for attempt N of `slug`."""
    press_dir = paths.phase_dirpath("press", paths.resolve_repo_root(None))
    return press_dir / f"{slug}.attempt-{attempt}.route.json"


def _read_route(slug: object, attempt: object) -> dict[str, object]:
    # Validate both locator fields before they touch a path: an unchecked slug
    # could otherwise name a file outside `.cheese/press/`.
    slug_error = paths.validate_slug(slug)
    if slug_error is not None:
        raise ValueError(slug_error)
    assert isinstance(slug, str)
    path = _route_artifact_path(slug, require_attempt_number(attempt))
    if not path.is_file():
        raise ValueError(
            f"route artifact not found: {path}; run press-route for this attempt first"
        )
    try:
        route = read_mapping_file(path)
    except ManifestLoadError as exc:
        raise ValueError(str(exc)) from exc
    require_exact_keys(route, _ROUTE_KEYS, f"route artifact {path}")
    return route


def _record(
    *,
    slug: object,
    attempt: object,
    tool_errors: object,
    delegations: object,
    changed_files: object,
) -> dict[str, object]:
    route = _read_route(slug, attempt)
    return telemetry_record(
        slug=slug,
        attempt=attempt,
        outcome=route["outcome"],
        repair_cycles=route["repair_cycles"],
        tool_errors=tool_errors,
        delegations=delegations,
        changed_files=changed_files,
    )


_USAGE = "usage: press_telemetry_cli.py [<request.json>]"


def press_telemetry_cmd(path: str | None = None) -> dict[str, object]:
    """Build the Press attempt telemetry record.

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
        require_exact_keys(payload, _REQUEST_KEYS, "request")
        return _record(**payload)
    except (TypeError, ValueError) as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc


def build_app() -> fromargs.App:
    return fromargs.App(
        "press-telemetry",
        help="Build the Press attempt telemetry record.",
        help_formatter="plain",
        default_command=press_telemetry_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
