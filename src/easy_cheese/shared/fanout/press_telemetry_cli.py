"""JSON CLI wrapper for the Press attempt telemetry record."""

from __future__ import annotations

import sys

from easy_cheese.shared.manifest_io import json_command

from .press_telemetry import telemetry_record

_REQUEST_KEYS = (
    "slug",
    "attempt",
    "outcome",
    "repair_cycles",
    "tool_errors",
    "delegations",
    "changed_files",
)

main = json_command(
    telemetry_record,
    "usage: press_telemetry_cli.py [<request.json>]",
    keys=_REQUEST_KEYS,
)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
