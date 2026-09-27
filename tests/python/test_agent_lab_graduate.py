"""CLI-level checks for `agent_lab.py graduate`'s promote/hold matrix.

Seed and candidate are SKILL.md-only components (no `has_code_changes`), so
building their overlays never runs the real build_pyz/pytest pipeline -- it
only checks out a disposable git worktree of this checkout and copies
`skills/cook`. This exercises the real `prepare_overlay` path while keeping
the test fast, and lets AC-8 assert that the real checkout is never touched.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

import agent_lab_candidate
from agent_lab import main
from agent_lab_candidate import CODE_PREFIX, CommandRunner
from agent_lab_tilth import REQUIRED_SKILL


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKOUT_SKILL_MD = REPO_ROOT / "skills" / "cook" / "SKILL.md"


def _git_status_for_cook_paths() -> str:
    """Snapshot `git status --porcelain` for the two trees a build can touch."""
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", "skills/cook", "src/easy_cheese/skills/cook"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _fake_candidate_run(calls: list[list[str]], *, fail_on: str | None = None) -> CommandRunner:
    """A `_default_run` stand-in: logs argv, simulates build_pyz/render/pytest
    success, and can fail on the step whose argv contains `fail_on`.
    """

    def run(argv: Sequence[str], cwd: Path) -> "subprocess.CompletedProcess[str]":
        calls.append(list(argv))
        joined = " ".join(argv)
        if fail_on is not None and fail_on in joined:
            return subprocess.CompletedProcess(argv, 1, "", "simulated failure")
        if "render_generated_regions.py" in joined:
            commands_md = cwd / "skills" / "cook" / "references" / "commands.md"
            _ = commands_md.write_text("REGENERATED-MARKER\n", encoding="utf-8")
        if "build_pyz.py" in joined and "--out-dir" in argv:
            out_dir = Path(argv[argv.index("--out-dir") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            _ = (out_dir / "cook.pyz").write_bytes(b"fake-pyz")
        return subprocess.CompletedProcess(argv, 0, "", "")

    return run

FAKE_RUN_GRADUATE = '''#!/usr/bin/env python3
import argparse, json, os, sys
from pathlib import Path

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

control = json.loads(Path(os.environ["FAKE_RUN_GRADUATE_CONTROL"]).read_text())
call_log_path = control.get("call_log")
if call_log_path:
    with Path(call_log_path).open("a") as handle:
        handle.write(json.dumps({"tasks": args.tasks, "models": args.models}) + "\\n")
modes = json.loads(Path(args.modes_json).read_text())
plugin_dir = Path(modes[0]["plugin_dir"])
skill_md = (plugin_dir / "skills" / "cook" / "SKILL.md").read_text(encoding="utf-8")
marker = ""
for candidate_marker in control["rows_by_marker_model"]:
    if candidate_marker in skill_md:
        marker = candidate_marker
        break
row = control["rows_by_marker_model"][marker][args.models]

lines = []
for task_id in args.tasks.split(","):
    entry = dict(row)
    entry.setdefault("task", task_id)
    entry.setdefault("model", args.models)
    lines.append(json.dumps(entry))
Path(args.output).write_text("\\n".join(lines) + "\\n")
'''


def _row(*, correct: bool, input_tokens: int) -> dict[str, object]:
    return {
        "correct": correct,
        "error": "",
        "skills": [REQUIRED_SKILL],
        "input_tokens": input_tokens,
        "output_tokens": 0,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "workspace_diff_lines": 4,
        "reference_changed_lines": 4,
        "lint_ok": True,
    }


def _write_skill_md_component(base_dir: Path, marker: str, *, include_commands_py: bool = False) -> Path:
    skill_dir = base_dir / "skills" / "cook"
    skill_dir.mkdir(parents=True)
    _ = (skill_dir / "SKILL.md").write_text(f"{marker} component text.", encoding="utf-8")
    if include_commands_py:
        commands_path = base_dir / CODE_PREFIX / "commands.py"
        commands_path.parent.mkdir(parents=True, exist_ok=True)
        _ = commands_path.write_text(f'"""Command surface marker: {marker}."""\n', encoding="utf-8")
    return base_dir


def _run_graduate_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows_by_marker_model: dict[str, dict[str, dict[str, object]]],
    models: str,
    seed_commands_py: bool = False,
    candidate_commands_py: bool = False,
    candidate_run: CommandRunner | None = None,
    call_log: Path | None = None,
) -> tuple[int, Path]:
    tilth_root = tmp_path / "tilth"
    benchmark_dir = tilth_root / "benchmark"
    benchmark_dir.mkdir(parents=True)
    _ = (benchmark_dir / "run.py").write_text(FAKE_RUN_GRADUATE, encoding="utf-8")
    control = tmp_path / "run_control.json"
    control_payload: dict[str, object] = {"rows_by_marker_model": rows_by_marker_model}
    if call_log is not None:
        control_payload["call_log"] = str(call_log)
    _ = control.write_text(json.dumps(control_payload), encoding="utf-8")
    monkeypatch.setenv("FAKE_RUN_GRADUATE_CONTROL", str(control))
    if candidate_run is not None:
        monkeypatch.setattr(agent_lab_candidate, "_default_run", candidate_run)

    seed_dir = _write_skill_md_component(tmp_path / "seed", "SEED", include_commands_py=seed_commands_py)
    candidate_dir = _write_skill_md_component(
        tmp_path / "candidate", "CANDIDATE", include_commands_py=candidate_commands_py
    )

    holdout = tmp_path / "holdout.json"
    _ = holdout.write_text(
        json.dumps(
            {"version": 1, "tasks": [{"id": "h1", "split": "holdout"}, {"id": "h2", "split": "holdout"}]}
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "graduation"

    code = main(
        [
            "graduate", "--seed", str(seed_dir), "--candidate", str(candidate_dir),
            "--holdout", str(holdout), "--tilth-root", str(tilth_root), "--models", models,
            "--output-dir", str(output_dir),
        ]
    )
    return code, output_dir


def test_candidate_nondominated_and_strictly_better_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    before_bytes = CHECKOUT_SKILL_MD.read_bytes()
    before_mtime = CHECKOUT_SKILL_MD.stat().st_mtime_ns
    before_status = _git_status_for_cook_paths()
    build_calls: list[list[str]] = []

    code, output_dir = _run_graduate_cli(
        tmp_path,
        monkeypatch,
        rows_by_marker_model={
            "SEED": {
                "sonnet": _row(correct=False, input_tokens=100),
                "opus": _row(correct=False, input_tokens=100),
                "fable": _row(correct=False, input_tokens=100),
            },
            "CANDIDATE": {
                "sonnet": _row(correct=True, input_tokens=100),
                "opus": _row(correct=True, input_tokens=100),
                "fable": _row(correct=True, input_tokens=100),
            },
        },
        models="sonnet,opus,fable",
        seed_commands_py=True,
        candidate_commands_py=True,
        candidate_run=_fake_candidate_run(build_calls),
    )

    assert code == 0
    result = cast(dict[str, object], json.loads((output_dir / "graduation.json").read_text(encoding="utf-8")))
    assert result["verdict"] == "promote"
    best_skill_md = output_dir / "best_candidate" / "skills" / "cook" / "SKILL.md"
    assert best_skill_md.read_text(encoding="utf-8") == "CANDIDATE component text."
    best_commands_py = output_dir / "best_candidate" / CODE_PREFIX / "commands.py"
    assert "CANDIDATE" in best_commands_py.read_text(encoding="utf-8")
    assert build_calls, "a changed commands.py component never ran the fake build seam"

    # AC-8: building disposable overlays from the checkout never touches it.
    assert CHECKOUT_SKILL_MD.read_bytes() == before_bytes
    assert CHECKOUT_SKILL_MD.stat().st_mtime_ns == before_mtime
    assert _git_status_for_cook_paths() == before_status


def test_candidate_dominated_on_one_model_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, output_dir = _run_graduate_cli(
        tmp_path,
        monkeypatch,
        rows_by_marker_model={
            "SEED": {
                "sonnet": _row(correct=False, input_tokens=100),
                "opus": _row(correct=False, input_tokens=100),
                "fable": _row(correct=False, input_tokens=100),
            },
            "CANDIDATE": {
                # Better on sonnet, but strictly worse (more tokens, same
                # correctness) on opus: the seed dominates there. fable is
                # equal on both axes, so it decides neither way.
                "sonnet": _row(correct=True, input_tokens=100),
                "opus": _row(correct=False, input_tokens=200),
                "fable": _row(correct=False, input_tokens=100),
            },
        },
        models="sonnet,opus,fable",
    )

    assert code == 2
    printed = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert printed["verdict"] == "hold"
    # A hold verdict writes neither best_candidate/ nor graduation.json.
    assert not (output_dir / "best_candidate").exists()
    assert not (output_dir / "graduation.json").exists()


def test_candidate_equal_to_seed_on_every_model_holds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code, output_dir = _run_graduate_cli(
        tmp_path,
        monkeypatch,
        rows_by_marker_model={
            "SEED": {
                "sonnet": _row(correct=False, input_tokens=100),
                "opus": _row(correct=False, input_tokens=100),
                "fable": _row(correct=False, input_tokens=100),
            },
            "CANDIDATE": {
                "sonnet": _row(correct=False, input_tokens=100),
                "opus": _row(correct=False, input_tokens=100),
                "fable": _row(correct=False, input_tokens=100),
            },
        },
        models="sonnet,opus,fable",
    )

    assert code == 2
    printed = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert printed["verdict"] == "hold"
    assert not (output_dir / "best_candidate").exists()
    assert not (output_dir / "graduation.json").exists()


def test_candidate_build_failure_holds_and_never_calls_the_benchmark_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both sides carry a changed `commands.py` and share one failing build
    seam, so both overlay builds guard with BUILD_GUARD before `graduate`
    ever evaluates a real row: the fake tilth `run.py`'s call log must stay
    empty, proving the guard short-circuits ahead of any benchmark spend.
    """
    call_log = tmp_path / "runner_calls.jsonl"

    code, output_dir = _run_graduate_cli(
        tmp_path,
        monkeypatch,
        rows_by_marker_model={
            "SEED": {"sonnet": _row(correct=False, input_tokens=100)},
            "CANDIDATE": {"sonnet": _row(correct=True, input_tokens=50)},
        },
        models="sonnet,opus,fable",
        seed_commands_py=True,
        candidate_commands_py=True,
        candidate_run=_fake_candidate_run([], fail_on="build_pyz.py --write-generated"),
        call_log=call_log,
    )

    assert code == 2
    assert not call_log.exists() or call_log.read_text(encoding="utf-8") == ""
    assert not (output_dir / "best_candidate").exists()
    assert not (output_dir / "graduation.json").exists()


def test_models_missing_a_required_alias_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AC-7 / decision F-4: graduation always grades sonnet, opus, and fable;
    a `--models` set missing one of the three is rejected before any build
    or benchmark run, not silently graded on a partial set.
    """
    seed_dir = _write_skill_md_component(tmp_path / "seed", "SEED")
    candidate_dir = _write_skill_md_component(tmp_path / "candidate", "CANDIDATE")
    holdout = tmp_path / "holdout.json"
    _ = holdout.write_text(
        json.dumps({"version": 1, "tasks": [{"id": "h1", "split": "holdout"}]}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "graduation"

    code = main(
        [
            "graduate", "--seed", str(seed_dir), "--candidate", str(candidate_dir),
            "--holdout", str(holdout), "--tilth-root", str(tmp_path / "tilth"),
            "--models", "sonnet,opus", "--output-dir", str(output_dir),
        ]
    )

    assert code == 2
    assert "fable" in capsys.readouterr().err
    assert not output_dir.exists()
