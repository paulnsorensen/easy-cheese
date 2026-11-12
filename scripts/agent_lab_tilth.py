"""Run selected Tilth JSON tasks through one Claude plugin overlay.

The adapter selects tasks before spawn, caps batch and cell spend, and verifies
that the returned JSONL contains exactly one row for each requested task.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import cast

from agent_lab_candidate import PLUGIN_NAME, SKILL_DIR_NAME, BuildResult


JsonObject = dict[str, object]

# The plugin overlay is named "easy-cheese" and carries only the cook skill;
# tilth's init event records the loaded skill as "<plugin>:<skill dir>".
REQUIRED_SKILL = f"{PLUGIN_NAME}:{SKILL_DIR_NAME}"

DEFAULT_TOOLS = ("Read", "Edit", "Grep", "Glob", "Bash")
DEFAULT_EROSION_RATIO = 3.0
EROSION_GUARD = "erosion"
# A row that never reached tilth (an agent crash, a missing skill, or a
# non-zero run.py exit) reports no token fields, so it must be guarded like
# `EROSION_GUARD` -- otherwise its zero-token vector would beat every real
# incorrect run that spent tokens.
RUNNER_ERROR_GUARD = "runner-error"


class RunnerError(RuntimeError):
    """tilth's `benchmark/run.py` exited non-zero, timed out, or produced no rows."""


def build_mode(name: str, *, overlay_dir: Path) -> JsonObject:
    """Return one plugin-only mode accepted by the pinned Tilth CLI."""
    return {
        "name": name,
        "plugin_dir": str(Path(overlay_dir).resolve()),
        "prompt_mode": "append",
        "tools": list(DEFAULT_TOOLS),
        "description": f"agent-lab overlay: {name}",
    }


class TilthRunner:
    """Invoke tilth benchmark/run.py and parse its JSONL output rows."""

    def __init__(
        self,
        *,
        tilth_root: Path,
        python_bin: str | None = None,
        max_cells: int = 100,
        timeout_seconds: float = 300,
        max_budget_usd: float = 0.5,
    ) -> None:
        if isinstance(max_cells, bool) or max_cells <= 0:
            raise RunnerError("max_cells must be positive")
        if isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise RunnerError("timeout_seconds must be finite and positive")
        if isinstance(max_budget_usd, bool) or not math.isfinite(max_budget_usd) or max_budget_usd <= 0:
            raise RunnerError("max_budget_usd must be finite and positive")
        self._tilth_root: Path = Path(tilth_root).resolve()
        self._python_bin: str = python_bin or sys.executable
        self._run_script: Path = self._tilth_root / "benchmark" / "run.py"
        self._max_cells: int = max_cells
        self._timeout_seconds: float = timeout_seconds
        self._max_budget_usd: float = max_budget_usd

    def run(
        self,
        *,
        overlay_dir: Path,
        tasks_path: Path,
        task_ids: Sequence[str],
        model: str,
        output_path: Path,
        mode_name: str = "candidate",
    ) -> list[JsonObject]:
        """Run `task_ids` at `model` through the overlay at `overlay_dir`.

        Returns the parsed JSONL rows, in file order.
        """
        if not task_ids:
            raise RunnerError("task_ids must not be empty")
        expected = set(task_ids)
        if len(expected) != len(task_ids) or any(not task_id.strip() for task_id in task_ids):
            raise RunnerError("requested task ids must be unique and nonempty")
        if len(task_ids) > self._max_cells:
            raise RunnerError("requested tasks exceed max_cells")
        try:
            document = cast(object, json.loads(Path(tasks_path).read_text(encoding="utf-8")))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RunnerError("task document is unreadable or invalid JSON") from error
        if not isinstance(document, dict):
            raise RunnerError("task document must contain version 1 and a tasks list")
        task_document = cast(JsonObject, document)
        if task_document.get("version") != 1 or not isinstance(task_document.get("tasks"), list):
            raise RunnerError("task document must contain version 1 and a tasks list")
        source_tasks = cast(list[object], task_document["tasks"])
        selected: list[JsonObject] = []
        seen: set[str] = set()
        for raw in source_tasks:
            if not isinstance(raw, dict):
                raise RunnerError("task document contains a non-object task")
            task = cast(JsonObject, raw)
            task_id = task.get("id")
            if not isinstance(task_id, str) or not task_id.strip() or task_id in seen:
                raise RunnerError("task document contains a missing or duplicate task id")
            seen.add(task_id)
            if task_id in expected:
                selected.append(task)
        if {cast(str, task["id"]) for task in selected} != expected:
            raise RunnerError("task document is missing a requested task")
        mode = build_mode(mode_name, overlay_dir=overlay_dir)
        output_path = Path(output_path).resolve()
        try:
            output_path.unlink(missing_ok=True)
            with tempfile.TemporaryDirectory(prefix="agent-lab-tilth-") as scratch:
                modes_path = Path(scratch) / "modes.json"
                selected_path = Path(scratch) / "tasks.json"
                _ = modes_path.write_text(json.dumps([mode]), encoding="utf-8")
                _ = selected_path.write_text(json.dumps({**task_document, "tasks": selected}), encoding="utf-8")
                argv = [
                    self._python_bin, str(self._run_script),
                    "--modes-json", str(modes_path),
                    "--tasks-json", str(selected_path),
                    "--models", model, "--reps", "1",
                    "--output", str(output_path), "--bare",
                    "--max-cells", str(self._max_cells),
                    "--max-usd", str(len(selected) * self._max_budget_usd),
                    "--max-budget-usd", str(self._max_budget_usd),
                    "--cell-estimate-usd", str(self._max_budget_usd),
                ]
                process = subprocess.Popen(
                    argv, cwd=self._tilth_root, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, text=True, start_new_session=True,
                )
                try:
                    _, stderr = process.communicate(timeout=self._timeout_seconds)
                except subprocess.TimeoutExpired as error:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    _ = process.communicate()
                    raise RunnerError(f"benchmark/run.py exceeded timeout of {self._timeout_seconds}s") from error
        except OSError as error:
            raise RunnerError(f"benchmark/run.py could not start or write output: {error}") from error
        if process.returncode != 0:
            raise RunnerError(f"benchmark/run.py exited {process.returncode}: {stderr[-2000:]}")
        try:
            lines = output_path.read_text(encoding="utf-8").splitlines()
            rows = [cast(object, json.loads(line)) for line in lines if line.strip()]
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RunnerError("benchmark/run.py produced missing or malformed JSONL output") from error
        if len(rows) != len(expected) or any(not isinstance(row, dict) for row in rows):
            raise RunnerError("benchmark/run.py returned malformed task coverage")
        actual: list[str] = []
        for raw in rows:
            row = cast(JsonObject, raw)
            task_id = row.get("task")
            if not isinstance(task_id, str) or not task_id.strip():
                raise RunnerError("benchmark/run.py returned malformed task id")
            actual.append(task_id)
        if set(actual) != expected or len(set(actual)) != len(actual):
            raise RunnerError("benchmark/run.py returned incomplete or duplicate task coverage")
        return cast(list[JsonObject], rows)


def score_row(row: Mapping[str, object], *, erosion_ratio: float = DEFAULT_EROSION_RATIO) -> JsonObject:
    """Score one tilth row, failing closed on invalid erosion evidence."""
    if isinstance(erosion_ratio, bool) or not math.isfinite(erosion_ratio) or erosion_ratio <= 0:
        raise ValueError("erosion ratio must be finite and positive")
    skills = row.get("skills")
    skill_missing = not isinstance(skills, list) or REQUIRED_SKILL not in skills
    failed = bool(row.get("error")) or skill_missing
    record: JsonObject = {
        "task": row.get("task"),
        "model": row.get("model"),
        "correct": False if failed else bool(row.get("correct")),
        "input_tokens": row.get("input_tokens", 0),
        "output_tokens": row.get("output_tokens", 0),
        "cache_creation_tokens": row.get("cache_creation_tokens", 0),
        "cache_read_tokens": row.get("cache_read_tokens", 0),
        "error": failed,
    }
    if failed:
        record["guard"] = RUNNER_ERROR_GUARD
        return record
    counts = (row.get("workspace_diff_lines"), row.get("reference_changed_lines"))
    valid_counts = all(
        isinstance(value, (int, float)) and not isinstance(value, bool)
        and math.isfinite(value) and value >= 0
        for value in counts
    )
    lint_ok = row.get("lint_ok")
    if not valid_counts or not isinstance(lint_ok, bool):
        record["correct"] = False
        record["guard"] = EROSION_GUARD
        return record
    workspace_diff_lines, reference_changed_lines = cast(tuple[float, float], counts)
    ratio = workspace_diff_lines / max(reference_changed_lines, 1.0)
    if ratio > erosion_ratio or not lint_ok:
        record["correct"] = False
        record["guard"] = EROSION_GUARD
    return record


def score_rows(rows: Sequence[Mapping[str, object]], *, erosion_ratio: float = DEFAULT_EROSION_RATIO) -> list[JsonObject]:
    return [score_row(row, erosion_ratio=erosion_ratio) for row in rows]


def evaluate_tilth(
    *,
    runner: TilthRunner,
    overlay_dir: Path,
    tasks_path: Path,
    task_ids: Sequence[str],
    model: str,
    output_path: Path,
    mode_name: str = "candidate",
    erosion_ratio: float = DEFAULT_EROSION_RATIO,
) -> JsonObject:
    """Run and score `task_ids`; `aggregate_score` is the mean of the scored
    `correct` values, derived only from the rows -- never from a local
    re-grade of the workspace.
    """
    rows = runner.run(
        overlay_dir=overlay_dir,
        tasks_path=tasks_path,
        task_ids=task_ids,
        model=model,
        output_path=output_path,
        mode_name=mode_name,
    )
    records = score_rows(rows, erosion_ratio=erosion_ratio)
    aggregate = sum(cast(float, record["correct"]) for record in records) / len(records)
    return {"aggregate_score": aggregate, "records": records, "rows": rows}


def guard_record(task_id: str, *, model: str, guard: str, detail: str = "") -> JsonObject:
    """Return the guard-record shape emitted when an overlay build itself
    guards, before a tilth run is ever spent on the candidate."""
    record: JsonObject = {"task": task_id, "model": model, "guard": guard, "correct": False}
    if detail:
        record["detail"] = detail
    return record


PrepareOverlay = Callable[..., BuildResult]


class OverlayCache:
    """Cache `prepare_overlay_detailed` results by the candidate components' hash.

    `graduate` and `optimize --runner tilth` both build the same overlay for
    a repeated candidate; this cache builds it once per process instead of
    once per (candidate, model, task) call.
    """

    def __init__(self, *, output_dir: Path, repo_root: Path, prepare_overlay: PrepareOverlay) -> None:
        self._output_dir: Path = output_dir
        self._repo_root: Path = repo_root
        self._prepare_overlay: PrepareOverlay = prepare_overlay
        self._result_by_key: dict[str, BuildResult] = {}

    def ensure(self, components: Mapping[str, str]) -> tuple[str, Path, BuildResult]:
        key = hashlib.sha256(json.dumps(dict(components), sort_keys=True).encode()).hexdigest()
        overlay_dir = self._output_dir / "overlays" / key
        if key not in self._result_by_key:
            self._result_by_key[key] = self._prepare_overlay(
                dict(components), repo_root=self._repo_root, overlay_dir=overlay_dir
            )
        return key, overlay_dir, self._result_by_key[key]


def evaluate_candidate(
    *,
    runner: TilthRunner,
    overlay_cache: OverlayCache,
    components: Mapping[str, str],
    tasks_path: Path,
    task_ids: Sequence[str],
    model: str,
    output_path: Path,
    erosion_ratio: float = DEFAULT_EROSION_RATIO,
) -> tuple[str, list[JsonObject]]:
    """Evaluate `components` on `task_ids` at `model`, building the overlay
    once per candidate hash and never spending a tilth run when the overlay
    build itself guards. Returns `(candidate_sha256, records)`.
    """
    key, overlay_dir, build_result = overlay_cache.ensure(components)
    if build_result.guard:
        return key, [
            guard_record(task_id, model=model, guard=build_result.guard, detail=build_result.detail)
            for task_id in task_ids
        ]
    result = evaluate_tilth(
        runner=runner,
        overlay_dir=overlay_dir,
        tasks_path=tasks_path,
        task_ids=task_ids,
        model=model,
        output_path=output_path,
        erosion_ratio=erosion_ratio,
    )
    return key, cast(list[JsonObject], result["records"])