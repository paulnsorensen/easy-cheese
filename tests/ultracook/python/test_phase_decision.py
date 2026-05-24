"""Tests for skills/ultracook/scripts/phase_decision.py — phase-table router.

Covers the 7-entry phase table, halt short-circuit, terminal stop, and the
age-only early-stop signal. Loaded via importlib (no conftest) so the test
stays self-contained under tests/ultracook/python/.
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


class TestSpawnPhases:
    """Each ok phase except the terminal one spawns the next phase."""

    def test_phase_0_cook_spawns_press(self, phase_decision: ModuleType) -> None:
        # Acceptance: phase index 0 with status=ok returns action=spawn next_phase=press.
        result = phase_decision.decide(0, "ok")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "press"

    def test_phase_1_press_spawns_age(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(1, "ok")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "age"

    def test_phase_2_age_spawns_cure(self, phase_decision: ModuleType) -> None:
        # Age with next!=done continues; the medium+ floor is not yet met.
        result = phase_decision.decide(2, "ok", "cure")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "cure"

    def test_phase_3_cure_spawns_age(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(3, "ok")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "age"

    def test_phase_4_age_spawns_cure(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(4, "ok", "cure")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "cure"

    def test_phase_5_cure_spawns_age(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(5, "ok")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "age"


class TestStopTerminal:
    """Phase 6 is the final age; the chain table is exhausted."""

    def test_phase_6_returns_stop(self, phase_decision: ModuleType) -> None:
        # Acceptance: phase index 6 returns action=stop.
        result = phase_decision.decide(6, "ok")
        assert result["action"] == "stop"
        assert result["next_phase"] is None

    def test_phase_6_stop_even_with_next_done(self, phase_decision: ModuleType) -> None:
        # Terminal stop wins over early-stop signal — the chain ends here either way.
        result = phase_decision.decide(6, "ok", "done")
        assert result["action"] == "stop"


class TestHaltShortCircuit:
    """status=halt at any phase produces action=halt regardless of next_phase."""

    def test_halt_at_phase_0(self, phase_decision: ModuleType) -> None:
        # Acceptance: status=halt at any phase returns action=halt.
        result = phase_decision.decide(0, "halt: cook gate failed")
        assert result["action"] == "halt"
        assert result["next_phase"] is None
        assert "halt" in result["exit_message"].lower()

    def test_halt_at_phase_3(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(3, "halt: cure could not apply any finding")
        assert result["action"] == "halt"

    def test_halt_at_terminal_phase(self, phase_decision: ModuleType) -> None:
        # Even the final phase honours halt — never silently coalesce to stop.
        result = phase_decision.decide(6, "halt: age crashed")
        assert result["action"] == "halt"

    def test_halt_case_insensitive(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(2, "HALT: scary thing")
        assert result["action"] == "halt"

    def test_halt_bare_word(self, phase_decision: ModuleType) -> None:
        # "halt" alone (no colon, no reason) still short-circuits.
        result = phase_decision.decide(1, "halt")
        assert result["action"] == "halt"


class TestEarlyStop:
    """Age-only signal: next=done means the diff is clean at medium+ floor."""

    def test_age_phase_2_next_done_stops_early(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(2, "ok", "done")
        assert result["action"] == "stop_early"
        assert result["next_phase"] is None

    def test_age_phase_4_next_done_stops_early(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(4, "ok", "done")
        assert result["action"] == "stop_early"

    def test_cure_with_next_done_still_spawns(self, phase_decision: ModuleType) -> None:
        # Cure never writes next=done per the SKILL.md contract, but if it
        # somehow did, the orchestrator must not treat it as early-stop.
        result = phase_decision.decide(3, "ok", "done")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "age"

    def test_age_with_other_next_keeps_spawning(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(2, "ok", "cure")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "cure"

    def test_age_with_no_next_keeps_spawning(self, phase_decision: ModuleType) -> None:
        # If the handoff slug omits `next`, default to spawn — the orchestrator
        # only stops early when the slug positively signals done.
        result = phase_decision.decide(2, "ok")
        assert result["action"] == "spawn"
        assert result["next_phase"] == "cure"


class TestInvalidIndex:
    def test_negative_index_raises(self, phase_decision: ModuleType) -> None:
        with pytest.raises(phase_decision.cli.CliError):
            phase_decision.decide(-1, "ok")

    def test_index_past_end_raises(self, phase_decision: ModuleType) -> None:
        with pytest.raises(phase_decision.cli.CliError):
            phase_decision.decide(7, "ok")


class TestOutputShape:
    def test_required_keys_present(self, phase_decision: ModuleType) -> None:
        result = phase_decision.decide(0, "ok")
        assert set(result.keys()) == {"action", "next_phase", "exit_message"}
        assert isinstance(result["exit_message"], str)
        assert result["exit_message"]

    def test_action_is_one_of_four(self, phase_decision: ModuleType) -> None:
        valid = {"spawn", "stop", "stop_early", "halt"}
        for idx, status, nxt in [
            (0, "ok", None),
            (6, "ok", None),
            (2, "ok", "done"),
            (3, "halt: oops", None),
        ]:
            result = phase_decision.decide(idx, status, nxt)
            assert result["action"] in valid


# ---------------------------------------------------------------------------
# CLI entrypoint tests via subprocess (cli.run calls sys.exit).
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(BUNDLE), "phase_decision", *args],
        capture_output=True,
        text=True,
    )


class TestCli:
    def test_phase_0_ok_spawns_press(self) -> None:
        result = _run_cli("--phase-index", "0", "--status", "ok")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["action"] == "spawn"
        assert payload["next_phase"] == "press"

    def test_phase_6_returns_stop(self) -> None:
        result = _run_cli("--phase-index", "6", "--status", "ok")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["action"] == "stop"

    def test_halt_returns_halt(self) -> None:
        result = _run_cli("--phase-index", "2", "--status", "halt: oops")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["action"] == "halt"

    def test_age_next_done_stops_early(self) -> None:
        result = _run_cli(
            "--phase-index", "4", "--status", "ok", "--next", "done"
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["action"] == "stop_early"

    def test_missing_phase_index_exits_2(self) -> None:
        result = _run_cli("--status", "ok")
        assert result.returncode == 2

    def test_missing_status_exits_2(self) -> None:
        result = _run_cli("--phase-index", "0")
        assert result.returncode == 2

    def test_invalid_phase_index_exits_2(self) -> None:
        result = _run_cli("--phase-index", "99", "--status", "ok")
        assert result.returncode == 2
        assert "phase-index" in result.stderr or "ERROR" in result.stderr

    def test_help_lists_required_flags(self) -> None:
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "--phase-index" in result.stdout
        assert "--status" in result.stdout
