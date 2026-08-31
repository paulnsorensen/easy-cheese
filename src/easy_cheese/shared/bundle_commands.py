"""Static bundle command manifests and direct dispatch."""

from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast

_COMMAND_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
# One trimmed line, no pipes: the summary is rendered verbatim into a
# generated markdown table cell by scripts/render_generated_regions.py.
_SUMMARY_RE = re.compile(r"[^\s|][^\n|]*")
CommandHandler = Callable[[list[str]], int]


@dataclass(frozen=True)
class Command:
    name: str
    target: str
    summary: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _COMMAND_RE.fullmatch(self.name) is None:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("invalid command name")
        if not isinstance(self.target, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("invalid command target")
        module, separator, attribute = self.target.partition(":")
        if not module or separator != ":" or not attribute:
            raise ValueError("invalid command target")
        if (
            not isinstance(self.summary, str)  # pyright: ignore[reportUnnecessaryIsInstance]
            or _SUMMARY_RE.fullmatch(self.summary) is None
            or self.summary != self.summary.strip()
        ):
            raise ValueError("invalid command summary")


def command_map(commands: Sequence[Command]) -> dict[str, Command]:
    mapping: dict[str, Command] = {}
    normalized_names: dict[str, str] = {}
    for command in commands:
        normalized = command.name.replace("_", "-")
        if command.name in mapping:
            raise ValueError(f"duplicate bundle command: {command.name}")
        existing_name = normalized_names.get(normalized)
        if existing_name is not None and existing_name != command.name:
            raise ValueError(
                f"bundle command alias collision: {existing_name} vs {command.name}"
            )
        mapping[command.name] = command
        normalized_names[normalized] = command.name
    if not mapping:
        raise ValueError("no bundle commands declared")
    return dict(sorted(mapping.items()))


def _handler(target: str) -> CommandHandler:
    module_name, _, attribute = target.partition(":")
    function = cast(object, getattr(importlib.import_module(module_name), attribute))
    if not callable(function):
        raise TypeError(f"bundle command target {target!r} is not callable")
    return cast(CommandHandler, function)


def dispatch(commands: Sequence[Command], argv: Sequence[str]) -> int:
    mapping = command_map(commands)
    choices = "|".join(mapping)
    if not argv or argv[0] in {"-h", "--help"}:
        print(f"usage: <pyz> {{{choices}}} [args...]")
        return 0 if argv else 2
    name = argv[0]
    command = mapping.get(name)
    if command is None and "_" in name:
        command = mapping.get(name.replace("_", "-"))
    if command is None:
        print(f"usage: <pyz> {{{choices}}} [args...]", file=sys.stderr)
        return 2
    result = _handler(command.target)(list(argv[1:]))
    if not isinstance(result, int):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"bundle command {name!r} did not return an integer status")
    return result


__all__ = ["Command", "command_map", "dispatch"]