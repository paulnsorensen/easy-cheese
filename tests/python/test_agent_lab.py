"""Offline checks for the real-agent evaluator using a scripted fake `claude`."""

from __future__ import annotations

import hashlib
import json
import stat
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import cast

import pytest

import agent_lab
from agent_lab import (
    ClaudeRunner,
    evaluate_agent_candidate,
    load_task_set,
    main,
    prepare_workspace,
    snapshot_files,
)
from agent_lab_candidate import TOKEN_BUDGET_GUARD
from agent_lab_tilth import REQUIRED_SKILL
from prompt_lab import BudgetExhausted, PromptLabError


FIXTURE = Path(__file__).parents[1] / "fixtures" / "prompt_lab" / "agent_tasks.json"
CLEAN_REPO = FIXTURE.parent / "repo"

FAKE_CLAUDE = '''#!/usr/bin/env python3
import json, os, shutil, sys
from pathlib import Path
argv = sys.argv[1:]
control = json.loads(Path(os.environ["FAKE_CLAUDE_CONTROL"]).read_text())
def value(flag):
    return argv[argv.index(flag) + 1] if flag in argv else None
candidate = value("--append-system-prompt") or ""
prompt = argv[argv.index("--") + 1] if "--" in argv else sys.stdin.read()
with Path(control["log"]).open("a") as handle:
    handle.write(json.dumps({"argv": argv, "cwd": os.getcwd(), "candidate": candidate,
        "prompt": prompt, "claudecode": "CLAUDECODE" in os.environ}) + "\\n")
if value("--output-format") == "text":
    print(control.get("reflection", "Add the word FIX to the instructions."))
    sys.exit(0)
mode = control["mode"]
if mode == "crash":
    sys.exit(3)
if mode == "garbage":
    print("not json")
    sys.exit(0)
fix = mode == "fix" or (mode == "fix-if-marker" and "FIX" in candidate)
if fix:
    shutil.copy(Path(control["clean_repo"]) / "calc.py", Path.cwd() / "calc.py")
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
    "result": control.get("result_text", "Fixed calc.py" if fix else "No change made."),
    "total_cost_usd": 0.01, "num_turns": 3, "duration_ms": 5}))
'''


class Fake:
    """A fake `claude` binary plus the control file and invocation log it uses."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, **extra: object) -> None:
        binary_dir = tmp_path / "bin"
        binary_dir.mkdir()
        self.binary: Path = binary_dir / "claude"
        _ = self.binary.write_text(FAKE_CLAUDE, encoding="utf-8")
        self.binary.chmod(self.binary.stat().st_mode | stat.S_IXUSR)
        self.log: Path = tmp_path / "calls.jsonl"
        control = tmp_path / "control.json"
        _ = control.write_text(
            json.dumps({"mode": mode, "log": str(self.log), "clean_repo": str(CLEAN_REPO), **extra}),
            encoding="utf-8",
        )
        monkeypatch.setenv("FAKE_CLAUDE_CONTROL", str(control))
        monkeypatch.setenv("CLAUDECODE", "1")

    def runner(self, max_runs: int = 10) -> ClaudeRunner:
        return ClaudeRunner(
            binary=str(self.binary), model="fake-model", max_runs=max_runs, max_budget_usd=0.1, timeout_seconds=30
        )

    def calls(self) -> list[dict[str, object]]:
        if not self.log.exists():
            return []
        return [
            cast(dict[str, object], json.loads(line))
            for line in self.log.read_text(encoding="utf-8").splitlines()
            if line
        ]


def _first_run(result: dict[str, object]) -> dict[str, object]:
    task_results = cast(list[dict[str, object]], result["task_results"])
    return cast(list[dict[str, object]], task_results[0]["runs"])[0]


def test_fixture_validates_and_each_mutation_breaks_its_own_test(tmp_path: Path) -> None:
    task_set = load_task_set(FIXTURE)
    assert {task.split for task in task_set.tasks} == {"train", "validation", "holdout"}
    for task in task_set.tasks:
        clean = subprocess.run(list(task.test_command), cwd=CLEAN_REPO, capture_output=True, check=False)
        assert clean.returncode == 0, task.identifier
        workspace = prepare_workspace(task_set, task, tmp_path / task.identifier)
        broken = subprocess.run(list(task.test_command), cwd=workspace, capture_output=True, check=False)
        assert broken.returncode != 0, task.identifier


def test_invalid_task_sets_are_rejected(tmp_path: Path) -> None:
    payload = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))
    tasks = cast(list[dict[str, object]], payload["tasks"])
    (tmp_path / "repo").mkdir()
    _ = (tmp_path / "repo" / "calc.py").write_text("nothing here\n", encoding="utf-8")
    path = tmp_path / "tasks.json"
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PromptLabError, match="mutation target not found"):
        _ = load_task_set(path)
    tasks[1]["family"] = tasks[0]["family"]
    _ = (tmp_path / "repo" / "calc.py").write_bytes((CLEAN_REPO / "calc.py").read_bytes())
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PromptLabError, match="leaks across splits"):
        _ = load_task_set(path)
    tasks[1]["family"] = "clamp"
    tasks[0]["mutations"] = [{"file_path": "../calc.py", "original": "a", "mutated": "b"}]
    _ = path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PromptLabError, match="inside the repo"):
        _ = load_task_set(path)


def test_fixing_agent_scores_one_and_leaves_no_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake(tmp_path, monkeypatch, "fix")
    task_set = load_task_set(FIXTURE)
    fixture_before = snapshot_files(CLEAN_REPO)
    result = evaluate_agent_candidate("Candidate text.", task_set, task_set.split("train"), fake.runner())
    assert result["aggregate_score"] == 1.0
    assert result["runs"] == 1
    assert result["cost_usd"] == pytest.approx(0.01)
    run = _first_run(result)
    assert run["score"] == 1.0
    assert run["failures"] == []
    assert run["changed_files"] == ["calc.py"]
    assert run["turns"] == 3
    assert run["workspace"] == ""
    assert snapshot_files(CLEAN_REPO) == fixture_before
    call = fake.calls()[0]
    assert call["candidate"] == "Candidate text."
    assert call["prompt"] == task_set.split("train")[0].prompt
    assert call["claudecode"] is False
    workspace = Path(cast(str, call["cwd"]))
    assert workspace != CLEAN_REPO.resolve()
    assert not workspace.exists()
    argv = cast(list[str], call["argv"])
    assert "--max-budget-usd" in argv and "--dangerously-skip-permissions" in argv


def test_idle_agent_scores_zero_with_test_diagnostics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake(tmp_path, monkeypatch, "nofix")
    task_set = load_task_set(FIXTURE)
    result = evaluate_agent_candidate("Candidate text.", task_set, task_set.split("validation"), fake.runner())
    assert result["aggregate_score"] == 0.0
    run = _first_run(result)
    assert run["changed_files"] == []
    assert run["failures"] == ["test command exited 1"]
    assert "FAIL" in cast(str, run["test_output_tail"])


def test_forbidden_reply_text_fails_even_when_tests_pass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake(tmp_path, monkeypatch, "fix", result_text="I cannot explain, but it passes now.")
    task_set = load_task_set(FIXTURE)
    result = evaluate_agent_candidate("Candidate text.", task_set, task_set.split("train"), fake.runner())
    assert result["aggregate_score"] == 0.0
    assert _first_run(result)["failures"] == ["forbidden text present: I cannot"]


@pytest.mark.parametrize(
    ("mode", "error"),
    [("crash", "agent exited 3"), ("garbage", "agent output was not a JSON object")],
)
def test_agent_failures_are_outcomes_not_exceptions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str, error: str
) -> None:
    fake = Fake(tmp_path, monkeypatch, mode)
    task_set = load_task_set(FIXTURE)
    result = evaluate_agent_candidate("Candidate text.", task_set, task_set.split("train"), fake.runner())
    run = _first_run(result)
    assert run["score"] == 0.0
    assert run["agent_error"] == error
    assert run["cost_usd"] == 0.0


def test_missing_binary_and_exhausted_budget_stop_loudly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(PromptLabError, match="agent binary not found"):
        _ = ClaudeRunner(binary="agent-lab-no-such-binary", model="m", max_runs=1, max_budget_usd=0.1, timeout_seconds=1)
    fake = Fake(tmp_path, monkeypatch, "fix")
    task_set = load_task_set(FIXTURE)
    with pytest.raises(BudgetExhausted):
        _ = evaluate_agent_candidate("Candidate text.", task_set, task_set.tasks, fake.runner(max_runs=1))
    assert len(fake.calls()) == 1


def test_cli_evaluate_keeps_workspaces_and_rejects_reuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Fake(tmp_path, monkeypatch, "fix")
    prompt = tmp_path / "prompt.md"
    _ = prompt.write_text("Fix it.", encoding="utf-8")
    output = tmp_path / "eval"
    argv = [
        "evaluate", "--tasks", str(FIXTURE), "--prompt", str(prompt), "--split", "holdout",
        "--model", "fake-model", "--output-dir", str(output), "--claude-bin", str(fake.binary),
        "--keep-workspaces",
    ]
    assert main(argv) == 0
    artifact = cast(dict[str, object], json.loads((output / "result.json").read_text(encoding="utf-8")))
    assert artifact["split"] == "holdout"
    assert artifact["aggregate_score"] == 1.0
    assert artifact["tasks_sha256"] and artifact["prompt_sha256"]
    run = _first_run(artifact)
    assert Path(cast(str, run["workspace"])).is_dir()
    assert (Path(cast(str, run["workspace"])) / "calc.py").read_bytes() == (CLEAN_REPO / "calc.py").read_bytes()
    assert main(argv) == 2
    assert main([*argv[:-1], "--max-budget-usd", "50", "--output-dir", str(tmp_path / "other")]) == 2
    assert not (tmp_path / "other").exists()


def test_real_gepa_optimization_sees_only_train_and_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        _ = import_module("gepa.optimize_anything")
    except ImportError:
        pytest.skip("gepa is not installed")
    fake = Fake(tmp_path, monkeypatch, "fix-if-marker")
    seed = tmp_path / "seed.md"
    _ = seed.write_text("Seed candidate without the marker.", encoding="utf-8")
    output = tmp_path / "optimization"
    code = main([
        "optimize", "--tasks", str(FIXTURE), "--seed-prompt", str(seed), "--model", "fake-model",
        "--output-dir", str(output), "--claude-bin", str(fake.binary), "--max-runs", "40",
        "--max-metric-calls", "3",
    ])
    artifact = cast(dict[str, object], json.loads((output / "result.json").read_text(encoding="utf-8")))
    task_set = load_task_set(FIXTURE)
    holdout_prompt = task_set.split("holdout")[0].prompt
    calls = fake.calls()
    assert calls
    assert all(call["prompt"] != holdout_prompt for call in calls)
    assert cast(int, artifact["runs"]) == len(calls)
    assert cast(dict[str, object], artifact["seed_result"])["aggregate_score"] == 0.0
    assert artifact["evaluation_records"]
    exported = (output / "best_candidate.md").exists()
    assert artifact["exported"] is exported
    assert code == (0 if exported else 2)
    if exported:
        assert "FIX" in (output / "best_candidate.md").read_text(encoding="utf-8")
        assert cast(float, cast(dict[str, object], artifact["best_result"])["aggregate_score"]) > 0.0


FAKE_RUN_OPT = '''#!/usr/bin/env python3
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
args.tasks = args.tasks.split(",")

control = json.loads(Path(os.environ["FAKE_RUN_OPT_CONTROL"]).read_text())
modes = json.loads(Path(args.modes_json).read_text())
plugin_dir = Path(modes[0]["plugin_dir"])
skill_md = (plugin_dir / "skills" / "cook" / "SKILL.md").read_text(encoding="utf-8")
row = control["default_row"]
marker = ""
for candidate_marker, candidate_row in control["row_by_marker"].items():
    if candidate_marker in skill_md:
        row = candidate_row
        marker = candidate_marker
        break

with Path(control["log"]).open("a") as handle:
    handle.write(json.dumps({"models": args.models, "tasks": args.tasks, "marker": marker}) + "\\n")

lines = []
for task_id in args.tasks:
    entry = dict(row)
    entry.setdefault("task", task_id)
    entry.setdefault("model", args.models)
    lines.append(json.dumps(entry))
Path(args.output).write_text("\\n".join(lines) + "\\n")
'''


class FakeOptimizeRun:
    """A scripted `benchmark/run.py` that scores a row by the SKILL.md marker text
    found in the candidate's overlay, so each unique GEPA-proposed candidate
    gets a deterministic, controllable score.
    """

    def __init__(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        *,
        row_by_marker: dict[str, dict[str, object]],
        default_row: dict[str, object],
    ) -> None:
        self.tilth_root: Path = tmp_path / "opt_tilth"
        benchmark_dir = self.tilth_root / "benchmark"
        benchmark_dir.mkdir(parents=True)
        _ = (benchmark_dir / "run.py").write_text(FAKE_RUN_OPT, encoding="utf-8")
        self.log: Path = tmp_path / "opt_run_calls.jsonl"
        control = tmp_path / "opt_run_control.json"
        _ = control.write_text(
            json.dumps({"log": str(self.log), "row_by_marker": row_by_marker, "default_row": default_row}),
            encoding="utf-8",
        )
        monkeypatch.setenv("FAKE_RUN_OPT_CONTROL", str(control))

    def calls(self) -> list[dict[str, object]]:
        if not self.log.exists():
            return []
        return [cast(dict[str, object], json.loads(line)) for line in self.log.read_text(encoding="utf-8").splitlines() if line]


def _opt_row(*, correct: bool, input_tokens: int) -> dict[str, object]:
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


def _skill_md_sha256(text: str) -> str:
    payload = json.dumps({"skills/cook/SKILL.md": text}, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass
class _FakeEngineConfig:
    max_metric_calls: int
    parallel: bool
    cache_evaluation: bool
    frontier_type: str


@dataclass
class _FakeReflectionConfig:
    reflection_lm: object


@dataclass
class _FakeGEPAConfig:
    engine: _FakeEngineConfig
    reflection: _FakeReflectionConfig


def _fake_optimize_anything(
    *,
    seed_candidate: dict[str, str],
    evaluator: Callable[[dict[str, str], dict[str, object]], tuple[float, dict[str, object]]],
    dataset: list[dict[str, object]],
    valset: list[dict[str, object]],
    objective: str,
    config: _FakeGEPAConfig,
) -> None:
    """Deterministic stand-in for gepa.optimize_anything: propose three
    reflection candidates and score each one on the full train and
    validation split, so the CLI wiring runs without the optional `gepa`
    dependency installed.
    """
    del objective
    engine = config.engine
    # Assert the constants _run_optimize_tilth always passes, so this stub
    # also proves the CLI wiring builds the engine config it claims to.
    assert (engine.parallel, engine.cache_evaluation, engine.frontier_type) == (False, True, "objective")
    reflection_lm = cast(Callable[[str], str], config.reflection.reflection_lm)
    key = next(iter(seed_candidate))
    for _ in range(3):
        text = reflection_lm("").strip().strip("`").strip()
        candidate = dict(seed_candidate)
        candidate[key] = text
        for example in dataset:
            _ = evaluator(candidate, example)
        for example in valset:
            _ = evaluator(candidate, example)


def _optimize_tilth_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    row_by_marker: dict[str, dict[str, object]],
    default_row: dict[str, object],
    reflection_markers: list[str],
) -> tuple[int, Path, FakeOptimizeRun]:
    monkeypatch.setattr(
        agent_lab,
        "_gepa_module_override",
        (_FakeEngineConfig, _FakeGEPAConfig, _FakeReflectionConfig, _fake_optimize_anything),
    )
    fake = FakeOptimizeRun(tmp_path, monkeypatch, row_by_marker=row_by_marker, default_row=default_row)
    reflection_texts = tmp_path / "reflection.json"
    _ = reflection_texts.write_text(
        json.dumps({"texts": [f"{marker} candidate." for marker in reflection_markers]}), encoding="utf-8"
    )
    monkeypatch.setenv("AGENT_LAB_FAKE_REFLECTION", str(reflection_texts))

    seed_dir = tmp_path / "seed"
    (seed_dir / "skills" / "cook").mkdir(parents=True)
    _ = (seed_dir / "skills" / "cook" / "SKILL.md").write_text("Seed prompt with no marker text.", encoding="utf-8")

    tasks_path = tmp_path / "tasks.json"
    tasks = {"version": 1, "tasks": [{"id": "train-1", "split": "train"}, {"id": "val-1", "split": "validation"}]}
    _ = tasks_path.write_text(json.dumps(tasks), encoding="utf-8")
    output = tmp_path / "optimization"

    code = main(
        [
            "optimize", "--runner", "tilth", "--tasks", str(tasks_path), "--model", "unused-model",
            "--output-dir", str(output), "--seed", str(seed_dir), "--tilth-root", str(fake.tilth_root),
            "--search-model", "search-m", "--validation-model", "validation-m", "--max-metric-calls", "60",
        ]
    )
    return code, output, fake


def test_cli_optimize_tilth_runner_pareto_front_and_model_routing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A: perfect but expensive. B: cheap but wrong. C: expensive and wrong,
    # so it is dominated by both A (better correctness, same tokens) and B
    # (same correctness, better tokens).
    code, output, fake = _optimize_tilth_cli(
        tmp_path,
        monkeypatch,
        row_by_marker={
            "MARKER-A": _opt_row(correct=True, input_tokens=5000),
            "MARKER-B": _opt_row(correct=False, input_tokens=50),
            "MARKER-C": _opt_row(correct=False, input_tokens=5000),
        },
        default_row=_opt_row(correct=False, input_tokens=5000),
        reflection_markers=["MARKER-A", "MARKER-B", "MARKER-C"],
    )
    assert code == 0

    result = cast(dict[str, object], json.loads((output / "result.json").read_text(encoding="utf-8")))
    front = cast(list[dict[str, object]], result["pareto_front"])
    front_shas = {cast(str, entry["candidate_sha256"]) for entry in front}
    models_by_sha = {cast(str, entry["candidate_sha256"]): cast(list[str], entry["models"]) for entry in front}
    calls = fake.calls()
    assert calls
    train_calls = [entry for entry in calls if cast(list[str], entry["tasks"]) == ["train-1"]]
    validation_calls = [entry for entry in calls if cast(list[str], entry["tasks"]) == ["val-1"]]
    assert train_calls
    assert validation_calls
    assert all(entry["models"] == "search-m" for entry in train_calls)
    assert all(entry["models"] == "validation-m" for entry in validation_calls)

    markers_seen = {cast(str, entry["marker"]) for entry in calls}
    assert markers_seen == {"MARKER-A", "MARKER-B", "MARKER-C"}

    assert _skill_md_sha256("MARKER-A candidate.") in front_shas
    assert _skill_md_sha256("MARKER-B candidate.") in front_shas
    assert _skill_md_sha256("MARKER-C candidate.") not in front_shas
    assert models_by_sha[_skill_md_sha256("MARKER-A candidate.")] == ["search-m", "validation-m"]


def test_cli_candidate_build_guard_prints_json_and_exits_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    candidate_dir = tmp_path / "candidate"
    skill_dir = candidate_dir / "skills" / "cook"
    skill_dir.mkdir(parents=True)
    oversized = "word " * 20_000
    _ = (skill_dir / "SKILL.md").write_text(oversized, encoding="utf-8")
    out = tmp_path / "overlay"

    code = main(["candidate", "build", str(candidate_dir), "--out", str(out)])

    assert code == 2
    captured = cast(dict[str, object], json.loads(capsys.readouterr().out))
    assert captured["guard"] == TOKEN_BUDGET_GUARD
    assert not out.exists()


FAKE_GH_MINE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
control = json.loads(Path(os.environ["FAKE_GH_MINE_CONTROL"]).read_text())
if argv[:2] == ["pr", "list"]:
    print(json.dumps(control["pr_list"]))
    sys.exit(0)
if argv[0] == "api":
    sha = argv[1].rsplit("/", 1)[-1]
    parents = control["parents"].get(sha, [])
    print(json.dumps({"parents": [{"sha": parent} for parent in parents]}))
    sys.exit(0)
if argv[:2] == ["pr", "diff"]:
    number = argv[2]
    print(control["diffs"][number])
    sys.exit(0)
print(f"no fake gh response for: {argv}", file=sys.stderr)
sys.exit(1)
'''

FAKE_CHECK_TASK = '''#!/usr/bin/env python3
import argparse, json
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument("--tasks-json")
args = parser.parse_args()
payload = json.loads(Path(args.tasks_json).read_text())
for task in payload["tasks"]:
    print(f"PASS {task['id']}: baseline passed; mutation failed")
'''


def _tasks_mine_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    pr_list: list[dict[str, object]],
    parents: dict[str, list[str]],
    diffs: dict[str, str],
) -> tuple[int, Path]:
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    gh_binary = binary_dir / "gh"
    _ = gh_binary.write_text(FAKE_GH_MINE, encoding="utf-8")
    gh_binary.chmod(gh_binary.stat().st_mode | stat.S_IXUSR)
    control = tmp_path / "gh_control.json"
    _ = control.write_text(
        json.dumps({"pr_list": pr_list, "parents": parents, "diffs": diffs}), encoding="utf-8"
    )
    monkeypatch.setenv("FAKE_GH_MINE_CONTROL", str(control))

    tilth_root = tmp_path / "tilth"
    benchmark_dir = tilth_root / "benchmark"
    benchmark_dir.mkdir(parents=True)
    _ = (benchmark_dir / "check_task.py").write_text(FAKE_CHECK_TASK, encoding="utf-8")

    out = tmp_path / "mined_tasks.json"
    code = main(
        [
            "tasks", "mine", "--repo", "acme/widgets", "--out", str(out),
            "--tilth-root", str(tilth_root), "--gh-bin", str(gh_binary),
        ]
    )
    return code, out


# One merged `fix:` PR that touches `widgets/core.py` and its test, used by
# test_cli_tasks_mine_writes_a_task_set_that_validate_accepts.
WIDGET_FIX_HEAD_SHA = "1" * 40
WIDGET_FIX_BASE_SHA = "0" * 40
WIDGET_FIX_DIFF = (
    "diff --git a/widgets/core.py b/widgets/core.py\n"
    "index abc123..def456 100644\n"
    "--- a/widgets/core.py\n"
    "+++ b/widgets/core.py\n"
    "@@ -1,3 +1,3 @@\n"
    " def process(items):\n"
    "-    return items[0]\n"
    "+    return items[0] if items else []\n"
    "diff --git a/tests/test_core.py b/tests/test_core.py\n"
    "index 111111..222222 100644\n"
    "--- a/tests/test_core.py\n"
    "+++ b/tests/test_core.py\n"
    "@@ -1,2 +1,5 @@\n"
    " def test_process_nonempty():\n"
    "     assert process([1]) == 1\n"
    "+\n"
    "+def test_process_empty():\n"
    "+    assert process([]) == []\n"
)
WIDGET_FIX_PR_LIST: list[dict[str, object]] = [
    {
        "number": 1,
        "title": "fix: crash on empty input",
        "authorAssociation": "OWNER",
        "body": (
            "Calling widget.process([]) crashes with IndexError. "
            "Fix process() so empty input returns an empty list."
        ),
        "mergeCommit": {"oid": WIDGET_FIX_HEAD_SHA},
        "baseRefOid": "unused",
        "headRefOid": "unused",
        "closingIssuesReferences": [],
        "files": [{"path": "widgets/core.py"}, {"path": "tests/test_core.py"}],
        "mergedAt": "2026-01-01T00:00:00Z",
    }
]


def test_cli_tasks_mine_writes_a_task_set_that_validate_accepts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    code, out = _tasks_mine_cli(
        tmp_path,
        monkeypatch,
        pr_list=WIDGET_FIX_PR_LIST,
        parents={WIDGET_FIX_HEAD_SHA: [WIDGET_FIX_BASE_SHA]},
        diffs={"1": WIDGET_FIX_DIFF},
    )

    assert code == 0
    payload = cast(dict[str, object], json.loads(out.read_text(encoding="utf-8")))
    assert payload["version"] == 1
    tasks = cast(list[dict[str, object]], payload["tasks"])
    assert len(tasks) == 1
    assert tasks[0]["id"] == "acme-widgets-1"

    assert main(["validate", str(out)]) == 0
