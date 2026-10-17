"""Build-only compiler for the cross-bundle command index.

This module is intentionally excluded from wheels and runtime bundles.  The
runtime imports only the generated `bundle_command_index` projection.
"""

from __future__ import annotations

from collections.abc import Sequence
from types import ModuleType
from typing import Protocol, cast


class _CommandLike(Protocol):
    name: str
    leaves: tuple[str, ...]


CommandIndex = tuple[tuple[str, tuple[str, ...]], ...]
LeafIndex = tuple[tuple[str, tuple[tuple[str, str], ...]], ...]


def collect(
    skills: Sequence[tuple[str, ModuleType]],
) -> tuple[CommandIndex, LeafIndex]:
    """Project each `(slug, commands module)` pair into cross-bundle indices.

    Returns a command-name -> owning-bundles index and a leaf-name ->
    (bundle, parent command) index, both sorted for deterministic output.
    """
    command_bundles: dict[str, set[str]] = {}
    leaf_owners: dict[str, set[tuple[str, str]]] = {}
    for skill, module in skills:
        commands = cast(Sequence[_CommandLike], getattr(module, "COMMANDS"))
        for command in commands:
            command_bundles.setdefault(command.name, set()).add(skill)
            for leaf in command.leaves:
                leaf_owners.setdefault(leaf, set()).add((skill, command.name))
    command_index = tuple(
        (name, tuple(sorted(bundles)))
        for name, bundles in sorted(command_bundles.items())
    )
    leaf_index = tuple(
        (leaf, tuple(sorted(owners))) for leaf, owners in sorted(leaf_owners.items())
    )
    return command_index, leaf_index


def render(command_index: CommandIndex, leaf_index: LeafIndex) -> str:
    """Render deterministic, dependency-free index source for `dispatch`."""
    lines = [
        '"""Generated cross-bundle command and leaf index.',
        "",
        "Do not edit. `just update-generated` regenerates this from every skill's",
        'static COMMANDS manifest."""',
        "",
        "from __future__ import annotations",
        "",
        "COMMAND_BUNDLES: dict[str, tuple[str, ...]] = {",
    ]
    lines.extend(f"    {name!r}: {bundles!r}," for name, bundles in command_index)
    lines.extend(["}", "", "LEAF_OWNERS: dict[str, tuple[tuple[str, str], ...]] = {"])
    lines.extend(f"    {leaf!r}: {owners!r}," for leaf, owners in leaf_index)
    lines.extend(["}", ""])
    return "\n".join(lines)
