"""CLI contract tests for the age-bench prepare/judge/scoreboard commands.

Spec: age-fanout-mechanics-benchmark.md, AC-6/AC-7/AC-8, curd/3.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
CASE_ID = "off-by-one-window-sum"

_DRIVER = (
    "from easy_cheese.skills.age_bench.commands import main;"
    "import sys;"
    "sys.exit(main(sys.argv[1:]))"
)


def _run_cli(args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, "PYTHONPATH": str(SRC)}
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, "-c", _DRIVER, *args],
        cwd=REPO_ROOT,
        env=full_env,
        capture_output=True,
        text=True,
    )


def test_prepare_seeds_an_isolated_worktree_and_prints_both_review_commands():
    result = _run_cli(["prepare", CASE_ID])

    assert result.returncode == 0, result.stderr
    assert "/age" in result.stdout
    assert "/code-review" in result.stdout

    worktree_line = next(
        line for line in result.stdout.splitlines() if line.startswith("worktree: ")
    )
    worktree_dir = Path(worktree_line.removeprefix("worktree: "))

    branch = subprocess.run(
        ["git", "-C", str(worktree_dir), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert branch == f"age-bench/{CASE_ID}"

    module_text = (worktree_dir / "module.py").read_text(encoding="utf-8")
    base_text = (REPO_ROOT / "benchmark" / "age" / "cases" / CASE_ID / "base" / "module.py").read_text(
        encoding="utf-8"
    )
    assert module_text != base_text


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

    result = _run_cli(
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


def test_judge_caps_recall_at_one_when_reviewer_reports_the_defect_multiple_times(tmp_path: Path) -> None:
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

    result = _run_cli(
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


def test_scoreboard_writes_per_overlap_area_table_under_the_corpus_root(tmp_path: Path) -> None:
    home = tmp_path / "cheese-home"
    env = {"EASY_CHEESE_HOME": str(home)}
    run_id = "run-42"

    from easy_cheese.shared.paths import project_corpus_root  # noqa: PLC0415

    os.environ["EASY_CHEESE_HOME"] = str(home)
    try:
        corpus_root = project_corpus_root()
    finally:
        del os.environ["EASY_CHEESE_HOME"]

    results_dir = corpus_root / "benchmark" / "age" / run_id / "results" / "age"
    results_dir.mkdir(parents=True)
    _ = (results_dir / f"{CASE_ID}.json").write_text(
        json.dumps({"recall": 1.0, "precision": 0.5, "snr": 1.0}), encoding="utf-8"
    )

    result = _run_cli(["scoreboard", run_id], env=env)

    assert result.returncode == 0, result.stderr
    scoreboard_path = Path(result.stdout.strip())
    assert scoreboard_path == corpus_root / "benchmark" / "age" / run_id / "scoreboard.md"
    assert scoreboard_path.is_file()
    assert ".cheese" not in scoreboard_path.parts

    table = scoreboard_path.read_text(encoding="utf-8")
    assert "off-by-one" in table
    assert CASE_ID in table
