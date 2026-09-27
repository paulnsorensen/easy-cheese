"""Drive tilth's `benchmark/run.py` harness for one candidate's plugin overlay.

This module owns the frozen subprocess contract between easy-cheese and
tilth: it writes a `ModeConfig` dict carrying `plugin_dir`, `description`,
and `prompt_mode="append"`, invokes `run.py --bare --modes-json ...
--tasks-json ... --tasks ... --models ... --reps 1 --output ... --max-cells
N`, and reads back only the JSONL row fields the scoring layer consumes:
`correct`, `error`, `model`, `model_alias`, the four token fields, `skills`,
`workspace_diff_lines`, `reference_changed_lines`, and `lint_ok`. It never
runs an agent itself and never re-grades a workspace locally.

`--tasks` and `--models` are each one comma-separated value (run.py's
`parse_comma_list`), `plugin_dir` and `mcp_config_path` must be absolute
(run.py runs with a different cwd and rejects a relative `plugin_dir`
outright), and every `ModeConfig` field run.py requires with no default
(`name`, `tools`, `mcp_config_path`, `description`) must be present.
"""

from __future__ import annotations

import hashlib
import json
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


def build_mode(name: str, *, overlay_dir: Path, tilth_root: Path) -> JsonObject:
    """Return one `ModeConfig` dict: the seed and every candidate share this
    shape (tools, mcp_config_path, prompt_mode, description) and differ only
    in `plugin_dir`, so the MCP prefix cost cancels in a paired comparison.

    `overlay_dir` and `tilth_root` are resolved to absolute paths: run.py
    validates every mode's `plugin_dir` is absolute before it spends a paid
    agent run, and it hands `mcp_config_path` to the agent with its own cwd,
    where a relative path would not resolve.
    """
    tilth_root = Path(tilth_root).resolve()
    overlay_dir = Path(overlay_dir).resolve()
    mcp_config_path = tilth_root / "benchmark" / "fixtures" / "tilth_mcp.json"
    return {
        "name": name,
        "plugin_dir": str(overlay_dir),
        "prompt_mode": "append",
        "tools": list(DEFAULT_TOOLS),
        "mcp_config_path": str(mcp_config_path),
        "description": f"agent-lab overlay: {name}",
    }


class TilthRunner:
    """Invoke tilth's `benchmark/run.py` and parse its JSONL output rows."""

    def __init__(
        self,
        *,
        tilth_root: Path,
        python_bin: str | None = None,
        max_cells: int = 100,
        timeout_seconds: int | None = None,
    ) -> None:
        self._tilth_root: Path = Path(tilth_root)
        self._python_bin: str = python_bin or sys.executable
        self._run_script: Path = self._tilth_root / "benchmark" / "run.py"
        self._max_cells: int = max_cells
        self._timeout_seconds: int | None = timeout_seconds

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
        mode = build_mode(mode_name, overlay_dir=overlay_dir, tilth_root=self._tilth_root)
        with tempfile.TemporaryDirectory(prefix="agent-lab-tilth-") as scratch:
            modes_path = Path(scratch) / "modes.json"
            _ = modes_path.write_text(json.dumps([mode]), encoding="utf-8")
            argv = [
                self._python_bin,
                str(self._run_script),
                "--modes-json",
                str(modes_path),
                "--modes",
                mode_name,
                "--tasks-json",
                str(tasks_path),
                "--tasks",
                ",".join(task_ids),
                "--models",
                model,
                "--reps",
                "1",
                "--output",
                str(output_path),
                "--bare",
                "--max-cells",
                str(self._max_cells),
            ]
            try:
                completed = subprocess.run(
                    argv, capture_output=True, text=True, check=False, timeout=self._timeout_seconds
                )
            except subprocess.TimeoutExpired as error:
                raise RunnerError(f"benchmark/run.py exceeded timeout of {self._timeout_seconds}s") from error
        if completed.returncode != 0:
            raise RunnerError(f"benchmark/run.py exited {completed.returncode}: {completed.stderr[-2000:]}")
        if not output_path.exists():
            raise RunnerError("benchmark/run.py produced no output file")
        rows = [
            cast(JsonObject, json.loads(line))
            for line in output_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not rows:
            raise RunnerError("benchmark/run.py produced no rows")
        return rows


def score_row(row: Mapping[str, object], *, erosion_ratio: float = DEFAULT_EROSION_RATIO) -> JsonObject:
    """Turn one raw tilth row into a scoring record with `task`, `model`,
    `correct`, the four token fields, and (when a guard fired) `guard`.

    A row whose `skills` lacks REQUIRED_SKILL, or that carries `error`, is
    scored as a failure and guarded with `RUNNER_ERROR_GUARD`: the row
    carries no real token spend, so an unguarded zero-token vector could
    otherwise beat a real incorrect run. The erosion guard fires when the
    workspace/reference diff-line ratio exceeds `erosion_ratio`, or when
    `lint_ok` is False; either guard also forces `correct` to False, so a
    guarded row never scores as correct.
    """
    skills = cast(list[object], row.get("skills") or [])
    skill_missing = REQUIRED_SKILL not in skills
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
    workspace_diff_lines = float(cast(float, row.get("workspace_diff_lines", 0)) or 0)
    reference_changed_lines = float(cast(float, row.get("reference_changed_lines", 0)) or 0)
    ratio = workspace_diff_lines / max(reference_changed_lines, 1.0)
    lint_ok = row.get("lint_ok", True)
    if ratio > erosion_ratio or lint_ok is False:
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