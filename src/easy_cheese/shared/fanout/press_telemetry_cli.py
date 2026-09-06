"""JSON CLI wrapper for the Press attempt telemetry record.

The request carries only what the agent observed: slug, attempt, tool errors,
delegations, and changed files. `outcome` and `repair_cycles` are read from
the attempt's route artifact, `.cheese/press/<slug>.attempt-N.route.json`,
the same document `press-route` routed on, so the record can never disagree
with the route it audits (#611). This module owns that one file read;
`press_telemetry` stays pure.
"""

from __future__ import annotations

import sys
from pathlib import Path

from easy_cheese.shared import paths
from easy_cheese.shared.manifest_io import ManifestLoadError, json_command, parse_mapping
from easy_cheese_schemas.validate import require_exact_keys

from .press_telemetry import require_attempt_number, telemetry_record

_REQUEST_KEYS = ("slug", "attempt", "tool_errors", "delegations", "changed_files")
_ROUTE_KEYS = ("outcome", "repair_cycles")


def route_artifact_path(slug: str, attempt: int, *, repo_root: Path | None = None) -> Path:
    """The route request `press-route` read for attempt N of `slug`.

    Resolved under the git worktree root, else the working directory, the
    same rule `paths.list_artifacts` uses for `.cheese/`.
    """
    root = repo_root if repo_root is not None else (paths.git_toplevel() or Path.cwd())
    return root / ".cheese" / paths.phase_dir("press") / f"{slug}.attempt-{attempt}.route.json"


def _read_route(slug: object, attempt: object) -> dict[str, object]:
    # Validate both locator fields before they touch a path: an unchecked slug
    # could otherwise name a file outside `.cheese/press/`.
    slug_error = paths.validate_slug(slug)
    if slug_error is not None:
        raise ValueError(slug_error)
    assert isinstance(slug, str)
    path = route_artifact_path(slug, require_attempt_number(attempt))
    try:
        route = parse_mapping(path.read_text(encoding="utf-8"), str(path))
    except FileNotFoundError as exc:
        raise ValueError(
            f"route artifact not found: {path}; run press-route for this attempt first"
        ) from exc
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


main = json_command(
    _record,
    "usage: press_telemetry_cli.py [<request.json>]",
    keys=_REQUEST_KEYS,
)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
