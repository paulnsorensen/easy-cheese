"""Tests for the genericized phase_decision tables.

The linear seven-phase table remains byte-equivalent. Fan remediation uses
the progress-aware state machine, so its retired parallel tables stay absent.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

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

    def test_parallel_tables_are_retired(self) -> None:
        assert "parallel-curd" not in phase_decision.TABLES
        assert "parallel-postmerge" not in phase_decision.TABLES

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



class TestCliTableFlag:
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(BUNDLE), "phase_decision", *args],
            capture_output=True,
            text=True,
        )


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