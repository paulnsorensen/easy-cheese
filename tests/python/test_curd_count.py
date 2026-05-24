"""Tests for src/mold/curd-count.py.

Covers section extraction, bullet counting, the recommendation decision rule,
the full analyze() digest, and the CLI entry point. Pure functions plus a
synthetic spec on disk; no real specs touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType

import pytest

SPEC_LARGE = """\
---
slug: ignored-by-stem
---

# Big spec

## Problem
Many things.

## Goals
- Add A
- Add B
- Add C
- Add D
- Add E
- Add F
- Add G

## Approach
Hexagonal-ish.

## Decisions
- Use JWT — less server state
- Postgres — already in stack

## Quality gates
- `pytest tests/a`: green
- `pytest tests/b`: green
- `pytest tests/c`: green
"""

SPEC_SMALL = """\
---
slug: ignored
---

# Small spec

## Goals
- Fix the bug

## Quality gates
- `pytest tests/auth`: green
"""

SPEC_EMPTY = """\
# Spec with no goals or gates

## Problem
Nothing actionable yet.
"""


class TestExtractSection:
    def test_returns_none_when_heading_missing(self, curd_count: ModuleType) -> None:
        assert curd_count._extract_section("# title\n", {"goals"}) is None

    def test_matches_exact_heading(self, curd_count: ModuleType) -> None:
        body = "## Goals\n- one\n- two\n"
        section = curd_count._extract_section(body, {"goals"})
        assert section is not None
        assert "- one" in section
        assert "- two" in section

    def test_case_insensitive(self, curd_count: ModuleType) -> None:
        body = "## GOALS\n- one\n"
        assert curd_count._extract_section(body, {"goals"}) is not None

    def test_alias_matching(self, curd_count: ModuleType) -> None:
        body = "## Acceptance criteria\n- one\n"
        section = curd_count._extract_section(
            body,
            {"quality gates", "acceptance criteria"},
        )
        assert section is not None
        assert "- one" in section

    def test_stops_at_next_h2_heading(self, curd_count: ModuleType) -> None:
        body = "## Goals\n- one\n- two\n\n## Approach\n- skip me\n"
        section = curd_count._extract_section(body, {"goals"})
        assert section is not None
        assert "- one" in section
        assert "- skip me" not in section

    def test_last_section_extends_to_end(self, curd_count: ModuleType) -> None:
        body = "## Approach\nstuff\n\n## Goals\n- final\n"
        section = curd_count._extract_section(body, {"goals"})
        assert section is not None
        assert "- final" in section


class TestCountBullets:
    def test_none_returns_zero(self, curd_count: ModuleType) -> None:
        assert curd_count._count_bullets(None) == 0

    def test_empty_returns_zero(self, curd_count: ModuleType) -> None:
        assert curd_count._count_bullets("") == 0

    def test_counts_dash_bullets(self, curd_count: ModuleType) -> None:
        assert curd_count._count_bullets("- a\n- b\n- c\n") == 3

    def test_counts_asterisk_and_plus_bullets(self, curd_count: ModuleType) -> None:
        assert curd_count._count_bullets("* a\n+ b\n") == 2

    def test_ignores_non_bullet_lines(self, curd_count: ModuleType) -> None:
        assert curd_count._count_bullets("preamble\n- one\nmore prose\n- two\n") == 2

    def test_counts_indented_bullets(self, curd_count: ModuleType) -> None:
        assert curd_count._count_bullets("  - nested\n    - deeper\n") == 2

    def test_ignores_bare_dash_separator(self, curd_count: ModuleType) -> None:
        # The bullet regex requires a non-whitespace char after the marker,
        # so "---" and "-" alone shouldn't count.
        assert curd_count._count_bullets("---\n-\n") == 0


class TestRecommend:
    def test_threshold_picks_cheese_factory(self, curd_count: ModuleType) -> None:
        skill, rationale = curd_count._recommend(5, "high")
        assert skill == "/cheese-factory"
        assert "5" in rationale

    def test_above_threshold_picks_cheese_factory(self, curd_count: ModuleType) -> None:
        skill, _ = curd_count._recommend(12, "low")
        assert skill == "/cheese-factory"

    def test_below_threshold_high_blast_picks_ultracook(
        self, curd_count: ModuleType
    ) -> None:
        skill, rationale = curd_count._recommend(4, "high")
        assert skill == "/ultracook"
        assert "high" in rationale

    def test_below_threshold_medium_blast_picks_cook(
        self, curd_count: ModuleType
    ) -> None:
        skill, _ = curd_count._recommend(3, "medium")
        assert skill == "/cook"

    def test_below_threshold_low_blast_picks_cook(self, curd_count: ModuleType) -> None:
        skill, _ = curd_count._recommend(1, "low")
        assert skill == "/cook"

    def test_below_threshold_unknown_blast_picks_cook(
        self, curd_count: ModuleType
    ) -> None:
        skill, rationale = curd_count._recommend(2, None)
        assert skill == "/cook"
        assert "unknown" in rationale

    def test_blast_radius_case_insensitive(self, curd_count: ModuleType) -> None:
        skill, _ = curd_count._recommend(3, "HIGH")
        assert skill == "/ultracook"


class TestAnalyze:
    def _write(self, tmp_path: Path, name: str, body: str) -> Path:
        path = tmp_path / name
        path.write_text(body)
        return path

    def test_decomposable_spec_recommends_cheese_factory(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "big.md", SPEC_LARGE)
        digest = curd_count.analyze(spec, "high")
        assert digest["candidate_curds"] == 7
        assert digest["decomposable"] is True
        assert digest["recommended_skill"] == "/cheese-factory"

    def test_small_spec_high_blast_recommends_ultracook(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "small.md", SPEC_SMALL)
        digest = curd_count.analyze(spec, "high")
        assert digest["candidate_curds"] == 1
        assert digest["decomposable"] is False
        assert digest["recommended_skill"] == "/ultracook"

    def test_small_spec_low_blast_recommends_cook(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "small.md", SPEC_SMALL)
        digest = curd_count.analyze(spec, "low")
        assert digest["recommended_skill"] == "/cook"

    def test_small_spec_no_blast_radius_recommends_cook(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "small.md", SPEC_SMALL)
        digest = curd_count.analyze(spec, None)
        assert digest["recommended_skill"] == "/cook"

    def test_candidate_curds_is_max_of_goals_and_gates(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        # SPEC_LARGE has 7 goals + 3 gates; max is 7.
        spec = self._write(tmp_path, "big.md", SPEC_LARGE)
        digest = curd_count.analyze(spec, "high")
        assert digest["signals"]["goals"] == 7
        assert digest["signals"]["quality_gates"] == 3
        assert digest["candidate_curds"] == 7

    def test_decisions_counted_but_not_used(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "big.md", SPEC_LARGE)
        digest = curd_count.analyze(spec, "high")
        assert digest["signals"]["decisions"] == 2

    def test_empty_spec_yields_zero_candidates(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "empty.md", SPEC_EMPTY)
        digest = curd_count.analyze(spec, "high")
        assert digest["candidate_curds"] == 0
        assert digest["decomposable"] is False
        assert digest["recommended_skill"] == "/ultracook"

    def test_slug_extracted_from_filename(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "my-feature-slug.md", SPEC_SMALL)
        digest = curd_count.analyze(spec, "low")
        assert digest["slug"] == "my-feature-slug"

    def test_digest_has_all_expected_keys(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "small.md", SPEC_SMALL)
        digest = curd_count.analyze(spec, "low")
        expected = {
            "spec_path",
            "slug",
            "blast_radius",
            "candidate_curds",
            "signals",
            "threshold",
            "decomposable",
            "recommended_skill",
            "rationale",
            "notes",
        }
        assert expected <= set(digest.keys())

    def test_threshold_field_matches_constant(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "small.md", SPEC_SMALL)
        digest = curd_count.analyze(spec, "low")
        assert digest["threshold"] == curd_count.CURD_THRESHOLD

    def test_notes_warn_about_independence(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = self._write(tmp_path, "small.md", SPEC_SMALL)
        digest = curd_count.analyze(spec, "low")
        joined = " ".join(digest["notes"])
        assert "criterion 4" in joined
        assert "signal" in joined or "verdict" in joined


class TestMain:
    def test_missing_file_exits_with_2(
        self, curd_count: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = curd_count.main([str(tmp_path / "nope.md")])
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "not found" in err

    def test_directory_exits_with_2(
        self, curd_count: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = curd_count.main([str(tmp_path)])
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "not a file" in err

    def test_valid_file_returns_0_and_emits_json(
        self, curd_count: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        spec = tmp_path / "small.md"
        spec.write_text(SPEC_SMALL)
        exit_code = curd_count.main([str(spec), "--blast-radius", "high"])
        assert exit_code == 0
        out = capsys.readouterr().out
        digest = json.loads(out)
        assert digest["recommended_skill"] == "/ultracook"
        assert digest["blast_radius"] == "high"

    def test_no_blast_radius_arg_still_works(
        self, curd_count: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        spec = tmp_path / "small.md"
        spec.write_text(SPEC_SMALL)
        exit_code = curd_count.main([str(spec)])
        assert exit_code == 0
        digest = json.loads(capsys.readouterr().out)
        assert digest["blast_radius"] is None
        assert digest["recommended_skill"] == "/cook"

    def test_invalid_blast_radius_rejected_by_argparse(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = tmp_path / "small.md"
        spec.write_text(SPEC_SMALL)
        with pytest.raises(SystemExit):
            curd_count.main([str(spec), "--blast-radius", "extreme"])

    def test_emits_trailing_newline(
        self, curd_count: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        spec = tmp_path / "small.md"
        spec.write_text(SPEC_SMALL)
        curd_count.main([str(spec)])
        out = capsys.readouterr().out
        assert out.endswith("\n")


class TestSpecReadError:
    def test_analyze_raises_on_non_utf8(
        self, curd_count: ModuleType, tmp_path: Path
    ) -> None:
        spec = tmp_path / "bad-encoding.md"
        # latin-1-only bytes that are invalid UTF-8 start sequences
        spec.write_bytes(b"## Goals\n- bad byte: \xff\n")
        with pytest.raises(curd_count.SpecReadError) as exc_info:
            curd_count.analyze(spec, "low")
        assert "UTF-8" in str(exc_info.value)

    def test_main_returns_2_on_non_utf8(
        self, curd_count: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        spec = tmp_path / "bad-encoding.md"
        spec.write_bytes(b"## Goals\n- bad byte: \xff\n")
        exit_code = curd_count.main([str(spec)])
        assert exit_code == 2
        err = capsys.readouterr().err
        assert "UTF-8" in err
        # Stack trace must not leak — only the clean error line.
        assert "Traceback" not in err

    def test_specreaderror_is_exception_subclass(self, curd_count: ModuleType) -> None:
        # Importable as a public type so callers can catch it specifically.
        assert issubclass(curd_count.SpecReadError, Exception)
