"""Readiness verdicts and iteration caps shared across press / cure / age.

Two-cure-pass cap (see skills/cook/SKILL.md § Auto mode, skills/age/SKILL.md):
the age → cure cycle in an auto chain stops after the second cure pass writes
its handoff. Centralising the counter makes the cap testable and prevents
drift when the chain shape changes.

Press readiness verdict (see skills/press/SKILL.md § Rules):

    ready for /age          hard floor met, level-1/3 gaps closed
    follow-up recommended   hard floor met, only level-4/5 gaps remain
    blocked                 level-1/2 unfixable or spinning wheels
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

CURE_PASS_CAP = 2
GAP_ITERATION_CAP = 3  # skills/press/SKILL.md § Spinning-wheels rule


class Readiness(str, Enum):
    READY = "ready for /age"
    FOLLOW_UP = "follow-up recommended"
    BLOCKED = "blocked"


@dataclass
class GapState:
    """Per-gap state for the iteration-cap rule."""

    name: str
    attempts: int = 0
    closed: bool = False

    def record_attempt(self) -> None:
        self.attempts += 1

    def close(self) -> None:
        self.closed = True

    def is_spinning(self, cap: int = GAP_ITERATION_CAP) -> bool:
        return not self.closed and self.attempts >= cap


def classify_readiness(
    *,
    hard_floor_met: bool,
    has_open_level_1_or_2: bool,
    has_open_level_3: bool,
    has_open_level_4_or_5: bool,
    any_spinning: bool,
) -> Readiness:
    """Map the press scoreboard to a readiness verdict.

    Inputs are booleans because the underlying gap taxonomy
    (skills/press/references/gap-analysis.md) demands model judgment to
    classify each gap's level. The function then maps the deterministic
    summary state to the verdict.
    """
    if any_spinning or (has_open_level_1_or_2 and not hard_floor_met):
        return Readiness.BLOCKED
    if has_open_level_1_or_2:
        return Readiness.BLOCKED
    if has_open_level_3:
        return Readiness.READY  # level-3 gaps are encouraged to close in /age
    if has_open_level_4_or_5:
        return Readiness.FOLLOW_UP
    return Readiness.READY


@dataclass
class CurePassCounter:
    """Track cure passes in an auto-mode chain. Cap is enforced inside /age."""

    completed: int = 0
    cap: int = CURE_PASS_CAP

    def record_pass(self) -> None:
        self.completed += 1

    @property
    def at_cap(self) -> bool:
        return self.completed >= self.cap

    def next_action(self) -> str:
        """Return the next chain action: 'cure', 'age-final', or 'done'."""
        if self.completed >= self.cap:
            return "done"
        return "cure"


def detect_halt(status: str, halt_reason: str | None) -> bool:
    """Mirror handoff.HandoffSlug.is_halt for code that only has the strings."""
    return status == "halt" and bool(halt_reason)
