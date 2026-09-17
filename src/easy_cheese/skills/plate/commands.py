"""Command surface for the Plate application bundle."""

from __future__ import annotations

import sys


from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("wheypoint-resolve")
def _wheypoint_resolve(argv: list[str]) -> int:
    from easy_cheese.shared.wheypoint.resolve_cli import main

    return main(argv)


@bundle_command("stack-tools")
def _stack_tools(argv: list[str]) -> int:
    from easy_cheese.skills.plate.stack_tools import main

    return main(argv)


@bundle_command("gh-stack-preflight")
def _gh_stack_preflight(argv: list[str]) -> int:
    from easy_cheese.skills.plate.gh_stack import preflight_main

    return preflight_main(argv)


@bundle_command("gh-stack-run")
def _gh_stack_run(argv: list[str]) -> int:
    from easy_cheese.skills.plate.gh_stack import run_main

    return run_main(argv)


@bundle_command("gh-stack-verify")
def _gh_stack_verify(argv: list[str]) -> int:
    from easy_cheese.skills.plate.gh_stack import verify_main

    return verify_main(argv)


@bundle_command("validate-publication")
def _validate_publication(argv: list[str]) -> int:
    from easy_cheese.skills.plate.publication import main

    return main(argv)


COMMANDS = (
    derive_command(
        _wheypoint_resolve,
        "Resolve a phase slug through the shared Wheypoint kernel (JSON out)",
    ),
    derive_command(
        _stack_tools,
        "Detect supported stacked-PR providers without mutating the repository",
    ),
    derive_command(
        _gh_stack_preflight,
        "Validate the gh-stack trunk and origin branch before mutation",
    ),
    derive_command(
        _gh_stack_run,
        "Run one gh-stack mutation and reject warning-only success",
    ),
    derive_command(
        _gh_stack_verify,
        "Verify exact gh-stack PR and remote stack publication state",
    ),
    derive_command(_validate_publication, "Validate terminal publication evidence"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
