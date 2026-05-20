"""Tests for shared/scripts/gates.py — readiness verdict."""

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

    def test_hard_floor_not_met_blocks_even_with_clean_gaps(
        self, gates: ModuleType
    ) -> None:
        # Hard floor is a precondition: failing it BLOCKs regardless of gap state.
        result = gates.classify_readiness(
            hard_floor_met=False,
            has_open_level_1_or_2=False,
            has_open_level_3=False,
            has_open_level_4_or_5=False,
            any_spinning=False,
        )
        assert result is gates.Readiness.BLOCKED

    def test_hard_floor_not_met_blocks_with_only_level_4_or_5(
        self, gates: ModuleType
    ) -> None:
        # Without the hard floor, even soft gaps don't promote to FOLLOW_UP.
        result = gates.classify_readiness(
            hard_floor_met=False,
            has_open_level_1_or_2=False,
            has_open_level_3=False,
            has_open_level_4_or_5=True,
            any_spinning=False,
        )
        assert result is gates.Readiness.BLOCKED
