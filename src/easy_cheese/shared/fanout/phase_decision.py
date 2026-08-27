#!/usr/bin/env python3
"""Decide what /ultracook should do after a phase sub-agent returns.

Replaces the LLM-judged "did this phase finish, halt, or early-stop?" branch at
the top of each /ultracook chain step. The orchestrator passes a 0-indexed phase
index plus the parsed handoff slug (`status`, `next`) and gets back a
deterministic verdict naming the next phase to spawn (or the reason to stop).

`decide()` walks a **phase table** — an ordered list of phase names. The phase
that runs after index `i` is `table[i + 1]`; the last entry is terminal
(terminal `next_phase=None`). Six tables ship: the RED-required linear chain,
fan per-curd and post-merge chains, plus matching `not-applicable-*` chains.
Fan per-curd chains never
include Press; the post-merge chain owns the single global Press after the
complete receipt has validated GREEN.

Inputs:

    --phase-index <int>     Which phase just returned (0-indexed into the table).
    --status <ok|halt:...>  Status field from the handoff slug.
    --next <name>           Optional. The `next` field from the handoff slug;
                            terminal age always gates publication, while a
                            nonterminal clean age ends the linear and
                            parallel-curd tables early (never post-merge).
    --table <name>          Which table to walk (default: linear).

Output (JSON):

    {
      "action": "spawn" | "stop" | "stop_early" | "clean_complete" | "halt",
      "next_phase": "press" | "age" | "cure" | null,
      "exit_message": "<one-line operator-visible reason>"
    }
"""
from __future__ import annotations

import argparse

# cli is co-staged in the bundled .pyz alongside this module
from easy_cheese.shared import cli

# A phase table is an ordered list of phase names; the phase that runs after
# index i is table[i + 1], and the last entry is terminal.
LINEAR_TABLE: list[str] = ["cook", "press", "age", "cure", "age", "cure", "age"]
PARALLEL_CURD: list[str] = ["cook", "age", "cure", "age"]
PARALLEL_POSTMERGE: list[str] = ["press", "age", "cure", "age"]
NOT_APPLICABLE_LINEAR: list[str] = ["cook", "age", "cure", "age", "cure", "age"]
NOT_APPLICABLE_CURD: list[str] = ["cook", "age", "cure", "age"]
NOT_APPLICABLE_POSTMERGE: list[str] = ["age", "cure", "age"]

TABLES: dict[str, list[str]] = {
    "linear": LINEAR_TABLE,
    "parallel-curd": PARALLEL_CURD,
    "parallel-postmerge": PARALLEL_POSTMERGE,
    "not-applicable-linear": NOT_APPLICABLE_LINEAR,
    "not-applicable-curd": NOT_APPLICABLE_CURD,
    "not-applicable-postmerge": NOT_APPLICABLE_POSTMERGE,
}


def _is_halt(status: str) -> bool:
    return status.strip().lower().startswith("halt")


def decide(
    phase_index: int,
    status: str,
    next_field: str | None = None,
    *,
    table: list[str] = LINEAR_TABLE,
    allow_early_stop: bool | None = None,
) -> dict:
    """Pure decision — no I/O. Raises CliError on invalid phase index."""
    max_index = len(table) - 1
    if phase_index < 0 or phase_index > max_index:
        raise cli.CliError(
            f"phase-index out of range: {phase_index} (valid 0..{max_index})"
        )
    current_phase = table[phase_index]
    next_phase = table[phase_index + 1] if phase_index < max_index else None
    if allow_early_stop is None:
        allow_early_stop = table is LINEAR_TABLE

    if _is_halt(status):
        return {
            "action": "halt",
            "next_phase": None,
            "exit_message": f"{current_phase} (phase {phase_index}) halted: {status.strip()}",
        }

    # The terminal entry of every table is the final review; it is publishable
    # only when it positively reports done. Missing/next=cure means findings
    # remain and publication must halt.
    if next_phase is None:
        if (next_field or "").strip().lower() == "done":
            return {
                "action": "stop",
                "next_phase": None,
                "exit_message": (
                    f"chain complete after final {current_phase} (phase {phase_index}); "
                    "review reported next=done"
                ),
            }
        return {
            "action": "halt",
            "next_phase": None,
            "exit_message": (
                f"final {current_phase} (phase {phase_index}) is not publishable: "
                f"next={(next_field or 'missing').strip()}"
            ),
        }

    # A nonterminal clean age ends the table early everywhere except
    # post-merge, which is the last review before publication and must run
    # its complete typed sequence through cure and final age. Linear mode
    # stops and hands the diff to the user; a parallel curd clean-completes —
    # its bound review context becomes the final one, and the post-merge
    # review still re-covers the merged diff.
    if current_phase == "age" and (next_field or "").strip().lower() == "done":
        if allow_early_stop:
            return {
                "action": "stop_early",
                "next_phase": None,
                "exit_message": (
                    f"age (phase {phase_index}) reported next=done; "
                    "diff is clean at medium+ severity floor"
                ),
            }
        if table in (PARALLEL_CURD, NOT_APPLICABLE_CURD):
            return {
                "action": "clean_complete",
                "next_phase": None,
                "exit_message": (
                    f"age (phase {phase_index}) reported next=done; curd is clean "
                    "at medium+ severity floor — record this age's review context "
                    "as final and mark the curd completed"
                ),
            }

    return {
        "action": "spawn",
        "next_phase": next_phase,
        "exit_message": f"{current_phase} (phase {phase_index}) ok; spawning {next_phase}",
    }


def _cmd_decide(args: argparse.Namespace) -> None:
    table = TABLES[args.table]
    verdict = decide(
        args.phase_index,
        args.status,
        args.next,
        table=table,
        allow_early_stop=table in (LINEAR_TABLE, NOT_APPLICABLE_LINEAR),
    )
    cli.emit(verdict, json_mode=True, stdout=args.stdout)


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
            "Which receipt-specific table to walk: linear, fan per-curd "
            "(without Press), fan post-merge (global Press), or N/A."
        ),
    )
    parser.set_defaults(func=_cmd_decide)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
