"""Static bundle command manifests and direct dispatch."""

from __future__ import annotations

import difflib
import importlib
import itertools
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import TypeVar, cast

_COMMAND_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
# Use one trimmed line without pipes.
# scripts/render_generated_regions.py inserts the summary into a Markdown table cell.
_SUMMARY_RE = re.compile(r"[^\s|][^\r\n\v\f|]*")
_LONG_FLAG_UNDERSCORE_RE = re.compile(r"^(--[a-z0-9]+(?:_[a-z0-9]+)+)(=.*)?$")
_HELP_FLAGS = frozenset({"-h", "--help"})
# fromargs strips these valueless global flags anywhere before `--`.
_HOISTABLE_FLAGS = frozenset({"--json", "--full"})
_Value = TypeVar("_Value")
CommandHandler = Callable[[list[str]], int]


@dataclass(frozen=True)
class Command:
    name: str
    target: str
    summary: str
    leaves: tuple[str, ...] = ()

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
        if not isinstance(self.leaves, tuple) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(leaf, str) or _COMMAND_RE.fullmatch(leaf) is None  # pyright: ignore[reportUnnecessaryIsInstance]
            for leaf in self.leaves
        ):
            raise ValueError("invalid command leaf")


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


def derive_command(
    fn: CommandHandler, summary: str, *, leaves: Sequence[str] = ()
) -> Command:
    """Compile a decorated handler and its summary into one command.

    `leaves` names the nested subcommands that the handler's own argparse
    subparsers expose. `dispatch` uses `leaves` to guide a caller who names a
    nested leaf at the top level (for example `compute` instead of `severity
    compute`).
    """
    name = cast("str | None", getattr(fn, "__bundle_command_name__", None))
    if name is None:
        raise ValueError(f"{fn!r} is not decorated with @bundle_command")
    return Command(name, f"{fn.__module__}:{fn.__qualname__}", summary, tuple(leaves))


def _declared_names(module: ModuleType) -> set[str]:
    """Every `@bundle_command` name declared by a function defined in `module`."""
    return {
        cast("str", getattr(value, "__bundle_command_name__"))
        for value in cast("dict[str, object]", vars(module)).values()
        if callable(value)
        and getattr(value, "__module__", None) == module.__name__
        and getattr(value, "__bundle_command_name__", None) is not None
    }


def validate_command_surface(module: ModuleType, commands: Sequence[Command]) -> None:
    """Reject `@bundle_command` declarations in `module` unreferenced by `commands`.

    Also rejects `commands` entries whose name was never declared via the
    decorator in `module`, closing the gate in both directions.
    """
    declared = _declared_names(module)
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


def _usage_line(mapping: dict[str, Command]) -> str:
    return f"usage: <pyz> {{{'|'.join(mapping)}}} [args...]"


def _help_text(mapping: dict[str, Command]) -> str:
    width = max(len(name) for name in mapping)
    lines = [_usage_line(mapping)]
    lines.extend(
        f"  {name.ljust(width)}  {command.summary}" for name, command in mapping.items()
    )
    lines.append("Run <pyz> <command> --help for the arguments of a command.")
    lines.append("references/commands.md in the skill directory lists the commands.")
    return "\n".join(lines)


def _lookup(table: Mapping[str, _Value], token: str) -> _Value | None:
    """Read `token` from `table`, accepting `_` as an alias of `-`."""
    value = table.get(token)
    if value is None and "_" in token:
        value = table.get(token.replace("_", "-"))
    return value


def _leaf_parents(mapping: dict[str, Command]) -> dict[str, list[str]]:
    parents: dict[str, list[str]] = {}
    for command in mapping.values():
        for leaf in command.leaves:
            parents.setdefault(leaf, []).append(command.name)
    return parents


def _unknown_command_message(mapping: dict[str, Command], token: str) -> str:
    name = token.replace("_", "-")
    lines = [_usage_line(mapping)]
    leaf_parents = _leaf_parents(mapping)
    local_parents = _lookup(leaf_parents, token) or []
    lines.extend(
        f"'{name}' is a subcommand of '{parent}'. Run: <pyz> {parent} {name} ..."
        for parent in local_parents
    )
    # Read the module through importlib. A `from` import reads a cached package
    # attribute, and that attribute can be stale.
    try:
        index = importlib.import_module("easy_cheese.shared.bundle_command_index")
    except ImportError:
        index = None
    if index is not None:
        command_bundles = cast("dict[str, tuple[str, ...]]", index.COMMAND_BUNDLES)
        leaf_owners = cast(
            "dict[str, tuple[tuple[str, str], ...]]", index.LEAF_OWNERS
        )
        bundles = _lookup(command_bundles, token)
        if bundles:
            joined = ", ".join(f"{bundle}.pyz" for bundle in bundles)
            lines.append(f"'{name}' is a command of {joined}.")
        # This bundle already names its own parents. Do not repeat them.
        by_parent: dict[str, list[str]] = {}
        for bundle, parent in _lookup(leaf_owners, token) or ():
            if parent not in local_parents:
                by_parent.setdefault(parent, []).append(bundle)
        for parent, bundles_for_parent in sorted(by_parent.items()):
            joined = ", ".join(f"{bundle}.pyz" for bundle in sorted(bundles_for_parent))
            lines.append(f"'{name}' is '{parent} {name}' in {joined}.")
    if len(lines) == 1:
        pool = sorted(set(mapping) | set(leaf_parents))
        matches = difflib.get_close_matches(name, pool, n=3, cutoff=0.6)
        if matches:
            lines.append(f"Did you mean: {', '.join(matches)}?")
    return "\n".join(lines)


def _hoisted_leading_flags(
    mapping: dict[str, Command], argv: Sequence[str], flags: list[str]
) -> list[str] | str:
    """Move the leading `flags` after the command, or return the reason to refuse.

    Only valueless global flags move. The value of any other flag can equal a
    command name, so a guess can run the wrong command.
    """
    rejected = [flag for flag in flags if flag not in _HOISTABLE_FLAGS]
    if rejected:
        return f"Only --json and --full can come before the command, not {rejected[0]}."
    if len(flags) == len(argv):
        return "No command follows the flags."
    command_name = argv[len(flags)]
    # An unknown name gets the unknown-command guidance, without a move note.
    if _lookup(mapping, command_name) is not None:
        print(f"note: moved {' '.join(flags)} after {command_name!r}", file=sys.stderr)
    return [command_name, *flags, *argv[len(flags) + 1 :]]


def _standardize_flags(argv: list[str]) -> list[str]:
    """Rewrite `--flag_name` to `--flag-name`, leaving `=value` and `--` alone."""
    standardized: list[str] = []
    literal = False
    for token in argv:
        if literal or token == "--":
            literal = True
            standardized.append(token)
            continue
        match = _LONG_FLAG_UNDERSCORE_RE.match(token)
        if match is None:
            standardized.append(token)
            continue
        flag, value = match.group(1), match.group(2) or ""
        standardized.append(flag.replace("_", "-") + value)
    return standardized


def dispatch(commands: Sequence[Command], argv: Sequence[str]) -> int:
    mapping = command_map(commands)
    if not argv:
        print(_help_text(mapping))
        return 2
    first = argv[0]
    if first == "help" and "help" not in mapping:
        print(_help_text(mapping))
        return 0
    if first.startswith("-"):
        leading = list(itertools.takewhile(lambda token: token.startswith("-"), argv))
        if _HELP_FLAGS.intersection(leading):
            print(_help_text(mapping))
            return 0
        hoisted = _hoisted_leading_flags(mapping, argv, leading)
        if isinstance(hoisted, str):
            print(_usage_line(mapping), file=sys.stderr)
            print("Put the command first: <pyz> <command> [flags]", file=sys.stderr)
            print(hoisted, file=sys.stderr)
            return 2
        return dispatch(commands, hoisted)
    command = _lookup(mapping, first)
    if command is None:
        print(_unknown_command_message(mapping, first), file=sys.stderr)
        return 2
    result = _handler(command.target)(_standardize_flags(list(argv[1:])))
    if not isinstance(result, int):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"bundle command {first!r} did not return an integer status")
    return result


__all__ = [
    "Command",
    "bundle_command",
    "command_map",
    "derive_command",
    "dispatch",
    "validate_command_surface",
]
