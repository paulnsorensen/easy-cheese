"""Command surface for the Plate application bundle."""

from __future__ import annotations

import sys


from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("stack-tools")
def _stack_tools(argv: list[str]) -> int:
    from easy_cheese.skills.plate.stack_tools import main

    return main(argv)


@bundle_command("validate-publication")
def _validate_publication(argv: list[str]) -> int:
    from easy_cheese.skills.plate.publication import main

    return main(argv)


COMMANDS = (
    derive_command(
        _stack_tools,
        "Detect supported stacked-PR providers without mutating the repository",
    ),
    derive_command(_validate_publication, "Validate terminal publication evidence"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
