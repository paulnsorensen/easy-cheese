"""Offline checks for the pinned tilth benchmark runner contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest

from agent_lab_tilth import (
    DEFAULT_EROSION_RATIO,
    EROSION_GUARD,
    REQUIRED_SKILL,
    RUNNER_ERROR_GUARD,
    RunnerError,
    TilthRunner,
    evaluate_tilth,
    score_row,
)


FAKE_RUN = '''#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--modes-json", required=True)
parser.add_argument("--tasks-json", required=True)
parser.add_argument("--models", required=True)
parser.add_argument("--reps", type=int, default=1)
parser.add_argument("--output", required=True)
parser.add_argument("--bare", action="store_true")
parser.add_argument("--max-cells", type=int, default=100)
parser.add_argument("--max-usd", type=float, required=True)
parser.add_argument("--max-budget-usd", type=float, required=True)
parser.add_argument("--cell-estimate-usd", type=float, required=True)
args = parser.parse_args()

control = json.loads(Path(os.environ["FAKE_RUN_CONTROL"]).read_text())
tasks = json.loads(Path(args.tasks_json).read_text())
assert tasks["version"] == 1
task_ids = [task["id"] for task in tasks["tasks"]]
raw_modes = json.loads(Path(args.modes_json).read_text())
assert len(raw_modes) == 1
mode = raw_modes[0]
assert "mcp_config_path" not in mode
assert Path(mode["plugin_dir"]).is_absolute()
assert mode["description"]
assert args.max_usd == len(task_ids) * args.max_budget_usd
assert args.cell_estimate_usd == args.max_budget_usd
log_entry = {
    "modes": raw_modes,
    "tasks": task_ids,
    "models": args.models,
    "max_cells": args.max_cells,
    "max_usd": args.max_usd,
    "max_budget_usd": args.max_budget_usd,
}
with Path(control["log"]).open("a") as handle:
    handle.write(json.dumps(log_entry) + "\\n")

rows_by_task = control["rows_by_task"]
lines = []
for task_id in task_ids:
    row = dict(rows_by_task[task_id])
    row.setdefault("task", task_id)
    row.setdefault("model", args.models)
    lines.append(json.dumps(row))
Path(args.output).write_text("\\n".join(lines) + "\\n")
if control.get("exit_code"):
    sys.exit(control["exit_code"])
'''


class FakeRun:
    """A scripted `benchmark/run.py` plus the invocation log it writes."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, rows_by_task: dict[str, dict[str, object]], exit_code: int = 0) -> None:
        self.tilth_root: Path = tmp_path / "tilth"
        benchmark_dir = self.tilth_root / "benchmark"
        benchmark_dir.mkdir(parents=True)
        _ = (benchmark_dir / "run.py").write_text(FAKE_RUN, encoding="utf-8")
        self.rows_by_task: dict[str, dict[str, object]] = rows_by_task
        self.log: Path = tmp_path / "run_calls.jsonl"
        control = tmp_path / "run_control.json"
        _ = control.write_text(
            json.dumps({"log": str(self.log), "rows_by_task": rows_by_task, "exit_code": exit_code}),
            encoding="utf-8",
        )
        monkeypatch.setenv("FAKE_RUN_CONTROL", str(control))

    def runner(self) -> TilthRunner:
        return TilthRunner(tilth_root=self.tilth_root, python_bin=sys.executable)

    def calls(self) -> list[dict[str, object]]:
        if not self.log.exists():
            return []
        return [cast(dict[str, object], json.loads(line)) for line in self.log.read_text().splitlines() if line]


def _row(*, correct: bool = True, input_tokens: int = 10, output_tokens: int = 5, **extra: object) -> dict[str, object]:
    row: dict[str, object] = {
        "correct": correct,
        "error": "",
        "model_alias": "haiku",
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "total_cost_usd": 0.01,
        "skills": [REQUIRED_SKILL],
        "workspace_diff_lines": 4,
        "reference_changed_lines": 4,
        "lint_ok": True,
    }
    row.update(extra)
    return row


def test_ac1_mode_carries_plugin_dir_and_append_and_aggregate_comes_from_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRun(tmp_path, monkeypatch, rows_by_task={"t1": _row(correct=True), "t2": _row(correct=False)})
    overlay = tmp_path / "overlay"
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": task_id} for task_id in fake.rows_by_task]}), encoding="utf-8")
    result = evaluate_tilth(
        runner=fake.runner(),
        overlay_dir=overlay,
        tasks_path=tasks_path,
        task_ids=["t1", "t2"],
        model="haiku",
        output_path=tmp_path / "rows.jsonl",
    )
    # Aggregate is the mean of the scored rows themselves, not a local re-grade.
    assert result["aggregate_score"] == 0.5
    call = fake.calls()[0]
    mode = cast(list[dict[str, object]], call["modes"])[0]
    assert mode["plugin_dir"] == str(overlay.resolve())
    assert mode["prompt_mode"] == "append"
    assert mode["description"]
    assert call["models"] == "haiku"
    assert call["tasks"] == ["t1", "t2"]


def test_row_score_marks_missing_skill_and_error_as_runner_error_guards(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRun(
        tmp_path,
        monkeypatch,
        rows_by_task={
            "t1": _row(correct=True, skills=[]),
            "t2": _row(correct=True, error="agent crashed"),
        },
    )
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": task_id} for task_id in fake.rows_by_task]}), encoding="utf-8")
    result = evaluate_tilth(
        runner=fake.runner(),
        overlay_dir=tmp_path / "overlay",
        tasks_path=tasks_path,
        task_ids=["t1", "t2"],
        model="haiku",
        output_path=tmp_path / "rows.jsonl",
    )
    records = cast(list[dict[str, object]], result["records"])
    assert all(record["correct"] is False for record in records)
    assert all(record["error"] is True for record in records)
    # A guarded failure must never win a Pareto comparison against a real
    # incorrect run that spent tokens (the row itself reports none).
    assert all(record["guard"] == RUNNER_ERROR_GUARD for record in records)


class TestErosionGuard:
    def test_diff_ratio_over_threshold_is_erosion(self) -> None:
        row = _row(correct=True, workspace_diff_lines=25, reference_changed_lines=5)
        record = score_row(row, erosion_ratio=DEFAULT_EROSION_RATIO)
        assert record["guard"] == EROSION_GUARD
        assert record["correct"] is False

    def test_lint_failure_is_erosion_even_under_ratio(self) -> None:
        row = _row(correct=True, workspace_diff_lines=2, reference_changed_lines=4, lint_ok=False)
        record = score_row(row)
        assert record["guard"] == EROSION_GUARD
        assert record["correct"] is False

    def test_within_ratio_and_lint_ok_has_no_guard(self) -> None:
        row = _row(correct=True, workspace_diff_lines=8, reference_changed_lines=4, lint_ok=True)
        record = score_row(row)
        assert "guard" not in record
        assert record["correct"] is True

    @pytest.mark.parametrize("field,value", [
        ("workspace_diff_lines", None),
        ("workspace_diff_lines", float("nan")),
        ("workspace_diff_lines", float("inf")),
        ("workspace_diff_lines", -1),
        ("workspace_diff_lines", True),
        ("reference_changed_lines", None),
        ("reference_changed_lines", float("nan")),
        ("reference_changed_lines", -1),
        ("lint_ok", None),
        ("lint_ok", 1),
    ])
    def test_invalid_measurement_is_guarded(self, field: str, value: object) -> None:
        row = _row(correct=True)
        row[field] = value
        record = score_row(row)
        assert record["correct"] is False
        assert record["guard"] == EROSION_GUARD

    def test_missing_measurement_is_guarded(self) -> None:
        row = _row(correct=True)
        del row["lint_ok"]
        assert score_row(row)["guard"] == EROSION_GUARD

    def test_ratio_three_boundary_passes(self) -> None:
        row = _row(correct=True, workspace_diff_lines=9, reference_changed_lines=3)
        assert score_row(row)["correct"] is True

    @pytest.mark.parametrize("ratio", [0, -1, float("nan"), float("inf")])
    def test_invalid_ratio_is_rejected(self, ratio: float) -> None:
        with pytest.raises(ValueError, match="erosion ratio"):
            _ = score_row(_row(), erosion_ratio=ratio)


def test_model_per_split_records_the_row_model_and_passes_the_split_alias(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeRun(
        tmp_path,
        monkeypatch,
        rows_by_task={
            "train-1": _row(correct=True, model="claude-haiku-4-5-20251001"),
            "val-1": _row(correct=True, model="claude-sonnet-4-5-20250929"),
        },
    )
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": task_id} for task_id in fake.rows_by_task]}), encoding="utf-8")

    train_result = evaluate_tilth(
        runner=fake.runner(),
        overlay_dir=tmp_path / "overlay",
        tasks_path=tasks_path,
        task_ids=["train-1"],
        model="haiku",
        output_path=tmp_path / "train.jsonl",
    )
    validation_result = evaluate_tilth(
        runner=fake.runner(),
        overlay_dir=tmp_path / "overlay",
        tasks_path=tasks_path,
        task_ids=["val-1"],
        model="sonnet",
        output_path=tmp_path / "validation.jsonl",
    )
    train_call, validation_call = fake.calls()
    assert train_call["models"] == "haiku"
    assert validation_call["models"] == "sonnet"
    train_record = cast(list[dict[str, object]], train_result["records"])[0]
    validation_record = cast(list[dict[str, object]], validation_result["records"])[0]
    assert train_record["model"] == "claude-haiku-4-5-20251001"
    assert validation_record["model"] == "claude-sonnet-4-5-20250929"


def test_runner_error_on_nonzero_exit_and_empty_task_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun(tmp_path, monkeypatch, rows_by_task={"t1": _row()}, exit_code=3)
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": task_id} for task_id in fake.rows_by_task]}), encoding="utf-8")
    with pytest.raises(RunnerError, match="exited 3"):
        _ = fake.runner().run(
            overlay_dir=tmp_path / "overlay",
            tasks_path=tasks_path,
            task_ids=["t1"],
            model="haiku",
            output_path=tmp_path / "rows.jsonl",
        )
    with pytest.raises(RunnerError, match="task_ids"):
        _ = fake.runner().run(
            overlay_dir=tmp_path / "overlay",
            tasks_path=tasks_path,
            task_ids=[],
            model="haiku",
            output_path=tmp_path / "rows2.jsonl",
        )


def test_run_filters_selected_tasks_without_old_cli_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner selects one task from a mixed-split document."""
    fake = FakeRun(tmp_path, monkeypatch, rows_by_task={"train-a": _row(), "validation-b": _row(), "holdout-c": _row()})
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [
        {"id": "train-a", "split": "train"},
        {"id": "validation-b", "split": "validation"},
        {"id": "holdout-c", "split": "holdout"},
    ]}), encoding="utf-8")
    _ = fake.runner().run(
        overlay_dir=tmp_path / "overlay",
        tasks_path=tasks_path,
        task_ids=["validation-b"],
        model="haiku",
        output_path=tmp_path / "rows.jsonl",
    )
    assert fake.calls()[0]["tasks"] == ["validation-b"]
    assert fake.calls()[0]["max_usd"] == 0.5


@pytest.mark.parametrize("rows", [
    {"t1": _row(task="wrong"), "t2": _row()},
    {"t1": _row(task="t1"), "t2": _row(task="t1")},
    {"t1": _row(task=""), "t2": _row()},
    {"t1": _row(task=None), "t2": _row()},
])
def test_runner_rejects_invalid_row_coverage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: dict[str, dict[str, object]]
) -> None:
    fake = FakeRun(tmp_path, monkeypatch, rows_by_task=rows)
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": task_id} for task_id in fake.rows_by_task]}), encoding="utf-8")
    with pytest.raises(RunnerError, match="task"):
        _ = fake.runner().run(
            overlay_dir=tmp_path / "overlay", tasks_path=tasks_path,
            task_ids=["t1", "t2"], model="haiku", output_path=tmp_path / "rows.jsonl",
        )


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_runner_rejects_unbounded_limits(tmp_path: Path, value: float) -> None:
    with pytest.raises(RunnerError, match="timeout_seconds"):
        _ = TilthRunner(tilth_root=tmp_path, timeout_seconds=value)
    with pytest.raises(RunnerError, match="max_budget_usd"):
        _ = TilthRunner(tilth_root=tmp_path, max_budget_usd=value)


def test_duplicate_source_ids_rejected_before_spawn(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeRun(tmp_path, monkeypatch, rows_by_task={"t1": _row()})
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": "t1"}, {"id": "t1"}]}), encoding="utf-8")
    with pytest.raises(RunnerError, match="duplicate"):
        _ = fake.runner().run(
            overlay_dir=tmp_path / "overlay", tasks_path=tasks_path,
            task_ids=["t1"], model="haiku", output_path=tmp_path / "rows.jsonl",
        )
    assert fake.calls() == []


def test_timeout_stops_runner_child(tmp_path: Path) -> None:
    import time

    benchmark = tmp_path / "benchmark"
    benchmark.mkdir()
    script = """import argparse, subprocess, sys, time
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--output")
args, _ = parser.parse_known_args()
subprocess.Popen([sys.executable, "-c", "import time, pathlib; time.sleep(0.5); pathlib.Path(sys.argv[1]).write_text('alive')", args.output + ".child"])
time.sleep(30)
"""
    _ = (benchmark / "run.py").write_text(script, encoding="utf-8")
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": "t1"}]}), encoding="utf-8")
    output_path = tmp_path / "rows.jsonl"
    with pytest.raises(RunnerError, match="timeout"):
        _ = TilthRunner(tilth_root=tmp_path, timeout_seconds=0.1).run(
            overlay_dir=tmp_path / "overlay", tasks_path=tasks_path,
            task_ids=["t1"], model="haiku", output_path=output_path,
        )
    time.sleep(0.7)
    assert not (tmp_path / "rows.jsonl.child").exists()


@pytest.mark.parametrize("document", ["not-json", "{}", '{"version": 1, "tasks": [{"id": "other"}]}'])
def test_invalid_task_document_never_spawns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, document: str
) -> None:
    fake = FakeRun(tmp_path, monkeypatch, rows_by_task={"t1": _row()})
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(document, encoding="utf-8")
    with pytest.raises(RunnerError, match="task document"):
        _ = fake.runner().run(
            overlay_dir=tmp_path / "overlay", tasks_path=tasks_path,
            task_ids=["t1"], model="haiku", output_path=tmp_path / "rows.jsonl",
        )
    assert fake.calls() == []


@pytest.mark.parametrize("body", ["", "{bad json"])
def test_stale_or_malformed_output_is_not_accepted(tmp_path: Path, body: str) -> None:
    benchmark = tmp_path / "benchmark"
    benchmark.mkdir()
    script = """import argparse
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--output")
args, _ = parser.parse_known_args()
Path(args.output).write_text(%r)
""" % body
    _ = (benchmark / "run.py").write_text(script, encoding="utf-8")
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"version": 1, "tasks": [{"id": "t1"}]}), encoding="utf-8")
    output_path = tmp_path / "rows.jsonl"
    _ = output_path.write_text(json.dumps({"task": "t1"}), encoding="utf-8")
    with pytest.raises(RunnerError, match="malformed|coverage"):
        _ = TilthRunner(tilth_root=tmp_path).run(
            overlay_dir=tmp_path / "overlay", tasks_path=tasks_path,
            task_ids=["t1"], model="haiku", output_path=output_path,
        )
