#!/usr/bin/env python3
"""Decide what /ultracook should do after a phase sub-agent returns.

Replaces the LLM-judged "did this phase finish, halt, or early-stop?" branch at
the top of each /ultracook chain step. The orchestrator passes a 0-indexed phase
index plus the parsed handoff slug (`status`, `next`) and gets back a
deterministic verdict naming the next phase to spawn (or the reason to stop).

`decide()` walks a **phase table** — an ordered list of phase names. The phase
that runs after index `i` is `table[i + 1]`; the last entry is terminal
(terminal `next_phase=None`). The linear chain remains fixed. Closed
not-applicable tables cover the legacy non-behavior paths. Fan remediation
uses the progress-aware state machine instead of these phase tables.

Routing always reads `status` through the declared handback vocabulary
(`parse_status_field` / `status_disposition`), never a prefix guess: a prefix
test on `halt` once silently spawned the next phase for every other stopping
status (`gated:`), because `"gated: x".startswith("halt")` is false and the
fallback branch was `spawn`. `disposition` is the only signal this module
branches on; adding a status to the vocabulary must never require editing this
router.

Inputs:

    --phase-index <int>     Which phase just returned (0-indexed into the table).
    --status <value>        Status field from the handoff slug. Parsed through
                            the declared handback vocabulary: a `proceed`
                            status walks the table, `retry` re-dispatches the
                            same phase (bounded by --retry-count), and `stop`
                            halts or gates.
    --next <name>           Optional. The `next` field from the handoff slug;
                            terminal age always gates publication, while a
                            nonterminal clean age ends the fixed linear table early.
    --table <name>          Which table to walk (default: linear).
    --retry-count <int>     How many needs-context retries this phase has
                            already consumed (default: 0). A second
                            RETRY-disposition status at retry-count >= 1 halts
                            instead of retrying again, capping the loop.

Output (JSON):

    {
      "action": "spawn" | "stop" | "stop_early" | "clean_complete" | "halt"
                | "needs_context" | "gated",
      "next_phase": "press" | "age" | "cure" | "cook" | null,
      "exit_message": "<one-line operator-visible reason>",
      "status": "<parsed status name>",
      "disposition": "proceed" | "retry" | "stop",
      "reason": "<one-line reason>" | null
    }

`next_phase` is only ever `"cook"` when `action` is `"needs_context"` at
phase 0. That value names an orchestrator spawn of the same phase with the
named gap; it is not a declared phase transition. The compiled registry has
no `cook -> cook` route, so a cook worker on this path still writes
`--next age`, the declared Cook transition, in its handoff slug. The router
ignores `next:` under a `retry` disposition.

`disposition` is the parsed handback's declared disposition; `action` is the
router's decision. They differ on purpose at the retry cap: a second `retry`
returns `action: "halt"` while `disposition` stays `"retry"`. Branch on
`action`.
"""
from __future__ import annotations

from typing import Annotated, Literal, TypedDict

import cyclopts
import fromargs

from easy_cheese_schemas.phase_contracts import (
    RETRY,
    STOP,
    HandbackStatus,
    StatusError,
    parse_status_field,
    status_disposition,
)

Action = Literal[
    "spawn",
    "stop",
    "stop_early",
    "clean_complete",
    "halt",
    "needs_context",
    "gated",
]


class Verdict(TypedDict):
    action: Action
    next_phase: str | None
    exit_message: str
    status: str
    disposition: str
    reason: str | None

# A phase table is an ordered list of phase names; the phase that runs after
# index i is table[i + 1], and the last entry is terminal.
LINEAR_TABLE: list[str] = ["cook", "press", "age", "cure", "age", "cure", "age"]
NOT_APPLICABLE_LINEAR: list[str] = ["cook", "age", "cure", "age", "cure", "age"]
NOT_APPLICABLE_CURD: list[str] = ["cook", "age", "cure", "age"]
NOT_APPLICABLE_POSTMERGE: list[str] = ["age", "cure", "age"]

TABLES: dict[str, list[str]] = {
    "linear": LINEAR_TABLE,
    "not-applicable-linear": NOT_APPLICABLE_LINEAR,
    "not-applicable-curd": NOT_APPLICABLE_CURD,
    "not-applicable-postmerge": NOT_APPLICABLE_POSTMERGE,
}


def decide(
    phase_index: int,
    status: str,
    next_field: str | None = None,
    *,
    table: list[str] = LINEAR_TABLE,
    allow_early_stop: bool | None = None,
    retry_count: int = 0,
) -> Verdict:
    """Pure decision — no I/O. Raises CliError on invalid phase index."""
    max_index = len(table) - 1
    if phase_index < 0 or phase_index > max_index:
        raise fromargs.CliError(
            f"phase-index out of range: {phase_index} (valid 0..{max_index})"
        )
    if retry_count < 0:
        raise fromargs.CliError(f"retry-count cannot be negative: {retry_count}")
    current_phase = table[phase_index]
    next_phase = table[phase_index + 1] if phase_index < max_index else None
    if allow_early_stop is None:
        allow_early_stop = table is LINEAR_TABLE

    context = f"{current_phase} (phase {phase_index})"
    try:
        name, reason = parse_status_field(status, require_reason=False)
    except StatusError as exc:
        raise fromargs.contract_error(exc, context=context) from exc
    disposition = status_disposition(name)

    if disposition == STOP:
        detail = reason if reason else status.strip()
        if name == HandbackStatus.GATED.value:
            return {
                "action": "gated",
                "next_phase": None,
                "exit_message": f"{context} gated on: {detail}",
                "status": name,
                "disposition": disposition.value,
                "reason": reason,
            }
        return {
            "action": "halt",
            "next_phase": None,
            "exit_message": f"{context} halted: {detail}",
            "status": name,
            "disposition": disposition.value,
            "reason": reason,
        }
    if disposition == RETRY:
        if reason is None:
            raise fromargs.contract_error(
                StatusError("needs-context requires a named gap"), context=context
            )
        if retry_count >= 1:
            return {
                "action": "halt",
                "next_phase": None,
                "exit_message": f"{context} retry cap (1) reached; halting",
                "status": name,
                "disposition": disposition.value,
                "reason": reason,
            }
        return {
            "action": "needs_context",
            "next_phase": current_phase,
            "exit_message": (
                f"{context} needs more context: {reason}; "
                "re-dispatch the same phase with it"
            ),
            "status": name,
            "disposition": disposition.value,
            "reason": reason,
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
                "status": name,
                "disposition": disposition.value,
                "reason": reason,
            }
        return {
            "action": "halt",
            "next_phase": None,
            "exit_message": (
                f"final {current_phase} (phase {phase_index}) is not publishable: "
                f"next={(next_field or 'missing').strip()}"
            ),
            "status": name,
            "disposition": disposition.value,
            "reason": reason,
        }

    # A nonterminal clean age ends a configured early-stop table. The fixed
    # linear chain keeps its declared two-Cure sequence. Closed N/A curd
    # execution can complete after a clean first review.
    if current_phase == "age" and (next_field or "").strip().lower() == "done":
        if allow_early_stop:
            return {
                "action": "stop_early",
                "next_phase": None,
                "exit_message": (
                    f"age (phase {phase_index}) reported next=done; "
                    "diff is clean at medium+ severity floor"
                ),
                "status": name,
                "disposition": disposition.value,
                "reason": reason,
            }
        if table is NOT_APPLICABLE_CURD:
            return {
                "action": "clean_complete",
                "next_phase": None,
                "exit_message": (
                    f"age (phase {phase_index}) reported next=done; curd is clean "
                    "at medium+ severity floor — record this age's review context "
                    "as final and mark the curd completed"
                ),
                "status": name,
                "disposition": disposition.value,
                "reason": reason,
            }

    exit_message = f"{current_phase} (phase {phase_index}) ok; spawning {next_phase}"
    if name == HandbackStatus.OK_WITH_CONCERNS.value and reason:
        exit_message += f"; concern: {reason}"
    return {
        "action": "spawn",
        "next_phase": next_phase,
        "exit_message": exit_message,
        "status": name,
        "disposition": disposition.value,
        "reason": reason,
    }


TableName = Literal[
    "linear",
    "not-applicable-linear",
    "not-applicable-curd",
    "not-applicable-postmerge",
]


def decide_cmd(
    *,
    phase_index: int,
    status: str,
    next_field: Annotated[
        str | None, cyclopts.Parameter(name="--next")
    ] = None,
    table: TableName = "linear",
    retry_count: int = 0,
) -> Verdict:
    """Decide /ultracook's next action from a phase handoff.

    Parameters
    ----------
    phase_index
        0-indexed phase that just returned.
    status
        `status` field from the handoff slug; see the handback vocabulary.
    next_field
        `next` field from the handoff slug (e.g. press, cure, done).
    table
        Which receipt-specific table to walk: linear or a closed
        not-applicable path. Fan remediation uses its progress-aware state.
    retry_count
        needs-context retries already consumed by this phase (default 0).
    """
    picked_table = TABLES[table]
    return decide(
        phase_index,
        status,
        next_field,
        table=picked_table,
        allow_early_stop=picked_table in (LINEAR_TABLE, NOT_APPLICABLE_LINEAR),
        retry_count=retry_count,
    )


def build_app() -> fromargs.App:
    return fromargs.App(
        "phase-decision",
        help="Decide /ultracook's next action from a phase handoff.",
        help_formatter="plain",
        default_command=decide_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)


if __name__ == "__main__":
    raise SystemExit(main())