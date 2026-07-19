"""Tests for shared/scripts/spec_match.py + spec_match_cli.py.

Covers the design contract from issue #267: ranking order, the 'high' tier
boundary (score + margin), and the 'weak' fallback -- plus the CLI's
front-matter/heading extraction and its rank subcommand end-to-end.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_MATCH_CLI = REPO_ROOT / "shared" / "scripts" / "spec_match_cli.py"


def _candidate(path: str, slug: str = "", title: str = "", first_heading: str = "") -> dict:
    return {"path": path, "slug": slug, "title": title, "first_heading": first_heading}


class TestScoreCandidatesRanking:
    def test_ranks_best_match_first(self, spec_match: ModuleType) -> None:
        candidates = [
            _candidate("a.md", slug="unrelated-topic"),
            _candidate("b.md", slug="retry-logic-for-uploads"),
            _candidate("c.md", slug="cheese-flavor-picker"),
        ]
        results = spec_match.score_candidates("add retry logic for uploads", candidates)
        assert [r["path"] for r in results] == ["b.md", "a.md", "c.md"]
        assert results[0]["score"] >= results[1]["score"] >= results[2]["score"]

    def test_result_shape(self, spec_match: ModuleType) -> None:
        results = spec_match.score_candidates(
            "add retry logic", [_candidate("only.md", slug="add retry logic")]
        )
        assert results == [{"path": "only.md", "score": 1.0, "tier": "high"}]

    def test_empty_candidates_returns_empty(self, spec_match: ModuleType) -> None:
        assert spec_match.score_candidates("anything", []) == []

    def test_scores_max_across_fields(self, spec_match: ModuleType) -> None:
        # slug/title are noise; first_heading is the real match.
        candidate = _candidate(
            "x.md",
            slug="zzz",
            title="zzz",
            first_heading="add retry logic for uploads",
        )
        results = spec_match.score_candidates("add retry logic for uploads", [candidate])
        assert results[0]["score"] == 1.0


class TestHighTierBoundary:
    def test_high_when_score_and_margin_both_clear(self, spec_match: ModuleType) -> None:
        candidates = [
            _candidate("strong.md", slug="add retry logic for uploads"),
            _candidate("weak.md", slug="zzz completely unrelated qqq"),
        ]
        results = spec_match.score_candidates("add retry logic for uploads", candidates)
        assert results[0]["score"] >= spec_match.HIGH_SCORE_THRESHOLD
        assert results[0]["score"] - results[1]["score"] >= spec_match.HIGH_MARGIN_THRESHOLD
        assert results[0]["tier"] == "high"
        assert results[1]["tier"] == "weak"

    def test_weak_when_score_below_threshold(self, spec_match: ModuleType) -> None:
        candidates = [_candidate("only.md", slug="totally different subject matter")]
        results = spec_match.score_candidates("add retry logic", candidates)
        assert results[0]["score"] < spec_match.HIGH_SCORE_THRESHOLD
        assert results[0]["tier"] == "weak"

    def test_weak_when_margin_too_small_despite_high_score(
        self, spec_match: ModuleType
    ) -> None:
        # Two near-duplicate slugs: top score clears the threshold but the
        # runner-up is close enough that reuse would be ambiguous.
        candidates = [
            _candidate("a.md", slug="add-retry-logic-for-uploads"),
            _candidate("b.md", slug="add-retry-logic-for-downloads"),
        ]
        results = spec_match.score_candidates("add retry logic for uploads", candidates)
        assert results[0]["score"] >= spec_match.HIGH_SCORE_THRESHOLD
        assert results[0]["score"] - results[1]["score"] < spec_match.HIGH_MARGIN_THRESHOLD
        assert results[0]["tier"] == "weak"
        assert results[1]["tier"] == "weak"

    def test_high_when_score_exactly_at_threshold(self, spec_match: ModuleType) -> None:
        # SequenceMatcher.ratio() = 2*M/T is exact here: "abc" vs "abcdefg"
        # shares a 3-char prefix out of a total length 10 -> ratio == 0.60
        # exactly. A regression from >= to > on the score check would flip
        # this candidate from 'high' to 'weak'.
        candidates = [
            _candidate("top.md", slug="abcdefg"),
            _candidate("other.md", slug="zzzzzzzzzzzzzzzzzzzz"),
        ]
        results = spec_match.score_candidates("abc", candidates)
        assert results[0]["score"] == spec_match.HIGH_SCORE_THRESHOLD
        assert results[0]["tier"] == "high"

    def test_high_when_margin_at_smallest_achievable_value(
        self, spec_match: ModuleType
    ) -> None:
        # req "xxx" vs "xxxyy" (3 matching x's, len 5): ratio = 2*3/8 = 0.75,
        # clearing HIGH_SCORE_THRESHOLD. vs "xxxyyyy" (3 matching x's, len 7):
        # ratio = 2*3/10 = 0.60. Margin is 0.75 - 0.60 == 0.15000000000000002,
        # the smallest margin >= HIGH_MARGIN_THRESHOLD reachable through this
        # string API (an exact-0.15 margin is unreachable, so this does not
        # distinguish >= from > on the margin check -- it pins the boundary
        # from the achievable side).
        candidates = [
            _candidate("top.md", slug="xxxyy"),
            _candidate("other.md", slug="xxxyyyy"),
        ]
        results = spec_match.score_candidates("xxx", candidates)
        assert results[0]["score"] >= spec_match.HIGH_SCORE_THRESHOLD
        assert results[0]["score"] - results[1]["score"] >= spec_match.HIGH_MARGIN_THRESHOLD
        assert results[0]["tier"] == "high"

    def test_weak_when_margin_just_below_threshold(self, spec_match: ModuleType) -> None:
        # req "xxx" vs "xxxyyy" (3 matching x's, len 6): ratio = 2*3/9 ==
        # 0.6666..., clearing HIGH_SCORE_THRESHOLD. vs "xxxyyyyy" (3 matching
        # x's, len 8): ratio = 2*3/11 == 0.5454..., margin == 0.1212...,
        # clearly below HIGH_MARGIN_THRESHOLD despite the top score clearing
        # HIGH_SCORE_THRESHOLD -- the margin gate alone drops it to 'weak'.
        candidates = [
            _candidate("top.md", slug="xxxyyy"),
            _candidate("other.md", slug="xxxyyyyy"),
        ]
        results = spec_match.score_candidates("xxx", candidates)
        assert results[0]["score"] >= spec_match.HIGH_SCORE_THRESHOLD
        assert results[0]["score"] - results[1]["score"] < spec_match.HIGH_MARGIN_THRESHOLD
        assert results[0]["tier"] == "weak"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SPEC_MATCH_CLI), *args],
        capture_output=True,
        text=True,
    )


def _write_spec(tmp_path: Path, filename: str, slug: str, title: str, first_body_line: str) -> None:
    (tmp_path / filename).write_text(
        f"---\nslug: {slug}\nsource: test\n---\n\n# {title}\n\n## Contract\n\n{first_body_line}\n"
    )


class TestRankCli:
    def test_missing_dir_emits_empty_list(self, tmp_path: Path) -> None:
        result = _run_cli("rank", "--request", "add retry", "--dir", str(tmp_path / "nope"))
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout) == []

    def test_empty_request_errors(self, tmp_path: Path) -> None:
        result = _run_cli("rank", "--request", "", "--dir", str(tmp_path))
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_ranks_specs_from_front_matter_and_headings(self, tmp_path: Path) -> None:
        _write_spec(
            tmp_path,
            "retry-uploads.md",
            slug="retry-uploads",
            title="Retry uploads",
            first_body_line="Add retry logic for flaky uploads.",
        )
        _write_spec(
            tmp_path,
            "cheese-flavors.md",
            slug="cheese-flavors",
            title="Cheese flavor picker",
            first_body_line="Let users pick a cheese flavor.",
        )
        result = _run_cli("rank", "--request", "add retry logic for flaky uploads", "--dir", str(tmp_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload[0]["path"] == str(tmp_path / "retry-uploads.md")
        assert payload[0]["tier"] == "high"
        assert payload[1]["path"] == str(tmp_path / "cheese-flavors.md")

    def test_falls_back_to_filename_stem_without_front_matter(self, tmp_path: Path) -> None:
        (tmp_path / "no-front-matter.md").write_text("# Some title\n\n## Section\n\nbody text\n")
        result = _run_cli("rank", "--request", "some title", "--dir", str(tmp_path))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload[0]["path"] == str(tmp_path / "no-front-matter.md")


class TestModuleImports:
    def test_loads_via_importlib(self, spec_match_cli_mod: ModuleType) -> None:
        assert callable(spec_match_cli_mod._cmd_rank)
        assert callable(spec_match_cli_mod._build_candidate)
