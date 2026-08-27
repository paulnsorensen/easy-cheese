"""Declarative bundle command registration, dispatch, and guidance."""

from __future__ import annotations

import inspect
import re
import runpy
import sys
from dataclasses import dataclass
from typing import Callable, Sequence

_COMMAND_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
_GUIDANCE_START = "<!-- GENERATED BUNDLE COMMANDS:START -->"
_GUIDANCE_END = "<!-- GENERATED BUNDLE COMMANDS:END -->"
CommandHandler = Callable[[list[str]], int]


@dataclass(frozen=True)
class BundleCommand:
    name: str
    function: CommandHandler
    guidance: str


_REGISTRY: dict[str, dict[str, BundleCommand]] = {}


def bundle_command(name: str) -> Callable[[CommandHandler], CommandHandler]:
    if not isinstance(name, str) or _COMMAND_RE.fullmatch(name) is None:
        raise ValueError("invalid command name")

    def decorate(function: CommandHandler) -> CommandHandler:
        commands = _REGISTRY.setdefault(function.__module__, {})
        if name in commands:
            raise ValueError(f"duplicate bundle command: {name}")
        commands[name] = BundleCommand(
            name, function, inspect.getdoc(function) or ""
        )
        setattr(function, "__bundle_command__", name)
        return function

    return decorate


def registered_commands(module: str) -> tuple[BundleCommand, ...]:
    return tuple(
        sorted(_REGISTRY.get(module, {}).values(), key=lambda command: command.name)
    )


def compile_bundle_commands(
    module: str, *, referenced: set[str] | None = None
) -> dict[str, str]:
    commands = _REGISTRY.get(module, {})
    if not commands:
        raise ValueError(f"no bundle commands registered for {module}")
    if referenced is not None:
        unreferenced = set(commands) - referenced
        missing = referenced - set(commands)
        if unreferenced or missing:
            raise ValueError(
                f"command references differ: unreferenced={sorted(unreferenced)}, "
                f"missing={sorted(missing)}"
            )
    return {
        name: command.function.__name__
        for name, command in sorted(commands.items())
    }


def dispatch(
    module: str,
    argv: Sequence[str],
    *,
    expected: dict[str, str] | None = None,
) -> int:
    mapping = compile_bundle_commands(module)
    if expected is not None and mapping != expected:
        raise RuntimeError("generated bundle command map is stale")
    choices = "|".join(mapping)
    if not argv or argv[0] in {"-h", "--help"}:
        print(f"usage: <pyz> {{{choices}}} [args...]")
        return 0 if argv else 2
    name = argv[0]
    command = _REGISTRY[module].get(name)
    if command is None:
        print(f"usage: <pyz> {{{choices}}} [args...]", file=sys.stderr)
        return 2
    result = command.function(list(argv[1:]))
    if not isinstance(result, int):
        raise TypeError(f"bundle command {name!r} did not return an integer status")
    return result


def dispatch_modules(commands: dict[str, str], argv: Sequence[str]) -> int:
    """Dispatch a legacy-style CLI module from a packaged application."""
    choices = "|".join(sorted(commands))
    if not argv or argv[0] in {"-h", "--help"}:
        print(f"usage: <pyz> {{{choices}}} [args...]")
        return 0 if argv else 2
    name = argv[0]
    module = commands.get(name)
    if module is None:
        print(f"usage: <pyz> {{{choices}}} [args...]", file=sys.stderr)
        return 2
    sys.argv = [name, *argv[1:]]
    try:
        runpy.run_module(module, run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code, file=sys.stderr)
        return 1
    return 0


def guidance_source(module: str) -> str:
    lines = [_GUIDANCE_START]
    for command in registered_commands(module):
        guidance = command.guidance.splitlines()[0] if command.guidance else ""
        lines.append(f"- `{command.name}` — {guidance}")
    lines.append(_GUIDANCE_END)
    return "\n".join(lines)


def validate_generated_region(text: str, module: str) -> None:
    expected = guidance_source(module)
    start = text.find(_GUIDANCE_START)
    end = text.find(_GUIDANCE_END, start + len(_GUIDANCE_START))
    actual = "" if start < 0 or end < 0 else text[start : end + len(_GUIDANCE_END)]
    if actual != expected:
        raise ValueError("generated command guidance drift")


__all__ = [
    "BundleCommand",
    "bundle_command",
    "compile_bundle_commands",
    "dispatch",
    "dispatch_modules",
    "guidance_source",
    "registered_commands",
    "validate_generated_region",
]
