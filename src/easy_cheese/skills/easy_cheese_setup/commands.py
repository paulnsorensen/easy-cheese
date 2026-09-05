"""Command surface for the Easy Cheese setup application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("global")
def _global(argv: list[str]) -> int:
    from easy_cheese.shared.hallouminate_setup import global_main

    return global_main(argv)


@bundle_command("local")
def _local(argv: list[str]) -> int:
    from easy_cheese.shared.hallouminate_setup import local_main

    return local_main(argv)


@bundle_command("doctor")
def _doctor(argv: list[str]) -> int:
    from easy_cheese.shared.hallouminate_setup import doctor_main

    return doctor_main(argv)


COMMANDS = (
    derive_command(_global, "Register or repair the durable Hallouminate corpus"),
    derive_command(_local, "Register or repair this repository's Hallouminate tenant"),
    derive_command(_doctor, "Run both the global and local registration legs"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)