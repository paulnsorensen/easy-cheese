"""JSON CLI wrapper for the Press route decision."""

from __future__ import annotations

import sys
from dataclasses import asdict

from easy_cheese.shared.manifest_io import json_command

from .press_route import Continue, Dispatch, Stop, press_route

_EXPECTED_KEYS = {"outcome", "repair_cycles"}


def _action_payload(action: Continue | Dispatch | Stop) -> dict[str, object]:
    if isinstance(action, Continue):
        name = "continue"
    elif isinstance(action, Dispatch):
        name = "dispatch"
    else:
        name = "stop"
    return {"action": name, **asdict(action)}


def _route(**payload: object) -> dict[str, object]:
    if set(payload) != _EXPECTED_KEYS:
        raise ValueError("request must contain exactly outcome and repair_cycles")
    outcome = payload["outcome"]
    repair_cycles = payload["repair_cycles"]
    if not isinstance(outcome, str):
        raise ValueError("outcome must be a string")
    if isinstance(repair_cycles, bool) or not isinstance(repair_cycles, int):
        raise ValueError("repair_cycles must be a non-negative integer")
    try:
        action = press_route(outcome, repair_cycles)
    except TypeError as exc:
        raise ValueError(str(exc)) from exc
    return _action_payload(action)


main = json_command(_route, "usage: press_route_cli.py [<request.json>]")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
