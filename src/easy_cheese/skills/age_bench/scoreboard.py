"""Write a per-overlap-area scoreboard for a benchmark run.

On-disk layout (private, not spec'd elsewhere): a run's judge results live
at ``<project_corpus_root>/benchmark/age/<run-id>/results/<tool>/<case-id>.json``,
one file per (tool, case) pair, each shaped like ``JudgeResult.to_dict()``.
This module reads that tree and renders
``<project_corpus_root>/benchmark/age/<run-id>/scoreboard.md`` -- never under
``.cheese/``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

from easy_cheese.shared import cli
from easy_cheese.shared.paths import project_corpus_root, resolve_repo_root
from easy_cheese.skills.age_bench.cases import CaseNotFoundError, load_case
from easy_cheese.skills.age_bench.errors import AgeBenchError

TOOLS: tuple[str, ...] = ("age", "code-review")


def run_root(run_id: str) -> Path:
    cli.reject_path_segment("run_id", run_id)
    if not run_id or run_id == ".":
        raise cli.CliError(f"run_id rejects path traversal: {run_id!r}")
    return project_corpus_root() / "benchmark" / "age" / run_id


def results_dir(root: Path, tool: str) -> Path:
    return root / "results" / tool


def write_result(run_id: str, tool: str, result: dict[str, object]) -> Path:
    """Persist a ``JudgeResult.to_dict()`` payload as ``results_dir(...)/<case-id>.json``."""
    case_id = cast(str, result["case_id"])
    directory = results_dir(run_root(run_id), tool)
    directory.mkdir(parents=True, exist_ok=True)
    out_path = directory / f"{case_id}.json"
    _ = out_path.write_text(json.dumps(result), encoding="utf-8")
    return out_path


@dataclass(frozen=True)
class ScoreboardRow:
    overlap_area: str
    case_id: str
    metrics: dict[str, dict[str, float | None] | None]


def _load_metrics(root: Path, tool: str, case_id: str) -> dict[str, float | None] | None:
    path = results_dir(root, tool) / f"{case_id}.json"
    if not path.is_file():
        return None
    data = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
    try:
        return {
            "recall": cast(float, data["recall"]),
            "precision": cast("float | None", data["precision"]),
            "snr": cast("float | None", data["snr"]),
        }
    except KeyError as exc:
        raise AgeBenchError(f"{path}: missing field {exc}") from exc


def build_rows(run_id: str, *, repo_root: Path | str | None = None) -> list[ScoreboardRow]:
    root = run_root(run_id)
    resolved_repo_root = resolve_repo_root(repo_root)
    case_ids: set[str] = set()
    for tool in TOOLS:
        tool_dir = results_dir(root, tool)
        if tool_dir.is_dir():
            case_ids.update(path.stem for path in tool_dir.glob("*.json"))

    rows: list[ScoreboardRow] = []
    for case_id in sorted(case_ids):
        try:
            overlap_area = load_case(case_id, repo_root=resolved_repo_root).overlap_area
        except CaseNotFoundError:
            overlap_area = "(unknown)"
        metrics = {tool: _load_metrics(root, tool, case_id) for tool in TOOLS}
        rows.append(ScoreboardRow(overlap_area=overlap_area, case_id=case_id, metrics=metrics))
    return rows


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|")


def _format_metric(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def _format_snr(value: float | None) -> str:
    return "∞" if value is None else f"{value:.2f}"


def _format_metrics(metrics: dict[str, float | None] | None) -> str:
    if metrics is None:
        return "-"
    return (
        f"{_format_metric(metrics['recall'])}/"
        f"{_format_metric(metrics['precision'])}/"
        f"{_format_snr(metrics['snr'])}"
    )


def render_table(rows: list[ScoreboardRow], *, run_id: str) -> str:
    # precision = (hits + suggestions) / findings, "-" when a case had no findings;
    # snr = hits / noise, "∞" when noise = 0.
    columns = ["overlap_area", "case"] + [f"{tool} recall/precision/snr" for tool in TOOLS]
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [f"Run: {run_id}", "", header, separator]
    for row in rows:
        cells = [_escape_cell(row.overlap_area), _escape_cell(row.case_id)] + [
            _format_metrics(row.metrics[tool]) for tool in TOOLS
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def write_scoreboard(run_id: str, *, repo_root: Path | str | None = None) -> Path:
    rows = build_rows(run_id, repo_root=repo_root)
    if not rows:
        raise AgeBenchError(f"no results found for run {run_id!r}")
    out_path = run_root(run_id) / "scoreboard.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _ = out_path.write_text(render_table(rows, run_id=run_id), encoding="utf-8")
    return out_path


def _cmd_scoreboard(args: argparse.Namespace) -> int:
    run_id = cast(str, args.run_id)
    repo_root = cast("str | None", args.repo_root)
    json_mode = cast(bool, args.json_mode)
    stdout = cast("TextIO | None", args.stdout)
    path = write_scoreboard(run_id, repo_root=repo_root)
    cli.emit(str(path), json_mode=json_mode, stdout=stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("run_id", help="benchmark run id")
    _ = parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.set_defaults(func=_cmd_scoreboard)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)