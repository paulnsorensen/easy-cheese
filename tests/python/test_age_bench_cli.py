"""CLI contract tests for the age-bench prepare/judge/scoreboard commands.

Spec: age-fanout-mechanics-benchmark.md, AC-6/AC-7/AC-8, curd/3.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from easy_cheese.shared.paths import project_corpus_root

from _age_bench_helpers import REPO_ROOT, run_cli  # pyright: ignore[reportImplicitRelativeImport]

CASE_ID = "off-by-one-window-sum"


@pytest.fixture
def _cleanup_scratch_dirs() -> Iterator[list[Path]]:  # pyright: ignore[reportUnusedFunction]
    scratch_dirs: list[Path] = []
    yield scratch_dirs
    for scratch_dir in scratch_dirs:
        shutil.rmtree(scratch_dir, ignore_errors=True)


def test_prepare_seeds_an_isolated_worktree_and_prints_both_review_commands(
    _cleanup_scratch_dirs: list[Path],
) -> None:
    result = run_cli(["prepare", CASE_ID])

    assert result.returncode == 0, result.stderr
    assert "/age" in result.stdout
    assert "/code-review" in result.stdout

    worktree_line = next(
        line for line in result.stdout.splitlines() if line.startswith("worktree: ")
    )
    worktree_dir = Path(worktree_line.removeprefix("worktree: "))

    scratch_line = next(
        line for line in result.stdout.splitlines() if line.startswith("scratch: ")
    )
    _cleanup_scratch_dirs.append(Path(scratch_line.removeprefix("scratch: ")))

    branch = subprocess.run(
        ["git", "-C", str(worktree_dir), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert branch == f"age-bench/{CASE_ID}"

    module_text = (worktree_dir / "module.py").read_text(encoding="utf-8")
    with (REPO_ROOT / "benchmark" / "age" / "cases" / CASE_ID / "case.toml").open(
        "rb"
    ) as handle:
        case_toml = tomllib.load(handle)
    defect_line = cast(int, case_toml["defect"]["line"])

    assert "range(start, len(values) - 1)" in module_text
    assert "range(start, len(values) - 1)" in module_text.splitlines()[defect_line - 1]


def test_judge_buckets_findings_and_emits_recall_precision_snr(tmp_path: Path) -> None:
    report_path = tmp_path / "report.md"
    _ = report_path.write_text(
        "## Blocker\n"
        + "- **[off-by-one:blocker]** `module.py:5` "
        + "— Loop upper bound excludes the last element, dropping it from the sum.\n"
        + "## Low\n"
        + "- **[style:low]** `module.py:12` — Variable name could be clearer.\n",
        encoding="utf-8",
    )
    fixture_path = tmp_path / "transport.json"
    _ = fixture_path.write_text(json.dumps(["Bug Hit", "Noise"]), encoding="utf-8")

    result = run_cli(
        [
            "judge",
            "--tool",
            "age",
            "--case",
            CASE_ID,
            "--report",
            str(report_path),
            "--transport-fixture",
            str(fixture_path),
        ]
    )

    assert result.returncode == 0, result.stderr
    payload = cast("dict[str, object]", json.loads(result.stdout))
    assert payload["buckets"] == ["Bug Hit", "Noise"]
    assert payload["hits"] == 1
    assert payload["noise"] == 1
    assert payload["recall"] == 1.0
    assert payload["precision"] == 0.5
    assert payload["snr"] == 1.0


def test_judge_caps_recall_at_one_when_reviewer_reports_the_defect_multiple_times(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "report.md"
    _ = report_path.write_text(
        "## Blocker\n"
        + "- **[off-by-one:blocker]** `module.py:5` "
        + "— Loop upper bound excludes the last element, dropping it from the sum.\n"
        + "## High\n"
        + "- **[off-by-one:high]** `module.py:5` "
        + "— Same defect flagged again from the range check angle.\n",
        encoding="utf-8",
    )
    fixture_path = tmp_path / "transport.json"
    _ = fixture_path.write_text(json.dumps(["Bug Hit", "Bug Hit"]), encoding="utf-8")

    result = run_cli(
        [
            "judge",
            "--tool",
            "age",
            "--case",
            CASE_ID,
            "--report",
            str(report_path),
            "--transport-fixture",
            str(fixture_path),
        ]
    )

    assert result.returncode == 0, result.stderr
    payload = cast("dict[str, object]", json.loads(result.stdout))
    assert payload["hits"] == 2
    assert payload["recall"] == 1.0


def test_judge_rejects_a_transport_response_naming_multiple_buckets(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "report.md"
    _ = report_path.write_text(
        "## High\n"
        + "- **[correctness:high]** `module.py:5` — The loop drops the final element.\n",
        encoding="utf-8",
    )
    fixture_path = tmp_path / "transport.json"
    _ = fixture_path.write_text(json.dumps(["Noise, not Bug Hit"]), encoding="utf-8")

    result = run_cli(
        [
            "judge",
            "--tool",
            "age",
            "--case",
            CASE_ID,
            "--report",
            str(report_path),
            "--transport-fixture",
            str(fixture_path),
        ]
    )

    assert result.returncode != 0
    assert "did not name a bucket" in result.stderr


def test_scoreboard_writes_per_overlap_area_table_under_the_corpus_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "cheese-home"
    env = {"EASY_CHEESE_HOME": str(home)}
    run_id = "run-42"

    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    corpus_root = project_corpus_root()

    results_dir = corpus_root / "benchmark" / "age" / run_id / "results" / "age"
    results_dir.mkdir(parents=True)
    _ = (results_dir / f"{CASE_ID}.json").write_text(
        json.dumps({"recall": 1.0, "precision": 0.5, "snr": 1.0}), encoding="utf-8"
    )

    result = run_cli(["scoreboard", run_id], env=env)

    assert result.returncode == 0, result.stderr
    scoreboard_path = Path(result.stdout.strip())
    assert (
        scoreboard_path == corpus_root / "benchmark" / "age" / run_id / "scoreboard.md"
    )
    assert scoreboard_path.is_file()
    assert ".cheese" not in scoreboard_path.parts

    table = scoreboard_path.read_text(encoding="utf-8")
    assert "off-by-one" in table
    assert CASE_ID in table
