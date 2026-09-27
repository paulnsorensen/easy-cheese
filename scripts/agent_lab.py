"""Development-only real-agent evaluator for skill prompts.

Each task runs a headless coding agent once inside a disposable copy of a fixture
repository. The task's bug mutations are applied first; the task's own test
command grades the resulting tree afterwards. This is the outcome-graded
counterpart to the conversation-state proxy in prompt_lab.py.
"""

from __future__ import annotations

from collections.abc import Sequence
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Callable, Protocol, cast, final

from prompt_lab import (
    MAX_REPEATS,
    MAX_TEXT,
    SPLITS,
    BudgetExhausted,
    JsonObject,
    Message,
    PromptLabError,
    ProviderError,
    new_output_dir,
    require_mapping,
    require_text,
    sha256_hex,
    write_json,
)


MAX_RUNS = 1_000
MAX_BUDGET_USD = 5.0
MAX_TIMEOUT_SECONDS = 3_600
MAX_TAIL = 2_000
IGNORED_DIRS = frozenset({"__pycache__", ".git", ".claude", ".pytest_cache"})
DEFAULT_FORBIDDEN = ("I cannot", "I don't have access")


@dataclass(frozen=True)
class Mutation:
    """Replace `original` with `mutated` once to inject the bug the agent must fix."""

    file_path: str
    original: str
    mutated: str


@dataclass(frozen=True)
class AgentTask:
    identifier: str
    family: str
    split: str
    capability: str
    prompt: str
    mutations: tuple[Mutation, ...]
    test_command: tuple[str, ...]
    required_strings: tuple[str, ...]
    forbidden_strings: tuple[str, ...]


@dataclass(frozen=True)
class TaskSet:
    tasks: tuple[AgentTask, ...]
    provenance: str
    repo: Path

    def split(self, name: str) -> tuple[AgentTask, ...]:
        return tuple(task for task in self.tasks if task.split == name)


@dataclass(frozen=True)
class AgentRun:
    text: str
    cost_usd: float
    turns: int
    duration_ms: int
    error: str


@dataclass(frozen=True)
class AgentArgs:
    tasks: str
    model: str
    output_dir: str
    max_runs: int
    max_budget_usd: float
    timeout_seconds: int
    repeats: int
    claude_bin: str
    keep_workspaces: bool
    prompt: str = ""
    split: str = "validation"
    seed_prompt: str = ""
    max_metric_calls: int = 8
    reflection_model: str = ""


class AgentRunner(Protocol):
    runs: int
    cost_usd: float

    def run(self, candidate: str, prompt: str, workspace: Path) -> AgentRun: ...


def _list(value: object, label: str) -> list[object]:
    if not isinstance(value, list):
        raise PromptLabError(f"{label} must be a list")
    return cast(list[object], value)


def _strings(value: object, label: str) -> tuple[str, ...]:
    items = _list(value, label)
    if not all(isinstance(item, str) and item for item in items):
        raise PromptLabError(f"{label} must contain non-empty strings")
    return tuple(cast(str, item) for item in items)


def _mutation(value: object, label: str) -> Mutation:
    item = require_mapping(value, label)
    file_path = require_text(item.get("file_path"), f"{label}.file_path")
    if Path(file_path).is_absolute() or ".." in Path(file_path).parts:
        raise PromptLabError(f"{label}.file_path must stay inside the repo")
    return Mutation(
        file_path,
        require_text(item.get("original"), f"{label}.original"),
        require_text(item.get("mutated"), f"{label}.mutated"),
    )


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def load_task_set(path: Path) -> TaskSet:
    try:
        raw = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as error:
        raise PromptLabError(f"cannot read task set: {path}") from error
    root = require_mapping(raw, "task set")
    if root.get("version") != 1:
        raise PromptLabError("task set version must be 1")
    repo = path.parent / require_text(root.get("repo"), "task set repo")
    if not repo.is_dir():
        raise PromptLabError(f"task set repo is not a directory: {repo}")
    tasks_raw = _list(root.get("tasks"), "task set tasks")
    if not tasks_raw:
        raise PromptLabError("task set tasks must be a non-empty list")
    tasks: list[AgentTask] = []
    for index, task_raw in enumerate(tasks_raw):
        task = require_mapping(task_raw, f"tasks[{index}]")
        identifier = require_text(task.get("id"), f"tasks[{index}].id")
        split = require_text(task.get("split"), f"{identifier}.split")
        if split not in SPLITS:
            raise PromptLabError(f"{identifier}.split is invalid")
        mutations = tuple(
            _mutation(item, f"{identifier}.mutations[{position}]")
            for position, item in enumerate(_list(task.get("mutations", []), f"{identifier}.mutations"))
        )
        test_command = _strings(task.get("test_command"), f"{identifier}.test_command")
        if not test_command:
            raise PromptLabError(f"{identifier}.test_command must not be empty")
        tasks.append(
            AgentTask(
                identifier=identifier,
                family=require_text(task.get("family"), f"{identifier}.family"),
                split=split,
                capability=require_text(task.get("capability", "fix"), f"{identifier}.capability"),
                prompt=require_text(task.get("prompt"), f"{identifier}.prompt"),
                mutations=mutations,
                test_command=test_command,
                required_strings=_strings(task.get("required_strings", []), f"{identifier}.required_strings"),
                forbidden_strings=_strings(
                    task.get("forbidden_strings", list(DEFAULT_FORBIDDEN)), f"{identifier}.forbidden_strings"
                ),
            )
        )
    task_set = TaskSet(tuple(tasks), require_text(root.get("provenance"), "task set provenance"), repo)
    validate_task_set(task_set)
    return task_set


def validate_task_set(task_set: TaskSet) -> None:
    if any(not task_set.split(split) for split in SPLITS):
        raise PromptLabError("each split must be non-empty")
    identifiers = [task.identifier for task in task_set.tasks]
    if len(identifiers) != len(set(identifiers)):
        raise PromptLabError("task ids must be unique")
    family_splits: dict[str, str] = {}
    for task in task_set.tasks:
        if family_splits.setdefault(task.family, task.split) != task.split:
            raise PromptLabError(f"family {task.family!r} leaks across splits")
        for mutation in task.mutations:
            target = task_set.repo / mutation.file_path
            if not target.is_file():
                raise PromptLabError(f"{task.identifier} mutates a missing file: {mutation.file_path}")
            if mutation.original not in target.read_text(encoding="utf-8"):
                raise PromptLabError(f"{task.identifier} mutation target not found in {mutation.file_path}")


def prepare_workspace(task_set: TaskSet, task: AgentTask, workspace: Path) -> Path:
    """Copy the fixture repo to `workspace` and inject the task's bug."""
    _ = shutil.copytree(task_set.repo, workspace, ignore=shutil.ignore_patterns(*IGNORED_DIRS))
    for mutation in task.mutations:
        target = workspace / mutation.file_path
        content = target.read_text(encoding="utf-8")
        if mutation.original not in content:
            raise PromptLabError(f"mutation target not found in {mutation.file_path}")
        _ = target.write_text(content.replace(mutation.original, mutation.mutated, 1), encoding="utf-8")
    return workspace


def snapshot_files(workspace: Path) -> dict[str, str]:
    digests: dict[str, str] = {}
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if path.is_file() and not IGNORED_DIRS & set(relative.parts):
            digests[relative.as_posix()] = sha256_hex(path.read_bytes())
    return digests


def required_matches(required: str, text_lower: str) -> bool:
    """Substring match; `a|b` inside one entry means either alternative satisfies it."""
    alternates = [alt for alt in (item.strip() for item in required.split("|")) if alt]
    return any(alt.lower() in text_lower for alt in alternates)


def grade_workspace(
    task: AgentTask, workspace: Path, text: str, timeout_seconds: int
) -> tuple[float, list[str], str]:
    """Score 1.0 only when the test command passes and the reply text meets its string checks."""
    failures: list[str] = []
    text_lower = text.lower()
    for required in task.required_strings:
        if not required_matches(required, text_lower):
            failures.append(f"missing required text: {required}")
    for forbidden in task.forbidden_strings:
        if forbidden.lower() in text_lower:
            failures.append(f"forbidden text present: {forbidden}")
    try:
        completed = subprocess.run(
            list(task.test_command),
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 0.0, [*failures, f"test command failed to run: {type(error).__name__}"], ""
    tail = (completed.stdout + completed.stderr)[-MAX_TAIL:]
    if completed.returncode != 0:
        failures.append(f"test command exited {completed.returncode}")
    return (1.0 if not failures else 0.0), failures, tail


@final
class ClaudeRunner:
    """Run headless `claude -p` with the candidate appended to the system prompt."""

    def __init__(
        self, *, binary: str, model: str, max_runs: int, max_budget_usd: float, timeout_seconds: int
    ) -> None:
        resolved = shutil.which(binary)
        if resolved is None:
            raise PromptLabError(f"agent binary not found: {binary}")
        self._binary: str = resolved
        self._model: str = model
        self._max_runs: int = max_runs
        self._max_budget_usd: float = max_budget_usd
        self._timeout: int = timeout_seconds
        self.runs: int = 0
        self.cost_usd: float = 0.0

    def _take_run(self) -> None:
        if self.runs >= self._max_runs:
            raise BudgetExhausted("max-runs budget exhausted")
        self.runs += 1

    @staticmethod
    def _env() -> dict[str, str]:
        # CLAUDECODE guards interactive nesting; a headless subprocess is safe.
        return {key: value for key, value in os.environ.items() if key != "CLAUDECODE"}

    def run(self, candidate: str, prompt: str, workspace: Path) -> AgentRun:
        self._take_run()
        command = [
            self._binary,
            "-p",
            "--output-format",
            "json",
            "--model",
            self._model,
            "--max-budget-usd",
            f"{self._max_budget_usd:.2f}",
            "--no-session-persistence",
            "--dangerously-skip-permissions",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--append-system-prompt",
            candidate,
            "--",
            prompt,
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                env=self._env(),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return AgentRun("", 0.0, 0, self._timeout * 1000, "agent timed out")
        except OSError as error:
            raise ProviderError("agent launch failed") from error
        if completed.returncode != 0:
            return AgentRun(completed.stdout[-MAX_TAIL:], 0.0, 0, 0, f"agent exited {completed.returncode}")
        try:
            payload = require_mapping(cast(object, json.loads(completed.stdout)), "agent output")
        except (json.JSONDecodeError, PromptLabError):
            return AgentRun(completed.stdout[-MAX_TAIL:], 0.0, 0, 0, "agent output was not a JSON object")
        cost = _number(payload.get("total_cost_usd"))
        self.cost_usd += cost
        result = payload.get("result")
        return AgentRun(
            text=result if isinstance(result, str) else "",
            cost_usd=cost,
            turns=int(_number(payload.get("num_turns"))),
            duration_ms=int(_number(payload.get("duration_ms"))),
            error="agent reported an error" if payload.get("is_error") is True else "",
        )

    def reflect(self, messages: str | list[Message], model: str) -> str:
        self._take_run()
        prompt = (
            messages
            if isinstance(messages, str)
            else "\n\n".join(f"{item.get('role', 'user')}: {item.get('content', '')}" for item in messages)
        )
        command = [
            self._binary,
            "-p",
            "--output-format",
            "text",
            "--model",
            model,
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--strict-mcp-config",
            "--tools",
            "",
        ]
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                env=self._env(),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProviderError("reflection request failed") from error
        if completed.returncode != 0:
            raise ProviderError("reflection request failed")
        return completed.stdout


def evaluate_agent_candidate(
    candidate: str,
    task_set: TaskSet,
    tasks: Sequence[AgentTask],
    runner: AgentRunner,
    *,
    repeats: int = 1,
    max_runs: int = 100,
    timeout_seconds: int = 300,
    workspace_root: Path | None = None,
) -> JsonObject:
    """Run every task `repeats` times and grade each resulting tree.

    Workspaces are discarded unless `workspace_root` is given.
    """
    if not candidate.strip() or len(candidate) > MAX_TEXT:
        raise PromptLabError("candidate prompt must be non-empty and within size limit")
    if not 1 <= repeats <= MAX_REPEATS or not 1 <= max_runs <= MAX_RUNS:
        raise PromptLabError("repeats and max_runs are outside the supported bounds")
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise PromptLabError("timeout_seconds is outside the supported bounds")
    if not tasks:
        raise PromptLabError("tasks must not be empty")
    keep = workspace_root is not None
    root = workspace_root if workspace_root is not None else Path(tempfile.mkdtemp(prefix="agent-lab-"))
    run_count = 0
    total_cost = 0.0
    task_results: list[JsonObject] = []
    try:
        for task in tasks:
            runs: list[JsonObject] = []
            for repeat in range(repeats):
                if run_count >= max_runs:
                    raise BudgetExhausted("max-runs budget exhausted")
                workspace = prepare_workspace(task_set, task, root / f"{task.identifier}-{repeat + 1}")
                before = snapshot_files(workspace)
                run = runner.run(candidate, task.prompt, workspace)
                run_count += 1
                total_cost += run.cost_usd
                after = snapshot_files(workspace)
                changed = sorted(name for name in set(before) | set(after) if before.get(name) != after.get(name))
                score, failures, tail = grade_workspace(task, workspace, run.text, timeout_seconds)
                runs.append(
                    {
                        "repeat": repeat + 1,
                        "score": score,
                        "failures": failures,
                        "agent_error": run.error,
                        "cost_usd": run.cost_usd,
                        "turns": run.turns,
                        "duration_ms": run.duration_ms,
                        "changed_files": changed,
                        "test_output_tail": tail,
                        "workspace": str(workspace) if keep else "",
                    }
                )
                if not keep:
                    shutil.rmtree(workspace, ignore_errors=True)
            task_results.append(
                {
                    "task_id": task.identifier,
                    "family": task.family,
                    "capability": task.capability,
                    "split": task.split,
                    "score": sum(cast(float, item["score"]) for item in runs) / len(runs),
                    "runs": runs,
                }
            )
    finally:
        if not keep:
            shutil.rmtree(root, ignore_errors=True)
    aggregate = sum(cast(float, item["score"]) for item in task_results) / len(task_results)
    return {
        "aggregate_score": aggregate,
        "task_results": task_results,
        "runs": run_count,
        "cost_usd": total_cost,
    }


def _read_prompt(value: str, root: Path) -> str:
    if value == "baseline":
        return "Fix the described bug in the current directory. Run the tests the user names before you finish."
    if value == "current":
        return (root / "skills/cook/SKILL.md").read_text(encoding="utf-8")
    text = Path(value).read_text(encoding="utf-8")
    if not text.strip() or len(text) > MAX_TEXT:
        raise PromptLabError("prompt file is empty or too large")
    return text


def _agent_args(namespace: argparse.Namespace) -> AgentArgs:
    return AgentArgs(
        tasks=cast(str, getattr(namespace, "tasks", "")),
        model=cast(str, getattr(namespace, "model", "")),
        output_dir=cast(str, getattr(namespace, "output_dir", "")),
        max_runs=cast(int, getattr(namespace, "max_runs", 0)),
        max_budget_usd=cast(float, getattr(namespace, "max_budget_usd", 0.0)),
        timeout_seconds=cast(int, getattr(namespace, "timeout_seconds", 0)),
        repeats=cast(int, getattr(namespace, "repeats", 0)),
        claude_bin=cast(str, getattr(namespace, "claude_bin", "claude")),
        keep_workspaces=cast(bool, getattr(namespace, "keep_workspaces", False)),
        prompt=cast(str, getattr(namespace, "prompt", "")),
        split=cast(str, getattr(namespace, "split", "validation")),
        seed_prompt=cast(str, getattr(namespace, "seed_prompt", "")),
        max_metric_calls=cast(int, getattr(namespace, "max_metric_calls", 8)),
        reflection_model=cast(str, getattr(namespace, "reflection_model", "")),
    )


def _runner(args: AgentArgs) -> ClaudeRunner:
    if not 1 <= args.max_runs <= MAX_RUNS or not 1 <= args.repeats <= MAX_REPEATS:
        raise PromptLabError("run and repeat limits are outside the supported bounds")
    if not 0.0 < args.max_budget_usd <= MAX_BUDGET_USD:
        raise PromptLabError(f"--max-budget-usd must be within (0, {MAX_BUDGET_USD}]")
    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise PromptLabError("--timeout-seconds is outside the supported bounds")
    if args.max_metric_calls < 1:
        raise PromptLabError("metric-call limit must be positive")
    if not args.model:
        raise PromptLabError("--model is required for paid commands")
    return ClaudeRunner(
        binary=args.claude_bin,
        model=args.model,
        max_runs=args.max_runs,
        max_budget_usd=args.max_budget_usd,
        timeout_seconds=args.timeout_seconds,
    )


def _settings(args: AgentArgs, tasks_path: Path) -> JsonObject:
    return {
        "tasks_sha256": sha256_hex(tasks_path.read_bytes()),
        "model": args.model,
        "repeats": args.repeats,
        "max_runs": args.max_runs,
        "max_budget_usd_per_run": args.max_budget_usd,
        "timeout_seconds": args.timeout_seconds,
    }


def _run_evaluate(args: AgentArgs, root: Path) -> int:
    tasks_path = Path(args.tasks)
    task_set = load_task_set(tasks_path)
    candidate = _read_prompt(args.prompt, root)
    runner = _runner(args)
    output_dir = Path(args.output_dir)
    new_output_dir(output_dir)
    result = evaluate_agent_candidate(
        candidate,
        task_set,
        task_set.split(args.split),
        runner,
        repeats=args.repeats,
        max_runs=args.max_runs,
        timeout_seconds=args.timeout_seconds,
        workspace_root=output_dir / "workspaces" if args.keep_workspaces else None,
    )
    write_json(
        output_dir / "result.json",
        {**_settings(args, tasks_path), "prompt_sha256": sha256_hex(candidate.encode()), "split": args.split, **result},
    )
    print(json.dumps({"aggregate_score": result["aggregate_score"], "runs": result["runs"], "cost_usd": result["cost_usd"]}))
    return 0


def _run_optimize(args: AgentArgs, root: Path) -> int:
    tasks_path = Path(args.tasks)
    task_set = load_task_set(tasks_path)
    seed = _read_prompt(args.seed_prompt, root)
    runner = _runner(args)
    output_dir = Path(args.output_dir)
    new_output_dir(output_dir)
    reflection_model = args.reflection_model or args.model
    try:
        module = import_module("gepa.optimize_anything")
        engine_config = cast(Callable[..., object], getattr(module, "EngineConfig"))
        gepa_config = cast(Callable[..., object], getattr(module, "GEPAConfig"))
        reflection_config = cast(Callable[..., object], getattr(module, "ReflectionConfig"))
        optimize_anything = cast(Callable[..., object], getattr(module, "optimize_anything"))
    except ImportError as error:
        raise PromptLabError("install requirements/prompt-lab.txt for optimization") from error
    visible = task_set.split("train") + task_set.split("validation")
    by_id = {task.identifier: task for task in visible}
    evaluation_records: list[JsonObject] = []

    def evaluate(candidate: str, tasks: Sequence[AgentTask]) -> JsonObject:
        return evaluate_agent_candidate(
            candidate,
            task_set,
            tasks,
            runner,
            repeats=args.repeats,
            max_runs=args.max_runs,
            timeout_seconds=args.timeout_seconds,
        )

    def evaluator(candidate: str, example: JsonObject) -> tuple[float, JsonObject]:
        task = by_id[cast(str, example["id"])]
        result = evaluate(candidate, [task])
        run = cast(list[JsonObject], cast(list[JsonObject], result["task_results"])[0]["runs"])[0]
        side_info: JsonObject = {
            "task_id": task.identifier,
            "score": result["aggregate_score"],
            "failures": run["failures"],
            "agent_error": run["agent_error"],
            "changed_files": run["changed_files"],
            "test_output_tail": run["test_output_tail"],
        }
        evaluation_records.append({"candidate_sha256": sha256_hex(candidate.encode()), **side_info})
        return float(cast(float, result["aggregate_score"])), side_info

    def reflection(messages: str | list[Message]) -> str:
        return runner.reflect(messages, reflection_model)

    artifact: JsonObject = {
        **_settings(args, tasks_path),
        "seed_prompt_sha256": sha256_hex(seed.encode()),
        "reflection_model": reflection_model,
        "max_metric_calls": args.max_metric_calls,
        "exported": False,
    }
    try:
        seed_result = evaluate(seed, visible)
        artifact["seed_result"] = seed_result
        config = gepa_config(
            engine=engine_config(max_metric_calls=args.max_metric_calls, parallel=False),
            reflection=reflection_config(reflection_lm=reflection),
        )
        optimized = optimize_anything(
            seed_candidate=seed,
            evaluator=evaluator,
            dataset=[{"id": task.identifier} for task in task_set.split("train")],
            valset=[{"id": task.identifier} for task in task_set.split("validation")],
            config=config,
        )
        best = cast(str, getattr(optimized, "best_candidate"))
        best_result = evaluate(best, visible) if best != seed else seed_result
        improved = cast(float, best_result["aggregate_score"]) > cast(float, seed_result["aggregate_score"])
        artifact.update(
            {"best_prompt_sha256": sha256_hex(best.encode()), "best_result": best_result, "exported": improved}
        )
        if improved:
            _ = (output_dir / "best_candidate.md").write_text(best, encoding="utf-8")
    except BudgetExhausted as error:
        artifact["budget_exhausted"] = str(error)
    finally:
        artifact.update(
            {"runs": runner.runs, "cost_usd": runner.cost_usd, "evaluation_records": evaluation_records[-100:]}
        )
        write_json(output_dir / "result.json", artifact)
    if "budget_exhausted" in artifact:
        print("Run budget exhausted before optimization finished; partial result saved.", file=sys.stderr)
        return 2
    if not artifact["exported"]:
        print("Best candidate did not beat the seed; no candidate was exported.", file=sys.stderr)
        return 2
    print(f"Wrote {output_dir / 'best_candidate.md'}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_lab.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    _ = validate.add_argument("tasks")
    for command in ("evaluate", "optimize"):
        subparser = subparsers.add_parser(command)
        _ = subparser.add_argument("--tasks", required=True)
        _ = subparser.add_argument("--model", required=True)
        _ = subparser.add_argument("--output-dir", required=True)
        _ = subparser.add_argument("--max-runs", type=int, default=32)
        _ = subparser.add_argument("--max-budget-usd", type=float, default=0.5, help="per agent run")
        _ = subparser.add_argument("--timeout-seconds", type=int, default=300)
        _ = subparser.add_argument("--repeats", type=int, default=1)
        _ = subparser.add_argument("--claude-bin", default="claude")
        _ = subparser.add_argument("--keep-workspaces", action="store_true")
    evaluate = subparsers.choices["evaluate"]
    _ = evaluate.add_argument("--prompt", required=True)
    _ = evaluate.add_argument("--split", choices=SPLITS, default="validation")
    optimize = subparsers.choices["optimize"]
    _ = optimize.add_argument("--seed-prompt", required=True)
    _ = optimize.add_argument("--max-metric-calls", type=int, default=8)
    _ = optimize.add_argument("--reflection-model")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        command = cast(str, getattr(args, "command", ""))
        if command == "validate":
            task_set = load_task_set(Path(cast(str, getattr(args, "tasks", ""))))
            counts = {split: len(task_set.split(split)) for split in SPLITS}
            print(json.dumps({"tasks": len(task_set.tasks), "splits": counts, "repo": str(task_set.repo)}))
            return 0
        agent_args = _agent_args(args)
        if command == "evaluate":
            return _run_evaluate(agent_args, root)
        return _run_optimize(agent_args, root)
    except (PromptLabError, ProviderError, BudgetExhausted) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
