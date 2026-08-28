"""Command surface for the Affinage application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command("pr-status", "easy_cheese.skills.affinage.pr_status:main"),
    Command("post-reply", "easy_cheese.skills.affinage.post_reply:main"),
    Command("age-route", "easy_cheese.shared.fanout.age_route_cli:main"),
    Command("review-surface", "easy_cheese.shared.fanout.review_surface_cli:main"),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)