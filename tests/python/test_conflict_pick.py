"""Tests for conflict-pick.resolve_hunks (pure function — no subprocess)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pytest


class _ConflictPickModule(Protocol):
    def resolve_hunks(self, content: str, strategy: str, grep_pattern: str | None = None) -> str: ...
    def main(self, argv: list[str] | None = ...) -> int: ...


def _conflict(ours: list[str], theirs: list[str], base: list[str] | None = None) -> str:
    parts = ["<<<<<<< HEAD", *ours]
    if base is not None:
        parts.extend(["||||||| merged", *base])
    parts.extend(["=======", *theirs, ">>>>>>> branch"])
    return "\n".join(parts)


class TestResolveHunks:
    def test_takes_ours(self, conflict_pick: _ConflictPickModule) -> None:
        content = "before\n" + _conflict(["A"], ["B"]) + "\nafter"
        result = conflict_pick.resolve_hunks(content, strategy="ours")
        assert "A" in result
        assert "B" not in result
        assert "<<<<<<<" not in result

    def test_takes_theirs(self, conflict_pick: _ConflictPickModule) -> None:
        content = "before\n" + _conflict(["A"], ["B"]) + "\nafter"
        result = conflict_pick.resolve_hunks(content, strategy="theirs")
        assert "B" in result
        assert "A" not in result

    def test_resolves_multiple_hunks(self, conflict_pick: _ConflictPickModule) -> None:
        content = _conflict(["A1"], ["B1"]) + "\nmiddle\n" + _conflict(["A2"], ["B2"])
        result = conflict_pick.resolve_hunks(content, strategy="ours")
        assert "A1" in result and "A2" in result
        assert "B1" not in result and "B2" not in result

    def test_grep_only_resolves_matching_hunks(self, conflict_pick: _ConflictPickModule) -> None:
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

    def test_grep_no_match_keeps_all_markers(self, conflict_pick: _ConflictPickModule) -> None:
        content = _conflict(["A"], ["B"])
        result = conflict_pick.resolve_hunks(content, strategy="ours", grep_pattern="zzz")
        assert result.strip() == content.strip()

    def test_diff3_base_section_is_dropped(self, conflict_pick: _ConflictPickModule) -> None:
        content = _conflict(["ours"], ["theirs"], base=["common"])
        result = conflict_pick.resolve_hunks(content, strategy="theirs")
        assert "theirs" in result
        assert "common" not in result
        assert "ours" not in result
        assert "|||||||" not in result

    def test_unterminated_conflict_is_preserved(self, conflict_pick: _ConflictPickModule) -> None:
        # Missing closing >>>>>>> marker — must not silently drop the partial hunk.
        content = "before\n<<<<<<< HEAD\nA\n=======\nB\nno-end-marker\n"
        result = conflict_pick.resolve_hunks(content, strategy="ours")
        assert "<<<<<<<" in result
        assert "=======" in result
        assert "A" in result
        assert "B" in result

    def test_no_conflicts_returns_input_unchanged(self, conflict_pick: _ConflictPickModule) -> None:
        content = "line1\nline2\nline3\n"
        # resolve_hunks splits and rejoins, so trailing newline normalization is OK.
        assert conflict_pick.resolve_hunks(content, strategy="ours").rstrip("\n") == content.rstrip(
            "\n"
        )


class TestMain:
    def test_rejects_generated_pyz_without_decoding_or_mutating(
        self,
        conflict_pick: _ConflictPickModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = tmp_path / "bundle.pyz"
        original = b"\x00\xffbinary archive"
        _ = path.write_bytes(original)
        assert conflict_pick.main([str(path), "--ours"]) == 1
        assert path.read_bytes() == original
        error = capsys.readouterr().err
        assert "source conflicts" in error
        assert "rebuild" in error

    def test_rejects_binary_content_without_mutating(
        self,
        conflict_pick: _ConflictPickModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = tmp_path / "logo.png"
        original = b"<<<<<<< HEAD\n\x00\xff\n=======\n\x01\n>>>>>>> b\n"
        _ = path.write_bytes(original)
        assert conflict_pick.main([str(path), "--theirs"]) == 1
        assert path.read_bytes() == original
        assert "binary file" in capsys.readouterr().err

    def test_rejects_non_utf8_text_without_a_traceback_or_mutation(
        self,
        conflict_pick: _ConflictPickModule,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        path = tmp_path / "notes.txt"
        original = "<<<<<<< HEAD\ncafé\n=======\nthé\n>>>>>>> b\n".encode("latin-1")
        _ = path.write_bytes(original)
        assert conflict_pick.main([str(path), "--ours"]) == 1
        assert path.read_bytes() == original
        assert "not UTF-8 text" in capsys.readouterr().err
