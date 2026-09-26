"""JSON CLI wrapper for the Press route decision."""

from __future__ import annotations

from dataclasses import asdict

import fromargs

from easy_cheese.shared.manifest_io import ManifestLoadError, read_mapping_arg_or_stdin
from easy_cheese_schemas.validate import is_int, require_exact_keys

from .press_route import Continue, Dispatch, Stop, press_route

_USAGE = "usage: press_route_cli.py [<request.json>]"
_KEYS = ("outcome", "repair_cycles")


def _action_payload(action: Continue | Dispatch | Stop) -> dict[str, object]:
    if isinstance(action, Continue):
        name = "continue"
    elif isinstance(action, Dispatch):
        name = "dispatch"
    else:
        name = "stop"
    return {"action": name, **asdict(action)}


def _route(*, outcome: object, repair_cycles: object) -> dict[str, object]:
    if not isinstance(outcome, str):
        raise ValueError("outcome must be a string")
    if not is_int(repair_cycles):
        raise ValueError("repair_cycles must be a non-negative integer")
    return _action_payload(press_route(outcome, repair_cycles))


def press_route_cmd(path: str | None = None) -> dict[str, object]:
    """Return the Press action: continue, dispatch /age, or stop.

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
        require_exact_keys(payload, _KEYS, "request")
        return _route(**payload)
    except (TypeError, ValueError) as exc:
        raise fromargs.CliError(str(exc), exit_code=1) from exc


def build_app() -> fromargs.App:
    return fromargs.App(
        "press-route",
        help="Return the Press action: continue, dispatch /age, or stop.",
        help_formatter="plain",
        default_command=press_route_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
