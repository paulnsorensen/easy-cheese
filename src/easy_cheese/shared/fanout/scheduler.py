"""Dependency-wave scheduling for fan remediation (mini-spec Sec9).

`schedule_wave` is pure: given the plan and the results gathered so far, it
reports which curds are ready to dispatch now, which must be finalized as
blocked (and by which prerequisites), and which are still waiting. The
orchestrator dispatches the ready curds, persists every completed and blocked
result, then calls `schedule_wave` again. Transitive blocking emerges from that
loop: a curd blocked this wave becomes a resulted prerequisite that blocks its
own descendants on the next call.

The scheduler reads only declared dependencies and recorded result
dispositions. It never treats a green project gate as a clean review result and
never dispatches a worker for a dependency-blocked curd.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import attrs

from easy_cheese_schemas import CurdDisposition, CurdPlan, CurdResult

_PASSED = CurdDisposition.PASSED


@attrs.frozen
class BlockedCurd:
    """A curd that cannot run because a prerequisite did not pass."""

    curd_id: str
    blocked_by: tuple[str, ...]


@attrs.frozen
class WaveDecision:
    """The next actionable step for a dependency wave.

    ``ready`` curds have every dependency passed and may be dispatched now.
    ``blocked`` curds have at least one resulted, non-passed dependency and must
    be finalized as blocked without dispatch. ``remaining`` curds still wait on
    dependencies that have no result yet. ``complete`` is true when every
    in-scope curd already has a result.
    """

    ready: tuple[str, ...]
    blocked: tuple[BlockedCurd, ...]
    remaining: tuple[str, ...]
    complete: bool


def schedule_wave(
    plan: CurdPlan,
    results: Mapping[str, CurdResult],
    *,
    selected: Sequence[str] | None = None,
) -> WaveDecision:
    """Return the next wave decision for `plan` given `results` so far.

    `results` maps a curd id to its recorded `CurdResult` (any disposition).
    `selected` restricts scheduling to a coverage subset; dependencies are
    assumed dependency-closed within that subset, as `_selected_curds` enforces.
    """
    curds = {curd.curd_id: curd for curd in plan.curds}
    scope = set(curds) if selected is None else set(selected)
    order = [curd.curd_id for curd in plan.curds if curd.curd_id in scope]
    done = {curd_id for curd_id in results if curd_id in scope}

    ready: list[str] = []
    blocked: list[BlockedCurd] = []
    remaining: list[str] = []
    for curd_id in order:
        if curd_id in done:
            continue
        deps = tuple(d for d in curds[curd_id].dependencies if d in scope)
        blockers = tuple(
            d for d in deps if d in results and results[d].disposition is not _PASSED
        )
        if blockers:
            blocked.append(BlockedCurd(curd_id=curd_id, blocked_by=blockers))
        elif all(d in done for d in deps):
            ready.append(curd_id)
        else:
            remaining.append(curd_id)
    complete = not ready and not blocked and not remaining
    return WaveDecision(
        ready=tuple(ready),
        blocked=tuple(blocked),
        remaining=tuple(remaining),
        complete=complete,
    )
