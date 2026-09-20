"""Repair one caller mistake: two or more arguments inside one quoted token.

Example: `--files '2 --modules 2'` arrives as the single value `2 --modules 2`.
The repair splits only the value of an option that cannot hold free text: the
option has `choices`, or a `type` other than `str`. It never splits a positional
token or the value of a plain string option. The repair applies only when the
original arguments fail to parse and the split arguments parse.

Boundary: `cli.run` calls this module through `cli.repair_argv`, and so does the
pre-handler gate `review_lock.gated_write_handoff_artifact`. A handler that
builds its own parser gets flag standardization from `dispatch`, but no quote
repair.
"""

from __future__ import annotations

import argparse
import shlex
import sys
from collections.abc import Callable, Iterable, Sequence
from typing import NoReturn

from typing_extensions import override

_HELP_FLAGS = frozenset({"-h", "--help"})


class _ParseFailure(Exception):
    """The quiet parser rejects the arguments."""


class QuietParser(argparse.ArgumentParser):
    """Raise on a parse error. Do not print usage and do not exit."""

    @override
    def error(self, message: str) -> NoReturn:
        raise _ParseFailure(message)


def _holds_free_text(action: argparse.Action) -> bool:
    if action.nargs == 0:
        return True
    return action.choices is None and action.type in (None, str)


def _option_tables(
    parsers: Iterable[argparse.ArgumentParser],
) -> tuple[set[str], set[str]]:
    """Return every option string, and the option strings that are safe to split.

    An option string is safe only when no parser declares it as free text.
    """
    declared: set[str] = set()
    free_text: set[str] = set()
    for parser in parsers:
        for action in parser._actions:
            declared.update(action.option_strings)
            if _holds_free_text(action):
                free_text.update(action.option_strings)
    return declared, declared - free_text


def _split_pieces(token: str, declared: set[str]) -> list[str] | None:
    """Return the shell pieces of `token` when one piece is a declared option."""
    if not any(character.isspace() for character in token):
        return None
    try:
        pieces = shlex.split(token)
    except ValueError:
        return None
    if len(pieces) < 2:
        return None
    if not any(piece.partition("=")[0] in declared for piece in pieces):
        return None
    return pieces


def _parses(parser: argparse.ArgumentParser, argv: Sequence[str]) -> bool:
    try:
        _ = parser.parse_args(list(argv))
    except (_ParseFailure, SystemExit):
        return False
    return True


def repair_split_quotes(
    argv: Sequence[str],
    parsers: Iterable[argparse.ArgumentParser],
    build_quiet_parser: Callable[[], argparse.ArgumentParser],
) -> list[str]:
    """Return `argv`, with merged tokens split when only the split form parses."""
    original = list(argv)
    if _HELP_FLAGS.intersection(original):
        return original
    declared, splittable = _option_tables(parsers)
    repaired: list[str] = []
    splits: list[tuple[str, list[str]]] = []
    previous = ""
    for position, token in enumerate(original):
        if token == "--":
            repaired.extend(original[position:])
            break
        receives = previous in splittable or (
            token.startswith("--") and token.partition("=")[0] in splittable
        )
        pieces = _split_pieces(token, declared) if receives else None
        if pieces is None:
            repaired.append(token)
        else:
            repaired.extend(pieces)
            splits.append((token, pieces))
        previous = token
    if not splits:
        return original
    # A freed help flag makes the probe parse print a help page to stdout.
    if any(_HELP_FLAGS.intersection(pieces) for _, pieces in splits):
        return original
    quiet_parser = build_quiet_parser()
    if _parses(quiet_parser, original) or not _parses(quiet_parser, repaired):
        return original
    for token, pieces in splits:
        print(
            f"note: split quoted argument {token!r} into {pieces!r}",
            file=sys.stderr,
        )
    return repaired


__all__ = ["QuietParser", "repair_split_quotes"]
