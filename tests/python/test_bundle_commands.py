"""Behavioral contract for static bundle command manifests."""

from __future__ import annotations

import ast
import contextlib
import importlib
import inspect
import io
import re
import sys
from pathlib import Path
from types import ModuleType
from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol, cast

import pytest

from easy_cheese.shared import bundle_commands as bc
from scripts import build_pyz as _build_pyz

_CommandHandler = Callable[[list[str]], int]
_CommandFactory = Callable[[str, str, str], bc.Command]


class _BundleCommandsSurface(Protocol):
    def bundle_command(
        self, name: str
    ) -> Callable[[_CommandHandler], _CommandHandler]: ...

    def derive_command(self, handler: _CommandHandler, summary: str) -> bc.Command: ...

    def validate_command_surface(
        self, module: ModuleType, commands: tuple[bc.Command, ...]
    ) -> None: ...


if TYPE_CHECKING:
    _bundle_commands: _BundleCommandsSurface
else:
    _bundle_commands = bc


def command(
    name: str = "go",
    target: str = "test_bundle_target:handler",
    summary: str = "Go somewhere",
) -> bc.Command:
    return cast(_CommandFactory, bc.Command)(name, target, summary)


@pytest.fixture
def target_module(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[list[str]], ModuleType]:
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
        "two\rlines",
        "two\r\nlines",
        "two\vlines",
        "two\flines",
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


@pytest.mark.parametrize(
    "commands",
    [
        (command("foo-bar"), command("foo_bar")),
        (command("foo_bar"), command("foo-bar")),
    ],
)
def test_normalized_alias_collision_rejected(
    commands: tuple[bc.Command, bc.Command],
) -> None:
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
    assert (
        bc.dispatch(
            (command("write-handoff-artifact"),), ["write_handoff_artifact", "x"]
        )
        == 7
    )
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


def _fake_command_module(*, decorated: tuple[str, ...]) -> ModuleType:
    module = ModuleType("test_bundle_surface_module")

    def make_handler(name: str) -> _CommandHandler:
        def handler(argv: list[str]) -> int:
            del argv
            return 0

        handler.__module__ = module.__name__
        handler.__qualname__ = f"_{name.replace('-', '_')}"
        return _bundle_commands.bundle_command(name)(handler)

    for name in decorated:
        setattr(module, f"_{name.replace('-', '_')}", make_handler(name))
    return module


def test_validate_command_surface_rejects_unreferenced_declaration() -> None:
    module = _fake_command_module(decorated=("foo", "bar"))
    bar = cast(_CommandHandler, module._bar)
    with pytest.raises(ValueError, match="declares unreferenced bundle command.*foo"):
        _bundle_commands.validate_command_surface(
            module, (_bundle_commands.derive_command(bar, "Bar command"),)
        )


def test_validate_command_surface_rejects_undeclared_reference() -> None:
    module = _fake_command_module(decorated=("foo",))
    foo = cast(_CommandHandler, module._foo)
    stray = command("stray")
    with pytest.raises(ValueError, match="references undeclared bundle command.*stray"):
        _bundle_commands.validate_command_surface(
            module, (_bundle_commands.derive_command(foo, "Foo command"), stray)
        )


@pytest.mark.parametrize("skill", _build_pyz.SKILLS)
def test_validate_command_surface_passes_for_every_skill(skill: str) -> None:
    package = skill.replace("-", "_")
    module = importlib.import_module(f"easy_cheese.skills.{package}.commands")
    commands = cast("tuple[bc.Command, ...]", module.COMMANDS)
    _bundle_commands.validate_command_surface(module, commands)


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
        assert len(bindings) == 1, (
            f"{module.__name__}.COMMANDS must have one top-level binding"
        )
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
        bc.Command("alpha", "test_bundle_target:handler", "Run the first step", ("one", "two")),
    )
    monkeypatch.setitem(sys.modules, module.__name__, module)

    assert rgr.render_skill_commands("fixture-skill") == (
        "# `/fixture-skill` bundle commands\n"
        "\n"
        "`scripts/render_generated_regions.py` generates this file from the static"
        " `COMMANDS` manifest in `src/easy_cheese/skills/fixture_skill/commands.py`."
        " Do not edit this file. Run each command as `python3"
        " skills/fixture-skill/scripts/fixture-skill.pyz <command> [args...]`. Each command"
        " returns an integer exit status. Pass `--help` to a command for its arguments and"
        " output format. Keep worked examples in the skill instructions.\n"
        "\n"
        "| Command | Purpose | Subcommands |\n"
        "| --- | --- | --- |\n"
        "| `alpha` | Run the first step | `one`, `two` |\n"
        "| `zeta` | Run the last step |  |\n"
    )


def test_rendering_command_docs_never_resolves_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scripts import build_pyz
    from scripts import render_generated_regions as rgr

    def explode(target: str) -> bc.CommandHandler:
        raise AssertionError(f"doc rendering resolved command target {target!r}")

    monkeypatch.setattr(bc, "_handler", explode)
    for skill in build_pyz.SKILLS:
        assert rgr.render_skill_commands(skill).startswith(
            f"# `/{skill}` bundle commands\n"
        )


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


def _underscore_long_options(source: str) -> list[str]:
    """Return each `--flag_name` string literal passed to an `add_argument` call."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_argument":
            continue
        for argument in node.args:
            if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                continue
            if argument.value.startswith("--") and "_" in argument.value:
                found.append(argument.value)
    return found


def test_the_underscore_guard_reads_every_option_string_of_a_call() -> None:
    source = 'parser.add_argument("-w", "--work_id")\nparser.add_argument("--ok-name")\n'
    assert _underscore_long_options(source) == ["--work_id"]


def test_no_long_option_uses_an_underscore_in_its_flag_name() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "easy_cheese"
    offenders = {
        str(path): found
        for path in root.rglob("*.py")
        if (found := _underscore_long_options(path.read_text(encoding="utf-8")))
    }
    assert offenders == {}


# argparse prints a subparser group as `{a,b} ...` in the usage text. A `choices=`
# option or positional has no trailing `...`.
_SUBPARSER_GROUP_RE = re.compile(r"\{([a-z0-9_,\s-]+)\}\s+\.\.\.")


def _subparser_names(handler: _CommandHandler) -> set[str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
        with contextlib.suppress(SystemExit):
            _ = handler(["--help"])
    match = _SUBPARSER_GROUP_RE.search(buffer.getvalue())
    if match is None:
        return set()
    return {name.strip() for name in match.group(1).split(",")}


@pytest.mark.parametrize("skill", _build_pyz.SKILLS)
def test_declared_leaves_match_the_handlers_subparsers(skill: str) -> None:
    package = skill.replace("-", "_")
    module = importlib.import_module(f"easy_cheese.skills.{package}.commands")
    commands = cast("tuple[bc.Command, ...]", module.COMMANDS)
    for item in commands:
        handler = bc._handler(item.target)  # pyright: ignore[reportPrivateUsage]
        assert set(item.leaves) == _subparser_names(handler), (
            f"{skill}: {item.name}.leaves does not match the subparsers in --help"
        )


_TWO_COMMAND_HELP = (
    "usage: <pyz> {alpha|beta-long} [args...]\n"
    "  alpha      Do alpha\n"
    "  beta-long  Do beta\n"
    "Run <pyz> <command> --help for the arguments of a command.\n"
    "references/commands.md in the skill directory lists the commands.\n"
)


@pytest.mark.parametrize(
    ("argv", "status"), [([], 2), (["-h"], 0), (["--help"], 0), (["help"], 0)]
)
def test_dispatch_top_level_help_is_the_same_full_block_for_every_form(
    argv: list[str], status: int, capsys: pytest.CaptureFixture[str]
) -> None:
    commands = (
        command("alpha", summary="Do alpha"),
        command("beta-long", summary="Do beta"),
    )
    assert bc.dispatch(commands, argv) == status
    assert capsys.readouterr().out == _TWO_COMMAND_HELP


def test_dispatch_help_dispatches_to_a_command_literally_named_help(
    target_module: tuple[list[list[str]], ModuleType],
) -> None:
    calls, _ = target_module
    commands = (command("help"),)
    assert bc.dispatch(commands, ["help", "x"]) == 7
    assert calls == [["x"]]


def test_dispatch_unknown_nested_leaf_names_the_owning_parent(
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands = (
        bc.Command(
            "severity", "test_bundle_target:handler", "Severity", ("compute", "bucket")
        ),
    )
    assert bc.dispatch(commands, ["compute"]) == 2
    err = capsys.readouterr().err
    assert err.splitlines()[0] == "usage: <pyz> {severity} [args...]"
    assert "'compute' is a subcommand of 'severity'. Run: <pyz> severity compute ..." in err


def test_dispatch_unknown_cross_bundle_command_names_the_owning_bundle(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_index = ModuleType("easy_cheese.shared.bundle_command_index")
    fake_index.COMMAND_BUNDLES = {"worktree": ("cook",)}  # pyright: ignore[reportAttributeAccessIssue]
    fake_index.LEAF_OWNERS = {}  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, fake_index.__name__, fake_index)
    commands = (command("go"),)
    assert bc.dispatch(commands, ["worktree"]) == 2
    err = capsys.readouterr().err
    assert "'worktree' is a command of cook.pyz." in err


def test_dispatch_unknown_cross_bundle_leaf_names_the_owning_parent_and_bundle(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_index = ModuleType("easy_cheese.shared.bundle_command_index")
    fake_index.COMMAND_BUNDLES = {}  # pyright: ignore[reportAttributeAccessIssue]
    fake_index.LEAF_OWNERS = {  # pyright: ignore[reportAttributeAccessIssue]
        "create": (("cook", "worktree"),)
    }
    monkeypatch.setitem(sys.modules, fake_index.__name__, fake_index)
    commands = (command("go"),)
    assert bc.dispatch(commands, ["create"]) == 2
    err = capsys.readouterr().err
    assert "'create' is 'worktree create' in cook.pyz." in err


def test_dispatch_close_match_suggests_without_running(
    target_module: tuple[list[list[str]], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = target_module
    commands = (command("go"),)
    assert bc.dispatch(commands, ["goo"]) == 2
    err = capsys.readouterr().err
    assert "Did you mean: go?" in err
    assert calls == []


def test_dispatch_never_suggests_the_same_name_twice(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_index = ModuleType("easy_cheese.shared.bundle_command_index")
    fake_index.COMMAND_BUNDLES = {"goo": ("cook",)}  # pyright: ignore[reportAttributeAccessIssue]
    fake_index.LEAF_OWNERS = {}  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, fake_index.__name__, fake_index)
    commands = (command("go"),)
    assert bc.dispatch(commands, ["goo"]) == 2
    err = capsys.readouterr().err
    assert "Did you mean" not in err


def test_dispatch_hoists_leading_flags_and_notes_it(
    target_module: tuple[list[list[str]], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = target_module
    commands = (command("go"),)
    assert bc.dispatch(commands, ["--json", "go", "x"]) == 7
    assert calls == [["--json", "x"]]
    err = capsys.readouterr().err
    assert "note: moved --json after 'go'" in err


def test_dispatch_gives_unknown_command_guidance_after_a_global_flag(
    target_module: tuple[list[list[str]], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = target_module
    assert bc.dispatch((command("go"),), ["--json", "value", "go"]) == 2
    err = capsys.readouterr().err
    assert err.splitlines()[0] == "usage: <pyz> {go} [args...]"
    assert "note:" not in err
    assert calls == []


def test_dispatch_never_reads_a_flag_value_as_the_command(
    target_module: tuple[list[list[str]], ModuleType],
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = target_module
    assert bc.dispatch((command("go"),), ["--slug", "go", "x"]) == 2
    err = capsys.readouterr().err
    assert "Put the command first: <pyz> <command> [flags]" in err
    assert "not --slug." in err
    assert calls == []


def test_dispatch_prints_help_for_a_help_flag_after_a_global_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert bc.dispatch((command("go"),), ["--json", "--help"]) == 0
    assert capsys.readouterr().out.startswith("usage: <pyz> {go} [args...]")


def test_dispatch_applies_the_underscore_alias_to_cross_bundle_guidance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake_index = ModuleType("easy_cheese.shared.bundle_command_index")
    fake_index.COMMAND_BUNDLES = {"stack-tools": ("plate",)}  # pyright: ignore[reportAttributeAccessIssue]
    fake_index.LEAF_OWNERS = {}  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, fake_index.__name__, fake_index)
    assert bc.dispatch((command("go"),), ["stack_tools"]) == 2
    assert "'stack-tools' is a command of plate.pyz." in capsys.readouterr().err


def test_dispatch_applies_the_underscore_alias_to_leaf_guidance(
    capsys: pytest.CaptureFixture[str],
) -> None:
    commands = (
        bc.Command("findings", "test_bundle_target:handler", "Findings", ("render-table",)),
    )
    assert bc.dispatch(commands, ["render_table"]) == 2
    err = capsys.readouterr().err
    assert "'render-table' is a subcommand of 'findings'." in err


def test_dispatch_standardizes_flag_names_before_the_handler_runs(
    target_module: tuple[list[list[str]], ModuleType],
) -> None:
    calls, _ = target_module
    commands = (command("go"),)
    assert bc.dispatch(commands, ["go", "--flag_name=1", "--", "--kept_as_is"]) == 7
    assert calls == [["--flag-name=1", "--", "--kept_as_is"]]
