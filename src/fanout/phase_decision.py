#!/usr/bin/env python3
"""Decide what /ultracook should do after a phase sub-agent returns.

Replaces the LLM-judged "did this phase finish, halt, or early-stop?" branch at
the top of each /ultracook chain step. The orchestrator passes a 0-indexed phase
index plus the parsed handoff slug (`status`, `next`) and gets back a
deterministic verdict naming the next phase to spawn (or the reason to stop).

`decide()` walks a **phase table** — an ordered list of phase names. The phase
that runs after index `i` is `table[i + 1]`; the last entry is terminal
(`next_phase=None`). Three tables ship:

- `LINEAR_TABLE` — the deep 7-phase chain for linear mode. Unchanged from the
  original single-mode ultracook, so linear behaviour is byte-for-byte the same.
- `PARALLEL_CURD` — the per-curd pipeline run in each curd's own worktree.
- `PARALLEL_POSTMERGE` — the single review pass over the merged diff.

Any `status` beginning with `halt` short-circuits to `action=halt`. An age phase
that reports `next: done` triggers `action=stop_early` because the medium+
severity floor is already met; the chain skips the remaining cure/age spawns.

Inputs:

    --phase-index <int>     Which phase just returned (0-indexed into the table).
    --status <ok|halt:...>  Status field from the handoff slug.
    --next <name>           Optional. The `next` field from the handoff slug;
                            only consulted on age phases to detect early-stop.
    --table <name>          Which table to walk (default: linear).

Output (JSON):

    {
      "action": "spawn" | "stop" | "stop_early" | "halt",
      "next_phase": "press" | "age" | "cure" | null,
      "exit_message": "<one-line operator-visible reason>"
    }
"""
from __future__ import annotations

import argparse

# cli is co-staged in the bundled .pyz alongside this module
import cli

# A phase table is an ordered list of phase names; the phase that runs after
# index i is table[i + 1], and the last entry is terminal.
LINEAR_TABLE: list[str] = ["cook", "press", "age", "cure", "age", "cure", "age"]
PARALLEL_CURD: list[str] = ["cook", "press", "age", "cure"]
PARALLEL_POSTMERGE: list[str] = ["press", "age", "cure"]

TABLES: dict[str, list[str]] = {
    "linear": LINEAR_TABLE,
    "parallel-curd": PARALLEL_CURD,
    "parallel-postmerge": PARALLEL_POSTMERGE,
}


def _is_halt(status: str) -> bool:
    return status.strip().lower().startswith("halt")


def decide(
    phase_index: int,
    status: str,
    next_field: str | None = None,
    *,
    table: list[str] = LINEAR_TABLE,
) -> dict:
    """Pure decision — no I/O. Raises CliError on invalid phase index."""
    max_index = len(table) - 1
    if phase_index < 0 or phase_index > max_index:
        raise cli.CliError(
            f"phase-index out of range: {phase_index} (valid 0..{max_index})"
        )
    current_phase = table[phase_index]
    next_phase = table[phase_index + 1] if phase_index < max_index else None

    if _is_halt(status):
        return {
            "action": "halt",
            "next_phase": None,
            "exit_message": f"{current_phase} (phase {phase_index}) halted: {status.strip()}",
        }

    # Terminal phase — the table is exhausted whether next says "done" or not.
    if next_phase is None:
        return {
            "action": "stop",
            "next_phase": None,
            "exit_message": f"chain complete after final {current_phase} (phase {phase_index})",
        }

    # Early-stop: an age phase reports `next: done` when the diff is clean at
    # the medium+ severity floor. Cure never writes `next: done`, so this only
    # fires on age phases.
    if current_phase == "age" and (next_field or "").strip().lower() == "done":
        return {
            "action": "stop_early",
            "next_phase": None,
            "exit_message": (
                f"age (phase {phase_index}) reported next=done; "
                "diff is clean at medium+ severity floor"
            ),
        }

    return {
        "action": "spawn",
        "next_phase": next_phase,
        "exit_message": f"{current_phase} (phase {phase_index}) ok; spawning {next_phase}",
    }


def _cmd_decide(args: argparse.Namespace) -> None:
    verdict = decide(args.phase_index, args.status, args.next, table=TABLES[args.table])
    cli.emit(verdict, json_mode=True)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Decide /ultracook's next action from a phase handoff."
    parser.add_argument(
        "--phase-index",
        type=int,
        required=True,
        dest="phase_index",
        help="0-indexed phase that just returned.",
    )
    parser.add_argument(
        "--status",
        required=True,
        help="`status` field from the handoff slug (ok | halt: <reason>).",
    )
    parser.add_argument(
        "--next",
        default=None,
        help="`next` field from the handoff slug (e.g. press, cure, done).",
    )
    parser.add_argument(
        "--table",
        choices=sorted(TABLES),
        default="linear",
        help=(
            "Which phase table to walk: linear (7-phase chain), parallel-curd "
            "(per curd in its worktree), or parallel-postmerge (merged diff)."
        ),
    )
    parser.set_defaults(func=_cmd_decide)


if __name__ == "__main__":
    cli.run(_setup)
