"""Tests for shared/scripts/gates.py — readiness, cure-pass cap, iteration cap."""

from __future__ import annotations

from types import ModuleType


class TestClassifyReadiness:
    def test_clean_returns_ready(self, gates: ModuleType) -> None:
        result = gates.classify_readiness(
            hard_floor_met=True,
            has_open_level_1_or_2=False,
            has_open_level_3=False,
            has_open_level_4_or_5=False,
            any_spinning=False,
        )
        assert result is gates.Readiness.READY

    def test_only_level_4_or_5_means_follow_up(self, gates: ModuleType) -> None:
        result = gates.classify_readiness(
            hard_floor_met=True,
            has_open_level_1_or_2=False,
            has_open_level_3=False,
            has_open_level_4_or_5=True,
            any_spinning=False,
        )
        assert result is gates.Readiness.FOLLOW_UP

    def test_open_level_1_or_2_blocks(self, gates: ModuleType) -> None:
        result = gates.classify_readiness(
            hard_floor_met=True,
            has_open_level_1_or_2=True,
            has_open_level_3=False,
            has_open_level_4_or_5=False,
            any_spinning=False,
        )
        assert result is gates.Readiness.BLOCKED

    def test_spinning_blocks_even_with_clean_floor(self, gates: ModuleType) -> None:
        result = gates.classify_readiness(
            hard_floor_met=True,
            has_open_level_1_or_2=False,
            has_open_level_3=False,
            has_open_level_4_or_5=False,
            any_spinning=True,
        )
        assert result is gates.Readiness.BLOCKED

    def test_level_3_still_ready(self, gates: ModuleType) -> None:
        # Level-3 gaps are surfaced for /age to address, not blockers themselves.
        result = gates.classify_readiness(
            hard_floor_met=True,
            has_open_level_1_or_2=False,
            has_open_level_3=True,
            has_open_level_4_or_5=False,
            any_spinning=False,
        )
        assert result is gates.Readiness.READY


class TestCurePassCounter:
    def test_cap_default(self, gates: ModuleType) -> None:
        counter = gates.CurePassCounter()
        assert counter.cap == gates.CURE_PASS_CAP == 2

    def test_records_passes(self, gates: ModuleType) -> None:
        counter = gates.CurePassCounter()
        assert counter.next_action() == "cure"
        counter.record_pass()
        assert counter.next_action() == "cure"
        counter.record_pass()
        assert counter.at_cap is True
        assert counter.next_action() == "done"

    def test_cap_is_inclusive(self, gates: ModuleType) -> None:
        counter = gates.CurePassCounter(completed=2)
        assert counter.at_cap is True


class TestGapState:
    def test_starts_unclosed_zero_attempts(self, gates: ModuleType) -> None:
        gap = gates.GapState(name="missing-assertion")
        assert gap.attempts == 0
        assert gap.closed is False
        assert gap.is_spinning() is False

    def test_spins_after_cap_attempts(self, gates: ModuleType) -> None:
        gap = gates.GapState(name="x")
        for _ in range(gates.GAP_ITERATION_CAP):
            gap.record_attempt()
        assert gap.is_spinning() is True

    def test_closing_stops_spinning(self, gates: ModuleType) -> None:
        gap = gates.GapState(name="x")
        for _ in range(gates.GAP_ITERATION_CAP):
            gap.record_attempt()
        gap.close()
        assert gap.is_spinning() is False


class TestDetectHalt:
    def test_halt_with_reason(self, gates: ModuleType) -> None:
        assert gates.detect_halt("halt", "tests broken") is True

    def test_ok_status_never_halts(self, gates: ModuleType) -> None:
        assert gates.detect_halt("ok", None) is False
        assert gates.detect_halt("ok", "x") is False

    def test_halt_without_reason_is_falsy(self, gates: ModuleType) -> None:
        # Defensive: an empty reason behind a "halt" label is treated as not-halt.
        assert gates.detect_halt("halt", "") is False
