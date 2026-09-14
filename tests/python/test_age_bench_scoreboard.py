"""Unit tests for the scoreboard slice: rendering, identifier safety, and
results-tree writes.

Spec: age-fanout-mechanics-benchmark.md; cure findings 6, 10, 20, 21, 22, 23,
49, 50 on src/easy_cheese/skills/age_bench/scoreboard.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from easy_cheese.shared import cli
from easy_cheese.skills.age_bench import scoreboard

CASE_ID = "off-by-one-window-sum"


@pytest.fixture()
def corpus_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "cheese-home"
    monkeypatch.setenv("EASY_CHEESE_HOME", str(home))
    return home


@pytest.mark.usefixtures("corpus_home")
def test_run_root_rejects_a_dot_run_id() -> None:
    with pytest.raises(cli.CliError, match="traversal"):
        _ = scoreboard.run_root(".")


@pytest.mark.usefixtures("corpus_home")
def test_run_root_rejects_an_empty_run_id() -> None:
    with pytest.raises(cli.CliError):
        _ = scoreboard.run_root("")


@pytest.mark.usefixtures("corpus_home")
def test_run_root_rejects_a_traversal_run_id() -> None:
    with pytest.raises(cli.CliError, match="traversal"):
        _ = scoreboard.run_root("../escape")


@pytest.mark.usefixtures("corpus_home")
def test_write_result_then_scoreboard_reads_it_back() -> None:
    payload: dict[str, object] = {
        "case_id": CASE_ID,
        "recall": 1.0,
        "precision": 0.5,
        "snr": None,
    }
    out_path = scoreboard.write_result("run-1", "age", payload)
    assert out_path == scoreboard.run_root("run-1") / "results" / "age" / f"{CASE_ID}.json"
    assert json.loads(out_path.read_text(encoding="utf-8")) == payload


@pytest.mark.usefixtures("corpus_home")
def test_write_scoreboard_fails_closed_when_no_results_exist() -> None:
    with pytest.raises(cli.CliError, match="no-such-run"):
        _ = scoreboard.write_scoreboard("no-such-run")


def test_render_table_derives_header_and_cells_from_tools() -> None:
    row = scoreboard.ScoreboardRow(
        overlap_area="off-by-one",
        case_id=CASE_ID,
        metrics={tool: None for tool in scoreboard.TOOLS},
    )
    table = scoreboard.render_table([row], run_id="run-9")
    for tool in scoreboard.TOOLS:
        assert f"{tool} recall/precision/snr" in table
    assert "Run: run-9" in table


def test_render_table_escapes_pipes_in_cell_values() -> None:
    row = scoreboard.ScoreboardRow(
        overlap_area="a|rea",
        case_id="ca|se",
        metrics={tool: None for tool in scoreboard.TOOLS},
    )
    table = scoreboard.render_table([row], run_id="run-9")
    lines = [line for line in table.splitlines() if line.startswith("| a")]
    assert lines
    assert "a\\|rea" in lines[0]
    assert "ca\\|se" in lines[0]


def test_format_metrics_renders_none_precision_as_dash_and_none_snr_as_infinity() -> None:
    row = scoreboard.ScoreboardRow(
        overlap_area="area",
        case_id=CASE_ID,
        metrics={
            "age": {"recall": 1.0, "precision": None, "snr": None},
            "code-review": None,
        },
    )
    table = scoreboard.render_table([row], run_id="run-9")
    assert "1.00/-/∞" in table


@pytest.mark.usefixtures("corpus_home")
def test_build_rows_marks_a_missing_case_manifest_unknown_instead_of_aborting() -> None:
    missing_case_id = "no-such-case-in-corpus"
    _ = scoreboard.write_result(
        "run-2", "age", {"case_id": missing_case_id, "recall": 0.0, "precision": None, "snr": None}
    )
    rows = scoreboard.build_rows("run-2")
    assert len(rows) == 1
    assert rows[0].overlap_area == "(unknown)"


@pytest.mark.usefixtures("corpus_home")
def test_load_metrics_names_the_path_and_field_on_a_missing_key() -> None:
    directory = scoreboard.results_dir(scoreboard.run_root("run-3"), "age")
    directory.mkdir(parents=True)
    bad_path = directory / f"{CASE_ID}.json"
    _ = bad_path.write_text(json.dumps({"recall": 1.0}), encoding="utf-8")
    with pytest.raises(cli.CliError, match=str(bad_path)):
        _ = scoreboard._load_metrics(  # noqa: SLF001  # pyright: ignore[reportPrivateUsage]
            scoreboard.run_root("run-3"), "age", CASE_ID
        )
