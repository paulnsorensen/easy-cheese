"""Command surface for the Wheypoint application bundle."""

from __future__ import annotations

import sys


from easy_cheese.shared.bundle_commands import (
    bundle_command,
    derive_command,
    dispatch,
)


@bundle_command("checkpoint")
def _checkpoint(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["checkpoint", *argv])


@bundle_command("validate")
def _validate(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["validate", *argv])


@bundle_command("schema")
def _schema(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["schema", *argv])


@bundle_command("resolve")
def _resolve(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["resolve", *argv])


@bundle_command("show")
def _show(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["show", *argv])


@bundle_command("lint")
def _lint(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["lint", *argv])


@bundle_command("list")
def _list(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["list", *argv])


@bundle_command("log")
def _log(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["log", *argv])


@bundle_command("turns")
def _turns(argv: list[str]) -> int:
    from easy_cheese.skills.wheypoint import wheypoint

    return wheypoint.main(["turns", *argv])


@bundle_command("handoff")
def _handoff(argv: list[str]) -> int:
    from easy_cheese.shared.handoff import main

    return main(argv)


COMMANDS = (
    derive_command(_checkpoint, "Checkpoint a semantic intent onto the current record"),
    derive_command(_validate, "Validate an intent against its schema without opening the store"),
    derive_command(_schema, "Print the JSON Schema for a registered contract slug"),
    derive_command(_resolve, "Resolve a slug, work id, or path to the current record"),
    derive_command(_show, "Print the current record for a work id"),
    derive_command(_lint, "Lint a generated projection against the record"),
    derive_command(_list, "List every work item under the corpus root"),
    derive_command(_log, "Walk the revisions of one work id, oldest first"),
    derive_command(_turns, "Print the user's own turns from a session transcript"),
    derive_command(_handoff, "Render, parse, and dispatch-split handoff preambles"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)
