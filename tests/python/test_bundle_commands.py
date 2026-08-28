"""Behavioral contract for static bundle command manifests."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from types import ModuleType

import pytest

from easy_cheese.shared import bundle_commands as bc


def command(name: str = "go", target: str = "test_bundle_target:handler") -> bc.Command:
    return bc.Command(name, target)


@pytest.fixture
def target_module(monkeypatch: pytest.MonkeyPatch) -> tuple[list[list[str]], ModuleType]:
    calls: list[list[str]] = []
    module = ModuleType("test_bundle_target")

    def handler(argv: list[str]) -> int:
        calls.append(argv)
        return 7

    module.handler = handler  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return calls, module


@pytest.mark.parametrize("name", ["Bad", "", "-x", "_x", "a b", "camelCase"])
def test_invalid_command_name_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="invalid command name"):
        command(name=name)


@pytest.mark.parametrize("target", ["", "module", ":main", "module:"])
def test_invalid_command_target_rejected(target: str) -> None:
    with pytest.raises(ValueError, match="invalid command target"):
        command(target=target)


def test_duplicate_command_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate bundle command"):
        bc.command_map((command(), command()))


@pytest.mark.parametrize("commands", [
    (command("foo-bar"), command("foo_bar")),
    (command("foo_bar"), command("foo-bar")),
])
def test_normalized_alias_collision_rejected(commands: tuple[bc.Command, bc.Command]) -> None:
    with pytest.raises(ValueError, match="alias collision"):
        bc.command_map(commands)


def test_command_map_sorted_by_name() -> None:
    commands = (command("beta"), command("alpha"))
    assert list(bc.command_map(commands)) == ["alpha", "beta"]


def test_dispatch_lazily_invokes_target_without_mutating_sys_argv(
    target_module: tuple[list[list[str]], ModuleType],
) -> None:
    calls, _ = target_module
    original = list(sys.argv)
    assert bc.dispatch((command(),), ["go", "x", "y"]) == 7
    assert calls == [["x", "y"]]
    assert sys.argv == original


def test_dispatch_accepts_legacy_underscore_alias(
    target_module: tuple[list[list[str]], ModuleType],
) -> None:
    calls, _ = target_module
    assert bc.dispatch((command("write-handoff-artifact"),), ["write_handoff_artifact", "x"]) == 7
    assert calls == [["x"]]


def test_dispatch_empty_argv_prints_usage_and_returns_2(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert bc.dispatch((command(),), []) == 2
    assert "usage: <pyz> {go}" in capsys.readouterr().out


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_dispatch_help_returns_0(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert bc.dispatch((command(),), [flag]) == 0
    assert "usage:" in capsys.readouterr().out


def test_dispatch_unknown_command_returns_2_to_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert bc.dispatch((command(),), ["nope"]) == 2
    assert "usage:" in capsys.readouterr().err


def test_dispatch_rejects_missing_target_attribute(
    target_module: tuple[list[list[str]], ModuleType],
) -> None:
    with pytest.raises(AttributeError):
        bc.dispatch((command(target="test_bundle_target:missing"),), ["go"])


def test_dispatch_rejects_non_integer_status(
    target_module: tuple[list[list[str]], ModuleType],
) -> None:
    _, module = target_module
    module.handler = lambda argv: "oops"  # type: ignore[attr-defined]
    with pytest.raises(TypeError, match="did not return an integer status"):
        bc.dispatch((command(),), ["go"])


def test_every_skill_declares_a_static_manifest() -> None:
    from scripts import build_pyz

    for skill in build_pyz.SKILLS:
        package = skill.replace("-", "_")
        module = importlib.import_module(f"easy_cheese.skills.{package}.commands")
        assert module.COMMANDS
        assert all(isinstance(item, bc.Command) for item in module.COMMANDS)
        bc.command_map(module.COMMANDS)
        assert all(callable(bc._handler(item.target)) for item in module.COMMANDS)


def test_skill_manifests_are_literal_tuples() -> None:
    from scripts import build_pyz

    for skill in build_pyz.SKILLS:
        package = skill.replace("-", "_")
        module = importlib.import_module(f"easy_cheese.skills.{package}.commands")
        tree = ast.parse(inspect.getsource(module))
        bindings = [
            node
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and (
                any(
                    isinstance(target, ast.Name) and target.id == "COMMANDS"
                    for target in node.targets
                )
                if isinstance(node, ast.Assign)
                else isinstance(node.target, ast.Name) and node.target.id == "COMMANDS"
            )
        ]
        assert len(bindings) == 1, f"{module.__name__}.COMMANDS must have one top-level binding"
        assert isinstance(bindings[0].value, ast.Tuple), (
            f"{module.__name__}.COMMANDS must be a literal tuple"
        )
