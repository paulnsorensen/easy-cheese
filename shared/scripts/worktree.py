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
import subprocess

# cli is co-staged in the bundled .pyz alongside this module
import cli

WORKTREE_DIR = ".claude/worktrees"


def _worktree_path(slug: str) -> str:
    return f"{WORKTREE_DIR}/agent-{slug}"


def _worktree_branch(slug: str) -> str:
    return f"worktree-agent-{slug}"


def _git(repo: str, *args: str) -> str:
    """Run a git command in `repo`; raise CliError (loud) on failure."""
    result = subprocess.run(
        ["git", "-C", repo, *args],
        capture_output=True,
        text=True,
    )
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
    if (
        not norm.startswith(prefix)
        or ".." in norm.split(os.sep)
        or not os.path.basename(norm).startswith("agent-")
    ):
        raise cli.CliError(
            f"refusing to tear down {path!r}: not a {WORKTREE_DIR}/agent-* worktree"
        )
    if not branch.startswith("worktree-agent-"):
        raise cli.CliError(
            f"refusing to delete branch {branch!r}: not a worktree-agent-* branch"
        )


def create(slug: str, base: str, *, repo: str = ".") -> dict:
    """Create a git worktree at `.claude/worktrees/agent-<slug>` on a fresh
    `worktree-agent-<slug>` branch off `base`. Mirrors the native primitive's
    path/branch shape. Returns `{path, branch}`."""
    _validate_slug(slug)
    path = _worktree_path(slug)
    branch = _worktree_branch(slug)
    _git(repo, "worktree", "add", "-b", branch, path, base)
    return {"path": path, "branch": branch}


def harvest(branch: str, onto: str, *, repo: str = ".") -> list[str]:
    """Cherry-pick the commits unique to `branch` onto `onto` (the orchestrator
    branch). Shared `.git` object store means no fetch. Returns the picked SHAs
    (oldest first); an empty list when `branch` added nothing over `onto`."""
    _git(repo, "checkout", onto)
    revs = _git(repo, "rev-list", "--reverse", f"{onto}..{branch}").split()
    if not revs:
        return []
    try:
        _git(repo, "cherry-pick", *revs)
    except cli.CliError:
        # Leave the repo clean for the orchestrator's /melt fallback: a
        # half-finished cherry-pick (unmerged index / CHERRY_PICK_HEAD) would
        # cascade-poison the next harvest's `git checkout onto`.
        subprocess.run(["git", "-C", repo, "cherry-pick", "--abort"], capture_output=True, text=True)
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
            _git(repo, *args)
        except cli.CliError as exc:
            errors.append(str(exc))
    if errors:
        raise cli.CliError("; ".join(errors))


def _cmd_create(args: argparse.Namespace) -> None:
    cli.emit(create(args.slug, args.base, repo=args.repo), json_mode=True)


def _cmd_harvest(args: argparse.Namespace) -> None:
    picked = harvest(args.branch, args.onto, repo=args.repo)
    cli.emit({"picked": picked}, json_mode=True)


def _cmd_teardown(args: argparse.Namespace) -> None:
    teardown(args.path, args.branch, repo=args.repo)
    cli.emit({"removed": args.path, "deleted_branch": args.branch}, json_mode=True)


def _setup(parser: argparse.ArgumentParser) -> None:
    parser.description = "Create, harvest, or tear down a curd worktree."
    sub = parser.add_subparsers(dest="action", required=True)

    p_create = sub.add_parser("create", help="Create a worktree off a base ref.")
    p_create.add_argument("--slug", required=True, help="Curd slug (names the worktree + branch).")
    p_create.add_argument("--base", required=True, help="Base ref to branch the worktree from.")
    p_create.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_create.set_defaults(func=_cmd_create)

    p_harvest = sub.add_parser("harvest", help="Cherry-pick a curd branch onto the orchestrator branch.")
    p_harvest.add_argument("--branch", required=True, help="Curd branch to harvest.")
    p_harvest.add_argument("--onto", required=True, help="Orchestrator branch to cherry-pick onto.")
    p_harvest.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_harvest.set_defaults(func=_cmd_harvest)

    p_teardown = sub.add_parser("teardown", help="Remove a worktree and delete its branch.")
    p_teardown.add_argument("--path", required=True, help="Worktree path to remove.")
    p_teardown.add_argument("--branch", required=True, help="Worktree branch to delete.")
    p_teardown.add_argument("--repo", default=".", help="Repo root (default: cwd).")
    p_teardown.set_defaults(func=_cmd_teardown)


if __name__ == "__main__":
    cli.run(_setup)
