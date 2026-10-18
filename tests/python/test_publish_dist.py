"""The dist publisher appends one source tree plus its archives per main commit."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import publish_dist  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish-dist.yml"
VALIDATE = REPO_ROOT / ".github" / "workflows" / "validate.yml"
RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"
ARCHIVE = "skills/cook/scripts/cook.pyz"


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
    (repo / "skills" / "cook").mkdir(parents=True)
    _ = (repo / "skills" / "cook" / "SKILL.md").write_text("# cook\n")
    _ = _git(repo, "add", "skills")
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
    archive = root / ARCHIVE
    archive.parent.mkdir(parents=True)
    _ = archive.write_bytes(f"#!/usr/bin/env python3\n# {version}\n".encode())
    archive.chmod(0o755)
    return root


def _publish(repo: Path, sha: str, staged: Path) -> publish_dist.Result:
    return publish_dist.publish(
        repo, source=sha, staged=staged, remote="origin", branch="dist", trunk="origin/main"
    )


def _clone_dist(repo: Path, into: Path) -> Path:
    """Clone dist the way `npx skills add` clones a branch: depth 1."""
    remote = _git(repo, "remote", "get-url", "origin")
    _ = subprocess.run(
        ["git", "clone", "-q", "--depth", "1", "--branch", "dist", remote, str(into)],
        check=True,
    )
    return into


def test_first_publish_holds_source_and_archives(source: Path, tmp_path: Path) -> None:
    sha = _git(source, "rev-parse", "HEAD")
    result = _publish(source, sha, _stage(tmp_path / "s1", "v1"))

    assert result.status == "published"
    clone = _clone_dist(source, tmp_path / "clone")
    assert (clone / "src.txt").read_text() == "one"
    assert (clone / "skills/cook/SKILL.md").read_text() == "# cook\n"
    archive = clone / ARCHIVE
    assert archive.read_bytes().endswith(b"# v1\n")
    assert archive.stat().st_mode & 0o111, "archive lost its executable bit"
    assert _git(clone, "log", "-1", "--format=%(trailers:key=Source-Commit,valueonly)") == sha


def test_next_publish_moves_source_and_archive_in_one_commit(
    source: Path, tmp_path: Path
) -> None:
    first = _publish(source, _git(source, "rev-parse", "HEAD"), _stage(tmp_path / "s1", "v1"))
    sha = _commit(source, "two")
    second = _publish(source, sha, _stage(tmp_path / "s2", "v2"))

    assert second.status == "published"
    clone = _clone_dist(source, tmp_path / "clone")
    assert _git(clone, "rev-parse", "HEAD^") == first.commit, "dist must fast-forward"
    changed = _git(clone, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(changed) == [ARCHIVE, "src.txt"]


def test_republishing_the_same_source_adds_no_commit(source: Path, tmp_path: Path) -> None:
    sha = _git(source, "rev-parse", "HEAD")
    first = _publish(source, sha, _stage(tmp_path / "s1", "v1"))
    again = _publish(source, sha, _stage(tmp_path / "s2", "v1"))

    assert again.status == "unchanged"
    assert again.commit == first.commit


def test_built_archives_replace_tracked_ones(source: Path, tmp_path: Path) -> None:
    """A stale tracked archive, or one for a removed skill, never ships."""
    for rel, body in ((ARCHIVE, b"stale"), ("skills/gone/scripts/gone.pyz", b"gone")):
        path = source / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_bytes(body)
    _ = _git(source, "add", "-f", "skills")
    sha = _commit(source, "tracked archives")

    _ = _publish(source, sha, _stage(tmp_path / "s1", "v1"))
    clone = _clone_dist(source, tmp_path / "clone")
    assert (clone / ARCHIVE).read_bytes().endswith(b"# v1\n")
    assert not (clone / "skills/gone").exists()


def test_older_source_is_a_no_op(source: Path, tmp_path: Path) -> None:
    """A late run for an older commit succeeds without moving dist back."""
    old = _git(source, "rev-parse", "HEAD")
    new = _commit(source, "two")
    newest = _publish(source, new, _stage(tmp_path / "s2", "v2"))

    late = _publish(source, old, _stage(tmp_path / "s1", "v1"))

    assert late.status == "superseded"
    assert _git(source, "ls-remote", "origin", "refs/heads/dist").split()[0] == newest.commit


def test_diverged_source_cannot_move_dist_back(source: Path, tmp_path: Path) -> None:
    base = _git(source, "rev-parse", "HEAD")
    published = _publish(source, _commit(source, "two"), _stage(tmp_path / "s1", "v1"))
    _ = _git(source, "reset", "-q", "--hard", base)
    _ = (source / "src.txt").write_text("rewritten")
    _ = _git(source, "commit", "-q", "-am", "rewritten")
    _ = _git(source, "push", "-q", "-f", "origin", "HEAD:main")
    _ = _git(source, "fetch", "-q", "origin")

    with pytest.raises(SystemExit, match="refusing to move dist back"):
        _ = _publish(source, "HEAD", _stage(tmp_path / "s2", "v2"))
    assert _git(source, "ls-remote", "origin", "refs/heads/dist").split()[0] == published.commit


def test_hand_pushed_tip_does_not_stall_publishing(source: Path, tmp_path: Path) -> None:
    """A dist commit with no Source-Commit trailer is published over, not a dead end."""
    first = _publish(source, _git(source, "rev-parse", "HEAD"), _stage(tmp_path / "s1", "v1"))
    hand = _git(source, "commit-tree", f"{first.commit}^{{tree}}", "-p", first.commit, "-m", "hand")
    _ = _git(source, "push", "-q", "origin", f"{hand}:refs/heads/dist")
    sha = _commit(source, "two")

    result = _publish(source, sha, _stage(tmp_path / "s2", "v2"))

    assert result.status == "published"
    clone = _clone_dist(source, tmp_path / "clone")
    assert _git(clone, "log", "-1", "--format=%(trailers:key=Source-Commit,valueonly)") == sha
    assert (clone / ARCHIVE).read_bytes().endswith(b"# v2\n")


def test_source_off_main_is_refused(source: Path, tmp_path: Path) -> None:
    _ = _git(source, "switch", "-q", "-c", "feature")
    _ = (source / "src.txt").write_text("unreviewed")
    _ = _git(source, "commit", "-q", "-am", "unreviewed")

    with pytest.raises(SystemExit, match="is not on origin/main"):
        _ = _publish(source, "HEAD", _stage(tmp_path / "s1", "v1"))
    assert _git(source, "ls-remote", "origin", "refs/heads/dist") == ""


def test_stage_without_archives_is_refused(source: Path, tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(SystemExit, match="no staged archives"):
        _ = _publish(source, "HEAD", tmp_path / "empty")


def test_main_tracks_no_archives() -> None:
    """Archives live only on dist; a branch cut from dist must not merge them back."""
    tracked = _git(REPO_ROOT, "ls-files", "--", publish_dist.ARCHIVES)
    assert tracked == "", (
        "main must not track archives; branch from main, not dist, and drop: " + tracked
    )


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


def _load(path: Path) -> dict[object, object]:
    return cast("dict[object, object]", yaml.safe_load(path.read_text(encoding="utf-8")))


def _steps(path: Path, job: str) -> list[dict[str, object]]:
    jobs = cast("dict[str, dict[str, list[dict[str, object]]]]", _load(path)["jobs"])
    return jobs[job]["steps"]


def test_workflow_publishes_the_main_tip_on_every_trigger() -> None:
    """A cancelled or failed run loses nothing, because the next run publishes main's tip."""
    triggers = cast("dict[str, object]", _load(WORKFLOW)[True])  # YAML reads `on` as True.
    assert set(triggers) == {"push", "schedule", "workflow_dispatch"}
    assert triggers["schedule"], "the hourly reconcile catches a lost or failed run"
    steps = _steps(WORKFLOW, "publish")
    checkout = next(s for s in steps if s.get("name") == "Checkout")
    assert cast("dict[str, object]", checkout["with"])["ref"] == "main"
    publish = str(next(s for s in steps if s.get("name") == "Publish dist commit")["run"])
    assert "--source HEAD" in publish
    assert "GITHUB_SHA" not in publish


def test_validate_runs_the_publish_checks_before_merge() -> None:
    """A change that would fail the dist publish fails its pull request first."""
    runs = [str(s.get("run", "")) for s in _steps(VALIDATE, "test")]
    order = [
        next(i for i, run in enumerate(runs) if "just wedge-build" in run),
        next(i for i, run in enumerate(runs) if "scripts/stage_release.py" in run),
        next(i for i, run in enumerate(runs) if "gh skill publish --dry-run" in run),
        next(i for i, run in enumerate(runs) if "--help" in run),
    ]
    assert order == sorted(order)


@pytest.mark.parametrize(
    "workflow", [WORKFLOW, VALIDATE, RELEASE], ids=["publish-dist", "validate", "release"]
)
def test_gh_install_makes_no_api_call(workflow: Path) -> None:
    """An unauthenticated API call hits the shared runner rate limit and fails with 403."""
    text = workflow.read_text(encoding="utf-8")
    assert "gh skill publish --dry-run" in text
    assert "api.github.com" not in text