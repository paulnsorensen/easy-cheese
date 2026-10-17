"""Press readiness verdict (see skills/press/SKILL.md § Rules):

    ready for /age          hard floor met, level-1/3 gaps closed
    follow-up recommended   hard floor met, only level-4/5 gaps remain
    blocked                 level-1/2 unfixable or spinning wheels
"""

from __future__ import annotations

from enum import Enum

import fromargs


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
def classify(
    *,
    press_status: str,
    hard_floor_met: bool = False,
    has_open_level_1_or_2: bool = False,
    has_open_level_3: bool = False,
    has_open_level_4_or_5: bool = False,
    any_spinning: bool = False,
) -> dict[str, str]:
    """Map scoreboard booleans to a readiness verdict.

    Parameters
    ----------
    press_status
        Press-status label (echoed in output).
    hard_floor_met
        Whether the hard floor gate is met.
    has_open_level_1_or_2
        Whether an open level-1 or level-2 gap remains.
    has_open_level_3
        Whether an open level-3 gap remains.
    has_open_level_4_or_5
        Whether an open level-4 or level-5 gap remains.
    any_spinning
        Whether any gate is spinning wheels.
    """
    try:
        verdict = classify_readiness(
            hard_floor_met=hard_floor_met,
            has_open_level_1_or_2=has_open_level_1_or_2,
            has_open_level_3=has_open_level_3,
            has_open_level_4_or_5=has_open_level_4_or_5,
            any_spinning=any_spinning,
        )
    except (ValueError, TypeError) as exc:
        raise fromargs.CliError(str(exc)) from exc
    return {"press_status": press_status, "readiness": verdict.value}


LEAVES = ("classify",)


def build_app() -> fromargs.App:
    app = fromargs.App(
        "gates",
        help="Compute /press readiness verdicts.",
        help_formatter="plain",
    )
    _ = app.command(classify, name="classify")
    return app


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())