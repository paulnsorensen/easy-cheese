"""JSON CLI wrapper for the Press attempt telemetry record."""

from __future__ import annotations

import sys

from easy_cheese.shared.manifest_io import json_command

from .press_telemetry import telemetry_record

_EXPECTED_KEYS = frozenset(
    {
        "slug",
        "attempt",
        "outcome",
        "repair_cycles",
        "tool_errors",
        "delegations",
        "changed_files",
    }
)


def _record(**payload: object) -> dict[str, object]:
    if set(payload) != set(_EXPECTED_KEYS):
        raise ValueError(
            "request must contain exactly "
            + ", ".join(sorted(_EXPECTED_KEYS))
        )
    return telemetry_record(
        slug=payload["slug"],
        attempt=payload["attempt"],
        outcome=payload["outcome"],
        repair_cycles=payload["repair_cycles"],
        tool_errors=payload["tool_errors"],
        delegations=payload["delegations"],
        changed_files=payload["changed_files"],
    )


main = json_command(_record, "usage: press_telemetry_cli.py [<request.json>]")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
