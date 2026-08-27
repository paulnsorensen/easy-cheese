"""Command surface for the Affinage application bundle."""

from __future__ import annotations

import sys

from easy_cheese.shared.bundle_commands import dispatch_modules

COMMANDS = {
    "pr-status": "easy_cheese.skills.affinage.pr_status",
    "post-reply": "easy_cheese.skills.affinage.post_reply",
    "age-route": "easy_cheese.shared.fanout.age_route_cli",
    "review-surface": "easy_cheese.shared.fanout.review_surface_cli",
}


def main(argv: list[str] | None = None) -> int:
    return dispatch_modules(COMMANDS, sys.argv[1:] if argv is None else argv)
