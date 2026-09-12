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

from easy_cheese.shared import cli
from easy_cheese.shared.paths import project_corpus_root
from easy_cheese.skills.age_bench.cases import load_case, validate_identifier

TOOLS: tuple[str, ...] = ("age", "code-review")


def run_root(run_id: str) -> Path:
    validate_identifier(run_id, "run_id")
    return project_corpus_root() / "benchmark" / "age" / run_id


def results_dir(run_id: str, tool: str) -> Path:
    return run_root(run_id) / "results" / tool


@dataclass(frozen=True)
class ScoreboardRow:
    overlap_area: str
    case_id: str
    metrics: dict[str, dict[str, float] | None]


def _load_metrics(run_id: str, tool: str, case_id: str) -> dict[str, float] | None:
    path = results_dir(run_id, tool) / f"{case_id}.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return {"recall": data["recall"], "precision": data["precision"], "snr": data["snr"]}


def build_rows(run_id: str, *, repo_root: Path | str | None = None) -> list[ScoreboardRow]:
    case_ids: set[str] = set()
    for tool in TOOLS:
        tool_dir = results_dir(run_id, tool)
        if tool_dir.is_dir():
            case_ids.update(path.stem for path in tool_dir.glob("*.json"))

    rows: list[ScoreboardRow] = []
    for case_id in sorted(case_ids):
        overlap_area = load_case(case_id, repo_root=repo_root).overlap_area
        metrics = {tool: _load_metrics(run_id, tool, case_id) for tool in TOOLS}
        rows.append(ScoreboardRow(overlap_area=overlap_area, case_id=case_id, metrics=metrics))
    return rows


def _format_metrics(metrics: dict[str, float] | None) -> str:
    if metrics is None:
        return "-"
    return f"{metrics['recall']:.2f}/{metrics['precision']:.2f}/{metrics['snr']:.2f}"


def render_table(rows: list[ScoreboardRow]) -> str:
    header = "| overlap_area | case | age recall/precision/snr | code-review recall/precision/snr |"
    separator = "| --- | --- | --- | --- |"
    lines = [header, separator]
    for row in rows:
        lines.append(
            f"| {row.overlap_area} | {row.case_id} "
            f"| {_format_metrics(row.metrics['age'])} "
            f"| {_format_metrics(row.metrics['code-review'])} |"
        )
    return "\n".join(lines) + "\n"


def write_scoreboard(run_id: str, *, repo_root: Path | str | None = None) -> Path:
    rows = build_rows(run_id, repo_root=repo_root)
    out_path = run_root(run_id) / "scoreboard.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_table(rows), encoding="utf-8")
    return out_path


def _cmd_scoreboard(args: argparse.Namespace) -> int:
    try:
        path = write_scoreboard(args.run_id, repo_root=args.repo_root)
    except Exception as exc:  # noqa: BLE001 - surfaced as a CliError below
        raise cli.CliError(str(exc)) from exc
    print(path, file=args.stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("run_id", help="benchmark run id")
    _ = parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.set_defaults(func=_cmd_scoreboard)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)
