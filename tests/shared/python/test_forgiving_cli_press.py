"""Adversarial tests for the forgiving bundle CLI (dispatch and cli.run)."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

from easy_cheese.shared import bundle_commands as bc
from cyclopts import App

from easy_cheese.shared import cli

_INDEX_MODULE = "easy_cheese.shared.bundle_command_index"


def _bucket_app() -> App:
    app = App(name="test")

    def bucket(files: int, modules: int = 1, title: str = "") -> None:
        print(files, modules, title)

    _ = app.command(bucket, name="bucket")
    return app


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    recorded: list[list[str]] = []
    module = ModuleType("press_bundle_target")

    def handler(argv: list[str]) -> int:
        recorded.append(argv)
        return 7

    module.handler = handler  # pyright: ignore[reportAttributeAccessIssue]
    monkeypatch.setitem(sys.modules, module.__name__, module)
    return recorded


def _command(name: str, leaves: tuple[str, ...] = ()) -> bc.Command:
    return bc.Command(name, "press_bundle_target:handler", "Do the work", leaves)


def test_unknown_command_survives_a_missing_index(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # A `None` entry makes the import raise ImportError.
    monkeypatch.setitem(sys.modules, _INDEX_MODULE, None)
    assert bc.dispatch((_command("show"),), ["shwo"]) == 2
    err = capsys.readouterr().err
    assert err.splitlines()[0] == "usage: <pyz> {show} [args...]"
    assert "Did you mean: show?" in err


@pytest.mark.parametrize("token", ["", " ", "sh ow", "show\n", "SHOW"])
def test_odd_command_tokens_fail_closed(
    calls: list[list[str]], token: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bc.dispatch((_command("show"),), [token]) == 2
    assert calls == []
    assert capsys.readouterr().err.startswith("usage: <pyz> {show} [args...]")


def test_a_leaf_is_never_run_from_the_top_level(
    calls: list[list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    commands = (_command("severity", ("compute", "bucket")),)
    assert bc.dispatch(commands, ["bucket", "--files", "2"]) == 2
    assert calls == []
    err = capsys.readouterr().err
    assert err.count("severity bucket") == 1


def test_local_leaf_is_not_repeated_from_the_index(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    index = ModuleType(_INDEX_MODULE)
    index.COMMAND_BUNDLES = {}  # pyright: ignore[reportAttributeAccessIssue]
    index.LEAF_OWNERS = {  # pyright: ignore[reportAttributeAccessIssue]
        "compute": (("age", "severity"), ("cure", "severity"), ("cook", "cost"))
    }
    monkeypatch.setitem(sys.modules, _INDEX_MODULE, index)
    commands = (_command("severity", ("compute",)),)
    assert bc.dispatch(commands, ["compute"]) == 2
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == len(set(lines))
    assert sum("severity compute" in line for line in lines) == 1
    assert "'compute' is 'cost compute' in cook.pyz." in lines


def test_hoist_accepts_the_underscore_alias(
    calls: list[list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    commands = (_command("read-slug"),)
    assert bc.dispatch(commands, ["--json", "--full", "read_slug", "x"]) == 7
    assert calls == [["--json", "--full", "x"]]
    assert "note: moved --json --full after 'read_slug'" in capsys.readouterr().err


def test_leading_flags_without_a_command_fail_closed(
    calls: list[list[str]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert bc.dispatch((_command("show"),), ["--json", "--full"]) == 2
    assert calls == []
    assert "Put the command first" in capsys.readouterr().err


def test_hoist_does_not_loop_on_a_command_that_looks_like_a_flag_value(
    calls: list[list[str]],
) -> None:
    # The second `show` is an argument of the first `show`.
    assert bc.dispatch((_command("show"),), ["--json", "show", "show"]) == 7
    assert calls == [["--json", "show"]]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("--work_id", "--work-id"),
        ("--fix_cost_later=a_b", "--fix-cost-later=a_b"),
        ("--note=keep_this", "--note=keep_this"),
        ("--Work_id", "--Work_id"),
        ("-x_y", "-x_y"),
        ("--_x", "--_x"),
        ("snake_value", "snake_value"),
        ("--trailing_", "--trailing_"),
    ],
)
def test_flag_standardization_changes_only_long_flag_names(
    calls: list[list[str]], given: str, expected: str
) -> None:
    assert bc.dispatch((_command("go"),), ["go", given]) == 7
    assert calls == [[expected]]


def test_repair_handles_the_equals_form(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.run(_bucket_app(), argv=["bucket", "--files=2 --modules=3"]) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "2 3"
    assert "note: split quoted argument" in captured.err


def test_repair_reads_sys_argv_when_argv_is_none(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["prog", "bucket", "--files", "4 --modules 5"])
    assert cli.run(_bucket_app()) == 0
    assert capsys.readouterr().out.strip() == "4 5"


def test_probe_failure_prints_nothing_before_the_real_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = cli.run(_bucket_app(), argv=["bucket", "--files", "x --modules y"])
    assert status == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("ERROR:") == 1


def test_whitespace_value_without_a_declared_flag_is_untouched(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["bucket", "--files", "2", "--title", "two words --unknown here"]
    assert cli.run(_bucket_app(), argv=argv) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "2 1 two words --unknown here"
    assert captured.err == ""


def test_handler_runs_once_when_repair_applies() -> None:
    runs: list[int] = []

    def record(files: int, modules: int = 1) -> None:
        del modules
        runs.append(files)

    app = App(name="test")
    _ = app.default(record)
    assert cli.run(app, argv=["--files", "2 --modules 3"]) == 0
    assert runs == [2]


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_wins_over_repair(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    status = cli.run(_bucket_app(), argv=["bucket", flag, "--files", "2 --modules 3"])
    assert status == 0
    captured = capsys.readouterr()
    assert "--modules" in captured.out
    assert "note:" not in captured.err


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_a_split_that_frees_help_prints_nothing_on_stdout(
    flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    status = cli.run(_bucket_app(), argv=["bucket", "--files", "2", "--modules", f"1 {flag} x"])
    assert status == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("ERROR:") == 1


def test_free_text_that_names_a_missing_required_flag_is_not_split(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = cli.run(_bucket_app(), argv=["bucket", "--title", "ran --files 9 on the diff"])
    assert status == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "--files" in captured.err
    assert "note:" not in captured.err


def test_free_text_stays_whole_beside_a_valid_call(
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["bucket", "--files", "2", "--title", "ran --modules 9 on the diff"]
    assert cli.run(_bucket_app(), argv=argv) == 0
    captured = capsys.readouterr()
    assert captured.out.strip() == "2 1 ran --modules 9 on the diff"
    assert captured.err == ""


def test_positional_free_text_is_not_split() -> None:
    seen: list[str] = []

    def record(text: str, files: int) -> None:
        del files
        seen.append(text)

    app = App(name="test")
    _ = app.default(record)
    assert cli.run(app, argv=["see --files 2"]) == 2
    assert cli.repair_argv(app, ["see --files 2"]) == ["see --files 2"]
    assert seen == []


def test_repair_stops_at_the_option_terminator(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = cli.run(_bucket_app(), argv=["bucket", "--", "--files", "2 --modules 3"])
    assert status == 2
    assert "note:" not in capsys.readouterr().err


def test_the_repair_note_prints_the_pieces(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.run(_bucket_app(), argv=["bucket", "--files", "2 --modules 3"]) == 0
    expected = "note: split quoted argument '2 --modules 3' into ['2', '--modules', '3']"
    assert expected in capsys.readouterr().err


def test_repair_argv_exposes_the_argv_that_the_parser_reads() -> None:
    app = App(name="test")

    def command(count: int, slug: str) -> None:
        del count, slug

    _ = app.default(command)
    repaired = cli.repair_argv(app, ["--count", "2 --slug victim"])
    assert repaired == ["--count", "2", "--slug", "victim"]


@pytest.mark.parametrize("flag", ["--slug", "--phase", "-x"])
def test_a_leading_value_flag_is_rejected_and_never_guessed(
    calls: list[list[str]], flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    # `show` can be the value of the flag, so the dispatcher does not run it.
    assert bc.dispatch((_command("show"),), [flag, "show", "x"]) == 2
    assert calls == []
    err = capsys.readouterr().err
    assert err.splitlines()[0] == "usage: <pyz> {show} [args...]"
    assert "Put the command first" in err
    assert f"not {flag}." in err


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_among_the_leading_flags_prints_the_top_level_help(
    calls: list[list[str]], flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert bc.dispatch((_command("show"),), ["--json", flag]) == 0
    assert calls == []
    assert capsys.readouterr().out.startswith("usage: <pyz> {show} [args...]")
