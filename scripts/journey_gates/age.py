"""Age journey gate: /age reviews and never changes the repository or publishes."""

# gate:strip-begin
# pyright: reportAny=false, reportExplicitAny=false, reportUnusedCallResult=false, reportDeprecated=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from __future__ import annotations

import os
import posixpath
import re
import subprocess
from pathlib import Path
from typing import Optional

from journey_gates.common import (
    Workspace,
    emit,
    read_bytes,
    rule_publication,
    SKIP_ROOTS,
    snapshot_visible,
    targets,
)

# gate:strip-end
import shutil
import tempfile

# Git subcommands that change the working tree, the index, or history.
GIT_MUTATIONS = {
    "add",
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
    "stage",
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
        # The restore script keeps its Git identity in $HOME/.config/git/config, because the
        # sandbox keeps .git/config read-only. A private HOME isolates it from the host.
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("GIT_CONFIG_GLOBAL", "XDG_CONFIG_HOME")
        }
        env.update(HOME=scratch, GIT_CONFIG_NOSYSTEM="1")
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
    if "$" in path or "`" in path:
        return None  # an unexpanded variable; the tree replay judges the result
    if not path.startswith("/"):
        rel = posixpath.normpath(path)
    elif ws.root and posixpath.normpath(path).startswith(ws.root + "/"):
        rel = posixpath.relpath(posixpath.normpath(path), ws.root)
    else:
        return None
    return None if rel.startswith("..") else rel

def read_only_stash(command: str) -> bool:
    """The step literally holds `git stash list` or `git stash show`; no alias is expanded."""
    stashes = re.findall(r"\bgit\s+stash\b(?!\s+(?:list|show)\b)", command)
    return "alias." not in command and not stashes and bool(re.search(r"\bgit\s+stash\s+(?:list|show)\b", command))


def exempt_write(rel: str) -> bool:
    """Review artifacts under `.cheese/` and the runtime roots are not production files."""
    return rel.split("/")[0] in (".cheese", *SKIP_ROOTS)


workspace = Workspace()
failures: set[str] = set()
if not workspace.has_turn:
    failures.add("no-trace")
rule_publication(workspace, failures, commit=True)
for index, facts in workspace.facts.items():
    mutations = facts.git & GIT_MUTATIONS
    if mutations == {"stash"} and read_only_stash(workspace.steps[index][1]):
        continue
    if mutations:
        failures.add("git-mutation")

visible = sorted(
    rel
    for rel in set(workspace.output) | set(workspace.fixtures)
    if snapshot_visible(rel) and "__pycache__" not in rel
)
writes = [path for _, path in workspace.write_targets()]
for path in writes:
    rel = workspace_rel(workspace, path)
    if rel is not None and not exempt_write(rel):
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
