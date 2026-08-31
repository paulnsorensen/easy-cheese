"""Behavioral contract for static bundle command manifests."""

from __future__ import annotations

import ast
import importlib
import inspect
import sys
from types import ModuleType
from typing import cast

import pytest

from easy_cheese.shared import bundle_commands as bc


def command(
    name: str = "go",
    target: str = "test_bundle_target:handler",
    summary: str = "Go somewhere",
) -> bc.Command:
    return bc.Command(name, target, summary)


@pytest.fixture
def target_module(monkeypatch: pytest.MonkeyPatch) -> tuple[list[list[str]], ModuleType]:
    calls: list[list[str]] = []
    module = ModuleType("test_bundle_target")

    def handler(argv: list[str]) -> int:
        calls.append(argv)
        return 7

    module.handler = handler  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return calls, module


@pytest.mark.parametrize("name", ["Bad", "", "-x", "_x", "a b", "camelCase"])
def test_invalid_command_name_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="invalid command name"):
        _ = command(name=name)


@pytest.mark.parametrize("target", ["", "module", ":main", "module:"])
def test_invalid_command_target_rejected(target: str) -> None:
    with pytest.raises(ValueError, match="invalid command target"):
        _ = command(target=target)


@pytest.mark.parametrize(
    "summary",
    [
        "",
        "   ",
        " leading space",
        "trailing space ",
        "two\nlines",
        "table | breaker",
        "|",
    ],
)
def test_invalid_command_summary_rejected(summary: str) -> None:
    with pytest.raises(ValueError, match="invalid command summary"):
        _ = command(summary=summary)


def test_duplicate_command_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate bundle command"):
        _ = bc.command_map((command(), command()))


@pytest.mark.parametrize("commands", [
    (command("foo-bar"), command("foo_bar")),
    (command("foo_bar"), command("foo-bar")),
])
def test_normalized_alias_collision_rejected(commands: tuple[bc.Command, bc.Command]) -> None:
    with pytest.raises(ValueError, match="alias collision"):
        _ = bc.command_map(commands)


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
    _ = target_module
    with pytest.raises(AttributeError):
        _ = bc.dispatch((command(target="test_bundle_target:missing"),), ["go"])


def test_dispatch_rejects_non_integer_status(
    target_module: tuple[list[list[str]], ModuleType],
) -> None:
    _, module = target_module

    def handler(argv: list[str]) -> str:
        del argv
        return "oops"

    module.handler = handler  # pyright: ignore[reportAttributeAccessIssue]
    with pytest.raises(TypeError, match="did not return an integer status"):
        _ = bc.dispatch((command(),), ["go"])


def test_every_skill_declares_a_static_manifest() -> None:
    from scripts import build_pyz

    for skill in build_pyz.SKILLS:
        package = skill.replace("-", "_")
        module = importlib.import_module(f"easy_cheese.skills.{package}.commands")
        commands = cast(tuple[bc.Command, ...], module.COMMANDS)
        assert commands
        assert all(isinstance(item, bc.Command) for item in commands)
        _ = bc.command_map(commands)
        assert all(
            callable(bc._handler(item.target))  # pyright: ignore[reportPrivateUsage]
            for item in commands
        )


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


def test_render_skill_commands_projects_the_manifest_verbatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import render_generated_regions as rgr

    module = ModuleType("easy_cheese.skills.fixture_skill.commands")
    module.COMMANDS = (  # pyright: ignore[reportAttributeAccessIssue]
        command("zeta", summary="Run the last step"),
        command("alpha", summary="Run the first step"),
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert rgr.render_skill_commands("fixture-skill") == (
        "# `/fixture-skill` bundle commands\n"
        "\n"
        "Generated by `scripts/render_generated_regions.py` from the static `COMMANDS`"
        " manifest in `src/easy_cheese/skills/fixture_skill/commands.py`; do not hand-edit."
        " Every command runs as `python3 skills/fixture-skill/scripts/fixture-skill.pyz"
        " <command> [args...]` and returns an integer exit status. Pass `--help` to a command"
        " for its own arguments and output format; worked examples stay in the skill prose.\n"
        "\n"
        "| Command | Purpose |\n"
        "| --- | --- |\n"
        "| `alpha` | Run the first step |\n"
        "| `zeta` | Run the last step |\n"
    )


def test_rendering_command_docs_never_resolves_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    from scripts import build_pyz
    from scripts import render_generated_regions as rgr

    def explode(target: str) -> bc.CommandHandler:
        raise AssertionError(f"doc rendering resolved command target {target!r}")

    monkeypatch.setattr(bc, "_handler", explode)
    for skill in build_pyz.SKILLS:
        assert rgr.render_skill_commands(skill).startswith(f"# `/{skill}` bundle commands\n")


def test_checked_in_command_docs_match_the_manifests() -> None:
    from scripts import build_pyz
    from scripts import render_generated_regions as rgr

    for skill in build_pyz.SKILLS:
        path = rgr.commands_doc_path(skill)
        assert path.read_text(encoding="utf-8") == rgr.render_skill_commands(skill), (
            f"{path} is stale; run scripts/render_generated_regions.py"
        )


def test_command_doc_slugs_match_the_bundled_skills() -> None:
    from scripts import build_pyz
    from scripts import render_generated_regions as rgr

    assert rgr.SKILL_SLUGS == build_pyz.SKILLS
