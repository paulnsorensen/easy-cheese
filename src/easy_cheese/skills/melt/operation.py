"""Inspect and continue an interrupted Git operation."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import IO, Annotated, Callable, Literal, TypedDict

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


_BINARY_PROBE_BYTES = 8000
_CHUNK_BYTES = 64 * 1024
# A marker run at a line start, then a space or the line end. The scan puts a
# synthetic "\n" before the first byte, so every line start follows \r or \n.
_LINE_MARKER = re.compile(rb"[\r\n](?:<{7,}|>{7,}|\|{7,})(?:[ \r\n]|\Z)")
_MARKER_PREFIX = re.compile(rb"[\r\n](?:<*|>*|\|*)")


def _stream_has_markers(stream: IO[bytes]) -> bool:
    """Report whether a line of a text stream starts with a conflict marker.

    The scan reads binary chunks and checks only line starts, so line length does
    not matter. A last line that can still become a marker carries into the next
    chunk, clipped to its terminator and seven marker bytes. Memory stays bounded,
    so there is no size cap: a cap must block clean large files or skip real markers.
    """
    chunk = stream.read(_BINARY_PROBE_BYTES)
    if b"\0" in chunk:
        return False
    pending = b"\n"
    while chunk:
        buffer = pending + chunk
        last = max(buffer.rfind(b"\n"), buffer.rfind(b"\r"))
        if last >= 0 and _MARKER_PREFIX.fullmatch(buffer, last):
            pending, end = buffer[last : last + 8], last
        else:
            pending, end = b"", len(buffer)
        if _LINE_MARKER.search(buffer, 0, end):
            return True
        chunk = stream.read(_CHUNK_BYTES)
    return _LINE_MARKER.search(pending) is not None


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
            return _stream_has_markers(stream)
    except FileNotFoundError:
        return False
    except OSError:
        return True


def _has_index_markers(root: Path, path: str) -> bool:
    """Stream the stage-0 blob; a path absent from stage 0 gives no output."""
    with subprocess.Popen(
        ["git", "-C", str(root), "cat-file", "blob", f":{path}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as process:
        assert process.stdout is not None
        try:
            return _stream_has_markers(process.stdout)
        finally:
            process.kill()


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
