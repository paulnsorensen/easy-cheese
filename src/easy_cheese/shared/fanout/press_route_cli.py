"""JSON CLI wrapper for the Press route decision."""

from __future__ import annotations

import sys
from dataclasses import asdict

from easy_cheese.shared.manifest_io import json_command
from easy_cheese_schemas.validate import is_int

from .press_route import Continue, Dispatch, Stop, press_route


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


main = json_command(
    _route,
    "usage: press_route_cli.py [<request.json>]",
    keys=("outcome", "repair_cycles"),
)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
