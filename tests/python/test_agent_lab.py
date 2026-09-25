"""Offline checks for the real-agent evaluator using a scripted fake `claude`."""

from __future__ import annotations

import json
import stat
import subprocess
from importlib import import_module
from pathlib import Path
from typing import cast

import pytest

from agent_lab import (
    ClaudeRunner,
    evaluate_agent_candidate,
    load_task_set,
    main,
    prepare_workspace,
    snapshot_files,
)
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
