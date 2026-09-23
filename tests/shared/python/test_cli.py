"""Tests for shared CLI parsing, output, and Cyclopts dispatch."""

from __future__ import annotations

import json
import io
from cyclopts import App
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol

import pytest

if TYPE_CHECKING:
    from collections.abc import Sequence
    from typing import TextIO
REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PATH = REPO_ROOT / "src" / "easy_cheese" / "shared" / "cli.py"


def _bucket_app() -> App:
    app = App(name="test")

    def bucket(
        files: int,
        modules: int = 1,
        title: str = "",
        json_mode: bool = False,
    ) -> None:
        del json_mode
        print(files, modules, title)

    _ = app.command(bucket, name="bucket")
    return app


class _CliError(Exception):
    """Typing stand-in for `cli.CliError`: an Exception carrying `exit_code`."""

    def __init__(self, message: str, *, exit_code: int = 2) -> None:
        super().__init__(message)
        self.exit_code: int = exit_code


class _CliModule(Protocol):
    CliError: type[_CliError]

    def contract_error(self, exc: Exception, *, context: str) -> _CliError: ...

    def emit(
        self,
        value: object,
        *,
        limit: int | None = ...,
        full: bool = ...,
        json_mode: bool = ...,
        stdout: TextIO | None = ...,
    ) -> None: ...

    def repair_argv(self, app: object, argv: Sequence[str]) -> list[str]: ...

    def run(
        self,
        app: object,
        *,
        argv: Sequence[str] | None = ...,
        stdout: TextIO | None = ...,
    ) -> int: ...


@pytest.fixture(scope="module")
def cli() -> ModuleType:
    import importlib.util
    spec = importlib.util.spec_from_file_location("cli", CLI_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["cli"] = module
    spec.loader.exec_module(module)
    return module


class TestLineBudget:
    def test_stays_tiny(self) -> None:
        # Spec quality gate was <= 75 lines; ruff E701/E702 (added repo-wide after the
        # spec was approved) forced one-statement-per-line, pushing the file to ~81.
        # Cap bumped to 90, then to 96 for the shared reject_path_segment helper that
        # single-sources a path-traversal denylist previously duplicated in callers.
        # Cap bumped to 110 for CliError.exit_code + contract_error (r014-phase-contracts #1).
        # Cap bumped to 126 for cli.repair_argv, the public hook the age
        # review-lock gate shares with cli.run so both read one repaired argv.
        assert sum(1 for _ in CLI_PATH.read_text().splitlines()) <= 126


class TestQuoteRepair:
    def test_splits_merged_token_when_only_the_split_form_parses(
        self, cli: _CliModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cli.run(_bucket_app(), argv=["bucket", "--files", "2 --modules 3"]) == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "2 3"
        assert "note: split quoted argument '2 --modules 3'" in captured.err

    def test_keeps_free_text_that_mentions_a_flag(
        self, cli: _CliModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        argv = ["bucket", "--files", "2", "--title", "handle --json flag"]
        assert cli.run(_bucket_app(), argv=argv) == 0
        captured = capsys.readouterr()
        assert captured.out.strip() == "2 1 handle --json flag"
        assert "note:" not in captured.err

    def test_shows_the_original_error_when_the_split_form_also_fails(
        self, cli: _CliModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        status = cli.run(_bucket_app(), argv=["bucket", "--files", "x --modules y"])
        assert status == 2
        captured = capsys.readouterr()
        assert 'x --modules y' in captured.err
        assert "note:" not in captured.err

    def test_ignores_a_token_with_unbalanced_quotes(
        self, cli: _CliModule, capsys: pytest.CaptureFixture[str]
    ) -> None:
        argv = ["bucket", "--files", "2", "--title", "it's --json here"]
        assert cli.run(_bucket_app(), argv=argv) == 0
        assert capsys.readouterr().out.strip() == "2 1 it's --json here"


class TestCliError:
    def test_is_exception(self, cli: _CliModule) -> None:
        assert issubclass(cli.CliError, Exception)

    def test_default_exit_code_is_two(self, cli: _CliModule) -> None:
        assert cli.CliError("bad").exit_code == 2

    def test_explicit_exit_code(self, cli: _CliModule) -> None:
        assert cli.CliError("bad", exit_code=3).exit_code == 3


class TestContractError:
    def test_wraps_message_and_exits_three(self, cli: _CliModule) -> None:
        wrapped = cli.contract_error(ValueError("nope"), context="--status")
        assert str(wrapped) == "--status: nope"
        assert wrapped.exit_code == 3



class TestEmitScalar:
    def test_print_plain_string(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("hello")
        assert capsys.readouterr().out == "hello\n"

    def test_print_int(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(42)
        assert capsys.readouterr().out == "42\n"

    def test_json_mode_wraps_scalar(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("hello", json_mode=True)
        assert json.loads(capsys.readouterr().out) == "hello"


class TestEmitDict:
    def test_dict_always_json(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit({"k": 1})
        assert json.loads(capsys.readouterr().out) == {"k": 1}

    def test_dict_json_mode(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit({"k": 1}, json_mode=True)
        assert json.loads(capsys.readouterr().out) == {"k": 1}


class TestEmitListNoLimit:
    def test_no_footer_when_limit_unset(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b", "c"])
        out = capsys.readouterr().out
        assert out == "a\nb\nc\n"
        assert "showing" not in out

    def test_json_mode_dumps_list(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b"], json_mode=True)
        assert json.loads(capsys.readouterr().out) == ["a", "b"]


class TestEmitListWithLimit:
    def test_no_footer_when_total_under_limit(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b"], limit=5)
        out = capsys.readouterr().out
        assert out == "a\nb\n"
        assert "showing" not in out  # spec mitigation: no ceremony on small lists

    def test_footer_when_total_exceeds_limit(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b", "c", "d", "e"], limit=2)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:2] == ["a", "b"]
        assert lines[2] == "... showing 2 of 5; pass --full for the rest (limit=2)"

    def test_full_always_emits_footer(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b"], limit=5, full=True)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:2] == ["a", "b"]
        assert lines[2] == "... showing 2 of 2 (--full; default limit=5)"

    def test_full_shows_all_items(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b", "c", "d", "e"], limit=2, full=True)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:5] == ["a", "b", "c", "d", "e"]
        assert lines[5] == "... showing 5 of 5 (--full; default limit=2)"


class TestEmitMultilineString:
    def test_string_with_limit_splits(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("line1\nline2\nline3", limit=2)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:2] == ["line1", "line2"]
        assert lines == ["line1", "line2", "... showing 2 of 3; pass --full for the rest (limit=2)"]

    def test_string_without_limit_prints_as_is(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("line1\nline2")
        assert capsys.readouterr().out == "line1\nline2\n"

    def test_string_with_limit_emits_footer(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("line1\nline2\nline3", limit=2)
        assert capsys.readouterr().out.splitlines() == [
            "line1", "line2", "... showing 2 of 3; pass --full for the rest (limit=2)"
        ]




class TestRun:
    def test_dispatch_to_func(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        app = App(name="test")

        def go(json_mode: bool = False) -> None:
            cli.emit({"ok": True}, json_mode=json_mode)

        _ = app.command(go, name="go")
        assert cli.run(app, argv=["go", "--json-mode"]) == 0
        assert json.loads(capsys.readouterr().out) == {"ok": True}


    def test_stdout_stream_is_used(self, cli: _CliModule) -> None:
        app = App(name="test")
        _ = app.command(lambda: print("ok"), name="go")
        output = io.StringIO()
        assert cli.run(app, argv=["go"], stdout=output) == 0
        assert output.getvalue() == "ok\n"
    def test_returns_status_and_invokes_once(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        app = App(name="test")
        calls: list[int] = []

        def go() -> int:
            calls.append(1)
            print("done")
            return 7

        _ = app.command(go, name="go")
        assert cli.run(app, argv=["go"]) == 7
        assert calls == [1]
        assert capsys.readouterr().out == "done\n"

    def test_cli_error_exits_two_with_stderr(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        app = App(name="test")

        def go() -> None:
            raise cli.CliError("bad input")

        _ = app.command(go, name="go")
        assert cli.run(app, argv=["go"]) == 2
        assert capsys.readouterr().err.strip() == "ERROR: bad input"

    def test_uncaught_exception_propagates(self, cli: _CliModule) -> None:
        app = App(name="test")

        def go() -> None:
            raise RuntimeError("boom")

        _ = app.command(go, name="go")
        with pytest.raises(RuntimeError, match="boom"):
            _ = cli.run(app, argv=["go"])

    def test_missing_subcommand_returns_two_with_error(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        app = App(name="test")
        _ = app.command(lambda: None, name="go")
        assert cli.run(app, argv=[]) == 2
        assert "command required" in capsys.readouterr().err

    def test_zero_arg_default_command_runs(self, cli: _CliModule) -> None:
        app = App(name="test")
        calls: list[str] = []

        def run() -> None:
            calls.append("ran")

        _ = app.default(run)
        assert cli.run(app, argv=[]) == 0
        assert calls == ["ran"]

    def test_help_flag_returns_zero(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        app = App(name="test")
        _ = app.command(lambda: None, name="go")
        assert cli.run(app, argv=["--help"]) == 0
        assert "Usage:" in capsys.readouterr().out

    def test_quote_repair_works_with_cyclopts(self, cli: _CliModule, capsys: pytest.CaptureFixture[str]) -> None:
        app = App(name="test")

        def go(files: int, modules: int = 1) -> None:
            print(files, modules)

        _ = app.command(go, name="go")
        assert cli.run(app, argv=["go", "--files", "2 --modules 3"]) == 0
        assert capsys.readouterr().out.strip() == "2 3"
class TestCliEntrypoint:
    def test_help_directly_on_cli_py(self) -> None:
        result = subprocess.run([sys.executable, str(CLI_PATH), "--help"], capture_output=True, text=True)
        assert result.returncode == 0


def test_quote_repair_preserves_free_text_option_values(
    cli: _CliModule, capsys: pytest.CaptureFixture[str]
) -> None:
    app = App(name="test")
    calls: list[tuple[int, str]] = []

    def go(files: int, path: str) -> None:
        calls.append((files, path))

    _ = app.command(go, name="go")
    assert cli.run(app, argv=["go", "--path", "safe --files 2"]) == 2
    assert calls == []
    assert "note:" not in capsys.readouterr().err
