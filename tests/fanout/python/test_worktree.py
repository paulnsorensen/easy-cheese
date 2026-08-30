"""Tests for shared/scripts/worktree.py — create / harvest / teardown.

Locks acceptance #5: the helper harvests a curd branch onto the orchestrator
branch with no `git fetch` (shared object store), and tears the worktree and
branch down afterwards so no `worktree-agent-*` branch or
`.claude/worktrees/agent-*` dir leaks.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _run(r, "init", "-b", "main")
    _run(r, "config", "user.email", "t@example.com")
    _run(r, "config", "user.name", "Tester")
    (r / "base.txt").write_text("base\n", encoding="utf-8")
    _run(r, "add", "-A")
    _run(r, "commit", "-m", "init")
    return r


class TestCreate:
    def test_native_path_and_branch_shape(self, worktree: ModuleType, repo: Path) -> None:
        info = worktree.create("curd1", "main", repo=str(repo))
        assert info["path"] == ".claude/worktrees/agent-curd1"
        assert info["branch"] == "worktree-agent-curd1"
        assert (repo / info["path"]).is_dir()
        branches = _run(repo, "branch", "--list", "worktree-agent-curd1").stdout
        assert "worktree-agent-curd1" in branches


class TestHarvest:
    def test_cherry_picks_curd_commit_without_fetch(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        info = worktree.create("curd2", "main", repo=str(repo))
        wt = repo / info["path"]
        (wt / "feature.txt").write_text("feature\n", encoding="utf-8")
        _run(wt, "add", "-A")
        _run(wt, "commit", "-m", "add feature")

        # No remote is configured, so a successful harvest proves no fetch.
        assert _run(repo, "remote").stdout.strip() == ""
        picked = worktree.harvest(info["branch"], "main", repo=str(repo))

        assert len(picked) == 1
        assert (repo / "feature.txt").exists()
        head_branch = _run(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        assert head_branch == "main"

    def test_empty_range_returns_empty(self, worktree: ModuleType, repo: Path) -> None:
        info = worktree.create("curd3", "main", repo=str(repo))
        assert worktree.harvest(info["branch"], "main", repo=str(repo)) == []

    def test_multiple_commits_harvested_in_order(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        info = worktree.create("curd5", "main", repo=str(repo))
        wt = repo / info["path"]
        for i in range(3):
            (wt / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
            _run(wt, "add", "-A")
            _run(wt, "commit", "-m", f"commit {i}")
        # Oldest-first: the picked SHAs must equal `git rev-list --reverse`.
        expected = _run(
            repo, "rev-list", "--reverse", f"main..{info['branch']}"
        ).stdout.split()
        picked = worktree.harvest(info["branch"], "main", repo=str(repo))
        assert picked == expected
        assert len(expected) == 3
        for i in range(3):
            assert (repo / f"f{i}.txt").exists()

    def test_conflict_aborts_and_leaves_repo_clean(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        # Two commits edit the same file on branch and onto → cherry-pick
        # conflict. harvest must raise AND abort, so the repo is not left
        # mid-cherry-pick (which would poison the next harvest's checkout).
        info = worktree.create("curd8", "main", repo=str(repo))
        wt = repo / info["path"]
        (wt / "base.txt").write_text("worktree edit\n", encoding="utf-8")
        _run(wt, "add", "-A")
        _run(wt, "commit", "-m", "wt edit")
        (repo / "base.txt").write_text("main edit\n", encoding="utf-8")
        _run(repo, "add", "-A")
        _run(repo, "commit", "-m", "main edit")

        with pytest.raises(worktree.cli.CliError):
            worktree.harvest(info["branch"], "main", repo=str(repo))

        # No CHERRY_PICK_HEAD left behind.
        head = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "-q", "--verify", "CHERRY_PICK_HEAD"],
            capture_output=True,
            text=True,
        )
        assert head.returncode != 0
        # A subsequent checkout succeeds — repo is clean for the /melt fallback.
        _run(repo, "checkout", "main")


class TestTeardown:
    def test_no_worktree_or_branch_leaks(self, worktree: ModuleType, repo: Path) -> None:
        info = worktree.create("curd4", "main", repo=str(repo))
        worktree.teardown(info["path"], info["branch"], repo=str(repo))

        assert not (repo / info["path"]).exists()
        branches = _run(repo, "branch", "--list", "worktree-agent-curd4").stdout
        assert "worktree-agent-curd4" not in branches
        assert "agent-curd4" not in _run(repo, "worktree", "list").stdout

    def test_full_lifecycle_leaves_clean_tree(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        info = worktree.create("curd6", "main", repo=str(repo))
        wt = repo / info["path"]
        (wt / "x.txt").write_text("x\n", encoding="utf-8")
        _run(wt, "add", "-A")
        _run(wt, "commit", "-m", "x")
        worktree.harvest(info["branch"], "main", repo=str(repo))
        worktree.teardown(info["path"], info["branch"], repo=str(repo))

        # No leaked worktree registrations or branches for a completed run.
        listing = _run(repo, "worktree", "list").stdout
        assert "agent-curd6" not in listing
        assert "worktree-agent-curd6" not in _run(repo, "branch", "--list").stdout

    def test_partial_teardown_still_deletes_branch(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        # Worktree dir vanishes out from under us (remove will fail), but the
        # branch still exists. teardown must still delete the branch — the
        # remove failure must not skip the branch delete, or the branch leaks.
        info = worktree.create("curd7", "main", repo=str(repo))
        shutil.rmtree(repo / info["path"])
        _run(repo, "worktree", "prune")

        with pytest.raises(worktree.cli.CliError):
            worktree.teardown(info["path"], info["branch"], repo=str(repo))

        branches = _run(repo, "branch", "--list", "worktree-agent-curd7").stdout
        assert "worktree-agent-curd7" not in branches


class TestFailsLoud:
    def test_teardown_of_missing_worktree_raises(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        with pytest.raises(worktree.cli.CliError):
            worktree.teardown(
                ".claude/worktrees/agent-nope", "worktree-agent-nope", repo=str(repo)
            )


class TestCreateValidatesSlug:
    """Review fix: create() must reject a slug that escapes
    .claude/worktrees/agent-<slug> — a path separator or '..' would place the
    worktree and branch at an attacker-chosen location."""

    @pytest.mark.parametrize("bad", ["../escape", "a/b", "..", "", "a\\b"])
    def test_bad_slug_raises_and_creates_nothing(
        self, worktree: ModuleType, repo: Path, bad: str
    ) -> None:
        with pytest.raises(worktree.cli.CliError, match="invalid slug"):
            worktree.create(bad, "main", repo=str(repo))
        assert "agent-" not in _run(repo, "worktree", "list").stdout


class TestTeardownGuardsTarget:
    """Review fix: teardown() must refuse a path outside
    .claude/worktrees/agent-* or a branch not named worktree-agent-*, so a bad
    argument cannot force-remove an arbitrary path or force-delete a branch."""

    def test_path_outside_worktree_dir_refused(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        with pytest.raises(worktree.cli.CliError, match="refusing to tear down"):
            worktree.teardown("some/other/dir", "worktree-agent-x", repo=str(repo))

    def test_escaping_path_refused(self, worktree: ModuleType, repo: Path) -> None:
        with pytest.raises(worktree.cli.CliError, match="refusing to tear down"):
            worktree.teardown(
                ".claude/worktrees/../../etc/agent-x", "worktree-agent-x", repo=str(repo)
            )

    def test_non_worktree_branch_refused(
        self, worktree: ModuleType, repo: Path
    ) -> None:
        with pytest.raises(worktree.cli.CliError, match="refusing to delete branch"):
            worktree.teardown(".claude/worktrees/agent-x", "main", repo=str(repo))