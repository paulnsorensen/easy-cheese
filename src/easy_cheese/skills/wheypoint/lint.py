"""Deterministic validation of a projection and of the work behind it.

Everything a caller would have to trust before acting on a checkpoint is
re-derived here from the bytes on disk: the projection hashes to the digest it
carries, the record hashes to the digest its receipt quotes, every parent in
the chain is present as an immutable local revision, the record belongs to this
project, the commit it cites still exists, and every artifact coverage claim
still resolves.

A lint finding is a *reason not to dispatch*, never a repair. Nothing in this
module writes, and nothing removes protected inline state -- an artifact whose
coverage claim has gone stale invalidates the claim, and the entries it claimed
to cover stay exactly where they were.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from attrs import define, field
from easy_cheese_schemas import WheypointProjection, WheypointRecord, WheypointRevision

from . import projection as projection_mod
from . import records, storage

_GIT_TIMEOUT_SECONDS = 5


class LintCode(str, Enum):
    """Why a checkpoint cannot be acted on automatically."""

    RECORD_MISSING = "record-missing"
    STORE_INCONSISTENT = "store-inconsistent"
    REVISION_INCOMPLETE = "revision-incomplete"
    PROJECTION_UNREADABLE = "projection-unreadable"
    PROJECTION_DIGEST_MISMATCH = "projection-digest-mismatch"
    PROJECTION_RECORD_MISMATCH = "projection-record-mismatch"
    PARENT_UNRESOLVED = "parent-unresolved"
    PROJECT_MISMATCH = "project-mismatch"
    GIT_OBJECT_MISSING = "git-object-missing"
    ARTIFACT_COVERAGE_INVALID = "artifact-coverage-invalid"


# Findings that describe the store's surroundings rather than the authority of
# the record being resumed. An interrupted promotion leaves an orphan no reader
# can have quoted, and the retry overwrites it; blocking continuation on one
# would strand a valid current record in exactly the crash it survived. The
# spec gates automatic continuation on projection and record digests, the
# parent chain, project identity, referenced Git objects, and required artifact
# coverage -- an orphan is none of those, so it is reported, not enforced.
ADVISORY_CODES = frozenset({LintCode.REVISION_INCOMPLETE})


def gates_continuation(finding: LintFinding) -> bool:
    """Whether this finding must stop automatic dispatch."""
    return finding.code not in ADVISORY_CODES


@define(frozen=True)
class LintFinding:
    code: LintCode
    detail: str


@define(frozen=True)
class LintReport:
    """Everything that is wrong, plus what was readable while checking."""

    findings: tuple[LintFinding, ...] = field(default=())
    record: WheypointRecord | None = None
    projection: WheypointProjection | None = None

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def codes(self) -> tuple[LintCode, ...]:
        return tuple(finding.code for finding in self.findings)


def git_object_exists_in(root: Path | str) -> Callable[[str], bool]:
    """Read-only `git cat-file -e <object>^{object}` in `root`.

    Inspection only: the runtime never commits, never publishes, and treats an
    unrunnable git as an unresolved reference rather than a pass.
    """

    def exists(obj: str) -> bool:
        try:
            completed = subprocess.run(
                ["git", "cat-file", "-e", f"{obj}^{{object}}"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return completed.returncode == 0

    return exists


def artifact_digest_in(root: Path | str) -> Callable[[str], str | None]:
    """Digest a regular artifact file contained by `root`."""
    resolved_root = Path(root).resolve()

    def digest(path: str) -> str | None:
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            return None
        try:
            resolved = (resolved_root / candidate).resolve()
            if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
                return None
            return storage.file_digest(resolved)
        except (OSError, RuntimeError):
            return None

    return digest


def lint_projection_text(text: str) -> LintReport:
    """Parse a projection document and check it against its own digest."""
    try:
        parsed = projection_mod.parse(text)
    except projection_mod.ProjectionParseError as exc:
        return LintReport(
            findings=(LintFinding(LintCode.PROJECTION_UNREADABLE, str(exc)),)
        )
    actual = projection_mod.projection_digest_of_text(text)
    if actual != parsed.projection_digest:
        return LintReport(
            findings=(
                LintFinding(
                    LintCode.PROJECTION_DIGEST_MISMATCH,
                    f"document hashes to {actual}, but claims "
                    + f"{parsed.projection_digest}",
                ),
            ),
            projection=parsed,
        )
    return LintReport(projection=parsed)


def lint_projection_file(path: Path | str) -> LintReport:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        return LintReport(
            findings=(LintFinding(LintCode.PROJECTION_UNREADABLE, str(exc)),)
        )
    return lint_projection_text(text)


def lint_work(
    store: storage.WorkStore,
    *,
    project_key: str,
    git_object_exists: Callable[[str], bool],
    artifact_digest: Callable[[str], str | None],
) -> LintReport:
    """Validate the whole current checkpoint of one work store."""
    recovery = store.recover()
    findings = [
        LintFinding(LintCode.STORE_INCONSISTENT, problem)
        for problem in recovery.problems
    ]
    record = recovery.record
    if record is None:
        if not findings:
            findings.append(
                LintFinding(
                    LintCode.RECORD_MISSING,
                    f"no record at {store.record_path}",
                )
            )
        findings.extend(_incomplete_findings(recovery))
        return LintReport(findings=tuple(findings))

    findings.extend(_incomplete_findings(recovery))

    if record.project_key != project_key:
        findings.append(
            LintFinding(
                LintCode.PROJECT_MISMATCH,
                f"record belongs to project {record.project_key!r}, not "
                + f"{project_key!r}",
            )
        )

    current = store.read_revision(record.revision_number, record.revision_id)
    projection = None
    if current is None:
        findings.append(
            LintFinding(
                LintCode.PARENT_UNRESOLVED,
                f"record names revision {record.revision_id!r}, which has no "
                + "immutable revision file",
            )
        )
    else:
        projection_report = _lint_current_projection(store, record, current)
        findings.extend(projection_report.findings)
        projection = projection_report.projection
        findings.extend(_chain_findings(recovery, current))
        findings.extend(_git_findings(current, git_object_exists))

    findings.extend(_coverage_findings(recovery, record, artifact_digest))
    return LintReport(findings=tuple(findings), record=record, projection=projection)


def _incomplete_findings(
    recovery: storage.RecoveryReport,
) -> list[LintFinding]:
    """Name every half-written pair: an interrupted promotion is not clean."""
    return [
        LintFinding(LintCode.REVISION_INCOMPLETE, detail)
        for detail in recovery.incomplete
    ]


def _lint_current_projection(
    store: storage.WorkStore,
    record: WheypointRecord,
    revision: WheypointRevision,
) -> LintReport:
    path = store.projection_path(revision.revision_number, revision.revision_id)
    report = lint_projection_file(path)
    parsed = report.projection
    if parsed is None:
        return report
    mismatches: list[str] = []
    if parsed.work_id != record.work_id:
        mismatches.append(f"work_id {parsed.work_id!r} != {record.work_id!r}")
    if parsed.revision_id != record.revision_id:
        mismatches.append(
            f"revision_id {parsed.revision_id!r} != {record.revision_id!r}"
        )
    expected_digest = records.record_digest(record)
    if parsed.record_digest != expected_digest:
        mismatches.append(
            f"record_digest {parsed.record_digest} != {expected_digest}"
        )
    if not mismatches:
        return report
    return LintReport(
        findings=(
            *report.findings,
            LintFinding(
                LintCode.PROJECTION_RECORD_MISMATCH,
                f"{path.name} describes a different record: "
                + "; ".join(mismatches),
            ),
        ),
        projection=parsed,
    )


def _chain_findings(
    recovery: storage.RecoveryReport, current: WheypointRevision
) -> list[LintFinding]:
    """Walk parents back to genesis; every step must be a local revision."""
    known = {
        file.revision.revision_id: file.revision for file in recovery.complete
    }
    findings: list[LintFinding] = []
    seen = {current.revision_id}
    revision = current
    while revision.parent_revision_id is not None:
        parent_id = revision.parent_revision_id
        if parent_id in seen:
            findings.append(
                LintFinding(
                    LintCode.PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} re-enters the chain at "
                    + f"{parent_id!r}",
                )
            )
            break
        parent = known.get(parent_id)
        if parent is None:
            findings.append(
                LintFinding(
                    LintCode.PARENT_UNRESOLVED,
                    f"revision {revision.revision_id!r} names parent "
                    + f"{parent_id!r}, which is not a complete immutable revision",
                )
            )
            break
        seen.add(parent_id)
        revision = parent
    return findings


def _git_findings(
    revision: WheypointRevision, git_object_exists: Callable[[str], bool]
) -> list[LintFinding]:
    commit = revision.repository.commit
    if commit is None or git_object_exists(commit):
        return []
    return [
        LintFinding(
            LintCode.GIT_OBJECT_MISSING,
            f"revision {revision.revision_id!r} cites commit {commit}, which "
            + "does not resolve in this repository",
        )
    ]


def _coverage_findings(
    recovery: storage.RecoveryReport,
    record: WheypointRecord,
    artifact_digest: Callable[[str], str | None],
) -> list[LintFinding]:
    report = records.coverage_report(
        record,
        artifact_digest=artifact_digest,
        known_revision_ids=recovery.revision_ids,
    )
    return [
        LintFinding(
            LintCode.ARTIFACT_COVERAGE_INVALID,
            f"{failure.path}: {failure.reason}",
        )
        for failure in report.failures
    ]
