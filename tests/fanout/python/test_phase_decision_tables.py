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
    def test_linear_table_shape(self, phase_decision: ModuleType) -> None:
        # AC1 guard: linear mode retains the fixed seven-phase chain.
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
        assert phase_decision.PARALLEL_CURD == ["cook", "press", "age", "cure", "age"]

    def test_parallel_postmerge_table(self, phase_decision: ModuleType) -> None:
        assert phase_decision.PARALLEL_POSTMERGE == ["press", "age", "cure", "age"]

    def test_default_table_is_linear(self, phase_decision: ModuleType) -> None:
        # Calling decide without a table must behave exactly like linear mode.
        assert phase_decision.decide(0, "ok")["next_phase"] == "press"
        assert phase_decision.decide(6, "ok", "done")["action"] == "stop"


class TestParallelCurdTable:
    def test_cook_spawns_press(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(0, "ok", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "press"

    def test_age_spawns_cure(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(2, "ok", "cure", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "cure"

    def test_cure_spawns_final_age(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(3, "ok", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_final_age_is_publishable_only_when_done(self, phase_decision: ModuleType) -> None:
        done = phase_decision.decide(4, "ok", "done", table=phase_decision.PARALLEL_CURD)
        assert done["action"] == "stop"
        blocked = phase_decision.decide(4, "ok", "cure", table=phase_decision.PARALLEL_CURD)
        assert blocked["action"] == "halt"

    def test_index_past_end_raises(self, phase_decision: ModuleType) -> None:
        with pytest.raises(phase_decision.cli.CliError):
            phase_decision.decide(5, "ok", table=phase_decision.PARALLEL_CURD)

    def test_first_age_next_done_still_spawns_cure(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(2, "ok", "done", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "cure"

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

    def test_first_age_next_done_still_spawns_cure(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(1, "ok", "done", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "cure"

    def test_cure_spawns_final_age(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(2, "ok", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_final_age_with_next_cure_halts(self, phase_decision: ModuleType) -> None:
        r = phase_decision.decide(3, "ok", "cure", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "halt"


class TestCliTableFlag:
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUNDLE), "phase_decision", *args],
            capture_output=True,
            text=True,
        )

    def test_parallel_curd_final_age_terminal(self) -> None:
        result = self._run(
            "--phase-index", "4", "--status", "ok", "--next", "done",
            "--table", "parallel-curd",
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["action"] == "stop"

    def test_parallel_postmerge_press_spawns_age(self) -> None:
        result = self._run(
            "--phase-index", "0", "--status", "ok", "--table", "parallel-postmerge"
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["next_phase"] == "age"

    def test_parallel_curd_first_age_done_still_spawns_cure(self) -> None:
        result = self._run(
            "--phase-index", "2", "--status", "ok", "--next", "done",
            "--table", "parallel-curd",
        )
        assert result.returncode == 0
        decision = json.loads(result.stdout)
        assert decision["action"] == "spawn"
        assert decision["next_phase"] == "cure"

    def test_default_table_is_linear(self) -> None:
        result = self._run("--phase-index", "6", "--status", "ok", "--next", "done")
        assert result.returncode == 0
        assert json.loads(result.stdout)["action"] == "stop"

    def test_unknown_table_rejected(self) -> None:
        result = self._run(
            "--phase-index", "0", "--status", "ok", "--table", "bogus"
        )
        assert result.returncode == 2
