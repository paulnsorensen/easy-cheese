"""Press readiness verdict (see skills/press/SKILL.md § Rules):

    ready for /age          hard floor met, level-1/3 gaps closed
    follow-up recommended   hard floor met, only level-4/5 gaps remain
    blocked                 level-1/2 unfixable or spinning wheels
"""

from __future__ import annotations

import argparse
from enum import Enum
from typing import TextIO, cast

from easy_cheese.shared import cli


class Readiness(str, Enum):
    READY = "ready for /age"
    FOLLOW_UP = "follow-up recommended"
    BLOCKED = "blocked"


def classify_readiness(
    *,
    hard_floor_met: bool,
    has_open_level_1_or_2: bool,
    has_open_level_3: bool,
    has_open_level_4_or_5: bool,
    any_spinning: bool,
) -> Readiness:
    # hard_floor_met is a precondition: without it, the press scoreboard is
    # incomplete (failing gates, missing tests, etc.) and the verdict is
    # BLOCKED regardless of which gap levels are still open.
    if any_spinning or not hard_floor_met or has_open_level_1_or_2:
        return Readiness.BLOCKED
    if has_open_level_3:
        return Readiness.READY  # level-3 gaps are encouraged to close in /age
    if has_open_level_4_or_5:
        return Readiness.FOLLOW_UP
    return Readiness.READY


# ---- CLI: classify ----
def _cmd_classify(args: argparse.Namespace) -> None:
    try:
        verdict = classify_readiness(
            hard_floor_met=cast(bool, args.hard_floor_met),
            has_open_level_1_or_2=cast(bool, args.has_open_level_1_or_2),
            has_open_level_3=cast(bool, args.has_open_level_3),
            has_open_level_4_or_5=cast(bool, args.has_open_level_4_or_5),
            any_spinning=cast(bool, args.any_spinning),
        )
    except (ValueError, TypeError) as exc:
        raise cli.CliError(str(exc)) from exc
    cli.emit(
        {"press_status": cast(str, args.press_status), "readiness": verdict.value},
        json_mode=cast(bool, args.json_mode),
        stdout=cast("TextIO", args.stdout),
    )


def _setup(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="cmd", required=True)

    classify = sub.add_parser("classify", help="map scoreboard booleans to a readiness verdict")
    _ = classify.add_argument("--press-status", required=True, help="press-status label (echoed in output)")
    _ = classify.add_argument("--hard-floor-met", action="store_true")
    _ = classify.add_argument("--has-open-level-1-or-2", action="store_true")
    _ = classify.add_argument("--has-open-level-3", action="store_true")
    _ = classify.add_argument("--has-open-level-4-or-5", action="store_true")
    _ = classify.add_argument("--any-spinning", action="store_true")
    classify.set_defaults(func=_cmd_classify)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
