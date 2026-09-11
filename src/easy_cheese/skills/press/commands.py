"""Command surface for the Press application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("wheypoint-resolve")
def _wheypoint_resolve(argv: list[str]) -> int:
    from easy_cheese.shared.wheypoint.resolve_cli import main

    return main(argv)


@bundle_command("press-route")
def _press_route(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.press_route_cli import main

    return main(argv)


@bundle_command("press-telemetry")
def _press_telemetry(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.press_telemetry_cli import main

    return main(argv)


@bundle_command("write-handoff-artifact")
def _write_handoff_artifact(argv: list[str]) -> int:
    from easy_cheese.shared.write_handoff_artifact import main

    return main(argv)


COMMANDS = (
    derive_command(
        _wheypoint_resolve,
        "Resolve a phase slug through the shared Wheypoint kernel (JSON out)",
    ),
    derive_command(
        _write_handoff_artifact,
        "Write a handoff preamble plus optional body atomically",
    ),
    derive_command(
        _press_route,
        "Return the Press action: continue, dispatch /age, or stop (JSON in, JSON out)",
    ),
    derive_command(
        _press_telemetry, "Build the Press attempt telemetry record (JSON in, JSON out)"
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
