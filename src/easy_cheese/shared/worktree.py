#!/usr/bin/env python3
"""Shared worktree floor for isolated sub-agent/worktree dispatch: create, harvest, teardown. Used by /ultracook's parallel-mode fan-out and by the repair-worktree pathway (skills/cook/references/quality-gates.md § Repair pathway).

On Claude Code the native `Agent(isolation:"worktree")` primitive creates the
worktree and returns `{agentId, worktreePath, worktreeBranch}`, so the
orchestrator never guesses the branch name. `create()` is the harness-agnostic
floor for harnesses that lack that primitive.

Both paths share one `.git` object store with the parent, so a curd branch is
`harvest()`-able with **no `git fetch`** — cherry-pick sees the sub-agent's
commits immediately. Worktrees leak unless explicitly removed, so the engine
owns `teardown()` (worktree remove + branch delete) for every completed curd.
"""
from __future__ import annotations
import os
from pathlib import Path
import sys


from cyclopts import App

# cli and git_utils are co-staged in the bundled .pyz alongside this module
from easy_cheese.shared import cli, git_utils

WORKTREE_DIR = ".claude/worktrees"


def _worktree_path(slug: str) -> str:
    return f"{WORKTREE_DIR}/agent-{slug}"


def _worktree_branch(slug: str) -> str:
    return f"worktree-agent-{slug}"


def _git(repo: str, *args: str) -> str:
    """Run a git command in `repo`; raise CliError (loud) on failure."""
    result = git_utils.run_git(list(args), cwd=repo)
    if result.returncode != 0:
        raise cli.CliError(
            f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def _validate_slug(slug: str) -> None:
    """Reject a slug that would escape .claude/worktrees/agent-<slug>: no path
    separators, no parent refs, no empty. The slug names the worktree dir and
    branch, so an unchecked slug is arbitrary path/branch injection."""
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        raise cli.CliError(
            f"invalid slug {slug!r}: must be non-empty and free of path separators or '..'"
        )


def _validate_teardown_target(path: str, branch: str) -> None:
    """Refuse anything but a .claude/worktrees/agent-* worktree on a
    worktree-agent-* branch: teardown force-removes a worktree and force-deletes
    a branch, so an arbitrary path/branch would be destructive."""
    norm = os.path.normpath(path)
    prefix = WORKTREE_DIR + os.sep
    norm_path = Path(norm)
    if (
        not norm.startswith(prefix)
        or ".." in norm_path.parts
        or not norm_path.name.startswith("agent-")
    ):
        raise cli.CliError(
            f"refusing to tear down {path!r}: not a {WORKTREE_DIR}/agent-* worktree"
        )
    if not branch.startswith("worktree-agent-"):
        raise cli.CliError(
            f"refusing to delete branch {branch!r}: not a worktree-agent-* branch"
        )


def create(slug: str, base: str, *, repo: str = ".") -> dict[str, object]:
    """Create a fresh worktree off ``base``."""
    _validate_slug(slug)
    path = _worktree_path(slug)
    branch = _worktree_branch(slug)
    _ = _git(repo, "worktree", "add", "-b", branch, path, base)
    return {"path": path, "branch": branch}


def harvest(branch: str, onto: str, *, repo: str = ".") -> list[str]:
    """Cherry-pick the commits unique to `branch` onto `onto` (the orchestrator
    branch). Shared `.git` object store means no fetch. Returns the picked SHAs
    (oldest first); an empty list when `branch` added nothing over `onto`."""
    _ = _git(repo, "checkout", onto)
    revs = _git(repo, "rev-list", "--reverse", f"{onto}..{branch}").split()
    if not revs:
        return []
    try:
        _ = _git(repo, "cherry-pick", *revs)
    except cli.CliError:
        # Leave the repo clean for the orchestrator's /melt fallback: a
        # half-finished cherry-pick (unmerged index / CHERRY_PICK_HEAD) would
        # cascade-poison the next harvest's `git checkout onto`.
        _ = git_utils.run_git(["cherry-pick", "--abort"], cwd=repo)
        raise
    return revs


def teardown(path: str, branch: str, *, repo: str = ".") -> None:
    """Remove the worktree at `path` and delete its `branch`. Leaves no
    `worktree-agent-*` branch or `.claude/worktrees/agent-*` dir behind.

    Best-effort and order-independent: a failure removing the worktree must not
    skip the branch delete (that would leak the branch). Both steps are always
    attempted; a combined error is raised at the end if either failed."""
    _validate_teardown_target(path, branch)
    errors: list[str] = []
    for args in (("worktree", "remove", "--force", path), ("branch", "-D", branch)):
        try:
            _ = _git(repo, *args)
        except cli.CliError as exc:
            errors.append(str(exc))
    if errors:
        raise cli.CliError("; ".join(errors))




def _create_command(*, slug: str, base: str, repo: str = ".") -> int:
    cli.emit(create(slug, base, repo=repo), json_mode=True)
    return 0

def _harvest_command(*, branch: str, onto: str, repo: str = ".") -> int:
    cli.emit({"picked": harvest(branch, onto, repo=repo)}, json_mode=True)
    return 0

def _teardown_command(*, path: str, branch: str, repo: str = ".") -> int:
    teardown(path, branch, repo=repo)
    cli.emit({"removed": path, "deleted_branch": branch}, json_mode=True)
    return 0

LEAVES = ("create", "harvest", "teardown")
app = App(name="worktree")
_ = app.command(_create_command, name="create")
_ = app.command(_harvest_command, name="harvest")
_ = app.command(_teardown_command, name="teardown")

def main(argv: list[str]) -> int:
    return cli.run(app, argv=argv)

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
