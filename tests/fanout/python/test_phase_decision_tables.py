"""Tests for the genericized phase_decision tables (parallel mode).

The linear 7-phase table is regression-locked in
tests/fanout/python/test_phase_decision.py (acceptance #1). This file locks
the two parallel tables and the table-parameterised decide()/CLI added for
parallel mode (acceptance #2).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
import build_pyz  # noqa: E402

BUNDLE = build_pyz.cached_bundle("ultracook")


class TestTableShapes:
    def test_linear_table_unchanged(self, phase_decision: ModuleType) -> None:
        # AC1 guard: linear mode is byte-for-byte the original chain.
        assert phase_decision.LINEAR_TABLE == [
            "cook",
            "press",
            "age",
            "cure",
            "age",
            "cure",
            "age",
        ]

    def test_parallel_curd_table(self, phase_decision: ModuleType) -> None:
        assert phase_decision.PARALLEL_CURD == ["cook", "press", "age", "cure"]

    def test_parallel_postmerge_table(self, phase_decision: ModuleType) -> None:
        assert phase_decision.PARALLEL_POSTMERGE == ["press", "age", "cure"]

    def test_default_table_is_linear(self, phase_decision: ModuleType) -> None:
        # Calling decide without a table must behave exactly like linear mode.
        assert phase_decision.decide(0, "ok")["next_phase"] == "press"
        assert phase_decision.decide(6, "ok")["action"] == "stop"


class TestParallelCurdTable:
    def test_cook_spawns_press(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(0, "ok", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "press"

    def test_age_spawns_cure(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(2, "ok", "cure", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "cure"

    def test_cure_is_terminal(self, phase_decision: ModuleType) -> None:
        # The per-curd pipeline ends at cure — no post-cure age in the curd.
        r = phase_decision.decide(3, "ok", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "stop"
        assert r["next_phase"] is None

    def test_index_past_end_raises(self, phase_decision: ModuleType) -> None:
        with pytest.raises(phase_decision.cli.CliError):
            phase_decision.decide(4, "ok", table=phase_decision.PARALLEL_CURD)

    def test_age_next_done_stops_early(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(2, "ok", "done", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "stop_early"

    def test_halt_short_circuits(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(1, "halt: boom", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "halt"


class TestParallelPostmergeTable:
    def test_press_spawns_age(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(0, "ok", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_age_spawns_cure(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(1, "ok", "cure", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["next_phase"] == "cure"

    def test_cure_is_terminal(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(2, "ok", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "stop"


class TestCliTableFlag:
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUNDLE), "phase_decision", *args],
            capture_output=True,
            text=True,
        )

    def test_parallel_curd_cure_terminal(self) -> None:
        result = self._run(
            "--phase-index", "3", "--status", "ok", "--table", "parallel-curd"
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["action"] == "stop"

    def test_parallel_postmerge_press_spawns_age(self) -> None:
        result = self._run(
            "--phase-index", "0", "--status", "ok", "--table", "parallel-postmerge"
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["next_phase"] == "age"

    def test_default_table_is_linear(self) -> None:
        result = self._run("--phase-index", "6", "--status", "ok")
        assert result.returncode == 0
        assert json.loads(result.stdout)["action"] == "stop"

    def test_unknown_table_rejected(self) -> None:
        result = self._run(
            "--phase-index", "0", "--status", "ok", "--table", "bogus"
        )
        assert result.returncode == 2
