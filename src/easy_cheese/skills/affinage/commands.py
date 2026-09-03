"""Command surface for the Affinage application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import bundle_command, derive_command, dispatch


@bundle_command("pr-status")
def _pr_status(argv: list[str]) -> int:
    from easy_cheese.skills.affinage.pr_status import main

    return main(argv)


@bundle_command("post-reply")
def _post_reply(argv: list[str]) -> int:
    from easy_cheese.skills.affinage.post_reply import main

    return main(argv)


@bundle_command("age-route")
def _age_route(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.age_route_cli import main

    return main(argv)


@bundle_command("review-surface")
def _review_surface(argv: list[str]) -> int:
    from easy_cheese.shared.fanout.review_surface_cli import main

    return main(argv)


COMMANDS = (
    derive_command(_pr_status),
    derive_command(_post_reply),
    derive_command(_age_route),
    derive_command(_review_surface),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)