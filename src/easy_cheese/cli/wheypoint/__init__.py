"""The nine commands the bundle exposes: checkpoint, validate, schema, resolve, show, lint, list, log, turns.

This package is a mouth, not a brain. Every decision it reports was made by
`commit`, `resolve`, or `lint`; nothing here parses a projection, compares a
revision, or decides what is dispatchable, because a second implementation of
any of those would be a second answer to a question the kernel already answers.

The contract with a caller is that *one line of JSON on stdout* is the whole
reply, success or failure. A refusal is an answer too, so it is emitted in the
same place and the same shape -- `{"ok": false, "command": ..., "error":
{"code": ..., "message": ...}}` -- and never as a traceback, which no caller
can parse. The exit code carries the same news for a shell:

| exit | meaning                                                          |
|------|------------------------------------------------------------------|
| 0    | the command answered; `ok` is true                                |
| 1    | the command refused; `error.code` says why                        |
| 2    | the invocation itself was wrong (unknown command, bad arguments)  |

A resolution that is gated, ambiguous, or not found is an *answer* about the
corpus, so it exits 0 with `ok: true` and the outcome in the payload; only a
reference that could not be interpreted at all is a refusal. Lint findings are
answers by the same rule.

All nine commands are reached through this one entry point because the bundle
dispatcher gives each subcommand its own entry point and rewrites `sys.argv[0]`
to the subcommand name -- so the command is read from `argv[0]` first, and
from `argv[1]` when the module is run directly.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path
from typing import TextIO

from easy_cheese.cli.envelope import (
    EXIT_INTERNAL,
    EXIT_OK,
    EXIT_REFUSED,
    EXIT_USAGE,
    BadUsage,
    Refused,
    emit,
    refuse,
)
from easy_cheese.shared.wheypoint.resolve_cli import resolve_status

from easy_cheese.cli.wheypoint.checkpoint import (
    request_identity_for as request_identity_for,
    run_checkpoint,
)
from easy_cheese.cli.wheypoint.parser import normalize_positional_ref, parser_for
from easy_cheese.cli.wheypoint.queries import (
    run_lint,
    run_list,
    run_log,
    run_resolve,
    run_schema,
    run_show,
    run_turns,
    run_validate,
)

COMMANDS = (
    "checkpoint",
    "validate",
    "schema",
    "resolve",
    "show",
    "lint",
    "list",
    "log",
    "turns",
)

_RUNNERS = {
    "checkpoint": run_checkpoint,
    "validate": run_validate,
    "schema": run_schema,
    "resolve": run_resolve,
    "show": run_show,
    "lint": run_lint,
    "list": run_list,
    "log": run_log,
    "turns": run_turns,
}


def _command_of(argv: list[str]) -> tuple[str | None, list[str]]:
    """The subcommand, read from the name it was invoked as, then from argv.

    The bundle gives every subcommand its own entry point into this one module
    and rewrites `argv[0]` to the subcommand name; running the module directly
    leaves `argv[0]` as the file, so the name is looked for in `argv[1]` next.
    """
    invoked = Path(argv[0]).name if argv else ""
    if invoked.endswith(".py"):
        invoked = invoked[: -len(".py")]
    if invoked in COMMANDS:
        return invoked, list(argv[1:])
    if len(argv) >= 2 and argv[1] in COMMANDS:
        return argv[1], list(argv[2:])
    return None, []


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> int:
    argv2: list[str] = sys.argv if argv is None else argv
    stdin2: TextIO = sys.stdin if stdin is None else stdin
    stdout2: TextIO = sys.stdout if stdout is None else stdout

    command, rest = _command_of(argv2)
    if command is None:
        return refuse(
            stdout2,
            "unknown",
            "usage",
            f"expected one of {', '.join(COMMANDS)}",
            EXIT_USAGE,
        )
    try:
        args = parser_for(command).parse_args(rest)
        normalize_positional_ref(command, args)
    except BadUsage as exc:
        return refuse(stdout2, command, "usage", str(exc), EXIT_USAGE)
    try:
        payload = _RUNNERS[command](args, stdin2)
    except Refused as exc:
        return refuse(stdout2, command, exc.code, str(exc), EXIT_REFUSED, exc.extra)
    except Exception as exc:  # noqa: BLE001 - a traceback is not a reply
        traceback.print_exc(file=sys.stderr)
        return refuse(
            stdout2,
            command,
            "internal-error",
            f"{type(exc).__name__}: {exc}",
            EXIT_INTERNAL,
        )
    status = resolve_status(payload)
    emit(stdout2, {"ok": status == EXIT_OK, "command": command, **payload})
    return status


if __name__ == "__main__":
    sys.exit(main())
