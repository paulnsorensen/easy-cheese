#!/usr/bin/env python3
"""Decide what /ultracook should do after a phase sub-agent returns.

Replaces the LLM-judged "did this phase finish, halt, or early-stop?" branch
at the top of each /ultracook chain step. The orchestrator passes a 0-indexed
phase index (0..6) plus the parsed handoff slug (`status`, `next`) and gets
back a deterministic verdict naming the next phase to spawn (or the reason to
stop).

The phase table is fixed at seven entries (cook, press, age, cure, age, cure,
age) per `skills/ultracook/SKILL.md` § Phases and slug paths. Phase index 6
is the terminal age spawn — `action=stop` once it returns. Any `status` that
starts with `halt` short-circuits to `action=halt`. An age phase that reports
`next: done` triggers `action=stop_early` because the medium+ severity floor
is already met; the chain skips the remaining cure/age spawns.

Inputs:

    --phase-index <0..6>    Which phase just returned.
    --status <ok|halt:...>  Status field from the handoff slug.
    --next <name>           Optional. The `next` field from the handoff
                            slug (e.g. `press`, `cure`, `done`); only
                            consulted on age phases to detect early-stop.

Output (JSON):

    {
      "action": "spawn" | "stop" | "stop_early" | "halt",
      "next_phase": "press" | "age" | "cure" | null,
      "exit_message": "<one-line operator-visible reason>"
    }
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared" / "scripts"))
import cli  # noqa: E402

# 0-indexed phase table: which phase just ran, and which phase the chain
# would spawn next if it continues. The seventh entry is terminal.
PHASE_TABLE: list[tuple[str, str | None]] = [
    ("cook", "press"),
    ("press", "age"),
    ("age", "cure"),
    ("cure", "age"),
    ("age", "cure"),
    ("cure", "age"),
    ("age", None),
]

MAX_PHASE_INDEX = len(PHASE_TABLE) - 1


def _is_halt(status: str) -> bool:
    return status.strip().lower().startswith("halt")


def decide(phase_index: int, status: str, next_field: str | None = None) -> dict:
    """Pure decision — no I/O. Raises CliError on invalid phase index."""
    if phase_index < 0 or phase_index > MAX_PHASE_INDEX:
        raise cli.CliError(
            f"phase-index out of range: {phase_index} (valid 0..{MAX_PHASE_INDEX})"
        )
    current_phase, next_phase = PHASE_TABLE[phase_index]

    if _is_halt(status):
        return {
            "action": "halt",
            "next_phase": None,
            "exit_message": f"{current_phase} (phase {phase_index}) halted: {status.strip()}",
        }

    # Terminal age phase — chain is exhausted whether next says "done" or not.
    if next_phase is None:
        return {
            "action": "stop",
            "next_phase": None,
            "exit_message": f"chain complete after final {current_phase} (phase {phase_index})",
        }

    # Early-stop: an age phase reports `next: done` when the diff is clean at
    # the medium+ severity floor. Cure never writes `next: done`, so this only
    # fires on age phases (indices 2 and 4 in the table above).
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
    verdict = decide(args.phase_index, args.status, args.next)
    cli.emit(verdict, json_mode=True)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Decide /ultracook's next action from a phase handoff."
    parser.add_argument(
        "--phase-index",
        type=int,
        required=True,
        dest="phase_index",
        help=f"0-indexed phase that just returned (0..{MAX_PHASE_INDEX}).",
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
    parser.set_defaults(func=_cmd_decide)


if __name__ == "__main__":
    cli.run(_setup)
