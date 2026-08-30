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

import argparse
import os
from pathlib import Path
from typing import TextIO, cast

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


def _cmd_create(args: argparse.Namespace) -> None:
    cli.emit(
        create(
            cast(str, args.slug),
            cast(str, args.base),
            repo=cast(str, args.repo),
        ),
        json_mode=True,
        stdout=cast("TextIO | None", args.stdout),
    )


def _cmd_harvest(args: argparse.Namespace) -> None:
    picked = harvest(cast(str, args.branch), cast(str, args.onto), repo=cast(str, args.repo))
    cli.emit({"picked": picked}, json_mode=True, stdout=cast("TextIO | None", args.stdout))


def _cmd_teardown(args: argparse.Namespace) -> None:
    path = cast(str, args.path)
    branch = cast(str, args.branch)
    teardown(path, branch, repo=cast(str, args.repo))
    cli.emit(
        {"removed": path, "deleted_branch": branch},
        json_mode=True,
        stdout=cast("TextIO | None", args.stdout),
    )


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Create, harvest, or tear down a curd worktree."
    sub = parser.add_subparsers(dest="action", required=True)

    p_create = sub.add_parser("create", help="Create a worktree off a base ref.")
    _ = p_create.add_argument("--slug", required=True, help="Curd slug (names the worktree + branch).")
    _ = p_create.add_argument("--base", required=True, help="Base ref to branch the worktree from.")
    _ = p_create.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_create.set_defaults(func=_cmd_create)

    p_harvest = sub.add_parser("harvest", help="Cherry-pick a curd branch onto the orchestrator branch.")
    _ = p_harvest.add_argument("--branch", required=True, help="Curd branch to harvest.")
    _ = p_harvest.add_argument("--onto", required=True, help="Orchestrator branch to cherry-pick onto.")
    _ = p_harvest.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_harvest.set_defaults(func=_cmd_harvest)

    p_teardown = sub.add_parser("teardown", help="Remove a worktree and delete its branch.")
    _ = p_teardown.add_argument("--path", required=True, help="Worktree path to remove.")
    _ = p_teardown.add_argument("--branch", required=True, help="Worktree branch to delete.")
    _ = p_teardown.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_teardown.set_defaults(func=_cmd_teardown)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)


if __name__ == "__main__":
    raise SystemExit(cli.run(_setup))
