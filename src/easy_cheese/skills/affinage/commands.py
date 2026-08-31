"""Command surface for the Affinage application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import Command, dispatch

COMMANDS = (
    Command(
        "pr-status",
        "easy_cheese.skills.affinage.pr_status:main",
        "Fetch a PR's build and merge status for grading",
    ),
    Command(
        "post-reply",
        "easy_cheese.skills.affinage.post_reply:main",
        "Post a PR reply carrying the mandatory agent attribution",
    ),
    Command(
        "age-route",
        "easy_cheese.shared.fanout.age_route_cli:main",
        "Size an /age review into single-pass or fan-out lanes (JSON in, JSON out)",
    ),
    Command(
        "review-surface",
        "easy_cheese.shared.fanout.review_surface_cli:main",
        "Score the reviewable git surface that routing sizes against (JSON out)",
    ),
)


def main(argv: list[str] | None = None) -> int:
    return dispatch(COMMANDS, sys.argv[1:] if argv is None else argv)