"""Tests for shared/scripts/handoff_cli.py — render / parse / dispatch CLI."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"
HANDOFF_CLI = SHARED_SCRIPTS / "handoff_cli.py"


@pytest.fixture(scope="module")
def handoff_cli_mod() -> ModuleType:
    # Make sibling modules (cli, handoff) importable.
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    spec = importlib.util.spec_from_file_location("handoff_cli", HANDOFF_CLI)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["handoff_cli"] = module
    spec.loader.exec_module(module)
    return module


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
        assert result.returncode == 2
        assert "halt status requires" in result.stderr

    def test_unknown_status_errors(self) -> None:
        result = _run(
            "render",
            "--status", "maybe",
            "--next", "age",
            "--artifact", "",
            "--orientation", "x",
        )
        assert result.returncode == 2
        assert "status must be" in result.stderr


class TestParse:
    def test_parses_file_and_returns_json(self, tmp_path: Path) -> None:
        fixture = tmp_path / "preamble.md"
        fixture.write_text(
            "status: ok\n"
            "next: press\n"
            "artifact: .cheese/cook/demo.md\n"
            "Cooked the retry path.\n"
        )
        result = _run("parse", "--file", str(fixture))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == {
            "status": "ok",
            "halt_reason": None,
            "next_skill": "press",
            "artifact": ".cheese/cook/demo.md",
            "orientation": "Cooked the retry path.",
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
        fixture.write_text(rendered.stdout + ("\n" if not rendered.stdout.endswith("\n") else ""))
        parsed = _run("parse", "--file", str(fixture))
        assert parsed.returncode == 0, parsed.stderr
        payload = json.loads(parsed.stdout)
        assert payload["status"] == "halt"
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
        fixture.write_text("status: ok\nnext: age\n")  # missing artifact + orientation
        result = _run("parse", "--file", str(fixture))
        assert result.returncode == 2
        assert "ERROR:" in result.stderr


class TestDispatch:
    def test_extracts_skill_and_args(self) -> None:
        result = _run("dispatch", "/age slug --safe")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == {"skill": "age", "args": ["slug", "--safe"]}

    def test_bare_skill(self) -> None:
        result = _run("dispatch", "/cure")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
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
        payload = json.loads(result.stdout)
        assert payload == {"skill": "age", "args": ["slug"]}

    def test_parse_explicit_json_flag(self, tmp_path: Path) -> None:
        fixture = tmp_path / "p.md"
        fixture.write_text(
            "status: ok\nnext: cure\nartifact: \nOrient.\n"
        )
        result = _run("parse", "--file", str(fixture), "--json")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
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
    def test_loads_via_importlib(self, handoff_cli_mod: ModuleType) -> None:
        # Sanity: the module exposes the subcommand handlers (in-process unit test).
        assert callable(handoff_cli_mod._cmd_render)
        assert callable(handoff_cli_mod._cmd_parse)
        assert callable(handoff_cli_mod._cmd_dispatch)
