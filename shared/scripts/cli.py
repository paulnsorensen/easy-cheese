"""CLI helper for shared/scripts: argparse + --full/--json injection + emit.

Public API:
    CliError -- one-line message; cli.run reports 'ERROR: <msg>' and returns 2.
    cli.run  -- dispatch and return integer statuses for normal, missing-handler,
                and CliError paths; argparse help/errors retain SystemExit.
    cli.emit -- print scalar/dict/list; truncation footer fires when limit is set.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Iterable, Sequence
from typing import Any, TextIO


class CliError(Exception):
    """One-line error; cli.run reports it on stderr and returns 2."""


def _iter_parsers(parser: argparse.ArgumentParser) -> Iterable[argparse.ArgumentParser]:
    yield parser
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub in action.choices.values():
                yield from _iter_parsers(sub)


def _inject_global_flags(parser: argparse.ArgumentParser) -> None:
    for p in _iter_parsers(parser):
        opts = {tuple(a.option_strings) for a in p._actions}
        if ("--full",) not in opts:
            p.add_argument("--full", action="store_true", help="emit full output, overriding default limit")
        if ("--json",) not in opts:
            p.add_argument("--json", dest="json_mode", action="store_true", help="emit JSON instead of plain text")


def run(
    setup: Callable[[argparse.ArgumentParser], None], *,
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Dispatch and return a status; argparse help/errors retain SystemExit."""
    parser = argparse.ArgumentParser()
    setup(parser)
    _inject_global_flags(parser)
    args = parser.parse_args(argv)
    args.stdout = stdout if stdout is not None else sys.stdout
    func: Callable[[argparse.Namespace], int | None] | None = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr)
        return 2
    try:
        status = func(args)
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0 if status is None else status




def emit(value: Any, *, limit: int | None = None, full: bool = False, json_mode: bool = False, stdout: TextIO | None = None) -> None:
    """Print scalar/dict/list per spec emit rules; footer only fires when limit is set."""
    stream = stdout if stdout is not None else sys.stdout
    if json_mode or isinstance(value, dict):
        print(json.dumps(value, indent=2, default=str), file=stream)
        return
    if isinstance(value, list):
        _emit_list(value, limit=limit, full=full, stdout=stream)
        return
    if isinstance(value, str) and limit is not None and "\n" in value:
        _emit_list(value.splitlines(), limit=limit, full=full, stdout=stream)
        return
    print(value, file=stream)


def _emit_list(items: list, *, limit: int | None, full: bool, stdout: TextIO) -> None:
    total = len(items)
    if limit is None:
        for item in items:
            print(item, file=stdout)
        return
    for item in items if full else items[:limit]:
        print(item, file=stdout)
    if full:
        print(f"... showing {total} of {total} (--full; default limit={limit})", file=stdout)
    elif total > limit:
        print(f"... showing {limit} of {total}; pass --full for the rest (limit={limit})", file=stdout)
