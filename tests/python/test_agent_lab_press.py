"""Adversarial press suite for the cook-skill-optimization-loop contract.

Attacks the in-contract edges of `agent_lab_candidate.py`, `agent_lab_tilth.py`,
`agent_lab_mine.py`, and `agent_lab_scoring.py` that the first-coverage suites
(`test_agent_lab*.py`) do not already exercise: reach-allowlist escapes
(shared/schemas/phase-contract, symlinks), exact guard boundaries, the
graduation gate's non-domination vs. improvement logic on a genuine
per-model trade-off, mining's prompt-leak and base-sha edge cases, and proof
that holdout task ids never reach the optimizer's runner.

Every test fakes its subprocess seam (fake `run.py`, fake `gh`); nothing here
runs a real agent, a real build, or touches the network.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest

import agent_lab
from agent_lab import main
from agent_lab_candidate import (
    CODE_PREFIX,
    SKILL_MD_PATH,
    TOKEN_BUDGET_GUARD,
    CandidateError,
    CommandRunner,
    build_candidate,
    load_candidate_dir,
    prepare_overlay,
    token_budget_guard,
    validate_candidate,
)
from agent_lab_mine import _build_candidate, _parent_sha, mine_tasks  # pyright: ignore[reportPrivateUsage]
from agent_lab_scoring import graduate, pareto_front
from agent_lab_tilth import REQUIRED_SKILL, DEFAULT_EROSION_RATIO, RUNNER_ERROR_GUARD, score_row
from prompt_lab import JsonObject


# Deterministic stand-in for gepa.optimize_anything, mirroring
# tests/python/test_agent_lab.py's stub: propose three reflection
# candidates and score each one on the full train and validation split, so
# the holdout-isolation proof below runs without the optional `gepa`
# dependency installed.
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
    del objective
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


REPO_ROOT = Path(__file__).resolve().parents[2]
COMMANDS_PATH = f"{CODE_PREFIX}commands.py"


# --------------------------------------------------------------------------
# AC-4 / F-2: candidate reach allowlist escapes
# --------------------------------------------------------------------------


class TestReachAllowlistEscapes:
    @pytest.mark.parametrize(
        "rel_path",
        [
            "src/easy_cheese/shared/utils.py",
            "src/easy_cheese/shared/__init__.py",
            "easy_cheese_schemas/schema.py",
            "easy_cheese_schemas/__init__.py",
            "phase-contract.yaml",
            "skills/cook/scripts/cook.pyz",
            "skills/cook/references/../../../etc/passwd.md",
            "skills/other-skill/SKILL.md",
        ],
    )
    def test_rejects_out_of_reach_component_paths(self, rel_path: str) -> None:
        with pytest.raises(CandidateError, match="out of reach"):
            validate_candidate({rel_path: "text"})

    def test_symlinked_component_escaping_base_dir_must_not_leak_secret_content(
        self, tmp_path: Path
    ) -> None:
        """AC-4: reach control must hold even when the allowed-looking path on
        disk is a symlink pointing outside `base_dir`. `load_candidate_dir`
        globs by pattern and checks `is_file()`, which a symlink also
        satisfies; if it followed the link, an attacker-controlled candidate
        directory could exfiltrate arbitrary files on the build host into the
        overlay under a name that looks like SKILL.md.
        """
        secret = tmp_path / "outside_base" / "secret.txt"
        secret.parent.mkdir(parents=True)
        secret_text = "TOP-SECRET-HOST-FILE-CONTENT"
        _ = secret.write_text(secret_text, encoding="utf-8")

        base_dir = tmp_path / "candidate"
        skill_dir = base_dir / "skills" / "cook"
        skill_dir.mkdir(parents=True)
        os.symlink(secret, skill_dir / "SKILL.md")

        candidate = load_candidate_dir(base_dir)

        assert candidate.get(SKILL_MD_PATH) != secret_text, (
            "load_candidate_dir followed a symlink outside base_dir and leaked "
            "host file content into the candidate; a symlinked component "
            "should be rejected, not read"
        )


def _fake_run(
    calls: list[list[str]], *, fail_on: str | None = None, worktrees: list[Path] | None = None
) -> CommandRunner:
    def run(argv: Sequence[str], cwd: Path) -> "subprocess.CompletedProcess[str]":
        calls.append(list(argv))
        if worktrees is not None and cwd not in worktrees:
            worktrees.append(cwd)
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


def _git_status() -> str:
    completed = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return completed.stdout


def _git_worktree_list() -> str:
    completed = subprocess.run(
        ["git", "worktree", "list", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    )
    return completed.stdout


class TestBuildNeverTouchesCheckoutOrLeaksWorktrees:
    """Asserts only on the disposable worktree(s) this test's own build
    creates (captured via the `run` seam's `cwd`), never on the global
    `git worktree list`: under a parallel gate (`PYTEST_WORKERS=auto`),
    other workers add and remove worktrees for their own tests at the same
    time, so a global-list comparison is not hermetic.
    """

    def test_successful_code_build_leaves_git_status_unchanged_and_removes_its_worktree(
        self, tmp_path: Path
    ) -> None:
        before_status = _git_status()
        original_commands = (REPO_ROOT / COMMANDS_PATH).read_text(encoding="utf-8")
        candidate = {COMMANDS_PATH: original_commands + "\n# press marker\n"}
        worktrees: list[Path] = []

        result = build_candidate(
            candidate,
            repo_root=REPO_ROOT,
            overlay_dir=tmp_path / "overlay",
            run=_fake_run([], worktrees=worktrees),
        )

        assert result.guard is None
        assert worktrees, "the fake run seam never received a build worktree cwd"
        build_worktree = worktrees[0]
        assert _git_status() == before_status
        assert not build_worktree.exists(), (
            "a successful build must remove its own disposable worktree directory"
        )
        assert build_worktree.as_posix() not in _git_worktree_list(), (
            "a successful build must unregister its own disposable worktree from "
            "git worktree list"
        )
        assert (REPO_ROOT / COMMANDS_PATH).read_text(encoding="utf-8") == original_commands

    def test_build_failure_still_removes_the_disposable_worktree(self, tmp_path: Path) -> None:
        candidate = {COMMANDS_PATH: "def broken(:\n"}
        worktrees: list[Path] = []

        result = build_candidate(
            candidate,
            repo_root=REPO_ROOT,
            overlay_dir=tmp_path / "overlay",
            run=_fake_run([], fail_on="--write-generated", worktrees=worktrees),
        )

        assert result.guard == "build"
        assert worktrees, "the fake run seam never received a build worktree cwd"
        build_worktree = worktrees[0]
        assert not build_worktree.exists(), (
            "a failed build must still remove its own disposable worktree directory"
        )
        assert build_worktree.as_posix() not in _git_worktree_list(), (
            "a failed build step must not leave a leftover git worktree registered "
            "against the checkout"
        )

    def test_no_code_change_build_never_creates_a_worktree(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Spies on this build's own `git` invocations instead of diffing the
        # global `git worktree list`: under `PYTEST_WORKERS=auto`, other
        # workers add and remove worktrees concurrently, so a global-state
        # comparison is not hermetic.
        candidate_module = import_module("agent_lab_candidate")
        real_run = cast("Callable[..., subprocess.CompletedProcess[str]]", subprocess.run)
        git_calls: list[list[str]] = []

        def spy_run(argv: Sequence[str], **kwargs: object) -> "subprocess.CompletedProcess[str]":
            argv_list = list(argv)
            if argv_list[:1] == ["git"]:
                git_calls.append(argv_list)
            return real_run(argv_list, **kwargs)

        candidate_subprocess = cast(ModuleType, candidate_module.subprocess)
        monkeypatch.setattr(candidate_subprocess, "run", spy_run)
        candidate = {SKILL_MD_PATH: "a small candidate prompt"}

        result = build_candidate(
            candidate, repo_root=REPO_ROOT, overlay_dir=tmp_path / "overlay", run=_fake_run([])
        )

        assert result.guard is None
        assert not any(call[:3] == ["git", "worktree", "add"] for call in git_calls), (
            "a candidate with no changed CODE_PREFIX component must reuse the "
            "tracked skills/cook tree via git archive, never a git worktree"
        )
        assert any(call[:2] == ["git", "archive"] for call in git_calls)


# --------------------------------------------------------------------------
# AC-5: token-budget guard exact boundary
# --------------------------------------------------------------------------


class TestTokenBudgetExactBoundary:
    """The repo's own budget for the `cook` skill is 3600 tokens
    (`estimate_tokens` = utf-8 byte length // 4), recorded at 3500 in
    `.github/skill-budgets.json` (not grandfathered, since 3500 <= 3600, so
    the effective cap is the flat 3600-token ceiling).
    """

    def test_exactly_at_budget_is_none(self) -> None:
        body = "a" * 14_400  # 14400 // 4 == 3600 tokens exactly
        assert token_budget_guard({SKILL_MD_PATH: body}) is None

    def test_one_token_over_budget_returns_guard(self) -> None:
        body = "a" * 14_404  # 14404 // 4 == 3601 tokens
        assert token_budget_guard({SKILL_MD_PATH: body}) == TOKEN_BUDGET_GUARD

    def test_guard_at_the_boundary_still_makes_zero_runner_calls(self, tmp_path: Path) -> None:
        calls: list[list[str]] = []
        body = "a" * 14_404
        guard = prepare_overlay(
            {SKILL_MD_PATH: body}, repo_root=REPO_ROOT, overlay_dir=tmp_path / "overlay", run=_fake_run(calls)
        )
        assert guard == TOKEN_BUDGET_GUARD
        assert calls == []
        assert not (tmp_path / "overlay").exists()


# --------------------------------------------------------------------------
# AC-10: erosion guard boundary and field edge cases
# --------------------------------------------------------------------------


def _erosion_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "correct": True,
        "error": "",
        "skills": [REQUIRED_SKILL],
        "input_tokens": 1,
        "output_tokens": 1,
        "cache_creation_tokens": 0,
        "cache_read_tokens": 0,
        "workspace_diff_lines": 4,
        "reference_changed_lines": 4,
        "lint_ok": True,
    }
    row.update(overrides)
    return row


class TestErosionGuardBoundaries:
    def test_ratio_exactly_at_threshold_is_not_erosion(self) -> None:
        # ratio = 15 / 5 == DEFAULT_EROSION_RATIO (3.0) exactly; the guard
        # fires on `ratio > erosion_ratio`, so an exact match must pass.
        row = _erosion_row(workspace_diff_lines=15, reference_changed_lines=5)
        record = score_row(row, erosion_ratio=DEFAULT_EROSION_RATIO)
        assert "guard" not in record

    def test_ratio_one_line_above_threshold_is_erosion(self) -> None:
        row = _erosion_row(workspace_diff_lines=16, reference_changed_lines=5)
        record = score_row(row, erosion_ratio=DEFAULT_EROSION_RATIO)
        assert record.get("guard") == "erosion"

    def test_reference_changed_lines_zero_floors_denominator_to_one(self) -> None:
        # ratio = workspace_diff_lines / max(reference_changed_lines, 1.0);
        # with reference_changed_lines == 0 the ratio is workspace_diff_lines
        # itself, not a division by zero.
        row = _erosion_row(workspace_diff_lines=3, reference_changed_lines=0)
        record = score_row(row, erosion_ratio=DEFAULT_EROSION_RATIO)
        assert "guard" not in record

        row_over = _erosion_row(workspace_diff_lines=4, reference_changed_lines=0)
        record_over = score_row(row_over, erosion_ratio=DEFAULT_EROSION_RATIO)
        assert record_over.get("guard") == "erosion"

    def test_lint_ok_none_does_not_guard_unlike_false(self) -> None:
        """`lint_ok is False` is the only lint trigger; `lint_ok: None` (an
        unknown/unrun lint result) silently passes through as if lint had
        succeeded, when the row is otherwise within the diff-ratio budget.
        """
        row = _erosion_row(workspace_diff_lines=2, reference_changed_lines=4, lint_ok=None)
        record = score_row(row)
        assert "guard" not in record


# --------------------------------------------------------------------------
# AC-2 (consumer side): a row missing REQUIRED_SKILL or carrying `error` is
# never scored as correct, across the field-shape edge cases.
# --------------------------------------------------------------------------


class TestRequiredSkillAndErrorConsumerEdges:
    def test_missing_skills_key_entirely_is_a_failure(self) -> None:
        row = _erosion_row(correct=True)
        del row["skills"]
        record = score_row(row)
        assert record["correct"] is False
        assert record["error"] is True
        assert record["guard"] == RUNNER_ERROR_GUARD

    def test_skills_value_none_is_a_failure(self) -> None:
        row = _erosion_row(correct=True, skills=None)
        record = score_row(row)
        assert record["correct"] is False
        assert record["error"] is True

    def test_error_as_boolean_true_is_a_failure_even_with_required_skill(self) -> None:
        row = _erosion_row(correct=True, error=True)
        record = score_row(row)
        assert record["correct"] is False
        assert record["error"] is True

    def test_falsy_empty_string_error_with_skill_present_is_not_a_failure(self) -> None:
        row = _erosion_row(correct=True, error="")
        record = score_row(row)
        assert record["correct"] is True
        assert record["error"] is False


# --------------------------------------------------------------------------
# AC-1: aggregate is derived only from the JSONL rows, never from local
# workspace state (there is no workspace to re-grade in this code path at
# all -- overlay_dir need not even exist on disk for evaluate_tilth to work).
# --------------------------------------------------------------------------


def _tilth_evaluate_tilth_import():  # local import to avoid polluting module namespace
    from agent_lab_tilth import TilthRunner, evaluate_tilth

    return TilthRunner, evaluate_tilth


FAKE_RUN_SIMPLE = '''#!/usr/bin/env python3
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

modes = json.loads(Path(args.modes_json).read_text())
for mode in modes:
    assert mode["description"]
    assert Path(mode["plugin_dir"]).is_absolute()

control = json.loads(Path(os.environ["FAKE_RUN_SIMPLE_CONTROL"]).read_text())
rows_by_task = control["rows_by_task"]
lines = []
for task_id in args.tasks.split(","):
    row = dict(rows_by_task[task_id])
    row.setdefault("task", task_id)
    row.setdefault("model", args.models)
    lines.append(json.dumps(row))
Path(args.output).write_text("\\n".join(lines) + "\\n")
'''


class TestAggregateComesOnlyFromRows:
    def test_aggregate_ignores_nonexistent_overlay_and_workspace_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        TilthRunner, evaluate_tilth = _tilth_evaluate_tilth_import()
        tilth_root = tmp_path / "tilth"
        benchmark_dir = tilth_root / "benchmark"
        benchmark_dir.mkdir(parents=True)
        _ = (benchmark_dir / "run.py").write_text(FAKE_RUN_SIMPLE, encoding="utf-8")
        control = tmp_path / "control.json"
        # correct=True for t1, False for t2: any local re-grade of a
        # (nonexistent) workspace would have no signal to contradict this,
        # proving there is nothing to re-grade against.
        _ = control.write_text(
            json.dumps(
                {
                    "rows_by_task": {
                        "t1": {"correct": True, "skills": [REQUIRED_SKILL], "error": ""},
                        "t2": {"correct": False, "skills": [REQUIRED_SKILL], "error": ""},
                    }
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("FAKE_RUN_SIMPLE_CONTROL", str(control))

        overlay_dir = tmp_path / "overlay-that-does-not-exist"
        assert not overlay_dir.exists()
        tasks_path = tmp_path / "tasks.json"
        _ = tasks_path.write_text("{}", encoding="utf-8")

        result = evaluate_tilth(
            runner=TilthRunner(tilth_root=tilth_root, python_bin=sys.executable),
            overlay_dir=overlay_dir,
            tasks_path=tasks_path,
            task_ids=["t1", "t2"],
            model="haiku",
            output_path=tmp_path / "rows.jsonl",
        )
        assert result["aggregate_score"] == 0.5
        # evaluate_tilth never created or required the overlay directory.
        assert not overlay_dir.exists()


# --------------------------------------------------------------------------
# AC-6 / AC-7: Pareto edges and the graduation gate's non-domination logic
# --------------------------------------------------------------------------


class TestParetoFrontEdges:
    def test_empty_input_returns_empty_front(self) -> None:
        assert pareto_front([]) == []


SEED = {"skills/cook/SKILL.md": "seed-marker seed prompt"}
CANDIDATE = {"skills/cook/SKILL.md": "candidate prompt"}


GradRows = dict[tuple[str, str], list[dict[str, object]]]


def _grad_evaluate(rows_by_model_and_component: GradRows) -> Callable[[Mapping[str, str], str], list[dict[str, object]]]:
    def evaluate(components: Mapping[str, str], model: str) -> list[dict[str, object]]:
        key = ("seed" if any("seed-marker" in text for text in components.values()) else "candidate", model)
        return rows_by_model_and_component[key]

    return evaluate


class TestGraduateTradeoff:
    def test_lower_accuracy_but_cheaper_tokens_on_one_model_reports_promote_expect_hold(
        self, tmp_path: Path
    ) -> None:
        """AC-7 Test Contract row (agent-lab-graduate-1): 'promote is reported
        when Fable rows show lower accuracy; the test asserts hold.'

        Sonnet and Opus show a genuine, unambiguous candidate improvement.
        On Fable the candidate is strictly worse on accuracy (0 vs 1) but
        strictly cheaper on tokens (100 vs 300): neither vector dominates the
        other on Fable, so `graduate`'s domination check alone never flags
        it, and the `better_somewhere` check is satisfied by Sonnet/Opus (or
        even by Fable's token axis). The graduation gate's intent -- never
        promote a candidate that regresses accuracy on any graded model --
        is not enforced by "non-dominated everywhere plus better somewhere";
        it only forbids literal both-axes domination by the seed.
        """
        rows: GradRows = {
            ("seed", "sonnet"): [{"task": "t1", "correct": False, "input_tokens": 200,
                                   "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}],
            ("candidate", "sonnet"): [{"task": "t1", "correct": True, "input_tokens": 100,
                                       "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}],
            ("seed", "opus"): [{"task": "t1", "correct": False, "input_tokens": 200,
                                "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}],
            ("candidate", "opus"): [{"task": "t1", "correct": True, "input_tokens": 100,
                                     "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}],
            ("seed", "fable"): [{"task": "t1", "correct": True, "input_tokens": 300,
                                 "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}],
            ("candidate", "fable"): [{"task": "t1", "correct": False, "input_tokens": 100,
                                      "output_tokens": 0, "cache_creation_tokens": 0, "cache_read_tokens": 0}],
        }
        result = graduate(
            SEED,
            CANDIDATE,
            evaluate=_grad_evaluate(rows),
            models=("sonnet", "opus", "fable"),
            output_dir=tmp_path,
        )
        assert result["verdict"] == "hold", (
            f"graduate() reported {result['verdict']!r} for a candidate that regresses "
            "accuracy on the fable model; the graduation gate must hold in this case"
        )


# --------------------------------------------------------------------------
# AC-3: mining edge cases (prompt leak via prose, check_task partial pass,
# PR without test-file changes, base_sha as first parent of a real merge)
# --------------------------------------------------------------------------


PR_DIFF_BASE = (
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


class TestMinePressEdges:
    def test_prompt_leaks_fix_line_as_plain_prose_drops_the_task(self) -> None:
        """The fenced-diff strip in `_clean_prompt` only removes ``` blocks
        and literal +/- lines; a PR/issue body that describes the fix in
        plain prose using the exact added line still leaks it, and
        `_leaks_fix` must catch that and drop the task.
        """
        pr: JsonObject = {
            "number": 1,
            "title": "fix: crash on empty input",
            "body": (
                "The fix makes process() return items[0] if items else [] "
                "instead of raising IndexError on empty input."
            ),
            "mergeCommit": {"oid": "1" * 40},
            "closingIssuesReferences": [],
            "files": [{"path": "widgets/core.py"}, {"path": "tests/test_core.py"}],
            "authorAssociation": "OWNER",
        }

        # _build_candidate calls module-level `_parent_sha` and `_pr_diff`;
        # patch those two to avoid a real `gh` invocation.
        import agent_lab_mine as mine_module

        def fake_parent_sha(repo: str, sha: str, *, gh_bin: str) -> str:
            _ = (repo, sha, gh_bin)
            return "0" * 40

        def fake_pr_diff(repo: str, number: int, *, gh_bin: str) -> str:
            _ = (repo, number, gh_bin)
            return PR_DIFF_BASE

        original_parent_sha = mine_module._parent_sha  # pyright: ignore[reportPrivateUsage]
        original_pr_diff = mine_module._pr_diff  # pyright: ignore[reportPrivateUsage]
        mine_module._parent_sha = fake_parent_sha  # pyright: ignore[reportPrivateUsage]
        mine_module._pr_diff = fake_pr_diff  # pyright: ignore[reportPrivateUsage]
        try:
            task, reason = _build_candidate("acme/widgets", pr, gh_bin="unused-gh")
        finally:
            mine_module._parent_sha = original_parent_sha  # pyright: ignore[reportPrivateUsage]
            mine_module._pr_diff = original_pr_diff  # pyright: ignore[reportPrivateUsage]

        assert task is None
        assert "leak" in reason

    def test_pr_without_test_file_changes_is_dropped_directly(self) -> None:
        pr: JsonObject = {
            "number": 2,
            "title": "fix: typo in docs",
            "body": "Fixes a typo.",
            "mergeCommit": {"oid": "9" * 40},
            "closingIssuesReferences": [],
            "files": [{"path": "docs/readme.md"}],
            "authorAssociation": "OWNER",
        }
        task, reason = _build_candidate("acme/widgets", pr, gh_bin="unused-gh")
        assert task is None
        assert "test file" in reason

    def test_base_sha_uses_first_parent_of_a_real_merge_commit_with_two_parents(
        self, tmp_path: Path
    ) -> None:
        fake_gh = '''#!/usr/bin/env python3
import json, sys
argv = sys.argv[1:]
if argv[0] == "api":
    sha = argv[1].rsplit("/", 1)[-1]
    parents = {"ffffffffffffffffffffffffffffffffffffffff":
        ["1111111111111111111111111111111111111111", "2222222222222222222222222222222222222222"]}
    print(json.dumps({"parents": [{"sha": p} for p in parents.get(sha, [])]}))
    sys.exit(0)
print(f"unexpected: {argv}", file=sys.stderr)
sys.exit(1)
'''
        binary_dir = tmp_path / "bin"
        binary_dir.mkdir()
        gh_binary = binary_dir / "gh"
        _ = gh_binary.write_text(fake_gh, encoding="utf-8")
        gh_binary.chmod(gh_binary.stat().st_mode | stat.S_IXUSR)

        base_sha = _parent_sha(
            "acme/widgets", "f" * 40, gh_bin=str(gh_binary)
        )
        assert base_sha == "1" * 40, "base_sha must be the FIRST parent, not any parent"

    def test_check_task_partial_pass_keeps_only_the_passing_task(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_gh = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
control = json.loads(Path(os.environ["FAKE_GH_PARTIAL_CONTROL"]).read_text())
if argv[:2] == ["pr", "list"]:
    print(json.dumps(control["pr_list"]))
    sys.exit(0)
if argv[0] == "api":
    sha = argv[1].rsplit("/", 1)[-1]
    print(json.dumps({"parents": [{"sha": control["parents"][sha]}]}))
    sys.exit(0)
if argv[:2] == ["pr", "diff"]:
    print(control["diffs"][argv[2]])
    sys.exit(0)
print(f"no fake gh response for: {argv}", file=sys.stderr)
sys.exit(1)
'''
        diff_a = PR_DIFF_BASE
        diff_b = (
            "diff --git a/widgets/other.py b/widgets/other.py\n"
            "index 111..222 100644\n"
            "--- a/widgets/other.py\n"
            "+++ b/widgets/other.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
            "diff --git a/tests/test_other.py b/tests/test_other.py\n"
            "index 333..444 100644\n"
            "--- a/tests/test_other.py\n"
            "+++ b/tests/test_other.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-pass\n"
            "+pass\n"
        )
        pr_list: list[dict[str, object]] = [
            {
                "number": 1,
                "title": "fix: bug A",
                "body": "Fixes bug A.",
                "mergeCommit": {"oid": "1" * 40},
                "closingIssuesReferences": [],
                "files": [{"path": "widgets/core.py"}, {"path": "tests/test_core.py"}],
                "authorAssociation": "OWNER",
            },
            {
                "number": 3,
                "title": "fix: bug B",
                "body": "Fixes bug B.",
                "mergeCommit": {"oid": "3" * 40},
                "closingIssuesReferences": [],
                "files": [{"path": "widgets/other.py"}, {"path": "tests/test_other.py"}],
                "authorAssociation": "OWNER",
            },
        ]
        binary_dir = tmp_path / "bin"
        binary_dir.mkdir()
        gh_binary = binary_dir / "gh"
        _ = gh_binary.write_text(fake_gh, encoding="utf-8")
        gh_binary.chmod(gh_binary.stat().st_mode | stat.S_IXUSR)
        control = tmp_path / "control.json"
        _ = control.write_text(
            json.dumps(
                {
                    "pr_list": pr_list,
                    "parents": {"1" * 40: "0" * 40, "3" * 40: "2" * 40},
                    "diffs": {"1": diff_a, "3": diff_b},
                }
            ),
            encoding="utf-8",
        )
        monkeypatch.setenv("FAKE_GH_PARTIAL_CONTROL", str(control))

        only_bug_a_id = "acme-widgets-1"

        def partial_check_task(tasks_path: Path) -> set[str]:
            payload = cast(dict[str, object], json.loads(tasks_path.read_text(encoding="utf-8")))
            ids = {cast(str, task["id"]) for task in cast(list[dict[str, object]], payload["tasks"])}
            assert ids == {"acme-widgets-1", "acme-widgets-3"}
            return {only_bug_a_id}

        tasks = mine_tasks("acme/widgets", gh_bin=str(gh_binary), check_task=partial_check_task)
        assert [task["id"] for task in tasks] == [only_bug_a_id]

    def test_uppercase_fix_title_is_not_recognized(self) -> None:
        """`FIX_TITLE_RE` matches the lowercase Conventional Commits `fix:`
        prefix only; a title of `Fix: bug` (capital F) is silently dropped
        even though it reads as an obvious fix commit to a human.
        """
        pr: JsonObject = {
            "number": 9,
            "title": "Fix: crash on empty input",
            "body": "Fixes a crash.",
            "mergeCommit": {"oid": "1" * 40},
            "closingIssuesReferences": [],
            "files": [{"path": "widgets/core.py"}, {"path": "tests/test_core.py"}],
        }
        task, reason = _build_candidate("acme/widgets", pr, gh_bin="unused-gh")
        assert task is None
        assert "fix:" in reason


# --------------------------------------------------------------------------
# AC-9: holdout task ids never reach optimize's runner
# --------------------------------------------------------------------------


FAKE_RUN_OPT_HOLDOUT = '''#!/usr/bin/env python3
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

task_ids = args.tasks.split(",")
control = json.loads(Path(os.environ["FAKE_RUN_HOLDOUT_CONTROL"]).read_text())
with Path(control["log"]).open("a") as handle:
    handle.write(json.dumps({"tasks": task_ids, "models": args.models}) + "\\n")

row = {"correct": True, "error": "", "skills": ["easy-cheese:cook"],
       "input_tokens": 10, "output_tokens": 0, "cache_creation_tokens": 0,
       "cache_read_tokens": 0, "workspace_diff_lines": 1, "reference_changed_lines": 1,
       "lint_ok": True}
lines = []
for task_id in task_ids:
    entry = dict(row)
    entry["task"] = task_id
    entry["model"] = args.models
    lines.append(json.dumps(entry))
Path(args.output).write_text("\\n".join(lines) + "\\n")
'''


class TestHoldoutNeverReachesOptimizeRunner:
    def test_holdout_split_task_id_never_appears_in_a_runner_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            agent_lab,
            "_gepa_module_override",
            (_FakeEngineConfig, _FakeGEPAConfig, _FakeReflectionConfig, _fake_optimize_anything),
        )

        tilth_root = tmp_path / "tilth"
        benchmark_dir = tilth_root / "benchmark"
        benchmark_dir.mkdir(parents=True)
        _ = (benchmark_dir / "run.py").write_text(FAKE_RUN_OPT_HOLDOUT, encoding="utf-8")
        log = tmp_path / "calls.jsonl"
        control = tmp_path / "control.json"
        _ = control.write_text(json.dumps({"log": str(log)}), encoding="utf-8")
        monkeypatch.setenv("FAKE_RUN_HOLDOUT_CONTROL", str(control))

        reflection_texts = tmp_path / "reflection.json"
        _ = reflection_texts.write_text(json.dumps({"texts": ["Improved seed prompt."]}), encoding="utf-8")
        monkeypatch.setenv("AGENT_LAB_FAKE_REFLECTION", str(reflection_texts))

        seed_dir = tmp_path / "seed"
        seed_skill = seed_dir / "skills" / "cook"
        seed_skill.mkdir(parents=True)
        _ = (seed_skill / "SKILL.md").write_text("Seed prompt.", encoding="utf-8")

        tasks_path = tmp_path / "tasks.json"
        _ = tasks_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "tasks": [
                        {"id": "train-1", "split": "train"},
                        {"id": "val-1", "split": "validation"},
                        {"id": "holdout-1", "split": "holdout"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        output = tmp_path / "optimization"

        code = main(
            [
                "optimize", "--runner", "tilth", "--tasks", str(tasks_path), "--model", "unused-model",
                "--output-dir", str(output), "--seed", str(seed_dir), "--tilth-root", str(tilth_root),
                "--search-model", "search-m", "--validation-model", "validation-m", "--max-metric-calls", "4",
            ]
        )
        assert code == 0

        calls = [
            cast(dict[str, object], json.loads(line))
            for line in log.read_text(encoding="utf-8").splitlines()
            if line
        ]
        assert calls
        for entry in calls:
            task_ids = cast(list[str], entry["tasks"])
            assert "holdout-1" not in task_ids
