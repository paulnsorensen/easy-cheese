"""Shared Cyclopts dispatch and output helpers."""

from __future__ import annotations

import json
import sys
from contextlib import nullcontext, redirect_stdout
from collections.abc import Callable, Sequence
from inspect import BoundArguments
from typing import Protocol, TextIO
from typing import cast

from cyclopts import CycloptsError
from easy_cheese.shared.argv_repair import repair_cyclopts_argv

class _CycloptsApp(Protocol):
    def parse_args(
        self,
        tokens: Sequence[str],
        *,
        print_error: bool,
        exit_on_error: bool,
        help_on_error: bool,
    ) -> tuple[Callable[..., object], BoundArguments, dict[str, object]]:
        ...

class _DefaultCommandApp(Protocol):
    default_command: object | None
def _has_default_command(app: object) -> bool:
    return cast(_DefaultCommandApp, app).default_command is not None
class CliError(Exception):
    """One-line error; cli.run reports it on stderr and returns exit_code."""

    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code: int = exit_code

def contract_error(exc: Exception, *, context: str) -> CliError:
    """Wrap a contract-violation exception as a CliError that exits 3."""
    return CliError(f"{context}: {exc}", exit_code=3)

def reject_path_segment(field: str, value: str) -> None:
    """Reject path-traversal segments and Windows drive/path designators."""
    if ".." in value or "/" in value or "\\" in value or ":" in value:
        raise CliError(f"{field} rejects path traversal: {value!r}")


def repair_argv(app: _CycloptsApp, argv: Sequence[str]) -> list[str]:
    """Return one verified canonical argv for a Cyclopts application."""
    return repair_cyclopts_argv(app, argv)


def run(
    app: _CycloptsApp,
    *,
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
) -> int:
    """Parse and invoke a Cyclopts application exactly once."""
    tokens = list(sys.argv[1:] if argv is None else argv)
    if not tokens and not _has_default_command(app):
        print("ERROR: command required", file=sys.stderr)
        return 2
    canonical = repair_argv(app, tokens)
    context = redirect_stdout(stdout) if stdout is not None else nullcontext()
    try:
        with context:
            func, bound, _ = app.parse_args(
                canonical,
                print_error=False,
                exit_on_error=False,
                help_on_error=False,
            )
            status = func(*bound.args, **bound.kwargs)
    except CliError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except CycloptsError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if status is None:
        return 0
    if not isinstance(status, int):
        raise TypeError(f"command returned non-integer status: {status!r}")
    return status

def emit(
    value: object,
    *,
    limit: int | None = None,
    full: bool = False,
    json_mode: bool = False,
    stdout: TextIO | None = None,
) -> None:
    """Print scalar, mapping, or sequence output using the shared format."""
    stream = stdout if stdout is not None else sys.stdout
    if json_mode or isinstance(value, dict):
        print(json.dumps(value, indent=2, default=str), file=stream)
        return
    if isinstance(value, list):
        _emit_list(cast(list[object], value), limit=limit, full=full, stdout=stream)
        return
    if isinstance(value, str) and limit is not None and "\n" in value:
        _emit_list(value.splitlines(), limit=limit, full=full, stdout=stream)
        return
    print(value, file=stream)


def _emit_list(
    items: Sequence[object],
    *,
    limit: int | None,
    full: bool,
    stdout: TextIO,
) -> None:
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