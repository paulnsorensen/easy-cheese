"""Regression tests for the Cyclopts fan-out command entrypoints."""

from __future__ import annotations

import io
import json
import sys
from typing import cast

import pytest

from easy_cheese.shared.fanout import baseline, milknado, mode, phase_decision


def test_mode_main_accepts_typed_cyclopts_options(capsys: pytest.CaptureFixture[str]) -> None:
    assert mode.main(["--count", "2"]) == 0
    assert capsys.readouterr().out.strip() == "parallel"


def test_milknado_main_reads_explicit_tools(capsys: pytest.CaptureFixture[str]) -> None:
    assert milknado.main(["--tools", "milknado_todo_add"]) == 0
    assert capsys.readouterr().out.strip() == "tracker"


def test_phase_decision_main_preserves_json_contract(capsys: pytest.CaptureFixture[str]) -> None:
    assert phase_decision.main(["--phase-index", "0", "--status", "ok"]) == 0
    result = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert result["action"] == "spawn"
    assert result["next_phase"] == "press"


def test_baseline_main_preserves_stdin_json_contract(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO('{"baseline": [], "current": []}'),
    )
    assert baseline.main([]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "identical": [],
        "new": [],
        "changed": [],
        "resolved": [],
    }
