"""Offline optimizer coverage and budget-stop regressions."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

import agent_lab
import agent_lab_candidate
import agent_lab_tilth
from agent_lab import OptimizeTilthArgs, _run_optimize_tilth  # pyright: ignore[reportPrivateUsage]
from prompt_lab import BudgetExhausted, PromptLabError


def _args(tmp_path: Path, tasks: list[dict[str, str]], *, max_runs: int = 4) -> OptimizeTilthArgs:
    tasks_path = tmp_path / "tasks.json"
    _ = tasks_path.write_text(json.dumps({"tasks": tasks}), encoding="utf-8")
    return OptimizeTilthArgs(
        tasks=str(tasks_path), seed=str(tmp_path / "seed"), tilth_root=str(tmp_path),
        max_cells=100, search_model="search", validation_model="validation",
        erosion_ratio=3.0, reflection_model="", max_metric_calls=8,
        max_runs=max_runs, timeout_seconds=30, max_budget_usd=0.5,
        claude_bin="claude", output_dir=str(tmp_path / "out"),
    )


@pytest.mark.parametrize("sequence,complete,partial", [
    (("train", "v1", "v1"), False, False),
    (("train", "v1", "v2"), True, False),
    (("train", "v1", "v2", "v1"), True, True),
])
def test_validation_identity_and_budget_export(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    sequence: tuple[str, ...], complete: bool, partial: bool,
) -> None:
    args = _args(tmp_path, [
        {"id": "train", "split": "train"},
        {"id": "v1", "split": "validation"},
        {"id": "v2", "split": "validation"},
    ], max_runs=3)
    calls: list[str] = []
    def load_candidate(_path: Path) -> dict[str, str]:
        return {"skills/cook/SKILL.md": "seed"}
    monkeypatch.setattr(agent_lab_candidate, "load_candidate_dir", load_candidate)
    def evaluate_candidate(**kwargs: object) -> tuple[str, list[dict[str, object]]]:
        task_id = cast(list[str], kwargs["task_ids"])[0]
        calls.append(task_id)
        return "candidate", [{
            "task": task_id, "correct": True, "model": kwargs["model"],
            "input_tokens": 10,
        }]
    monkeypatch.setattr(agent_lab_tilth, "evaluate_candidate", evaluate_candidate)
    def optimize_anything(**kwargs: object) -> None:
        evaluator = cast(Callable[[dict[str, str], dict[str, str]], object], kwargs["evaluator"])
        for task_id in sequence:
            _ = evaluator({"skills/cook/SKILL.md": "seed"}, {"id": task_id})
    def no_config(**_kwargs: object) -> None:
        pass
    monkeypatch.setattr(agent_lab, "_gepa_module_override", (no_config, no_config, no_config, optimize_anything))
    code = _run_optimize_tilth(args, tmp_path)
    result = cast(dict[str, object], json.loads((Path(args.output_dir) / "result.json").read_text()))
    assert bool(result["pareto_front"]) is complete
    assert (Path(args.output_dir) / "candidates" / "candidate").exists() is complete
    assert result.get("status") == ("partial" if partial else "complete")
    assert code == (2 if partial else 0)
    assert calls == list(sequence[:3])


def test_duplicate_source_task_ids_rejected_before_work(tmp_path: Path) -> None:
    args = _args(tmp_path, [{"id": "train", "split": "train"}, {"id": "train", "split": "validation"}])
    with pytest.raises(PromptLabError, match="duplicate"):
        _ = _run_optimize_tilth(args, tmp_path)
    assert not Path(args.output_dir).exists()


@pytest.mark.parametrize("max_runs,benchmark_calls,reflection_calls", [
    (2, 2, 0),
    (3, 2, 1),
])
def test_reflection_shares_cap_even_when_gepa_catches_exhaustion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    max_runs: int, benchmark_calls: int, reflection_calls: int,
) -> None:
    args = _args(tmp_path, [
        {"id": "train", "split": "train"},
        {"id": "validation", "split": "validation"},
    ], max_runs=max_runs)
    reflection = tmp_path / "reflection.json"
    _ = reflection.write_text(json.dumps({"texts": ["candidate"]}), encoding="utf-8")
    monkeypatch.setenv("AGENT_LAB_FAKE_REFLECTION", str(reflection))
    def load_candidate(_path: Path) -> dict[str, str]:
        return {"skills/cook/SKILL.md": "seed"}
    monkeypatch.setattr(agent_lab_candidate, "load_candidate_dir", load_candidate)
    calls: list[str] = []
    def evaluate_candidate(**kwargs: object) -> tuple[str, list[dict[str, object]]]:
        task_id = cast(list[str], kwargs["task_ids"])[0]
        calls.append(task_id)
        return "candidate", [{"task": task_id, "correct": True, "input_tokens": 10}]
    monkeypatch.setattr(agent_lab_tilth, "evaluate_candidate", evaluate_candidate)
    observed_reflections: list[str] = []
    def optimize_anything(**kwargs: object) -> None:
        evaluator = cast(Callable[[dict[str, str], dict[str, str]], object], kwargs["evaluator"])
        config = cast(SimpleNamespace, kwargs["config"])
        reflection_config = cast(SimpleNamespace, getattr(config, "reflection"))
        reflect = cast(Callable[[str], str], getattr(reflection_config, "reflection_lm"))
        seed = {"skills/cook/SKILL.md": "seed"}
        _ = evaluator(seed, {"id": "train"})
        _ = evaluator(seed, {"id": "validation"})
        try:
            observed_reflections.append(reflect("improve"))
            _ = evaluator(seed, {"id": "train"})
        except BudgetExhausted:
            pass
    def config(**kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(**kwargs)
    monkeypatch.setattr(agent_lab, "_gepa_module_override", (config, config, config, optimize_anything))
    code = _run_optimize_tilth(args, tmp_path)
    result = cast(dict[str, object], json.loads((Path(args.output_dir) / "result.json").read_text()))
    assert code == 2
    assert result["status"] == "partial"
    assert result["pareto_front"]
    assert len(calls) == benchmark_calls
    assert len(observed_reflections) == reflection_calls


def test_gepa_task_loader_preserves_global_ids_and_fetch_order() -> None:
    train_ids = ["train:alpha", "train:beta"]
    validation_ids = ["validation:alpha", "validation:beta"]
    train = agent_lab._GepaTaskLoader(train_ids)  # pyright: ignore[reportPrivateUsage]
    validation = agent_lab._GepaTaskLoader(validation_ids)  # pyright: ignore[reportPrivateUsage]

    assert train.all_ids() == train_ids
    assert validation.all_ids() == validation_ids
    assert set(train.all_ids()).isdisjoint(validation.all_ids())
    assert train.fetch(["train:beta", "train:alpha"]) == [
        {"id": "train:beta"}, {"id": "train:alpha"},
    ]
    assert validation.fetch(["validation:beta", "validation:alpha"]) == [
        {"id": "validation:beta"}, {"id": "validation:alpha"},
    ]
    assert len(train) == len(train_ids)
    assert len(validation) == len(validation_ids)
    assert list(train) == [{"id": task_id} for task_id in train_ids]
    assert list(validation) == [{"id": task_id} for task_id in validation_ids]
