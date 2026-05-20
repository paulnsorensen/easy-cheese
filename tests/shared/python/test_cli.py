"""Tests for shared/scripts/cli.py: argparse runner, CliError, emit, --full/--json injection."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PATH = REPO_ROOT / "shared" / "scripts" / "cli.py"


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
    def test_under_seventy_five(self) -> None:
        # The 75-line cap is a spec quality gate.
        assert sum(1 for _ in CLI_PATH.read_text().splitlines()) <= 75


class TestCliError:
    def test_is_exception(self, cli: ModuleType) -> None:
        assert issubclass(cli.CliError, Exception)


class TestInjectGlobalFlags:
    def test_injects_full_and_json(self, cli: ModuleType) -> None:
        parser = argparse.ArgumentParser()
        cli._inject_global_flags(parser)
        args = parser.parse_args(["--full", "--json"])
        assert args.full is True
        assert args.json_mode is True

    def test_injection_recurses_into_subparsers(self, cli: ModuleType) -> None:
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        sub.add_parser("do")
        cli._inject_global_flags(parser)
        args = parser.parse_args(["do", "--full", "--json"])
        assert args.full is True
        assert args.json_mode is True

    def test_does_not_double_register(self, cli: ModuleType) -> None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--full", action="store_true")
        # Must not raise argparse.ArgumentError for duplicate option.
        cli._inject_global_flags(parser)
        args = parser.parse_args(["--full"])
        assert args.full is True


class TestEmitScalar:
    def test_print_plain_string(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("hello")
        assert capsys.readouterr().out == "hello\n"

    def test_print_int(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(42)
        assert capsys.readouterr().out == "42\n"

    def test_json_mode_wraps_scalar(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("hello", json_mode=True)
        assert json.loads(capsys.readouterr().out) == "hello"


class TestEmitDict:
    def test_dict_always_json(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit({"k": 1})
        assert json.loads(capsys.readouterr().out) == {"k": 1}

    def test_dict_json_mode(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit({"k": 1}, json_mode=True)
        assert json.loads(capsys.readouterr().out) == {"k": 1}


class TestEmitListNoLimit:
    def test_no_footer_when_limit_unset(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b", "c"])
        out = capsys.readouterr().out
        assert out == "a\nb\nc\n"
        assert "showing" not in out

    def test_json_mode_dumps_list(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b"], json_mode=True)
        assert json.loads(capsys.readouterr().out) == ["a", "b"]


class TestEmitListWithLimit:
    def test_no_footer_when_total_under_limit(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b"], limit=5)
        out = capsys.readouterr().out
        assert out == "a\nb\n"
        assert "showing" not in out  # spec mitigation: no ceremony on small lists

    def test_footer_when_total_exceeds_limit(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b", "c", "d", "e"], limit=2)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:2] == ["a", "b"]
        assert lines[2] == "... showing 2 of 5; pass --full for the rest (limit=2)"

    def test_full_always_emits_footer(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b"], limit=5, full=True)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:2] == ["a", "b"]
        assert lines[2] == "... showing 2 of 2 (--full; default limit=5)"

    def test_full_shows_all_items(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit(["a", "b", "c", "d", "e"], limit=2, full=True)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:5] == ["a", "b", "c", "d", "e"]
        assert lines[5] == "... showing 5 of 5 (--full; default limit=2)"


class TestEmitMultilineString:
    def test_string_with_limit_splits(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("line1\nline2\nline3", limit=2)
        out = capsys.readouterr().out
        lines = out.splitlines()
        assert lines[:2] == ["line1", "line2"]
        assert lines[2] == "... showing 2 of 3; pass --full for the rest (limit=2)"

    def test_string_without_limit_prints_as_is(self, cli: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
        cli.emit("line1\nline2")
        assert capsys.readouterr().out == "line1\nline2\n"


def _write_runner(tmp_path: Path, body: str) -> Path:
    """Drop a tiny executable script next to cli.py so the import works."""
    runner = tmp_path / "runner.py"
    runner.write_text(
        textwrap.dedent(
            f"""
            import sys
            sys.path.insert(0, {str(CLI_PATH.parent)!r})
            import cli
            {body}
            """
        ).strip()
        + "\n"
    )
    return runner


class TestRun:
    def test_dispatch_to_func(self, tmp_path: Path) -> None:
        runner = _write_runner(
            tmp_path,
            """
            def _cmd(args): cli.emit({"ok": True}, json_mode=args.json_mode)
            def _setup(p):
                sub = p.add_subparsers(dest="cmd", required=True)
                q = sub.add_parser("go")
                q.set_defaults(func=_cmd)
            cli.run(_setup)
            """.strip()
        )
        result = subprocess.run([sys.executable, str(runner), "go", "--json"], capture_output=True, text=True)
        assert result.returncode == 0
        assert json.loads(result.stdout) == {"ok": True}

    def test_cli_error_exits_two_with_stderr(self, tmp_path: Path) -> None:
        runner = _write_runner(
            tmp_path,
            """
            def _cmd(args): raise cli.CliError("bad input")
            def _setup(p):
                sub = p.add_subparsers(dest="cmd", required=True)
                q = sub.add_parser("go")
                q.set_defaults(func=_cmd)
            cli.run(_setup)
            """.strip()
        )
        result = subprocess.run([sys.executable, str(runner), "go"], capture_output=True, text=True)
        assert result.returncode == 2
        assert result.stderr.strip() == "ERROR: bad input"
        assert result.stdout == ""

    def test_uncaught_exception_propagates(self, tmp_path: Path) -> None:
        runner = _write_runner(
            tmp_path,
            """
            def _cmd(args): raise RuntimeError("boom")
            def _setup(p):
                sub = p.add_subparsers(dest="cmd", required=True)
                q = sub.add_parser("go")
                q.set_defaults(func=_cmd)
            cli.run(_setup)
            """.strip()
        )
        result = subprocess.run([sys.executable, str(runner), "go"], capture_output=True, text=True)
        assert result.returncode != 0
        assert result.returncode != 2
        assert "RuntimeError" in result.stderr
        assert "boom" in result.stderr

    def test_missing_subcommand_prints_help_and_exits_two(self, tmp_path: Path) -> None:
        runner = _write_runner(
            tmp_path,
            """
            def _setup(p):
                p.add_subparsers(dest="cmd")
            cli.run(_setup)
            """.strip()
        )
        result = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True)
        assert result.returncode == 2
        assert "usage:" in result.stderr.lower()

    def test_help_flag_exits_zero(self, tmp_path: Path) -> None:
        runner = _write_runner(
            tmp_path,
            """
            def _setup(p):
                p.add_subparsers(dest="cmd")
            cli.run(_setup)
            """.strip()
        )
        result = subprocess.run([sys.executable, str(runner), "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "--full" in result.stdout
        assert "--json" in result.stdout


class TestCliEntrypoint:
    def test_help_directly_on_cli_py(self) -> None:
        result = subprocess.run([sys.executable, str(CLI_PATH), "--help"], capture_output=True, text=True)
        assert result.returncode == 0
