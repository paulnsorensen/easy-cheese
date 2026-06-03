"""Press readiness verdict (see skills/press/SKILL.md § Rules):

    ready for /age          hard floor met, level-1/3 gaps closed
    follow-up recommended   hard floor met, only level-4/5 gaps remain
    blocked                 level-1/2 unfixable or spinning wheels
"""

from __future__ import annotations

from enum import Enum


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
