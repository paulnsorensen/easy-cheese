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
from typing import cast

import pytest

from easy_cheese.shared import cli
from easy_cheese.shared.fanout import phase_decision
from easy_cheese.shared.fanout.phase_decision import Verdict

BUNDLE = Path(__file__).resolve().parents[3] / "skills/cook/scripts/cook.pyz"


def _verdict(stdout: str) -> Verdict:
    return cast(Verdict, cast(object, json.loads(stdout)))


class TestTableShapes:
    def test_linear_table_shape(self) -> None:
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

    def test_parallel_curd_table(self) -> None:
        assert phase_decision.PARALLEL_CURD == ["cook", "age", "cure", "age"]

    def test_parallel_postmerge_table(self) -> None:
        assert phase_decision.PARALLEL_POSTMERGE == ["press", "age", "cure", "age"]

    def test_not_applicable_tables_omit_press(self) -> None:
        assert phase_decision.NOT_APPLICABLE_LINEAR == [
            "cook",
            "age",
            "cure",
            "age",
            "cure",
            "age",
        ]
        assert phase_decision.NOT_APPLICABLE_CURD == [
            "cook",
            "age",
            "cure",
            "age",
        ]
        assert phase_decision.NOT_APPLICABLE_POSTMERGE == ["age", "cure", "age"]

    def test_default_table_is_linear(self) -> None:
        # Calling decide without a table must behave exactly like linear mode.
        assert phase_decision.decide(0, "ok")["next_phase"] == "press"
        assert phase_decision.decide(6, "ok", "done")["action"] == "stop"


class TestParallelCurdTable:
    def test_cook_spawns_age(self) -> None:
        r = phase_decision.decide(0, "ok", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_age_spawns_cure(self) -> None:
        r = phase_decision.decide(1, "ok", "cure", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "cure"

    def test_cure_spawns_final_age(self) -> None:
        r = phase_decision.decide(2, "ok", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_final_age_is_publishable_only_when_done(self) -> None:
        done = phase_decision.decide(3, "ok", "done", table=phase_decision.PARALLEL_CURD)
        assert done["action"] == "stop"
        blocked = phase_decision.decide(3, "ok", "cure", table=phase_decision.PARALLEL_CURD)
        assert blocked["action"] == "halt"

    def test_index_past_end_raises(self) -> None:
        with pytest.raises(cli.CliError):
            _ = phase_decision.decide(4, "ok", table=phase_decision.PARALLEL_CURD)

    def test_first_age_next_done_clean_completes(self) -> None:
        # A clean first age ends the curd: its bound review context becomes
        # the final review identity; cure and final age are skipped.
        r = phase_decision.decide(1, "ok", "done", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "clean_complete"
        assert r["next_phase"] is None
        assert "review context" in r["exit_message"]

    @pytest.mark.parametrize("nxt", ["DONE", " done ", "Done"])
    def test_first_age_next_done_normalised_clean_completes(self, nxt: str) -> None:
        r = phase_decision.decide(1, "ok", nxt, table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "clean_complete"

    def test_first_age_with_no_next_still_spawns_cure(self) -> None:
        # Clean-complete requires a positive done signal, never a missing field.
        r = phase_decision.decide(1, "ok", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "cure"

    def test_cure_with_next_done_still_spawns_final_age(self) -> None:
        # Only age phases may clean-complete; a stray done from cure spawns on.
        r = phase_decision.decide(2, "ok", "done", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_halt_short_circuits(self) -> None:
        r = phase_decision.decide(1, "halt: boom", table=phase_decision.PARALLEL_CURD)
        assert r["action"] == "halt"


class TestNotApplicableTables:
    def test_linear_cook_spawns_age(self) -> None:
        result = phase_decision.decide(
            0, "ok", table=phase_decision.NOT_APPLICABLE_LINEAR
        )
        assert result["next_phase"] == "age"

    def test_curd_first_age_can_clean_complete(self) -> None:
        result = phase_decision.decide(
            1,
            "ok",
            "done",
            table=phase_decision.NOT_APPLICABLE_CURD,
        )
        assert result["action"] == "clean_complete"

    def test_postmerge_age_still_spawns_cure(self) -> None:
        result = phase_decision.decide(
            0,
            "ok",
            "done",
            table=phase_decision.NOT_APPLICABLE_POSTMERGE,
        )
        assert result["action"] == "spawn"
        assert result["next_phase"] == "cure"


class TestParallelPostmergeTable:
    def test_press_spawns_age(self) -> None:
        r = phase_decision.decide(0, "ok", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_age_spawns_cure(self) -> None:
        r = phase_decision.decide(1, "ok", "cure", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["next_phase"] == "cure"

    def test_first_age_next_done_still_spawns_cure(self) -> None:
        # Post-merge is the last review before publication — no clean-complete
        # hatch; the full sequence through cure and final age always runs.
        r = phase_decision.decide(1, "ok", "done", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "cure"

    def test_cure_spawns_final_age(self) -> None:
        r = phase_decision.decide(2, "ok", table=phase_decision.PARALLEL_POSTMERGE)
        assert r["action"] == "spawn"
        assert r["next_phase"] == "age"

    def test_final_age_with_next_cure_halts(self) -> None:
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
            "--phase-index", "3", "--status", "ok", "--next", "done",
            "--table", "parallel-curd",
        )
        assert result.returncode == 0
        assert _verdict(result.stdout)["action"] == "stop"

    def test_parallel_postmerge_press_spawns_age(self) -> None:
        result = self._run(
            "--phase-index", "0", "--status", "ok", "--table", "parallel-postmerge"
        )
        assert result.returncode == 0
        assert _verdict(result.stdout)["next_phase"] == "age"

    def test_parallel_curd_first_age_done_clean_completes(self) -> None:
        result = self._run(
            "--phase-index", "1", "--status", "ok", "--next", "done",
            "--table", "parallel-curd",
        )
        assert result.returncode == 0
        decision = _verdict(result.stdout)
        assert decision["action"] == "clean_complete"
        assert decision["next_phase"] is None

    def test_parallel_postmerge_first_age_done_still_spawns_cure(self) -> None:
        result = self._run(
            "--phase-index", "1", "--status", "ok", "--next", "done",
            "--table", "parallel-postmerge",
        )
        assert result.returncode == 0
        decision = _verdict(result.stdout)
        assert decision["action"] == "spawn"
        assert decision["next_phase"] == "cure"

    def test_not_applicable_table_skips_press(self) -> None:
        result = self._run(
            "--phase-index",
            "0",
            "--status",
            "ok",
            "--table",
            "not-applicable-linear",
        )
        assert result.returncode == 0
        assert _verdict(result.stdout)["next_phase"] == "age"

    def test_default_table_is_linear(self) -> None:
        result = self._run("--phase-index", "6", "--status", "ok", "--next", "done")
        assert result.returncode == 0
        assert _verdict(result.stdout)["action"] == "stop"

    def test_unknown_table_rejected(self) -> None:
        result = self._run(
            "--phase-index", "0", "--status", "ok", "--table", "bogus"
        )
        assert result.returncode == 2