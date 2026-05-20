"""Tests for shared/scripts/gates_cli.py — CLI wrapper around gates.py.

Loaded via importlib (not the conftest fixture) so the test file is
self-contained per curd file-assignment constraint.
"""

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
GATES_CLI_PATH = SHARED_SCRIPTS / "gates_cli.py"
CLI_PATH = SHARED_SCRIPTS / "cli.py"
GATES_PATH = SHARED_SCRIPTS / "gates.py"


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gates_cli() -> ModuleType:
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    _load("cli", CLI_PATH)
    _load("gates", GATES_PATH)
    return _load("gates_cli", GATES_CLI_PATH)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(GATES_CLI_PATH), *args],
        capture_output=True,
        text=True,
    )


class TestClassifyHappyPath:
    def test_clean_floor_no_gaps_is_ready(self) -> None:
        result = _run("classify", "--press-status", "ready-for-age", "--hard-floor-met", "--json")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == {"press_status": "ready-for-age", "readiness": "ready for /age"}

    def test_level_4_or_5_only_means_follow_up(self) -> None:
        result = _run(
            "classify",
            "--press-status",
            "soft-only",
            "--hard-floor-met",
            "--has-open-level-4-or-5",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["readiness"] == "follow-up recommended"

    def test_open_level_1_or_2_blocks(self) -> None:
        result = _run(
            "classify",
            "--press-status",
            "hard-broken",
            "--hard-floor-met",
            "--has-open-level-1-or-2",
            "--json",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["readiness"] == "blocked"

    def test_missing_press_status_exits_two(self) -> None:
        # argparse-level missing required arg -> exit 2
        result = _run("classify", "--hard-floor-met")
        assert result.returncode == 2
        assert "press-status" in result.stderr.lower()


class TestAttemptBudget:
    def test_initial_state_for_slug(self) -> None:
        result = _run("attempt-budget", "--slug", "foo", "--json")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload == {
            "slug": "foo",
            "completed": 0,
            "cap": 2,
            "at_cap": False,
            "next_action": "cure",
        }

    def test_different_slug_same_initial_state(self) -> None:
        # No persistence — every slug starts fresh.
        result = _run("attempt-budget", "--slug", "bar", "--json")
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["slug"] == "bar"
        assert payload["completed"] == 0
        assert payload["next_action"] == "cure"

    def test_missing_slug_exits_two(self) -> None:
        result = _run("attempt-budget", "--json")
        assert result.returncode == 2

    def test_empty_slug_exits_two_with_cli_error(self) -> None:
        # argparse accepts empty strings; our CliError guard catches them.
        result = _run("attempt-budget", "--slug", "", "--json")
        assert result.returncode == 2
        assert "slug must be non-empty" in result.stderr


class TestJsonMode:
    def test_json_flag_emits_valid_json(self) -> None:
        result = _run("attempt-budget", "--slug", "foo", "--json")
        assert result.returncode == 0
        # Must parse cleanly as JSON.
        json.loads(result.stdout)

    def test_default_dict_emit_is_also_json(self) -> None:
        # cli.emit always JSON-serialises dicts (see cli.py emit rules).
        result = _run("attempt-budget", "--slug", "foo")
        assert result.returncode == 0
        json.loads(result.stdout)


class TestInvalidInput:
    def test_unknown_subcommand_exits_two(self) -> None:
        result = _run("frobnicate")
        assert result.returncode == 2

    def test_missing_subcommand_exits_two(self) -> None:
        result = _run()
        assert result.returncode == 2


class TestInProcessClassify:
    def test_classify_helper_emits_dict(
        self, gates_cli: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import argparse

        ns = argparse.Namespace(
            press_status="ready-for-age",
            hard_floor_met=True,
            has_open_level_1_or_2=False,
            has_open_level_3=False,
            has_open_level_4_or_5=False,
            any_spinning=False,
            json_mode=True,
        )
        gates_cli._cmd_classify(ns)
        payload = json.loads(capsys.readouterr().out)
        assert payload == {"press_status": "ready-for-age", "readiness": "ready for /age"}

    def test_attempt_budget_helper_emits_dict(
        self, gates_cli: ModuleType, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import argparse

        ns = argparse.Namespace(slug="my-slug", json_mode=True)
        gates_cli._cmd_attempt_budget(ns)
        payload = json.loads(capsys.readouterr().out)
        assert payload["slug"] == "my-slug"
        assert payload["completed"] == 0
