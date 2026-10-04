"""Inspect and continue an interrupted Git operation."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Annotated, Callable, Literal, TypedDict

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


def _changed_paths(root: Path) -> list[str]:
    result = run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=root)
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


def _unmerged_paths(root: Path) -> list[str]:
    result = run_git(["diff", "--name-only", "--diff-filter=U", "-z"], cwd=root)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return sorted(path for path in result.stdout.split("\0") if path)


_MAX_SCAN_BYTES = 8 * 1024 * 1024
_MARKER = re.compile(rb"^<{7,}(?: |$)")


def _contains_markers(content: bytes) -> bool:
    if b"\0" in content[:8000]:
        return False
    return any(_MARKER.match(line) for line in content.splitlines())


def _has_worktree_markers(root: Path, path: str) -> bool:
    relative = Path(path)
    if relative.is_absolute() or ".." in relative.parts:
        return True
    target = root / relative
    try:
        for parent in target.parents:
            if parent == root:
                break
            if parent.is_symlink():
                return True
        descriptor = os.open(target, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                return True
            if b"\0" in stream.read(8000):
                return False
            _ = stream.seek(0)
            scanned = 0
            while line := stream.readline(65536):
                scanned += len(line)
                if scanned > _MAX_SCAN_BYTES or len(line) == 65536 and not line.endswith(b"\n"):
                    return True
                if _MARKER.match(line.rstrip(b"\r\n")):
                    return True
            return False
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _has_index_markers(root: Path, path: str) -> bool:
    size = run_git(["cat-file", "-s", f":{path}"], cwd=root)
    if size.returncode:
        return False
    if int(size.stdout.strip()) > _MAX_SCAN_BYTES:
        return True
    result = run_git(["show", f":{path}"], cwd=root)
    return result.returncode == 0 and _contains_markers(result.stdout.encode())


def abort_args(operation: Operation | None) -> list[str] | None:
    return [operation, "--abort"] if operation else None


def status() -> OperationState:
    operation, branch = current_operation()
    root_result = run_git(["rev-parse", "--show-toplevel"])
    if root_result.returncode:
        raise RuntimeError(root_result.stderr.strip() or "not inside a Git repository")
    root = Path(root_result.stdout.strip())
    unmerged = _unmerged_paths(root)
    markers = [
        path for path in _changed_paths(root)
        if _has_worktree_markers(root, path) or _has_index_markers(root, path)
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


def build_app(command: Callable[..., OperationState] = operation_cmd) -> fromargs.App:
    return fromargs.App(
        "operation", help="Report or continue the current Git operation.",
        help_formatter="plain", default_command=command,
    )


def main(argv: list[str] | None = None) -> int:
    failed = False

    def cli_operation(
        *, continue_operation: Annotated[bool, fromargs.Parameter(name="--continue")] = False
    ) -> OperationState:
        nonlocal failed
        result = operation_cmd(continue_operation=continue_operation)
        failed = result["status"] == "failure"
        return result

    exit_code = build_app(cli_operation).run(argv)
    return exit_code or int(failed)
