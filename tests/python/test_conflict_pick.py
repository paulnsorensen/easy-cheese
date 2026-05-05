"""Tests for conflict-pick.resolve_hunks (pure function — no subprocess)."""

from __future__ import annotations

from types import ModuleType


def _conflict(ours: list[str], theirs: list[str], base: list[str] | None = None) -> str:
    parts = ["<<<<<<< HEAD", *ours]
    if base is not None:
        parts.extend(["||||||| merged", *base])
    parts.extend(["=======", *theirs, ">>>>>>> branch"])
    return "\n".join(parts)


class TestResolveHunks:
    def test_takes_ours(self, conflict_pick: ModuleType) -> None:
        content = "before\n" + _conflict(["A"], ["B"]) + "\nafter"
        result = conflict_pick.resolve_hunks(content, strategy="ours")
        assert "A" in result
        assert "B" not in result
        assert "<<<<<<<" not in result

    def test_takes_theirs(self, conflict_pick: ModuleType) -> None:
        content = "before\n" + _conflict(["A"], ["B"]) + "\nafter"
        result = conflict_pick.resolve_hunks(content, strategy="theirs")
        assert "B" in result
        assert "A" not in result

    def test_resolves_multiple_hunks(self, conflict_pick: ModuleType) -> None:
        content = _conflict(["A1"], ["B1"]) + "\nmiddle\n" + _conflict(["A2"], ["B2"])
        result = conflict_pick.resolve_hunks(content, strategy="ours")
        assert "A1" in result and "A2" in result
        assert "B1" not in result and "B2" not in result

    def test_grep_only_resolves_matching_hunks(self, conflict_pick: ModuleType) -> None:
        content = (
            _conflict(["timeout=10"], ["timeout=20"])
            + "\n"
            + _conflict(["color=red"], ["color=blue"])
        )
        result = conflict_pick.resolve_hunks(content, strategy="ours", grep_pattern="timeout")
        assert "timeout=10" in result
        assert "timeout=20" not in result
        # The non-matching hunk must still have its conflict markers preserved.
        assert "<<<<<<<" in result
        assert "color=red" in result
        assert "color=blue" in result

    def test_grep_no_match_keeps_all_markers(self, conflict_pick: ModuleType) -> None:
        content = _conflict(["A"], ["B"])
        result = conflict_pick.resolve_hunks(content, strategy="ours", grep_pattern="zzz")
        assert result.strip() == content.strip()

    def test_diff3_base_section_is_dropped(self, conflict_pick: ModuleType) -> None:
        content = _conflict(["ours"], ["theirs"], base=["common"])
        result = conflict_pick.resolve_hunks(content, strategy="theirs")
        assert "theirs" in result
        assert "common" not in result
        assert "ours" not in result
        assert "|||||||" not in result

    def test_unterminated_conflict_is_preserved(self, conflict_pick: ModuleType) -> None:
        # Missing closing >>>>>>> marker — must not silently drop the partial hunk.
        content = "before\n<<<<<<< HEAD\nA\n=======\nB\nno-end-marker\n"
        result = conflict_pick.resolve_hunks(content, strategy="ours")
        assert "<<<<<<<" in result
        assert "=======" in result
        assert "A" in result
        assert "B" in result

    def test_no_conflicts_returns_input_unchanged(self, conflict_pick: ModuleType) -> None:
        content = "line1\nline2\nline3\n"
        # resolve_hunks splits and rejoins, so trailing newline normalization is OK.
        assert conflict_pick.resolve_hunks(content, strategy="ours").rstrip("\n") == content.rstrip(
            "\n"
        )
