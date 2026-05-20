"""Tests for skills/cook/scripts/self_eval_check.py — honesty-rule detector."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "skills" / "cook" / "scripts" / "self_eval_check.py"
SHARED_SCRIPTS = REPO_ROOT / "shared" / "scripts"


@pytest.fixture(scope="module")
def self_eval_check() -> ModuleType:
    # Mirror the script's path-insert so the in-process import of `cli` works.
    if str(SHARED_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SHARED_SCRIPTS))
    spec = importlib.util.spec_from_file_location("self_eval_check", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["self_eval_check"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# In-process detect_violations() — pure function, regex-shape coverage.
# ---------------------------------------------------------------------------


class TestDetectViolationsClean:
    def test_empty_report_returns_empty_list(self, self_eval_check: ModuleType) -> None:
        assert self_eval_check.detect_violations("") == []

    def test_clean_report_returns_empty_list(self, self_eval_check: ModuleType) -> None:
        report = (
            "## Cook Report — feature-x\n\n"
            "### Tests\n- pytest -q: pass\n\n"
            "### Self-eval\n- [x] Quality gates pass.\n"
        )
        assert self_eval_check.detect_violations(report) == []

    def test_skip_alone_without_green_claim_is_not_a_violation(
        self, self_eval_check: ModuleType
    ) -> None:
        # A skipped test honestly reported is allowed by the honesty rules —
        # only the combination of skip + green claim is a confirmation-bias cheat.
        report = "### Tests\n- pytest: 1 skipped (reason: needs network)\n"
        assert self_eval_check.detect_violations(report) == []

    def test_green_claim_alone_without_skip_is_not_a_violation(
        self, self_eval_check: ModuleType
    ) -> None:
        report = "### Tests\n- pytest: all tests pass\n"
        assert self_eval_check.detect_violations(report) == []


class TestSkippedClaimedPass:
    def test_skipped_with_green_claim_flags(self, self_eval_check: ModuleType) -> None:
        report = (
            "### Tests\n"
            "- pytest -q: all tests pass\n"
            "- one test was skipped due to flaky network\n"
        )
        violations = self_eval_check.detect_violations(report)
        kinds = [v["kind"] for v in violations]
        assert "skipped-claimed-pass" in kinds

    def test_pytest_mark_skip_with_green_flags(self, self_eval_check: ModuleType) -> None:
        report = (
            "### Tests\n"
            "- @pytest.mark.skip on test_x for env reasons\n"
            "- otherwise all green\n"
        )
        violations = self_eval_check.detect_violations(report)
        assert any(v["kind"] == "skipped-claimed-pass" for v in violations)

    def test_violation_carries_line_and_snippet(self, self_eval_check: ModuleType) -> None:
        report = (
            "line one\n"
            "all tests pass\n"
            "but one was skipped silently\n"
        )
        violations = self_eval_check.detect_violations(report)
        skipped = [v for v in violations if v["kind"] == "skipped-claimed-pass"]
        assert len(skipped) == 1
        # The skip marker is on line 3 ("but one was skipped silently").
        assert skipped[0]["line"] == 3
        assert "skipped" in skipped[0]["snippet"].lower()

    def test_case_insensitive(self, self_eval_check: ModuleType) -> None:
        report = "All Tests Pass\nSomething was SKIPPED\n"
        violations = self_eval_check.detect_violations(report)
        assert any(v["kind"] == "skipped-claimed-pass" for v in violations)


class TestUnverifiedClaim:
    def test_should_work_flags(self, self_eval_check: ModuleType) -> None:
        report = "The retry path should work for transient errors.\n"
        violations = self_eval_check.detect_violations(report)
        assert [v["kind"] for v in violations] == ["unverified-claim"]

    def test_probably_flags(self, self_eval_check: ModuleType) -> None:
        report = "The handler probably catches the timeout.\n"
        violations = self_eval_check.detect_violations(report)
        assert [v["kind"] for v in violations] == ["unverified-claim"]

    def test_i_think_flags(self, self_eval_check: ModuleType) -> None:
        report = "I think the parser handles UTF-16 too.\n"
        violations = self_eval_check.detect_violations(report)
        assert [v["kind"] for v in violations] == ["unverified-claim"]

    def test_unverified_claim_carries_snippet(self, self_eval_check: ModuleType) -> None:
        report = "header\nThe retry logic should work in prod.\n"
        violations = self_eval_check.detect_violations(report)
        assert violations[0]["line"] == 2
        assert "should work" in violations[0]["snippet"].lower()


class TestScopeCreep:
    def test_while_i_was_there_flags(self, self_eval_check: ModuleType) -> None:
        report = "While I was there I tidied the imports.\n"
        violations = self_eval_check.detect_violations(report)
        assert [v["kind"] for v in violations] == ["scope-creep"]

    def test_also_fixed_flags(self, self_eval_check: ModuleType) -> None:
        report = "Also fixed an unrelated typo in README.\n"
        violations = self_eval_check.detect_violations(report)
        assert [v["kind"] for v in violations] == ["scope-creep"]

    def test_also_updated_flags(self, self_eval_check: ModuleType) -> None:
        report = "Also updated the changelog while in the area.\n"
        violations = self_eval_check.detect_violations(report)
        assert [v["kind"] for v in violations] == ["scope-creep"]

    def test_additionally_flags(self, self_eval_check: ModuleType) -> None:
        report = "Additionally, I removed a dead import.\n"
        violations = self_eval_check.detect_violations(report)
        assert [v["kind"] for v in violations] == ["scope-creep"]


class TestMixedViolations:
    def test_all_three_kinds_in_one_report(self, self_eval_check: ModuleType) -> None:
        report = (
            "## Cook Report\n"
            "All tests pass after the rewrite.\n"
            "One slow test was skipped for now.\n"
            "The retry path should work in prod.\n"
            "Also fixed a typo while I was in there.\n"
        )
        violations = self_eval_check.detect_violations(report)
        kinds = {v["kind"] for v in violations}
        assert kinds == {"skipped-claimed-pass", "unverified-claim", "scope-creep"}

    def test_results_sorted_by_line(self, self_eval_check: ModuleType) -> None:
        report = (
            "Additionally, X.\n"  # line 1: scope-creep
            "I think Y.\n"  # line 2: unverified-claim
        )
        violations = self_eval_check.detect_violations(report)
        lines = [v["line"] for v in violations]
        assert lines == sorted(lines)


# ---------------------------------------------------------------------------
# CLI subprocess — exit codes, JSON shape, missing file behavior.
# ---------------------------------------------------------------------------


def _run_cli(report_path: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--report", str(report_path), *extra],
        capture_output=True,
        text=True,
    )


class TestCliCleanReport:
    def test_clean_report_exits_zero(self, tmp_path: Path) -> None:
        report = tmp_path / "clean.md"
        report.write_text("## Cook Report\nAll quality gates pass.\n", encoding="utf-8")
        result = _run_cli(report)
        assert result.returncode == 0

    def test_clean_report_emits_empty_json_list(self, tmp_path: Path) -> None:
        report = tmp_path / "clean.md"
        report.write_text("## Cook Report\nclean.\n", encoding="utf-8")
        result = _run_cli(report)
        assert json.loads(result.stdout) == []


class TestCliDirtyReport:
    def test_dirty_report_exits_one(self, tmp_path: Path) -> None:
        report = tmp_path / "dirty.md"
        report.write_text(
            "## Cook Report\n"
            "all tests pass after the rewrite\n"
            "one test was skipped for now\n",
            encoding="utf-8",
        )
        result = _run_cli(report)
        assert result.returncode == 1

    def test_dirty_report_emits_violation_entries(self, tmp_path: Path) -> None:
        report = tmp_path / "dirty.md"
        report.write_text(
            "## Cook Report\n"
            "all tests pass after the rewrite\n"
            "one test was skipped for now\n",
            encoding="utf-8",
        )
        result = _run_cli(report)
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert len(payload) >= 1
        assert payload[0]["kind"] == "skipped-claimed-pass"
        assert "line" in payload[0]
        assert "snippet" in payload[0]

    def test_acceptance_criterion_fixture(self, tmp_path: Path) -> None:
        # Verbatim from the curd's acceptance criterion: "all tests pass" + a
        # skipped block must emit a skipped-claimed-pass entry.
        report = tmp_path / "report.md"
        report.write_text(
            "### Tests\n"
            "- pytest: all tests pass\n"
            "- @pytest.mark.skip(reason='flaky network') on test_retry\n",
            encoding="utf-8",
        )
        result = _run_cli(report)
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        kinds = [entry["kind"] for entry in payload]
        assert "skipped-claimed-pass" in kinds


class TestCliJsonFlag:
    def test_json_flag_emits_parseable_json(self, tmp_path: Path) -> None:
        report = tmp_path / "r.md"
        report.write_text("I think this is fine.\n", encoding="utf-8")
        result = _run_cli(report, "--json")
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
        assert payload[0]["kind"] == "unverified-claim"


class TestCliMissingFile:
    def test_missing_file_exits_two(self, tmp_path: Path) -> None:
        missing = tmp_path / "does-not-exist.md"
        result = _run_cli(missing)
        # cli.CliError is mapped to exit code 2 by cli.run.
        assert result.returncode == 2

    def test_missing_file_writes_error_to_stderr(self, tmp_path: Path) -> None:
        missing = tmp_path / "nope.md"
        result = _run_cli(missing)
        assert "report not found" in result.stderr
        assert "nope.md" in result.stderr
        # JSON list must not be emitted on the error path.
        assert result.stdout == ""

    def test_directory_path_treated_as_missing(self, tmp_path: Path) -> None:
        # Path exists but is not a regular file; this still fails the is_file gate.
        result = _run_cli(tmp_path)
        assert result.returncode == 2
        assert "report not found" in result.stderr
