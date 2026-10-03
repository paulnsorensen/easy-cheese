"""Command surface for the Press application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("wheypoint-resolve")
def _wheypoint_resolve(argv: list[str]) -> int:
    from easy_cheese.shared.wheypoint.resolve_cli import main

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
        "Write a handoff preamble plus optional body atomically; pass --grounded paths",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
