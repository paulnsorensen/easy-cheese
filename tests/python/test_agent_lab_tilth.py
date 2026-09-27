"""Offline checks for the tilth benchmark runner using a scripted fake `run.py`.

The fake enforces the same contract tilth's real `benchmark/run.py` does:
`--tasks`/`--models` are one comma-separated value validated against a fixed
alias dict (`parse_comma_list`), every `ModeConfig` dict is built through a
dataclass that requires `name`, `tools`, `mcp_config_path`, and
`description` with no default, and `plugin_dir` must be an absolute path.
"""

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
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional


@dataclass
class ModeConfig:
    name: str
    tools: list
    mcp_config_path: Optional[str]
    description: str
    plugin_dir: Optional[str] = None
    prompt_mode: str = "replace"


MODELS = {"haiku": "claude-haiku-4-5-20251001", "sonnet": "claude-sonnet-4-6"}


def parse_comma_list(value, valid_options, name):
    if value.lower() == "all":
        return list(valid_options.keys())
    items = [item.strip() for item in value.split(",") if item.strip()]
    invalid = [item for item in items if item not in valid_options]
    if invalid:
        raise ValueError(f"Invalid {name}: {', '.join(invalid)}")
    return items


parser = argparse.ArgumentParser()
parser.add_argument("--modes-json", required=True)
parser.add_argument("--modes", required=True)
parser.add_argument("--tasks-json", required=True)
parser.add_argument("--tasks", required=True)
parser.add_argument("--models", required=True)
parser.add_argument("--reps", type=int, default=1)
parser.add_argument("--output", required=True)
parser.add_argument("--bare", action="store_true")
parser.add_argument("--max-cells", type=int, default=100)
args = parser.parse_args()

control = json.loads(Path(os.environ["FAKE_RUN_CONTROL"]).read_text())
models = parse_comma_list(args.models, control.get("model_aliases", MODELS), "models")
task_ids = parse_comma_list(args.tasks, control["rows_by_task"], "tasks")
raw_modes = json.loads(Path(args.modes_json).read_text())
modes = {entry["name"]: ModeConfig(**entry) for entry in raw_modes}
for mode in modes.values():
    if mode.plugin_dir and not os.path.isabs(mode.plugin_dir):
        print(f"ERROR: plugin_dir must be an absolute path: {mode.plugin_dir}", file=sys.stderr)
        sys.exit(1)
log_entry = {
    "modes": raw_modes,
    "modes_arg": args.modes,
    "tasks": task_ids,
    "models": models[0],
    "max_cells": args.max_cells,
}
with Path(control["log"]).open("a") as handle:
    handle.write(json.dumps(log_entry) + "\\n")

rows_by_task = control["rows_by_task"]
lines = []
for task_id in task_ids:
    row = dict(rows_by_task[task_id])
    row.setdefault("task", task_id)
    row.setdefault("model", models[0])
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
    _ = tasks_path.write_text("{}", encoding="utf-8")
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
    _ = tasks_path.write_text("{}", encoding="utf-8")
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
    _ = tasks_path.write_text("{}", encoding="utf-8")

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
    _ = tasks_path.write_text("{}", encoding="utf-8")
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


def test_run_rejects_a_multi_task_argv_that_would_split_on_commas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A task id with a comma in it would be misread as two ids by run.py's
    `parse_comma_list`; the fake's task universe never has one, so this
    only guards the join shape, not comma-bearing ids themselves."""
    fake = FakeRun(tmp_path, monkeypatch, rows_by_task={"t1": _row(), "t2": _row()})
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text("{}", encoding="utf-8")
    _ = fake.runner().run(
        overlay_dir=tmp_path / "overlay",
        tasks_path=tasks_path,
        task_ids=["t1", "t2"],
        model="haiku",
        output_path=tmp_path / "rows.jsonl",
    )
    assert fake.calls()[0]["tasks"] == ["t1", "t2"]
