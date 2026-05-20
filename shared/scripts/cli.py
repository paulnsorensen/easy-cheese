"""CLI helper for shared/scripts: argparse + --full/--json injection + emit.

Public API:
    CliError -- one-line message; cli.run prints 'ERROR: <msg>' and exits 2.
    cli.run  -- build parser via setup(parser), dispatch args.func(args).
    cli.emit -- print scalar/dict/list; truncation footer fires when limit is set.

Stdlib-only, capped at 75 lines per spec quality gate.
"""
from __future__ import annotations
import argparse, json, sys
from typing import Any, Callable, Iterable, NoReturn


class CliError(Exception):
    """One-line error; cli.run prints 'ERROR: <msg>' on stderr and exits 2."""


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


def run(setup: Callable[[argparse.ArgumentParser], None]) -> NoReturn:
    """Build parser, auto-inject globals, dispatch args.func(args)."""
    parser = argparse.ArgumentParser()
    setup(parser)
    _inject_global_flags(parser)
    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr); sys.exit(2)
    try:
        func(args)
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr); sys.exit(2)
    sys.exit(0)


def emit(value: Any, *, limit: int | None = None, full: bool = False, json_mode: bool = False) -> None:
    """Print scalar/dict/list per spec emit rules; footer only fires when limit is set."""
    if json_mode or isinstance(value, dict):
        print(json.dumps(value, indent=2, default=str)); return
    if isinstance(value, list):
        _emit_list(value, limit=limit, full=full); return
    if isinstance(value, str) and limit is not None and "\n" in value:
        _emit_list(value.splitlines(), limit=limit, full=full); return
    print(value)


def _emit_list(items: list, *, limit: int | None, full: bool) -> None:
    total = len(items)
    if limit is None:
        for item in items: print(item)
        return
    for item in (items if full else items[:limit]): print(item)
    if full:
        print(f"... showing {total} of {total} (--full; default limit={limit})")
    elif total > limit:
        print(f"... showing {limit} of {total}; pass --full for the rest (limit={limit})")
