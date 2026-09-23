"""Repair safely merged command-line arguments for Cyclopts applications.

A shell caller can quote multiple arguments as one token. Recovery only returns
an equivalent split when Cyclopts rejects the original and accepts exactly one
candidate. Parsing is a probe; handlers never run during recovery.
"""

from __future__ import annotations

import shlex
import sys
from collections.abc import Sequence
from typing import Protocol, cast

from cyclopts import CycloptsError


class _Argument(Protocol):
    names: Sequence[str]
    hint: object

    def is_flag(self) -> bool:
        ...

    def get_choices(self) -> object:
        ...


class _App(Protocol):
    def parse_args(
        self,
        tokens: Sequence[str],
        *,
        print_error: bool,
        exit_on_error: bool,
        help_on_error: bool,
    ) -> tuple[object, object, object]:
        ...

    def parse_commands(
        self, tokens: Sequence[str], *, include_parent_meta: bool = True
    ) -> tuple[tuple[str, ...], tuple["_App", ...], list[str]]:
        ...

    def assemble_argument_collection(self) -> Sequence[_Argument]:
        ...


_HELP_FLAGS = frozenset({"-h", "--help"})


def _parse(app: _App, argv: Sequence[str]) -> bool:
    try:
        _ = app.parse_args(
            list(argv),
            print_error=False,
            exit_on_error=False,
            help_on_error=False,
        )
    except CycloptsError:
        return False
    return True


def _splittable_options(app: _App, argv: Sequence[str]) -> set[str]:
    try:
        _, apps, _ = app.parse_commands(list(argv))
    except CycloptsError:
        return set()
    options: set[str] = set()
    for command_app in apps:
        try:
            arguments = command_app.assemble_argument_collection()
        except ValueError:
            continue
        for argument in arguments:
            if argument.is_flag():
                continue
            if argument.hint is str and argument.get_choices() is None:
                continue
            options.update(argument.names)
    return options


def _pieces(token: str) -> list[str] | None:
    if not any(character.isspace() for character in token):
        return None
    try:
        pieces = shlex.split(token)
    except ValueError:
        return None
    if len(pieces) < 2 or not any(piece.startswith("-") and len(piece) > 1 for piece in pieces):
        return None
    return pieces


def repair_cyclopts_argv(app: object, argv: Sequence[str]) -> list[str]:
    """Return one verified split form, or the original argv when uncertain."""
    typed_app = cast(_App, app)
    original = list(argv)
    if _HELP_FLAGS.intersection(original) or _parse(typed_app, original):
        return original
    splittable = _splittable_options(typed_app, original)
    candidates: list[tuple[list[str], int, list[str]]] = []
    for index, token in enumerate(original):
        if token == "--":
            break
        pieces = _pieces(token)
        if pieces is None or _HELP_FLAGS.intersection(pieces):
            continue
        previous = original[index - 1] if index else ""
        option = token.partition("=")[0] if token.startswith("--") else previous
        if option not in splittable:
            continue
        candidate = original[:index] + pieces + original[index + 1 :]
        if _parse(typed_app, candidate):
            candidates.append((candidate, index, pieces))
    if len(candidates) != 1:
        return original
    candidate, index, pieces = candidates[0]
    print(
        f"note: split quoted argument {original[index]!r} into {pieces!r}",
        file=sys.stderr,
    )
    return candidate


__all__ = ["repair_cyclopts_argv"]