"""Git operation status and continuation use a real temporary repository."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, cast

import pytest

from easy_cheese.skills.melt.operation import operation_cmd


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    _ = git(tmp_path, "init", "-q", "-b", "master")
    _ = git(tmp_path, "config", "user.name", "Test")
    _ = git(tmp_path, "config", "user.email", "test@example.com")
    _ = (tmp_path / "file.txt").write_text("base\n")
    _ = git(tmp_path, "add", "file.txt")
    _ = git(tmp_path, "commit", "-qm", "base")
    _ = monkeypatch.chdir(tmp_path)
    return tmp_path


def conflict(repo: Path) -> None:
    _ = git(repo, "switch", "-qc", "topic")
    _ = (repo / "file.txt").write_text("topic\n")
    _ = git(repo, "commit", "-qam", "topic")
    _ = git(repo, "switch", "-q", "master")
    _ = (repo / "file.txt").write_text("main\n")
    _ = git(repo, "commit", "-qam", "main")
    _ = git(repo, "merge", "topic", check=False)


def test_operation_status_reports_blockers_and_configuration(repo: Path) -> None:
    _ = git(repo, "config", "rerere.enabled", "true")
    _ = git(repo, "config", "merge.tool", "vimdiff")
    conflict(repo)

    result = operation_cmd()

    assert result["status"] == "blocked"
    assert result["operation"] == "merge"
    assert result["unmerged_paths"] == ["file.txt"]
    assert result["conflict_marker_files"] == ["file.txt"]
    assert result["rerere_enabled"] is True
    assert result["configured_merge_tool"] == "vimdiff"
    assert result["continuation_command"] == "git merge --continue"


def test_operation_refuses_unmerged_and_marker_files(repo: Path) -> None:
    conflict(repo)
    blocked = operation_cmd(continue_operation=True)
    assert blocked["status"] == "blocked"
    assert git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0

    _ = git(repo, "add", "file.txt")
    marker_blocked = operation_cmd(continue_operation=True)
    assert marker_blocked["status"] == "blocked"
    assert marker_blocked["unmerged_paths"] == []
    assert marker_blocked["conflict_marker_files"] == ["file.txt"]


def test_operation_blocks_markers_staged_but_removed_from_worktree(repo: Path) -> None:
    conflict(repo)
    _ = git(repo, "add", "file.txt")
    _ = (repo / "file.txt").write_text("clean worktree\n")

    state = operation_cmd(continue_operation=True)

    assert state["status"] == "blocked"
    assert state["unmerged_paths"] == []
    assert state["conflict_marker_files"] == ["file.txt"]
    assert git(repo, "show", ":file.txt").stdout.startswith("<<<<<<<")
    assert git(repo, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode == 0


def test_operation_continues_once_and_finishes(repo: Path) -> None:
    conflict(repo)
    _ = (repo / "file.txt").write_text("resolved\n")
    _ = git(repo, "add", "file.txt")

    assert operation_cmd()["status"] == "ready"
    result = operation_cmd(continue_operation=True)

    assert result["status"] == "complete"
    assert result["operation"] is None
    assert git(repo, "show", "HEAD:file.txt").stdout == "resolved\n"
    assert git(repo, "log", "-1", "--format=%s").stdout.strip() == "Merge branch 'topic'"


def test_operation_detects_rebase_and_cherry_pick_metadata(repo: Path) -> None:
    _ = git(repo, "switch", "-qc", "topic")
    _ = (repo / "file.txt").write_text("topic\n")
    _ = git(repo, "commit", "-qam", "topic")
    _ = git(repo, "switch", "-q", "master")
    _ = (repo / "file.txt").write_text("main\n")
    _ = git(repo, "commit", "-qam", "main")
    _ = git(repo, "cherry-pick", "topic", check=False)
    cherry = operation_cmd()
    assert cherry["operation"] == "cherry-pick"
    assert cherry["abort_command"] == "git cherry-pick --abort"
    _ = git(repo, "cherry-pick", "--abort")
    _ = git(repo, "switch", "-q", "topic")
    _ = git(repo, "rebase", "master", check=False)
    rebase = operation_cmd()
    assert rebase["operation"] == "rebase"
    assert rebase["original_branch"] == "topic"
    assert rebase["abort_command"] == "git rebase --abort"


def squash_with_followups(repo: Path, *, conflict_on_replay: bool = False) -> list[str]:
    _ = git(repo, "switch", "-qc", "topic")
    _ = (repo / "file.txt").write_text("squashed\n")
    _ = git(repo, "commit", "-qam", "squashed")
    _ = git(repo, "switch", "-q", "master")
    _ = git(repo, "merge", "--squash", "topic")
    _ = git(repo, "commit", "-qm", "squash topic")
    if conflict_on_replay:
        _ = (repo / "file.txt").write_text("base changed\n")
        _ = git(repo, "commit", "-qam", "base changed")
    _ = git(repo, "switch", "-q", "topic")
    commits: list[str] = []
    for name, content in (("one", "one\n"), ("two", "two\n")):
        path = repo / ("file.txt" if conflict_on_replay else f"{name}.txt")
        _ = path.write_text(content)
        _ = git(repo, "add", path.name)
        _ = git(repo, "commit", "-qm", name)
        _ = commits.append(git(repo, "rev-parse", "HEAD").stdout.strip())
    return commits


def test_squash_apply_replays_exact_commits_in_order(repo: Path) -> None:
    from easy_cheese.skills.melt.detect_squash_residue import detect_squash_residue_cmd

    commits = squash_with_followups(repo)
    result = detect_squash_residue_cmd(base="master", apply=True)

    application = result.get("application")
    assert application is not None
    assert application["state"] == "applied"
    assert application["remedy"] == "clean-branch"
    assert git(repo, "branch", "--show-current").stdout.strip() == "topic-clean"
    assert git(repo, "log", "-2", "--reverse", "--format=%s").stdout.splitlines() == ["one", "two"]
    assert git(repo, "rev-parse", "topic").stdout.strip() == commits[-1]
    assert (repo / "one.txt").read_text() == "one\n"
    assert (repo / "two.txt").read_text() == "two\n"


def test_squash_apply_collision_preflights_before_abort(repo: Path) -> None:
    from easy_cheese.skills.melt.detect_squash_residue import detect_squash_residue_cmd

    _ = squash_with_followups(repo, conflict_on_replay=True)
    _ = git(repo, "branch", "topic-clean")
    _ = git(repo, "rebase", "master", check=False)
    result = detect_squash_residue_cmd(base="master", apply=True)

    application = result.get("application")
    assert application is not None
    assert application["state"] == "failed"
    assert application["failed_step"] == "preflight-branch"
    assert operation_cmd()["operation"] == "rebase"
    assert git(repo, "branch", "--show-current").stdout.strip() == ""


def test_squash_apply_stops_on_new_conflict(repo: Path) -> None:
    from easy_cheese.skills.melt.detect_squash_residue import detect_squash_residue_cmd

    _ = squash_with_followups(repo, conflict_on_replay=True)
    result = detect_squash_residue_cmd(base="master", apply=True)

    application = result.get("application")
    assert application is not None
    assert application["state"] == "needs-resolution"
    assert application["recovery_branch"] == "topic"
    failed_step = application["failed_step"]
    assert failed_step is not None and failed_step.startswith("git cherry-pick ")
    assert operation_cmd()["operation"] == "cherry-pick"
    assert operation_cmd()["unmerged_paths"] == ["file.txt"]


def test_squash_apply_reports_nonconflict_failure_with_recovery(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from easy_cheese.skills.melt import detect_squash_residue as detector

    _ = squash_with_followups(repo)
    actual_run_git = cast("Callable[[list[str]], subprocess.CompletedProcess[str]]", getattr(detector, "run_git"))

    def fail_cherry_pick(args: list[str]) -> subprocess.CompletedProcess[str]:
        if args[:1] == ["cherry-pick"]:
            return subprocess.CompletedProcess(args, 128, "", "injected failure")
        return actual_run_git(args)

    monkeypatch.setattr(detector, "run_git", fail_cherry_pick)
    result = detector.detect_squash_residue_cmd(base="master", apply=True)

    application = result.get("application")
    assert application is not None
    assert application["state"] == "failed"
    failed_step = application["failed_step"]
    assert failed_step is not None and failed_step.startswith("git cherry-pick ")
    assert application["recovery_branch"] == "topic"
    assert application["error"] == "injected failure"
    assert git(repo, "branch", "--show-current").stdout.strip() == "topic-clean"


def test_squash_apply_uncertain_plan_merges_base(repo: Path) -> None:
    from unittest.mock import patch

    from easy_cheese.skills.melt import detect_squash_residue as detector

    _ = squash_with_followups(repo)
    squashed_sha = git(repo, "rev-list", "--reverse", "master..topic").stdout.splitlines()[0]
    gh = {
        "number": 1,
        "url": "https://example.com/pr/1",
        "merge_commit": None,
        "merged_at": "2026-01-01T00:00:00Z",
        "pr_commits": [squashed_sha],
        "multiple_prs": False,
    }
    with (
        patch.object(detector, "_check_via_tree_match", return_value=None),
        patch.object(detector, "_check_via_gh", return_value=gh),
    ):
        result = detector.detect_squash_residue_cmd(base="master", apply=True)

    application = result.get("application")
    assert application is not None
    assert application["state"] == "applied"
    assert application["remedy"] == "merge"
    assert git(repo, "branch", "--show-current").stdout.strip() == "topic"
    assert len(git(repo, "rev-list", "--parents", "-n", "1", "HEAD").stdout.split()) == 3


def test_operation_continue_returns_next_rebase_conflict(repo: Path) -> None:
    _ = (repo / "first.txt").write_text("base\n")
    _ = (repo / "second.txt").write_text("base\n")
    _ = git(repo, "add", "first.txt", "second.txt")
    _ = git(repo, "commit", "-qm", "files")
    _ = git(repo, "switch", "-qc", "topic")
    _ = (repo / "first.txt").write_text("topic first\n")
    _ = git(repo, "commit", "-qam", "first")
    _ = (repo / "second.txt").write_text("topic second\n")
    _ = git(repo, "commit", "-qam", "second")
    _ = git(repo, "switch", "-q", "master")
    _ = (repo / "first.txt").write_text("main first\n")
    _ = (repo / "second.txt").write_text("main second\n")
    _ = git(repo, "add", "first.txt", "second.txt")
    _ = git(repo, "commit", "-qm", "main")
    _ = git(repo, "switch", "-q", "topic")
    _ = git(repo, "rebase", "master", check=False)
    assert operation_cmd()["unmerged_paths"] == ["first.txt"]

    _ = (repo / "first.txt").write_text("resolved first\n")
    _ = git(repo, "add", "first.txt")
    result = operation_cmd(continue_operation=True)

    assert result["status"] == "blocked"
    assert result["operation"] == "rebase"
    assert result["unmerged_paths"] == ["second.txt"]


def test_gh_only_clean_branch_requires_merge_commit_on_selected_base(repo: Path) -> None:
    from unittest.mock import patch

    from easy_cheese.skills.melt import detect_squash_residue as detector

    _ = squash_with_followups(repo)
    base_sha = git(repo, "merge-base", "master", "topic").stdout.strip()
    _ = git(repo, "branch", "stale-base", base_sha)
    merge_sha = git(repo, "rev-parse", "master").stdout.strip()
    branch_shas = git(repo, "rev-list", "--reverse", f"{base_sha}..topic").stdout.splitlines()
    gh = {
        "number": 42,
        "url": "https://example.com/pr/42",
        "merge_commit": merge_sha,
        "merged_at": "2026-01-01T00:00:00Z",
        "pr_commits": branch_shas,
        "multiple_prs": False,
    }
    with (
        patch.object(detector, "_check_via_tree_match", return_value=None),
        patch.object(detector, "_check_via_gh", return_value=gh),
    ):
        stale = detector.detect("topic", "stale-base")
        contained = detector.detect("topic", "master")
        applied = detector.detect_squash_residue_cmd(base="stale-base", apply=True)

    assert [remedy["name"] for remedy in stale["remedies"]] == ["merge"]
    assert any("merge commit" in warning and "stale-base" in warning for warning in stale["warnings"])
    assert [remedy["name"] for remedy in contained["remedies"]] == ["clean-branch", "merge"]
    application = applied.get("application")
    assert application is not None
    assert application["remedy"] == "merge"
    assert application["state"] == "applied"
    assert git(repo, "show-ref", "--verify", "--quiet", "refs/heads/topic-clean", check=False).returncode == 1


def test_gh_only_unknown_merge_commit_uses_merge(repo: Path) -> None:
    from unittest.mock import patch

    from easy_cheese.skills.melt import detect_squash_residue as detector

    _ = squash_with_followups(repo)
    branch_shas = git(repo, "rev-list", "--reverse", "master..topic").stdout.splitlines()
    gh = {
        "number": 43,
        "url": "https://example.com/pr/43",
        "merge_commit": None,
        "merged_at": "2026-01-01T00:00:00Z",
        "pr_commits": branch_shas,
        "multiple_prs": False,
    }
    with (
        patch.object(detector, "_check_via_tree_match", return_value=None),
        patch.object(detector, "_check_via_gh", return_value=gh),
    ):
        result = detector.detect("topic", "master")

    assert [remedy["name"] for remedy in result["remedies"]] == ["merge"]
    assert any("merge commit" in warning for warning in result["warnings"])
