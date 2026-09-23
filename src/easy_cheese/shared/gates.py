"""Press readiness verdict (see skills/press/SKILL.md § Rules):

    ready for /age          hard floor met, level-1/3 gaps closed
    follow-up recommended   hard floor met, only level-4/5 gaps remain
    blocked                 level-1/2 unfixable or spinning wheels
"""

from __future__ import annotations
import sys

from typing import Annotated

from cyclopts import App, Parameter
from enum import Enum

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


LEAVES = ("classify",)

def _command(
    *,
    press_status: Annotated[str, Parameter(name="--press-status")],
    hard_floor_met: Annotated[bool, Parameter(name="--hard-floor-met")] = False,
    has_open_level_1_or_2: Annotated[bool, Parameter(name="--has-open-level-1-or-2")] = False,
    has_open_level_3: Annotated[bool, Parameter(name="--has-open-level-3")] = False,
    has_open_level_4_or_5: Annotated[bool, Parameter(name="--has-open-level-4-or-5")] = False,
    any_spinning: Annotated[bool, Parameter(name="--any-spinning")] = False,
    json_mode: Annotated[bool, Parameter(name="--json")] = False,
) -> int:
    verdict = classify_readiness(hard_floor_met=hard_floor_met, has_open_level_1_or_2=has_open_level_1_or_2, has_open_level_3=has_open_level_3, has_open_level_4_or_5=has_open_level_4_or_5, any_spinning=any_spinning)
    cli.emit({"press_status": press_status, "readiness": verdict.value}, json_mode=json_mode)
    return 0

app = App(name="gates")
_ = app.command(_command, name="classify")

def main(argv: list[str]) -> int:
    if not argv:
        print("ERROR: command required", file=sys.stderr)
        return 2
    return cli.run(app, argv=argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
