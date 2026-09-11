"""What the working tree says about a record that its own bytes cannot.

`lint` derives whether a checkpoint hangs together internally -- digests,
lineage, conservation. The checks here ask the other half of the question, and
every one of them has to leave the store to answer it: does the commit a
revision cites still resolve, does a linked artifact still hash to what the
record pinned, does a grounded pointer still name a file in this checkout.

They are all advisory by construction and all degrade to silence when the tool
they need cannot run, so keeping them apart from the deterministic checks keeps
the one git subprocess responsibility in one place.

The two modules name each other: `lint_work` composes these checks, and these
checks speak `lint`'s finding vocabulary. Nothing is read across the boundary
at import time -- only attribute lookups inside function bodies -- so neither
module needs the other to be fully initialised to be imported first.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from easy_cheese_schemas import WheypointRecord
from easy_cheese_schemas.validate import is_relative_path

from easy_cheese.shared import git_utils

from . import grounded, storage
from .lint_types import LintCode, LintFinding


GIT_TIMEOUT_SECONDS = 5
# A `PR#<n>` or URL pointer in working_context references something outside the
# checkout, so the grounded path grammar has nothing local to check it against.
_EXTERNAL_POINTER_RE = re.compile(r"PR#[0-9]+|[a-z][a-z0-9+.-]*://.*")


def run_git_ok(
    args: list[str], *, cwd: Path | str, timeout: float
) -> subprocess.CompletedProcess[str] | None:
    """Run one advisory git command, or None when it could not run at all."""
    try:
        return git_utils.run_git(args, cwd=cwd, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        # Advisory checks degrade to silence, but a silence with no cause is
        # indistinguishable from a pass. Name the command, where it ran, and
        # what stopped it -- in plain ASCII, because this stream belongs to
        # whatever harness is watching, not to a particular one.
        print(
            f"wheypoint: git-unavailable git {' '.join(args[:2])} cwd={cwd} "
            + type(exc).__name__,
            file=sys.stderr,
        )
        return None


def git_object_exists_in(root: Path | str) -> Callable[[str], bool]:
    """Read-only `git cat-file -e <object>^{object}` in `root`.

    Inspection only: the runtime never commits, never publishes, and treats an
    unrunnable git as an unresolved reference rather than a pass.
    """

    def exists(obj: str) -> bool:
        completed = run_git_ok(
            ["cat-file", "-e", f"{obj}^{{object}}"],
            cwd=root,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        return completed is not None and completed.returncode == 0

    return exists


def artifact_digest_in(root: Path | str) -> Callable[[str], str | None]:
    """Digest a regular artifact file contained by `root`."""
    resolved_root = Path(root).resolve()

    def digest(path: str) -> str | None:
        if not is_relative_path(path):
            return None
        candidate = Path(path)
        try:
            resolved = (resolved_root / candidate).resolve()
            if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
                return None
            return storage.file_digest(resolved)
        except (OSError, RuntimeError):
            return None

    return digest


def stale_commit_findings(
    commit: str,
    *,
    repository_root: Path,
) -> list[LintFinding]:
    """Report a revision written on a history HEAD no longer descends from."""
    ancestor = run_git_ok(
        ["merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=repository_root,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if ancestor is None or ancestor.returncode != 1:
        return []
    distance_result = run_git_ok(
        ["rev-list", "--count", f"{commit}..HEAD"],
        cwd=repository_root,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    if distance_result is None or distance_result.returncode != 0:
        return []
    try:
        distance = int(distance_result.stdout.strip())
    except ValueError:
        return []
    return [
        LintFinding(
            LintCode.STALE_COMMIT,
            f"HEAD does not descend from repository commit {commit}; "
            + f"distance is {distance}",
        )
    ]


def artifact_link_findings(
    record: WheypointRecord,
    artifact_digest: Callable[[str], str | None],
) -> list[LintFinding]:
    """Re-check each digest-bearing artifact link against its current file."""
    findings: list[LintFinding] = []
    for link in record.artifact_links:
        if link.digest is None:
            continue
        actual = artifact_digest(link.path)
        if actual == link.digest:
            continue
        current = "missing" if actual is None else repr(actual)
        findings.append(
            LintFinding(
                LintCode.STALE_ARTIFACT_LINK,
                f"{link.path}: linked digest {link.digest!r}, current file "
                + f"digest is {current}",
            )
        )
    return findings


def grounded_path_findings(
    record: WheypointRecord, repository_root: Path
) -> list[LintFinding]:
    """Warn when a grounded entry violates the writer's own path grammar.

    Parses with `grounded.parse_grounded_entry` (the same grammar
    `validate_grounded` enforces at write time) so an entry one side calls
    valid the other cannot silently accept. A `PR#<n>` or URL pointer is
    exempt: it names something outside the checkout, so no local file can
    confirm or deny it and the writer never promised one would.
    """
    findings: list[LintFinding] = []
    for entry in record.working_context:
        if _EXTERNAL_POINTER_RE.fullmatch(entry):
            continue
        try:
            path_text, _range = grounded.parse_grounded_entry(entry)
        except grounded.GroundedEntryError:
            findings.append(
                LintFinding(
                    LintCode.GROUNDED_PATH_MISSING,
                    f"working_context entry {entry!r} does not satisfy the "
                    + "grounded path grammar",
                )
            )
            continue
        landed = grounded.resolve_within(path_text, repository_root)
        if isinstance(landed, grounded.GroundedPathIssue):
            findings.append(
                LintFinding(
                    LintCode.GROUNDED_PATH_MISSING,
                    f"working_context path {entry!r} {landed.value}",
                )
            )
    return findings
