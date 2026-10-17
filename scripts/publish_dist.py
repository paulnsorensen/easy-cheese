#!/usr/bin/env python3
"""Publish one staged release tree as one commit on the dist branch.

Each dist commit holds the complete shippable tree built from one main
commit. One push moves the branch, so a clone sees the old skills and
archives or the new ones, never a mix. The branch is append-only: a publish
fast-forwards it and records its source in a `Source-Commit` trailer. A
source that does not descend from the last published source is refused, so
a late or manual run cannot move dist back.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

TRAILER = "Source-Commit"
BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "actions@github.com"


@dataclass(frozen=True)
class Result:
    status: str  # "published" or "unchanged"
    commit: str
    source: str


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        detail = (cast(str | None, exc.stderr) or cast(str | None, exc.stdout) or "").strip()
        raise SystemExit(f"publish_dist: git {' '.join(args)} failed: {detail}") from exc
    return completed.stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
        text=True,
    )
    if completed.returncode not in (0, 1):
        raise SystemExit(
            f"publish_dist: cannot compare {ancestor} with {descendant}: "
            + completed.stderr.strip()
        )
    return completed.returncode == 0


def _remote_tip(repo: Path, remote: str, branch: str) -> str | None:
    """Fetch the dist tip, or return None when the branch does not exist yet."""
    if not _git(repo, "ls-remote", "--heads", remote, f"refs/heads/{branch}"):
        return None
    _ = _git(repo, "fetch", "--quiet", "--no-tags", "--depth=1", remote, f"refs/heads/{branch}")
    return _git(repo, "rev-parse", "FETCH_HEAD^{commit}")


def _staged_tree(repo: Path, staged: Path) -> str:
    """Write the staged directory as a tree object; ignore rules do not apply."""
    git_dir = _git(repo, "rev-parse", "--absolute-git-dir")
    with tempfile.TemporaryDirectory() as scratch:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(scratch) / "index")}
        tree_args = ("--git-dir", git_dir, "--work-tree", str(staged))
        _ = _git(staged, *tree_args, "add", "--all", "--force", ".", env=env)
        return _git(staged, *tree_args, "write-tree", env=env)


def publish(
    repo: Path,
    *,
    source: str,
    staged: Path,
    remote: str,
    branch: str,
    trunk: str,
) -> Result:
    """Append the staged tree for `source` to `branch` on `remote`."""
    if not any(staged.glob("skills/*/SKILL.md")):
        raise SystemExit(f"publish_dist: no staged skills under {staged}")
    source = _git(repo, "rev-parse", "--verify", f"{source}^{{commit}}")
    if not _is_ancestor(repo, source, trunk):
        raise SystemExit(f"publish_dist: {source} is not on {trunk}; refusing to publish")

    tip = _remote_tip(repo, remote, branch)
    tree = _staged_tree(repo, staged)
    if tip is not None:
        published = _git(repo, "log", "-1", f"--format=%(trailers:key={TRAILER},valueonly)", tip)
        if not published:
            raise SystemExit(f"publish_dist: {branch} tip {tip} has no {TRAILER} trailer")
        if not _is_ancestor(repo, published, source):
            raise SystemExit(
                f"publish_dist: {branch} already holds {published}, which {source} "
                + "does not descend from; refusing to move dist back"
            )
        if _git(repo, "rev-parse", f"{tip}^{{tree}}") == tree:
            return Result("unchanged", tip, source)

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": BOT_NAME,
        "GIT_AUTHOR_EMAIL": BOT_EMAIL,
        "GIT_COMMITTER_NAME": BOT_NAME,
        "GIT_COMMITTER_EMAIL": BOT_EMAIL,
    }
    message = f"dist: main@{source}\n\n{TRAILER}: {source}\n"
    parents = ("-p", tip) if tip is not None else ()
    commit = _git(repo, "commit-tree", tree, *parents, "-m", message, env=env)
    # No force: a concurrent writer makes this push fail instead of losing a commit.
    _ = _git(repo, "push", "--quiet", remote, f"{commit}:refs/heads/{branch}")
    return Result("published", commit, source)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--source", required=True, help="main commit the tree was built from")
    _ = parser.add_argument("--staged", type=Path, required=True, help="stage_release.py output")
    _ = parser.add_argument("--remote", default="origin")
    _ = parser.add_argument("--branch", default="dist")
    _ = parser.add_argument("--trunk", default="origin/main", help="ref the source must be on")
    _ = parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args(argv[1:])
    result = publish(
        cast(Path, args.repo),
        source=cast(str, args.source),
        staged=cast(Path, args.staged).resolve(),
        remote=cast(str, args.remote),
        branch=cast(str, args.branch),
        trunk=cast(str, args.trunk),
    )
    print(f"{result.status} {cast(str, args.branch)}@{result.commit} from main@{result.source}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
