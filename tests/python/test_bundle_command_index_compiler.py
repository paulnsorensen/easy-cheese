"""Behavior of the build-only cross-bundle command index compiler."""

from __future__ import annotations

from types import ModuleType

from easy_cheese.shared import bundle_commands as bc
from scripts import _bundle_command_index_compiler as compiler


def _module(*commands: bc.Command) -> ModuleType:
    module = ModuleType("fixture_commands")
    module.COMMANDS = commands  # pyright: ignore[reportAttributeAccessIssue]
    return module


def test_collect_uses_the_given_slug_and_render_is_deterministic() -> None:
    shared = bc.Command("handoff", "m:f", "Handoff", ("render",))
    pairs = [
        ("zeta-skill", _module(shared)),
        ("alpha-skill", _module(shared, bc.Command("only", "m:f", "Only"))),
    ]
    command_index, leaf_index = compiler.collect(pairs)
    assert command_index == (
        ("handoff", ("alpha-skill", "zeta-skill")),
        ("only", ("alpha-skill",)),
    )
    assert leaf_index == (
        ("render", (("alpha-skill", "handoff"), ("zeta-skill", "handoff"))),
    )
    source = compiler.render(command_index, leaf_index)
    assert source == compiler.render(*compiler.collect(list(reversed(pairs))))
    namespace: dict[str, object] = {}
    exec(source, namespace)  # noqa: S102 - the compiler's own output
    assert namespace["COMMAND_BUNDLES"] == dict(command_index)
    assert namespace["LEAF_OWNERS"] == dict(leaf_index)
