"""Inspect and continue an interrupted Git operation."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated, Literal, TypedDict

import fromargs

from easy_cheese.shared.git_utils import run_git


Operation = Literal["merge", "rebase", "cherry-pick"]


class OperationState(TypedDict):
    status: Literal["complete", "blocked", "ready", "failure"]
    operation: Operation | None
    original_branch: str | None
    abort_command: str | None
    continuation_command: str | None
    unmerged_paths: list[str]
    conflict_marker_files: list[str]
    rerere_enabled: bool
    configured_merge_tool: str | None
    selected_manual_tool: str | None
    failed_step: str | None
    error: str | None


def _git_dir() -> Path:
    result = run_git(["rev-parse", "--git-dir"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "not inside a Git repository")
    return Path(result.stdout.strip())


def current_operation(git_dir: Path | None = None) -> tuple[Operation | None, str | None]:
    directory = git_dir if git_dir is not None else _git_dir()
    for name in ("rebase-merge", "rebase-apply"):
        state = directory / name
        if state.exists():
            head_name = state / "head-name"
            branch = head_name.read_text().strip().removeprefix("refs/heads/") if head_name.exists() else None
            return "rebase", branch
    if (directory / "MERGE_HEAD").exists():
        return "merge", None
    if (directory / "CHERRY_PICK_HEAD").exists():
        return "cherry-pick", None
    return None, None


def _changed_paths() -> list[str]:
    result = run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    entries = result.stdout.split("\0")
    paths: list[str] = []
    index = 0
    while index < len(entries) and entries[index]:
        entry = entries[index]
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            index += 1
        index += 1
    return sorted(set(paths))


def _unmerged_paths() -> list[str]:
    result = run_git(["diff", "--name-only", "--diff-filter=U", "-z"])
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return sorted(path for path in result.stdout.split("\0") if path)


def _contains_markers(content: bytes) -> bool:
    if b"\0" in content[:8000]:
        return False
    return any(line.startswith(b"<<<<<<< ") or line == b"<<<<<<<" for line in content.splitlines())


def _has_worktree_markers(path: str) -> bool:
    try:
        return _contains_markers(Path(path).read_bytes())
    except OSError:
        return False


def _has_index_markers(path: str) -> bool:
    result = run_git(["show", f":{path}"])
    return result.returncode == 0 and _contains_markers(result.stdout.encode())


def abort_args(operation: Operation | None) -> list[str] | None:
    return [operation, "--abort"] if operation else None


def status() -> OperationState:
    operation, branch = current_operation()
    unmerged = _unmerged_paths()
    markers = [
        path for path in _changed_paths()
        if _has_worktree_markers(path) or _has_index_markers(path)
    ]
    rerere = run_git(["config", "--bool", "--get", "rerere.enabled"])
    merge_tool = run_git(["config", "--get", "merge.tool"])
    configured = merge_tool.stdout.strip() if merge_tool.returncode == 0 else None
    return {
        "status": "blocked" if unmerged or markers else "ready" if operation else "complete",
        "operation": operation,
        "original_branch": branch,
        "abort_command": f"git {operation} --abort" if operation else None,
        "continuation_command": f"git {operation} --continue" if operation else None,
        "unmerged_paths": unmerged,
        "conflict_marker_files": markers,
        "rerere_enabled": rerere.returncode == 0 and rerere.stdout.strip() == "true",
        "configured_merge_tool": configured,
        "selected_manual_tool": "kdiff3" if shutil.which("kdiff3") else configured,
        "failed_step": None,
        "error": None,
    }


def operation_cmd(
    *, continue_operation: Annotated[bool, fromargs.Parameter(name="--continue")] = False
) -> OperationState:
    """Report Git conflict state, or continue when every conflict is resolved."""
    state = status()
    if not continue_operation or state["status"] != "ready":
        return state
    operation = state["operation"]
    assert operation is not None
    env = os.environ.copy()
    env["GIT_EDITOR"] = "true"
    result = subprocess.run(
        ["git", operation, "--continue"], capture_output=True, text=True, env=env
    )
    after = status()
    if result.returncode and after["status"] != "blocked":
        after["status"] = "failure"
        after["failed_step"] = f"git {operation} --continue"
        after["error"] = result.stderr.strip() or result.stdout.strip()
    return after


def build_app() -> fromargs.App:
    return fromargs.App(
        "operation", help="Report or continue the current Git operation.",
        help_formatter="plain", default_command=operation_cmd,
    )


def main(argv: list[str] | None = None) -> int:
    return build_app().run(argv)
