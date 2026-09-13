"""Seed an isolated git worktree for a benchmark case.

Creates a scratch git repo from the case's ``base/`` tree, applies
``seed.patch`` on a fresh branch in a linked worktree, and prints the
worktree path plus the two review commands (``/age`` and ``/code-review``)
an operator runs next.
"""

from __future__ import annotations

import argparse
import contextlib
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

from easy_cheese.shared import cli
from easy_cheese.skills.age_bench.cases import load_case

GIT_TIMEOUT_SECONDS = 30


class PrepareError(Exception):
    """Raised when a git step in preparing the worktree fails."""


@dataclass(frozen=True)
class PreparedWorktree:
    case_id: str
    worktree_dir: Path
    branch: str
    scratch_dir: Path


def _run(argv: list[str], *, cwd: Path) -> None:
    try:
        result = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise PrepareError(
            f"{' '.join(argv)} timed out after {GIT_TIMEOUT_SECONDS}s"
        ) from exc
    if result.returncode != 0:
        raise PrepareError(f"{' '.join(argv)} failed: {result.stderr.strip()}")


def prepare_worktree(case_id: str, *, repo_root: Path | str | None = None) -> PreparedWorktree:
    case = load_case(case_id, repo_root=repo_root)
    scratch_dir = Path(tempfile.mkdtemp(prefix=f"age-bench-{case_id}-"))
    repo_dir = scratch_dir / "repo"
    worktree_dir = scratch_dir / "worktree"
    branch = f"age-bench/{case_id}"

    worktree_registered = False
    try:
        _ = shutil.copytree(case.base_dir, repo_dir)
        _run(["git", "init", "-q", "-b", "main"], cwd=repo_dir)
        _run(["git", "config", "user.email", "age-bench@example.invalid"], cwd=repo_dir)
        _run(["git", "config", "user.name", "age-bench"], cwd=repo_dir)
        _run(["git", "add", "-A"], cwd=repo_dir)
        _run(["git", "commit", "-q", "-m", "base"], cwd=repo_dir)
        _run(["git", "worktree", "add", "-q", "-b", branch, str(worktree_dir)], cwd=repo_dir)
        worktree_registered = True
        _run(["git", "apply", str(case.seed_patch.resolve())], cwd=worktree_dir)
    except Exception:
        if worktree_registered:
            with contextlib.suppress(OSError, subprocess.TimeoutExpired):
                _ = subprocess.run(
                    ["git", "worktree", "remove", "-f", str(worktree_dir)],
                    cwd=repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=GIT_TIMEOUT_SECONDS,
                )
        shutil.rmtree(scratch_dir, ignore_errors=True)
        raise

    return PreparedWorktree(
        case_id=case_id, worktree_dir=worktree_dir, branch=branch, scratch_dir=scratch_dir
    )


def _cmd_prepare(args: argparse.Namespace) -> int:
    case_id = cast(str, args.case_id)
    repo_root = cast("str | None", args.repo_root)
    try:
        prepared = prepare_worktree(case_id, repo_root=repo_root)
    except Exception as exc:  # noqa: BLE001 - surfaced as a CliError below
        raise cli.CliError(str(exc)) from exc
    stdout = cast("TextIO | None", args.stdout)
    print(f"worktree: {prepared.worktree_dir}", file=stdout)
    print(f"branch: {prepared.branch}", file=stdout)
    print(f"cd {prepared.worktree_dir}", file=stdout)
    print("/age", file=stdout)
    print("/code-review", file=stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument("case_id", help="benchmark case id under benchmark/age/cases/")
    _ = parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.set_defaults(func=_cmd_prepare)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)
