"""Static bundle command manifests and direct dispatch."""

from __future__ import annotations

import importlib
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import cast

_COMMAND_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
CommandHandler = Callable[[list[str]], int]


@dataclass(frozen=True)
class Command:
    name: str
    target: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or _COMMAND_RE.fullmatch(self.name) is None:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("invalid command name")
        if not isinstance(self.target, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError("invalid command target")
        module, separator, attribute = self.target.partition(":")
        if not module or separator != ":" or not attribute:
            raise ValueError("invalid command target")


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


def bundle_command(name: str) -> Callable[[CommandHandler], CommandHandler]:
    """Decorator declaring a handler function as bundle command `name`.

    Applied at the handler's own definition site. Transparent at runtime; the
    build compiles the declared name into the owning package's dispatcher via
    `derive_command`.
    """
    if not isinstance(name, str) or _COMMAND_RE.fullmatch(name) is None:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise ValueError("invalid command name")

    def decorator(fn: CommandHandler) -> CommandHandler:
        fn.__bundle_command_name__ = name  # pyright: ignore[reportFunctionMemberAccess]
        return fn

    return decorator


def derive_command(fn: CommandHandler) -> Command:
    """Compile a `@bundle_command`-decorated handler into its dispatcher `Command`."""
    name = cast("str | None", getattr(fn, "__bundle_command_name__", None))
    if name is None:
        raise ValueError(f"{fn!r} is not decorated with @bundle_command")
    return Command(name, f"{fn.__module__}:{fn.__qualname__}")


def compiled_commands(module: ModuleType) -> tuple[Command, ...]:
    """Every `@bundle_command`-decorated top-level function defined in `module`."""
    declared = (
        value
        for value in vars(module).values()
        if callable(value)
        and getattr(value, "__module__", None) == module.__name__
        and getattr(value, "__bundle_command_name__", None) is not None
    )
    return tuple(
        sorted((derive_command(fn) for fn in declared), key=lambda command: command.name)
    )


def validate_command_surface(module: ModuleType, commands: Sequence[Command]) -> None:
    """Reject `@bundle_command` declarations in `module` unreferenced by `commands`.

    Also rejects `commands` entries whose name was never declared via the
    decorator in `module`, closing the gate in both directions.
    """
    declared = {command.name for command in compiled_commands(module)}
    referenced = {command.name for command in commands}
    unreferenced = declared - referenced
    if unreferenced:
        raise ValueError(
            f"{module.__name__} declares unreferenced bundle command(s): "
            + ", ".join(sorted(unreferenced))
        )
    undeclared = referenced - declared
    if undeclared:
        raise ValueError(
            f"{module.__name__} COMMANDS references undeclared bundle command(s): "
            + ", ".join(sorted(undeclared))
        )


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


__all__ = [
    "Command",
    "bundle_command",
    "command_map",
    "compiled_commands",
    "derive_command",
    "dispatch",
    "validate_command_surface",
]