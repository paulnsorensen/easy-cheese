"""The dist publisher appends one complete tree per main commit and never moves back."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import publish_dist  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-dist.yml"


def _git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env
    ).stdout.strip()


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """A source checkout on main with a bare origin, like a CI checkout."""
    remote = tmp_path / "origin.git"
    _ = subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    repo = tmp_path / "source"
    _ = subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _ = _git(repo, "remote", "add", "origin", str(remote))
    _ = _commit(repo, "one")
    return repo


def _commit(repo: Path, label: str) -> str:
    _ = (repo / "src.txt").write_text(label)
    _ = _git(repo, "add", "src.txt")
    _ = _git(repo, "commit", "-q", "-m", label)
    _ = _git(repo, "push", "-q", "origin", "HEAD:main")
    _ = _git(repo, "fetch", "-q", "origin")
    return _git(repo, "rev-parse", "HEAD")


def _stage(root: Path, version: str) -> Path:
    scripts = root / "skills" / "cook" / "scripts"
    scripts.mkdir(parents=True)
    _ = (root / "skills" / "cook" / "SKILL.md").write_text(f"# cook {version}\n")
    archive = scripts / "cook.pyz"
    _ = archive.write_bytes(f"#!/usr/bin/env python3\n# {version}\n".encode())
    archive.chmod(0o755)
    return root


def _publish(repo: Path, sha: str, staged: Path) -> publish_dist.Result:
    return publish_dist.publish(
        repo, source=sha, staged=staged, remote="origin", branch="dist", trunk="origin/main"
    )


def _clone_dist(repo: Path, into: Path) -> Path:
    """Clone dist the way `npx skills add owner/repo#dist` does."""
    remote = _git(repo, "remote", "get-url", "origin")
    _ = subprocess.run(
        ["git", "clone", "-q", "--depth", "1", "--branch", "dist", remote, str(into)],
        check=True,
    )
    return into


def test_first_publish_creates_dist_with_the_whole_tree(source: Path, tmp_path: Path) -> None:
    sha = _git(source, "rev-parse", "HEAD")
    result = _publish(source, sha, _stage(tmp_path / "s1", "v1"))

    assert result.status == "published"
    clone = _clone_dist(source, tmp_path / "clone")
    assert (clone / "skills/cook/SKILL.md").read_text() == "# cook v1\n"
    archive = clone / "skills/cook/scripts/cook.pyz"
    assert archive.stat().st_mode & 0o111, "archive lost its executable bit"
    assert not (clone / "src.txt").exists(), "dist must hold only the staged tree"
    assert _git(clone, "log", "-1", "--format=%(trailers:key=Source-Commit,valueonly)") == sha


def test_next_publish_appends_one_commit_with_both_files(source: Path, tmp_path: Path) -> None:
    first = _publish(source, _git(source, "rev-parse", "HEAD"), _stage(tmp_path / "s1", "v1"))
    sha = _commit(source, "two")
    second = _publish(source, sha, _stage(tmp_path / "s2", "v2"))

    assert second.status == "published"
    clone = _clone_dist(source, tmp_path / "clone")
    assert _git(clone, "rev-parse", "HEAD^") == first.commit, "dist must fast-forward"
    changed = _git(clone, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(changed) == ["skills/cook/SKILL.md", "skills/cook/scripts/cook.pyz"]


def test_unchanged_tree_adds_no_commit(source: Path, tmp_path: Path) -> None:
    first = _publish(source, _git(source, "rev-parse", "HEAD"), _stage(tmp_path / "s1", "v1"))
    sha = _commit(source, "tests only")
    again = _publish(source, sha, _stage(tmp_path / "s2", "v1"))

    assert again.status == "unchanged"
    assert again.commit == first.commit


def test_older_source_cannot_move_dist_back(source: Path, tmp_path: Path) -> None:
    old = _git(source, "rev-parse", "HEAD")
    new = _commit(source, "two")
    newest = _publish(source, new, _stage(tmp_path / "s2", "v2"))

    with pytest.raises(SystemExit, match="refusing to move dist back"):
        _ = _publish(source, old, _stage(tmp_path / "s1", "v1"))
    assert _git(source, "ls-remote", "origin", "refs/heads/dist").split()[0] == newest.commit


def test_source_off_main_is_refused(source: Path, tmp_path: Path) -> None:
    _ = _git(source, "switch", "-q", "-c", "feature")
    _ = (source / "src.txt").write_text("unreviewed")
    _ = _git(source, "commit", "-q", "-am", "unreviewed")

    with pytest.raises(SystemExit, match="is not on origin/main"):
        _ = _publish(source, "HEAD", _stage(tmp_path / "s1", "v1"))
    assert _git(source, "ls-remote", "origin", "refs/heads/dist") == ""


def test_empty_stage_is_refused(source: Path, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit, match="no staged skills"):
        _ = _publish(source, "HEAD", tmp_path / "empty")


def test_workflow_builds_stages_checks_then_publishes() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    order = [
        workflow.index("just wedge-build"),
        workflow.index("python3 scripts/stage_release.py"),
        workflow.index("gh skill publish --dry-run"),
        workflow.index("--help"),
        workflow.index("python3 scripts/publish_dist.py"),
    ]
    assert order == sorted(order)


def test_workflow_runs_one_publish_at_a_time() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "group: publish-dist" in workflow
    assert "cancel-in-progress: false" in workflow
