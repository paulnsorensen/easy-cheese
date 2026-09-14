"""Seed an isolated git worktree for a benchmark case.

Creates a scratch git repo from the case's ``base/`` tree, applies
``seed.patch`` on a fresh branch in a linked worktree, and prints the
worktree path plus the two review commands (``/age`` and ``/code-review``)
an operator runs next.
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO, cast

from easy_cheese.shared import cli
from easy_cheese.shared.git_utils import run_git
from easy_cheese.skills.age_bench.cases import load_case
from easy_cheese.skills.age_bench.errors import AgeBenchError

GIT_TIMEOUT_SECONDS = 30

# A fixed identity plus disabled hooks/signing keeps every case's git steps
# independent of the caller's global git config (~/.gitconfig).
_GIT_CONFIG_FLAGS = (
    "-c",
    "user.email=age-bench@example.invalid",
    "-c",
    "user.name=age-bench",
    "-c",
    "commit.gpgsign=false",
    "-c",
    "core.hooksPath=/dev/null",
)


class PrepareError(AgeBenchError):
    """Raised when a git step in preparing the worktree fails."""


def _remove_scratch_dir(scratch_dir: Path) -> None:
    try:
        shutil.rmtree(scratch_dir)
    except OSError as exc:
        print(f"warning: failed to remove {scratch_dir}: {exc}", file=sys.stderr)


@dataclass(frozen=True)
class PreparedWorktree:
    case_id: str
    worktree_dir: Path
    branch: str
    scratch_dir: Path

    def cleanup(self) -> None:
        _remove_scratch_dir(self.scratch_dir)


def _run(argv: list[str], *, cwd: Path) -> None:
    git_args = [*_GIT_CONFIG_FLAGS, *argv[1:]]
    try:
        result = run_git(git_args, cwd=cwd, timeout=GIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as exc:
        raise PrepareError(
            f"{' '.join(argv)} timed out after {GIT_TIMEOUT_SECONDS}s"
        ) from exc
    if result.returncode != 0:
        raise PrepareError(f"{' '.join(argv)} failed: {result.stderr.strip()}")


def _reject_escaping_symlinks(base_dir: Path, case_dir: Path) -> None:
    case_root = case_dir.resolve()
    for entry in base_dir.rglob("*"):
        if not entry.is_symlink():
            continue
        target = entry.resolve()
        if target != case_root and case_root not in target.parents:
            raise PrepareError(
                f"case base/ contains a symlink escaping the case directory: {entry} -> {target}"
            )


def prepare_worktree(
    case_id: str, *, repo_root: Path | str | None = None
) -> PreparedWorktree:
    case = load_case(case_id, repo_root=repo_root)
    scratch_dir = Path(tempfile.mkdtemp(prefix=f"age-bench-{case_id}-"))
    repo_dir = scratch_dir / "repo"
    worktree_dir = scratch_dir / "worktree"
    branch = f"age-bench/{case_id}"

    try:
        _reject_escaping_symlinks(case.base_dir, case.dir)
        _ = shutil.copytree(case.base_dir, repo_dir, symlinks=True)
        _run(["git", "init", "-q", "-b", "main"], cwd=repo_dir)
        _run(["git", "add", "-A"], cwd=repo_dir)
        _run(["git", "commit", "-q", "-m", "base"], cwd=repo_dir)
        _run(
            ["git", "worktree", "add", "-q", "-b", branch, str(worktree_dir)],
            cwd=repo_dir,
        )
        _run(["git", "apply", str(case.seed_patch.resolve())], cwd=worktree_dir)
    except Exception:
        _remove_scratch_dir(scratch_dir)
        raise

    return PreparedWorktree(
        case_id=case_id,
        worktree_dir=worktree_dir,
        branch=branch,
        scratch_dir=scratch_dir,
    )


def _cmd_prepare(args: argparse.Namespace) -> int:
    case_id = cast(str, args.case_id)
    repo_root = cast("str | None", args.repo_root)
    json_mode = cast(bool, args.json_mode)
    stdout = cast("TextIO | None", args.stdout)
    prepared = prepare_worktree(case_id, repo_root=repo_root)
    lines = [
        f"worktree: {prepared.worktree_dir}",
        f"branch: {prepared.branch}",
        f"scratch: {prepared.scratch_dir}",
        f"cd {shlex.quote(str(prepared.worktree_dir))}",
        "/age",
        "/code-review",
    ]
    cli.emit(lines, json_mode=json_mode, stdout=stdout)
    return 0


def _setup(parser: argparse.ArgumentParser) -> None:
    _ = parser.add_argument(
        "case_id", help="benchmark case id under benchmark/age/cases/"
    )
    _ = parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.set_defaults(func=_cmd_prepare)


def main(argv: list[str]) -> int:
    return cli.run(_setup, argv=argv)
