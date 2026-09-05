"""Tests for shared/handoff.py's render / parse / dispatch CLI."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

import pytest

from easy_cheese.shared.bundle_commands import Command

if TYPE_CHECKING:
    from collections.abc import Callable


class _HandoffCliModule(Protocol):
    _cmd_render: Callable[..., None]
    _cmd_parse: Callable[..., None]
    _cmd_dispatch: Callable[..., None]

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "src" / "easy_cheese" / "shared"
HANDOFF_CLI = SHARED_SCRIPTS / "handoff.py"


@pytest.fixture(scope="module")
def handoff_cli_mod() -> ModuleType:
    return importlib.import_module("easy_cheese.shared.handoff")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HANDOFF_CLI), *args],
        capture_output=True,
        text=True,
    )


class TestRender:
    def test_emits_four_line_preamble(self) -> None:
        result = _run(
            "render",
            "--status", "ok",
            "--next", "cure",
            "--artifact", "foo",
            "--orientation", "bar",
        )
        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines == [
            "status: ok",
            "next: cure",
            "artifact: foo",
            "bar",
        ]

    def test_halt_with_reason(self) -> None:
        result = _run(
            "render",
            "--status", "halt: dep conflict",
            "--next", "done",
            "--artifact", "",
            "--orientation", "Stopped.",
        )
        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[0] == "status: halt: dep conflict"
        assert lines[1] == "next: done"
        assert lines[2] == "artifact: "
        assert lines[3] == "Stopped."

    def test_strips_leading_slash_on_next(self) -> None:
        result = _run(
            "render",
            "--status", "ok",
            "--next", "/age",
            "--artifact", "x",
            "--orientation", "y",
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines()[1] == "next: age"

    def test_halt_without_reason_errors(self) -> None:
        result = _run(
            "render",
            "--status", "halt:",
            "--next", "done",
            "--artifact", "",
            "--orientation", "x",
        )
        assert result.returncode == 3
        assert "halt status requires" in result.stderr
        assert "--status" in result.stderr

    def test_unknown_status_errors(self) -> None:
        result = _run(
            "render",
            "--status", "maybe",
            "--next", "age",
            "--artifact", "",
            "--orientation", "x",
        )
        assert result.returncode == 3
        assert "status must be" in result.stderr
        assert "--status" in result.stderr


class TestParse:
    def test_parses_file_and_returns_json(self, tmp_path: Path) -> None:
        fixture = tmp_path / "preamble.md"
        _ = fixture.write_text(
            "status: ok\n"
            + "next: press\n"
            + "artifact: .cheese/cook/demo.md\n"
            + "Cooked the retry path.\n"
        )
        result = _run("parse", "--file", str(fixture))
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload == {
            "status": "ok",
            "reason": None,
            "halt_reason": None,
            "next": "press",
            "baseline": None,
            "next_skill": "press",
            "artifact": ".cheese/cook/demo.md",
            "orientation": "Cooked the retry path.",
            "taste_test": None,
            "durable_flags": None,
            "disposition": "proceed",
        }

    def test_round_trip_through_render(self, tmp_path: Path) -> None:
        rendered = _run(
            "render",
            "--status", "halt: stuck",
            "--next", "done",
            "--artifact", ".cheese/age/x.md",
            "--orientation", "Could not converge.",
        )
        assert rendered.returncode == 0, rendered.stderr
        fixture = tmp_path / "p.md"
        _ = fixture.write_text(rendered.stdout + ("\n" if not rendered.stdout.endswith("\n") else ""))
        parsed = _run("parse", "--file", str(fixture))
        assert parsed.returncode == 0, parsed.stderr
        payload = cast("dict[str, object]", json.loads(parsed.stdout))
        assert payload["status"] == "halt"
        assert payload["reason"] == "stuck"
        assert payload["halt_reason"] == "stuck"
        assert payload["next_skill"] == "done"
        assert payload["artifact"] == ".cheese/age/x.md"
        assert payload["orientation"] == "Could not converge."

    def test_missing_file_errors(self, tmp_path: Path) -> None:
        result = _run("parse", "--file", str(tmp_path / "nope.md"))
        assert result.returncode == 2
        assert "file not found" in result.stderr

    def test_malformed_preamble_errors(self, tmp_path: Path) -> None:
        fixture = tmp_path / "bad.md"
        _ = fixture.write_text("status: ok\nnext: age\n")  # missing artifact + orientation
        result = _run("parse", "--file", str(fixture))
        assert result.returncode == 3
        assert "ERROR:" in result.stderr

    def test_malformed_preamble_error_carries_file_path(self, tmp_path: Path) -> None:
        fixture = tmp_path / "bad.md"
        _ = fixture.write_text("status: ok\nnext: age\n")
        result = _run("parse", "--file", str(fixture))
        assert str(fixture) in result.stderr


class TestDispatch:
    def test_extracts_skill_and_args(self) -> None:
        result = _run("dispatch", "/age slug --hard")
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload == {"skill": "age", "args": ["slug", "--hard"]}

    def test_bare_skill(self) -> None:
        result = _run("dispatch", "/cure")
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload == {"skill": "cure", "args": []}

    def test_non_dispatch_errors(self) -> None:
        result = _run("dispatch", "age slug")
        assert result.returncode == 2
        assert "not a skill dispatch" in result.stderr


class TestJsonMode:
    def test_dispatch_explicit_json_flag(self) -> None:
        # dict output already JSON; --json must still succeed (and not double-wrap).
        result = _run("dispatch", "/age slug", "--json")
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload == {"skill": "age", "args": ["slug"]}

    def test_parse_explicit_json_flag(self, tmp_path: Path) -> None:
        fixture = tmp_path / "p.md"
        _ = fixture.write_text(
            "status: ok\nnext: cure\nartifact: \nOrient.\n"
        )
        result = _run("parse", "--file", str(fixture), "--json")
        assert result.returncode == 0, result.stderr
        payload = cast("dict[str, object]", json.loads(result.stdout))
        assert payload["next_skill"] == "cure"
        assert payload["artifact"] is None


class TestArgparse:
    def test_missing_subcommand_exits_two(self) -> None:
        result = _run()
        assert result.returncode == 2

    def test_render_missing_required_arg_exits_two(self) -> None:
        result = _run("render", "--status", "ok")  # missing --next/--orientation
        assert result.returncode == 2
        assert "usage:" in result.stderr.lower() or "required" in result.stderr.lower()

    def test_parse_missing_file_arg_exits_two(self) -> None:
        result = _run("parse")
        assert result.returncode == 2

    def test_dispatch_missing_command_exits_two(self) -> None:
        result = _run("dispatch")
        assert result.returncode == 2


class TestModuleImports:
    def test_loads_via_importlib(self, handoff_cli_mod: _HandoffCliModule) -> None:
        # Sanity: the module exposes the subcommand handlers (in-process unit test).
        assert callable(handoff_cli_mod._cmd_render)  # pyright: ignore[reportPrivateUsage]
        assert callable(handoff_cli_mod._cmd_parse)  # pyright: ignore[reportPrivateUsage]
        assert callable(handoff_cli_mod._cmd_dispatch)  # pyright: ignore[reportPrivateUsage]

    def test_old_module_is_not_importable(self) -> None:
        with pytest.raises(ImportError):
            _ = importlib.import_module("easy_cheese.shared.handoff_cli")


def _bundle_commands(bundle: str) -> list[Command]:
    module = importlib.import_module(f"easy_cheese.skills.{bundle}.commands")
    return list(cast("tuple[Command, ...]", module.COMMANDS))


class TestBundleRegistration:
    @pytest.mark.parametrize("bundle", ["age", "cure", "cook"])
    def test_handoff_registered_and_handoff_cli_absent(self, bundle: str) -> None:
        names = {command.name for command in _bundle_commands(bundle)}
        assert "handoff" in names
        assert "handoff-cli" not in names

    def test_render_output_is_byte_identical_across_bundles(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = [
            "render",
            "--status", "ok",
            "--next", "cure",
            "--artifact", "foo",
            "--orientation", "bar",
        ]
        outputs: set[str] = set()
        for bundle in ("age", "cure", "cook"):
            handler = next(c for c in _bundle_commands(bundle) if c.name == "handoff")
            module_name, _, attribute = handler.target.partition(":")
            handler_fn = cast(
                "Callable[[list[str]], int]", getattr(importlib.import_module(module_name), attribute)
            )
            assert handler_fn(args) == 0
            outputs.add(capsys.readouterr().out)
        assert outputs == {"status: ok\nnext: cure\nartifact: foo\nbar\n"}


class TestModeCli:
    def test_render_emits_mode_only_when_given_and_parse_echoes_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from easy_cheese.shared import handoff as handoff_mod

        base = ["render", "--status", "ok", "--next", "cook", "--artifact", "", "--orientation", "o"]
        assert handoff_mod.main(base) == 0
        plain = capsys.readouterr().out
        assert handoff_mod.main([*base, "--mode", "parallel"]) == 0
        with_mode = capsys.readouterr().out
        assert "mode:" not in plain
        assert "mode: parallel\n" in with_mode

        preamble = tmp_path / "pre.md"
        _ = preamble.write_text(with_mode, encoding="utf-8")
        assert handoff_mod.main(["parse", "--file", str(preamble)]) == 0
        parsed = cast(dict[str, object], json.loads(capsys.readouterr().out))
        assert parsed["mode"] == "parallel"
        _ = preamble.write_text(plain, encoding="utf-8")
        assert handoff_mod.main(["parse", "--file", str(preamble)]) == 0
        assert "mode" not in cast(dict[str, object], json.loads(capsys.readouterr().out))

class TestSharedEmitter:
    def test_read_handoff_slug_emits_mode_like_handoff_parse(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from easy_cheese.shared import handoff as handoff_mod
        from easy_cheese.shared import paths, read_handoff_slug

        artifact = tmp_path / ".cheese" / "age" / "slug.md"
        artifact.parent.mkdir(parents=True)
        _ = artifact.write_text("status: ok\nnext: tasks\nartifact: \nmode: parallel\norient\n", encoding="utf-8")
        def _fixed(_phase: str, _slug: str) -> Path:
            return artifact

        monkeypatch.setattr(paths, "artifact_path", _fixed)
        assert read_handoff_slug.main(["--phase", "age", "--slug", "slug"]) == 0
        via_reader = cast(dict[str, object], json.loads(capsys.readouterr().out))
        assert handoff_mod.main(["parse", "--file", str(artifact)]) == 0
        via_parse = cast(dict[str, object], json.loads(capsys.readouterr().out))
        assert via_reader["mode"] == via_parse["mode"] == "parallel"
        assert set(via_reader) <= set(via_parse)
