"""Age journey gate: /age reviews and never changes the repository or publishes."""

# gate:strip-begin
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false, reportDeprecated=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

import os
import posixpath
import subprocess
from pathlib import Path
from typing import Optional

from journey_gates.common import (
    Workspace,
    emit,
    read_bytes,
    rule_publication,
    snapshot_visible,
    targets,
)
from journey_gates.common import _basename as _basename
from journey_gates.common import _commands as _commands

# gate:strip-end
import shutil
import tempfile

# Git subcommands that change the working tree, the index, or history.
GIT_MUTATIONS = {
    "am",
    "apply",
    "checkout",
    "cherry-pick",
    "clean",
    "merge",
    "mv",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rm",
    "stash",
    "switch",
}
RESTORE = "restore-repo.sh"


def visible_tree(root: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_file() and snapshot_visible(rel) and "__pycache__" not in rel:
            found[rel] = read_bytes(path)
    return found


def replayed_baseline(ws: Workspace) -> Optional[dict[str, bytes]]:
    """The tree that the case's restore script builds, or None when it cannot run."""
    if RESTORE not in ws.fixtures:
        return None
    scratch = tempfile.mkdtemp()
    try:
        for rel, path in ws.fixtures.items():
            target = Path(scratch, rel)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        env = dict(
            os.environ,
            HOME=scratch,
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
        )
        proc = subprocess.run(
            ["bash", RESTORE],
            cwd=scratch,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
        return visible_tree(Path(scratch)) if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def workspace_rel(ws: Workspace, path: str) -> Optional[str]:
    """The workspace-relative form of a write target, or None when it lies outside."""
    if not path.startswith("/"):
        rel = posixpath.normpath(path)
    elif ws.root and posixpath.normpath(path).startswith(ws.root + "/"):
        rel = posixpath.relpath(posixpath.normpath(path), ws.root)
    else:
        return None
    return None if rel.startswith("..") else rel


def in_place_targets(argv: list[str]) -> list[str]:
    """Files that `sed -i` or `perl -i` rewrites in place."""
    name = _basename(argv[0])
    if name not in ("sed", "perl"):
        return []
    script_flags = ("-e", "--expression", "-f", "--file") if name == "sed" else ("-e", "-E")
    in_place = False
    has_script = False
    files: list[str] = []
    args = argv[1:]
    index = 0
    while index < len(args):
        word = args[index]
        if word.split("=", 1)[0] in script_flags:
            has_script = True
            index += 1 if "=" in word else 2
            continue
        if word.startswith("--in-place"):
            in_place = True
        elif word.startswith("-") and not word.startswith("--") and len(word) > 1:
            in_place = in_place or "i" in word[1:]
            has_script = has_script or (name == "perl" and word[-1] in "eE")
            if name == "perl" and word[-1] in "eE":
                index += 1
        elif not word.startswith("-"):
            files.append(word)
        index += 1
    if not in_place:
        return []
    return files if has_script else files[1:]


workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures, commit=True)
for facts in workspace.facts.values():
    if facts.git & GIT_MUTATIONS:
        failures.add("git-mutation")

visible = sorted(
    rel
    for rel in set(workspace.output) | set(workspace.fixtures)
    if snapshot_visible(rel) and "__pycache__" not in rel
)
writes = [path for _, path in workspace.write_targets()]
for kind, value in workspace.steps:
    if kind == "shell":
        try:
            commands = [argv for argv, _ in _commands(value) if argv]
        except Exception:
            commands = []
        for argv in commands:
            writes.extend(in_place_targets(argv))
for path in writes:
    rel = workspace_rel(workspace, path)
    if rel is not None and snapshot_visible(rel):
        failures.add("production-write")
if any(targets(workspace, rel) for rel in visible):
    failures.add("production-write")

# The strongest check: replay the restore script and compare every visible file.
baseline = replayed_baseline(workspace)
if baseline is not None and workspace.output_dir:
    output = visible_tree(Path("output"))
    restored = any(rel in output for rel in baseline if rel not in workspace.fixtures)
    if restored and output != baseline:
        failures.add("production-changed")

emit(failures)
